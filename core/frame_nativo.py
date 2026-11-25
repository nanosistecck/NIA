"""Façade reutilizável do quadro nativo do DWM para janelas secundárias.

`aplicar_frame_nativo` integra qualquer janela ao quadro nativo do Windows:
barra de título sinônima, botões de janela à direita do DWM e hit-testing do
DWM. `FrameNativoMixin` espelha as delegações de `ui.py` para quem herda.

Convenção para janelas futuras: herdar `FrameNativoMixin` e, no fim de
`__init__`, chamar `self._instalar_frame_nativo(cor=...)`. A cor explícita é
o valor da faixa de cada janela; sem `cor`, a paleta do widget é usada
(`QPalette.ColorRole.Window`). Fora do Windows, o helper não altera a janela.
"""
from PyQt6.QtCore import QEvent
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

from core.windows_frame import CAPTION_PAINT_EVENT


def aplicar_frame_nativo(janela, *, cor=None) -> bool:
    """Integra `janela` ao quadro nativo do DWM; reusa a instância em `_frame_nativo`.

    `cor` aceita `QColor | str | None`; retorna `False` fora do Windows.
    """
    if QApplication.platformName() != "windows":
        return False
    if cor is None:
        cor = janela.palette().color(QPalette.ColorRole.Window)
    else:
        cor = QColor(cor)
    if not hasattr(janela, '_frame_nativo'):
        from core.windows_frame import WindowsFrame
        janela._frame_nativo = WindowsFrame(janela, cor=cor)
    return janela._frame_nativo.install()


class FrameNativoMixin:
    """Delega `event`/`nativeEvent` para o frame nativo instalado por `_instalar_frame_nativo`."""

    def _instalar_frame_nativo(self, *, cor=None) -> bool:
        return aplicar_frame_nativo(self, cor=cor)

    def event(self, event):
        result = super().event(event)
        try:
            frame = getattr(self, '_frame_nativo', None)
        except RuntimeError:
            return result
        if frame is not None and frame.active:
            if event.type() in (QEvent.Type.UpdateRequest, CAPTION_PAINT_EVENT):
                frame.paint_caption()
        return result

    def nativeEvent(self, event_type, message):
        try:
            frame = getattr(self, '_frame_nativo', None)
        except RuntimeError:
            return super().nativeEvent(event_type, message)
        if frame is not None:
            result = frame.native_event(message)
            if result is not None:
                return True, result
        return super().nativeEvent(event_type, message)
