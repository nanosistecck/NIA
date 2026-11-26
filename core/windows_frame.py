"""DWM custom frame for MainWindow; all coordinates here are physical pixels.

The central CanvasBackground fills the enlarged client rect, including the
caption. No second painter, caption widgets, or icon mutation is needed.
"""
import ctypes as c
from ctypes import wintypes as w
import logging
import math

from PyQt6.QtCore import QCoreApplication, QEvent
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication

# Posted after WM_PAINT, so Qt has finished flushing its opaque backing store.
CAPTION_PAINT_EVENT = QEvent.Type(QEvent.registerEventType())


class Margins(c.Structure):
    _fields_ = [(name, c.c_int) for name in ('left', 'right', 'top', 'bottom')]


class MonitorInfo(c.Structure):
    _fields_ = [('size', w.DWORD), ('monitor', w.RECT), ('work', w.RECT),
                ('flags', w.DWORD)]


class BitmapHeader(c.Structure):
    _fields_ = [('size', w.DWORD), ('width', w.LONG), ('height', w.LONG),
                ('planes', w.WORD), ('bits', w.WORD), ('compression', w.DWORD),
                ('image_size', w.DWORD), ('xppm', w.LONG), ('yppm', w.LONG),
                ('colors', w.DWORD), ('important', w.DWORD)]


