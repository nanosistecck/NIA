"""Façade reutilizável do quadro nativo do DWM para janelas secundárias."""
import json
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QWidget

import core.windows_frame
from core.config_dashboard import ConfigDashboardWindow
from core.config_preferencias import ConfigService
from core.frame_nativo import aplicar_frame_nativo, FrameNativoMixin
from core.interface_agenda import AgendaWindow
from core.interface_planos import PlanosWindow
from core.personas import ESCOLHA_PADRAO


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


# ── janelas secundárias ─────────────────────────────────────────────────────
def servico_falso(tmp_path):
    """ConfigService em arquivos temporários, no estilo dos outros testes."""
    persona = tmp_path / 'persona.json'
    if not persona.exists():
        persona.write_text(
            json.dumps(dict(ESCOLHA_PADRAO, personagem='sulafat')),
            encoding='utf-8')
    return ConfigService(persona_path=persona,
                         dashboard_path=tmp_path / 'dashboard_config.json',
                         interface_path=tmp_path / 'interface.json')


def construir_janela(chave, tmp_path, monkeypatch):
    monkeypatch.setenv('NIA_AGENDA', str(tmp_path / 'agenda.json'))
    monkeypatch.setenv('NIA_PLANOS_DIR', str(tmp_path / 'planos'))
    if chave == 'config':
        return ConfigDashboardWindow(servico_falso(tmp_path))
    if chave == 'agenda':
        return AgendaWindow()
    return PlanosWindow()


@pytest.mark.parametrize('chave, cor', [
    ('config', None),          # cor conferida depois, via janela._paleta['bg']
    ('agenda', '#061524'),
    ('planos', '#081527'),
])
def test_janelas_secundarias_instalam_frame(monkeypatch, chave, cor, tmp_path):
    chamados = []
    monkeypatch.setattr('core.frame_nativo.aplicar_frame_nativo',
                        lambda janela, *, cor=None: chamados.append(cor) or True)
    janela = construir_janela(chave, tmp_path, monkeypatch)
    esperado = janela._paleta['bg'] if chave == 'config' else cor
    assert chamados == [esperado]
    assert janela.windowTitle()  # rótulo da barra de tarefas preservado
