"""Regressões do contrato de pixels DWM, DPI e área útil do monitor."""
import ctypes as c
from ctypes import wintypes as w
import os
import math
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout
from core.interface_canvas import CanvasBackground
from core.windows_frame import WindowsFrame


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def native_message(hwnd, code, lparam=0, wparam=0):
    msg = w.MSG()
    msg.hWnd, msg.message, msg.wParam, msg.lParam = hwnd, code, wparam, lparam
    return msg


def test_encaminha_hit_test_e_saida_ao_dwm():
    frame = WindowsFrame(SimpleNamespace(isFullScreen=lambda: False))
    frame.active, frame.hwnd = True, 1
    received = []

    def dwm(hwnd, code, wp, lp, result):
        received.append(code)
        result._obj.value = 9  # HTMAXBUTTON must remain owned by Windows
        return True

    frame.dwm = SimpleNamespace(DwmDefWindowProc=dwm)
    for code in (0x84, 0x2A2):
        msg = native_message(1, code)
        assert frame.native_event(c.addressof(msg)) == 9
    assert received == [0x84, 0x2A2]


@pytest.mark.parametrize('dpi,border,caption', [(96, 8, 31), (144, 12, 47)])
def test_bordas_e_arraste_em_monitor_com_coordenadas_negativas(dpi, border, caption):
    frame = WindowsFrame(None)
    frame.hwnd = 1
    def rect(hwnd, output):
        output._obj.left, output._obj.top = -1600, -200
        output._obj.right, output._obj.bottom = -400, 600
        return 1
    frame.user = SimpleNamespace(GetWindowRect=rect, GetDpiForWindow=lambda _: dpi,
        GetSystemMetricsForDpi=lambda n, _: {32: border//2, 92: border//2, 4: caption-border}[n],
        IsZoomed=lambda _: False)
    frame.dwm = SimpleNamespace(DwmGetWindowAttribute=lambda *args: -1)
    def hit(x, y):
        return frame.hit_test(((y & 0xffff) << 16) | (x & 0xffff))
    assert hit(-1599, -199) == 13  # top-left
    assert hit(-401, 599) == 17  # bottom-right
    assert hit(-401, 100) == 11  # right edge
    assert hit(-1000, -200 + border + 1) == 2  # system caption
    assert hit(-1000, 100) == 1  # client controls


def test_maximizada_respeita_barra_de_tarefas_sem_quebrar_hit_test_dwm():
    frame = WindowsFrame(SimpleNamespace(isFullScreen=lambda: False))
    frame.active, frame.hwnd = True, 1
    def monitor(_, output):
        output._obj.work = w.RECT(1920, 0, 4480, 1400)
        return 1
    frame.user = SimpleNamespace(IsZoomed=lambda _: True,
        MonitorFromWindow=lambda *args: 1, GetMonitorInfoW=monitor)
    rect = w.RECT(1908, -12, 4492, 1424)
    msg = native_message(1, 0x83, c.addressof(rect), 1)
    assert frame.native_event(c.addressof(msg)) == 0
    assert (rect.left, rect.top, rect.right, rect.bottom) == (1920, -12, 4480, 1400)


@pytest.mark.parametrize('dpr,height', [(1, 31), (1.5, 47)])
def test_caption_copia_rgb_do_mesmo_canvas_sem_modificar_cache(app, monkeypatch, dpr, height):
    window = QMainWindow()
    canvas = CanvasBackground()
    window.setCentralWidget(canvas)
    layout = QVBoxLayout(canvas)
    layout.setContentsMargins(28, 16, 28, 24)
    canvas.resize(500, 400)
    monkeypatch.setattr(canvas, 'devicePixelRatioF', lambda: dpr)
    monkeypatch.setattr(window, 'devicePixelRatioF', lambda: dpr)
    frame = WindowsFrame(window)
    frame.active, frame.hwnd, frame.caption_height = True, 1, height
    frame._base_margins = layout.contentsMargins()
    released, copied = [], []
    frame.user = SimpleNamespace(GetDC=lambda _: 1, ReleaseDC=lambda *args: released.append(args))
    def copy(*args):
        copied.append(bytes(args[9]))
        return height
    frame.gdi = SimpleNamespace(SetDIBitsToDevice=copy)
    frame.paint_caption()
    from PyQt6.QtGui import QImage
    image = canvas._cache.copy(0, 0, canvas._cache.width(), height).toImage()
    image = image.convertToFormat(QImage.Format.Format_RGB32)
    expected = image.constBits().asstring(image.sizeInBytes())
    for channel in (0, 1, 2):
        assert copied[0][channel::4] == expected[channel::4]
    assert copied[0][3::4] == bytes(len(expected)//4)
    assert expected[3::4] == bytes([255]) * (len(expected)//4)
    assert layout.contentsMargins().top() == 16 + math.ceil(height/dpr)
    assert released == [(1, 1)]
    window.deleteLater()


def test_falha_de_composicao_restaura_margens_e_moldura(app, caplog):
    window = QMainWindow()
    canvas = CanvasBackground()
    window.setCentralWidget(canvas)
    layout = QVBoxLayout(canvas)
    layout.setContentsMargins(28, 16, 28, 24)
    canvas.resize(500, 400)
    frame = WindowsFrame(window)
    frame.active, frame.hwnd, frame.caption_height = True, 1, 31
    frame._base_margins = layout.contentsMargins()
    frame.user = SimpleNamespace(GetDC=lambda _: 1, ReleaseDC=lambda *args: 1,
                                 SetWindowPos=lambda *args: 1)
    reset = []
    frame.dwm = SimpleNamespace(DwmExtendFrameIntoClientArea=lambda hwnd, margins: reset.append(margins._obj.top))
    frame.gdi = SimpleNamespace(SetDIBitsToDevice=lambda *args: 0)
    frame.paint_caption()
    assert not frame.active and frame.failed
    assert reset == [0]
    assert layout.contentsMargins().top() == 16
    assert 'moldura padrão mantida' in caplog.text
    window.deleteLater()