class WindowsFrame:
    def __init__(self, window, *, cor=None):
        self.window = window
        self.active = False
        self.hwnd = None
        self.failed = False
        self._paint_pending = False
        self._dib_key = None
        # cor=None mantém o caminho do cache da CanvasBackground do main window.
        self.cor = QColor(cor) if cor is not None else None

    def _layout(self):
        """Layout do conteúdo da janela: centralWidget() quando houver."""
        if hasattr(self.window, 'centralWidget'):
            central = self.window.centralWidget()
            if central is not None:
                return central.layout()
        return self.window.layout()

    def install(self):
        if self.failed or QApplication.platformName() != "windows":
            return False
        try:
            # winId() pode falhar na janela que ainda está sendo construída.
            # Nunca deixe essa exceção chegar ao clique do dock: a janela
            # continua com a moldura padrão do Windows.
            hwnd = int(self.window.winId())
            if self.active and self.hwnd == hwnd:
                return True
            self.user = c.WinDLL('user32', use_last_error=True)
            self.dwm = c.WinDLL('dwmapi')
            self.gdi = c.WinDLL('gdi32', use_last_error=True)
            self.user.GetDC.argtypes = [w.HWND]
            self.user.GetDC.restype = w.HDC
            self.user.ReleaseDC.argtypes = [w.HWND, w.HDC]
            self.gdi.SetDIBitsToDevice.argtypes = [
                w.HDC, c.c_int, c.c_int, w.DWORD, w.DWORD, c.c_int, c.c_int,
                w.UINT, w.UINT, c.c_void_p, c.POINTER(BitmapHeader), w.UINT]
            self.gdi.SetDIBitsToDevice.restype = c.c_int
            self.user.DefWindowProcW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
            self.user.DefWindowProcW.restype = c.c_ssize_t
            self.user.GetWindowLongW.argtypes = [w.HWND, c.c_int]
            self.user.GetWindowLongW.restype = w.LONG
            self.user.SetWindowPos.argtypes = [w.HWND, w.HWND, c.c_int, c.c_int,
                                               c.c_int, c.c_int, w.UINT]
            self.user.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
            self.user.IsZoomed.argtypes = [w.HWND]
            self.user.GetDpiForWindow.argtypes = [w.HWND]
            self.user.GetSystemMetricsForDpi.argtypes = [c.c_int, w.UINT]
            self.user.MonitorFromWindow.argtypes = [w.HWND, w.DWORD]
            self.user.MonitorFromWindow.restype = w.HMONITOR
            self.user.GetMonitorInfoW.argtypes = [w.HMONITOR, c.POINTER(MonitorInfo)]
            self.dwm.DwmDefWindowProc.argtypes = [w.HWND, w.UINT, w.WPARAM,
                                                 w.LPARAM, c.POINTER(c.c_ssize_t)]
            self.dwm.DwmExtendFrameIntoClientArea.argtypes = [w.HWND, c.POINTER(Margins)]
            self.dwm.DwmGetWindowAttribute.argtypes = [w.HWND, w.DWORD, c.c_void_p, w.DWORD]
            self.dwm.DwmIsCompositionEnabled.argtypes = [c.POINTER(w.BOOL)]
            self.dwm.DwmIsCompositionEnabled.restype = c.c_long
            enabled = w.BOOL()
            if self.dwm.DwmIsCompositionEnabled(c.byref(enabled)) < 0 or not enabled.value:
                raise OSError('Composição DWM indisponível')
            # Qt must retain WS_CAPTION, WS_SYSMENU, WS_THICKFRAME and both boxes.
            required = 0x00C00000 | 0x00080000 | 0x00040000 | 0x00030000
            if self.user.GetWindowLongW(hwnd, -16) & required != required:
                raise OSError('Estilos nativos de janela ausentes')
            self.hwnd = hwnd
            # Qt may disable non-client rendering; DWM must own caption glyphs.
            self._original_policy = c.c_int(0)  # DWMNCRP_USEWINDOWSTYLE if query fails
            self.dwm.DwmGetWindowAttribute(hwnd, 2, c.byref(self._original_policy), 4)
            policy = c.c_int(2)  # DWMNCRP_ENABLED
            self.dwm.DwmSetWindowAttribute.argtypes = [w.HWND, w.DWORD, c.c_void_p, w.DWORD]
            if self.dwm.DwmSetWindowAttribute(hwnd, 2, c.byref(policy), c.sizeof(policy)) < 0:
                raise OSError('Renderização não cliente DWM indisponível')
            self.extend()
            self.active = True
            if not self.user.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0037):
                raise c.WinError(c.get_last_error())
            if not hasattr(self, "_base_margins"):
                layout = self._layout()
                if layout is not None:
                    self._base_margins = layout.contentsMargins()
            self._dib_key = None
            self.reserve_caption()
            return True
        except Exception as exc:
            self.disable(exc)
            return False

    def extend(self):
        dpi = self.user.GetDpiForWindow(self.hwnd) or 96
        self.caption_height = (self.user.GetSystemMetricsForDpi(4, dpi)
                               + self.user.GetSystemMetricsForDpi(33, dpi)
                               + self.user.GetSystemMetricsForDpi(92, dpi))
        height = self.caption_height
        if self.dwm.DwmExtendFrameIntoClientArea(self.hwnd, c.byref(Margins(0, 0, height, 0))) < 0:
            raise OSError('DwmExtendFrameIntoClientArea falhou')

    def reserve_caption(self):
        base = self._base_margins
        extra = math.ceil(self.caption_height / self.window.devicePixelRatioF())
        layout = self._layout()
        if layout is not None and layout.contentsMargins().top() != base.top() + extra:
            layout.setContentsMargins(base.left(), base.top() + extra,
                                      base.right(), base.bottom())

    def request_caption_paint(self):
        if not self._paint_pending:
            self._paint_pending = True
            QCoreApplication.postEvent(self.window, QEvent(CAPTION_PAINT_EVENT))

    def paint_caption(self):
        """Copy the EXISTING canvas pixels, with the alpha contract DWM needs.

        Qt's raster flush writes alpha=255, hiding DWM's caption glyphs. A
        top-down DIB copies the same RGB bytes with alpha=0 in the extended
        strip only. The window stays opaque (no layered window, blur or opacity
        changes). Windows composites and hit-tests all three caption buttons.
        """
        self._paint_pending = False
        if not self.active or self.window.isMinimized() or self.window.isFullScreen():
            return
        try:
            self.reserve_caption()
            if self.cor is not None:
                # Janela sem CanvasBackground: pinta uma faixa só com a cor dada.
                largura = max(1, int(self.window.width() * self.window.devicePixelRatioF()))
                image = QImage(largura, self.caption_height, QImage.Format.Format_RGB32)
                image.fill(self.cor)
                height = self.caption_height
                self._dib = bytearray(image.constBits().asstring(image.sizeInBytes()))
                self._dib[3::4] = bytes(len(self._dib) // 4)
                self._header = BitmapHeader(40, image.width(), -image.height(), 1, 32,
                                            0, 0, 0, 0, 0, 0)
            else:
                canvas = self.window.centralWidget()
                canvas._ensure_cache()
                height = min(self.caption_height, canvas._cache.height())
                key = (canvas._key, height)
                if key != self._dib_key:
                    image = canvas._cache.copy(0, 0, canvas._cache.width(), height).toImage()
                    image = image.convertToFormat(QImage.Format.Format_RGB32)
                    self._dib = bytearray(image.constBits().asstring(image.sizeInBytes()))
                    self._dib[3::4] = bytes(len(self._dib) // 4)
                    self._header = BitmapHeader(40, image.width(), -image.height(), 1, 32,
                                                0, 0, 0, 0, 0, 0)
                    self._dib_key = key
            dc = self.user.GetDC(self.hwnd)
            if not dc:
                raise c.WinError(c.get_last_error())
            try:
                buffer = (c.c_ubyte * len(self._dib)).from_buffer(self._dib)
                lines = self.gdi.SetDIBitsToDevice(dc, 0, 0, self._header.width,
                    height, 0, 0, 0, height, buffer, c.byref(self._header), 0)
                if lines == 0:
                    raise OSError('Falha ao compor os pixels do gradiente no quadro DWM')
            finally:
                self.user.ReleaseDC(self.hwnd, dc)
        except Exception as exc:
            self.disable(exc)

    def disable(self, error):
        self.active = False
        self.failed = True
        if hasattr(self, '_base_margins'):
            layout = self._layout()
            if layout is not None:
                layout.setContentsMargins(self._base_margins)
        if self.hwnd:
            self.dwm.DwmExtendFrameIntoClientArea(self.hwnd, c.byref(Margins()))
            if hasattr(self, '_original_policy'):
                self.dwm.DwmSetWindowAttribute(self.hwnd, 2, c.byref(self._original_policy), 4)
            self.user.SetWindowPos(self.hwnd, None, 0, 0, 0, 0, 0x0037)
        logging.getLogger(__name__).warning('Integração DWM indisponível; moldura padrão mantida: %s', error)

    def native_event(self, pointer):
        if not self.active or self.window.isFullScreen():
            return None
        msg = w.MSG.from_address(int(pointer))
        if msg.hWnd != self.hwnd:
            return None
        try:
            if msg.message == 0x000F:  # WM_PAINT: restore native alpha after Qt's flush
                self.request_caption_paint()
            if msg.message in (0x0084, 0x02A2):  # NCHITTEST, NCMOUSELEAVE
                result = c.c_ssize_t()
                handled = self.dwm.DwmDefWindowProc(msg.hWnd, msg.message,
                                                    msg.wParam, msg.lParam, c.byref(result))
                if handled:
                    return result.value
                if msg.message == 0x0084:
                    return self.hit_test(msg.lParam)
            elif msg.message in (0x0085, 0x0086):  # NCPAINT/NCACTIVATE: retain DWM drawing
                return self.user.DefWindowProcW(msg.hWnd, msg.message, msg.wParam, msg.lParam)
            elif msg.message == 0x0083 and msg.wParam:  # NCCALCSIZE_PARAMS starts with RECT
                if self.user.IsZoomed(msg.hWnd):
                    info = MonitorInfo()
                    info.size = c.sizeof(info)
                    monitor = self.user.MonitorFromWindow(msg.hWnd, 2)
                    if not self.user.GetMonitorInfoW(monitor, c.byref(info)):
                        raise c.WinError(c.get_last_error())
                    rect = w.RECT.from_address(msg.lParam)
                    # Keep zero top non-client inset: DwmDefWindowProc stops
                    # hit-testing caption buttons if maximization introduces a
                    # top inset (the sizing frame is already clipped by Windows).
                    rect.left = info.work.left
                    rect.top = min(rect.top, info.work.top)
                    rect.right, rect.bottom = info.work.right, info.work.bottom
                return 0
            elif msg.message in (0x0006, 0x031E, 0x02E0):  # activation, composition, DPI
                self.extend()
                self.request_caption_paint()
        except Exception as exc:
            self.disable(exc)
        return None

    def hit_test(self, lparam):
        x = c.c_short(lparam & 0xffff).value
        y = c.c_short((lparam >> 16) & 0xffff).value
        rect = w.RECT()
        if not self.user.GetWindowRect(self.hwnd, c.byref(rect)):
            raise c.WinError(c.get_last_error())
        dpi = self.user.GetDpiForWindow(self.hwnd) or 96
        metric = lambda n: self.user.GetSystemMetricsForDpi(n, dpi)
        border = metric(32) + metric(92)  # sizing frame + padded border
        caption = metric(4) + border
        # DWM owns exact caption bounds, including the maximize Snap target.
        buttons = w.RECT()
        if self.dwm.DwmGetWindowAttribute(self.hwnd, 5, c.byref(buttons), c.sizeof(buttons)) >= 0:
            if buttons.left <= x-rect.left < buttons.right and buttons.top <= y-rect.top < buttons.bottom:
                return 1  # never turn an unhandled caption-button point into a drag
        if not self.user.IsZoomed(self.hwnd):
            left, right = x < rect.left+border, x >= rect.right-border
            top, bottom = y < rect.top+border, y >= rect.bottom-border
            if top:
                return 13 if left else 14 if right else 12
            if bottom:
                return 16 if left else 17 if right else 15
            if left or right:
                return 10 if left else 11
        if y < rect.top + caption:
            return 2  # HTCAPTION: system move, double-click, restore-drag
        return 1
