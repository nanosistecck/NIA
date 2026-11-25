"""Façade reutilizável do quadro nativo do DWM para janelas secundárias."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QWidget

import core.windows_frame
from core.frame_nativo import aplicar_frame_nativo, FrameNativoMixin


@pytest.fixture(scope='module', autouse=True)
def app():
    return QApplication.instance() or QApplication([])


def test_helper_no_op_fora_do_windows(monkeypatch):
    monkeypatch.setattr(QApplication, 'platformName', lambda: 'offscreen')
    w = QWidget()
    assert aplicar_frame_nativo(w) is False
    assert not hasattr(w, '_frame_nativo')


def test_helper_instala_frame_com_cor_da_janela(monkeypatch):
    chamados = []
    class FakeFrame:
        def __init__(self, janela, *, cor=None):
            chamados.append((janela, cor))
        def install(self):
            return True
    monkeypatch.setattr(QApplication, 'platformName', lambda: 'windows')
    monkeypatch.setattr(core.windows_frame, 'WindowsFrame', FakeFrame)
    w = QWidget()
    assert aplicar_frame_nativo(w, cor='#061524') is True
    assert chamados == [(w, QColor('#061524'))]
    assert isinstance(w._frame_nativo, FakeFrame)


def test_mixin_instala_e_delega_event(monkeypatch):
    class Janela(FrameNativoMixin, QWidget):
        pass
    w = Janela()
    w.installado = []
    monkeypatch.setattr(w, '_instalar_frame_nativo', lambda **kw: w.installado.append(kw) or True)
    assert w._instalar_frame_nativo(cor='#00060a') is True
    assert w.installado == [{'cor': '#00060a'}]
    assert w.window() is w  # mixin não altera hierarquia Qt
