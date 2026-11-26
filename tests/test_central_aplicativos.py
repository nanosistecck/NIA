# -*- coding: utf-8 -*-
"""Central de Aplicativos: grade, pesquisa, categorias, teclado e ações."""
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

import core.registro_aplicativos as RA
from core.central_aplicativos import CentralAplicativos


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


class GerenciadorFalso:
    def __init__(self, chaves=()):
        self.chaves = set(chaves)
        self.abertos = []

    def registradas(self):
        return tuple(self.chaves)

    def abrir(self, chave):
        self.abertos.append(chave)
        return chave


@pytest.fixture
def registro(monkeypatch):
    monkeypatch.setattr(RA, '_DESCRITORS', {})
    RA.registrar(RA.DescritorApp(
        id='pesquisa', nome='Pesquisa', descricao='Investiga informações',
        categoria='pesquisa', icone='search', cor='#00d4ff',
        possui_interface=True, janela='pesquisa', dominio_ferramenta='pesquisa'))
    RA.registrar(RA.DescritorApp(
        id='biblioteca', nome='Biblioteca', descricao='Guarda documentos',
        categoria='conhecimento', icone='save', cor='#00ff88',
        possui_interface=True, janela='biblioteca', dominio_ferramenta='biblioteca'))
    RA.registrar(RA.DescritorApp(
        id='resumo', nome='Resumo do dia', descricao='Gera resumo local',
        categoria='habilidades', tipo='habilidade', possui_interface=False,
        dominio_ferramenta='habilidades', fixavel_no_dock=False))
    monkeypatch.setattr(RA, 'sincronizar_habilidades', lambda: 0)
    monkeypatch.setattr(RA, 'sincronizar_ferramentas', lambda: 0)
    return RA


@pytest.fixture
def central(app, registro):
    ger = GerenciadorFalso({'pesquisa', 'biblioteca'})
    w = CentralAplicativos(None, registro=registro, gerenciador=ger, animacoes=False)
    w.resize(1000, 700)
    w.abrir()
    yield w, ger
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_grade_e_estado_vazio(central):
    w, _ = central
    assert len(w._tiles) == 2
    assert 'resumo' not in w._tiles
    w._campo.setText('nao-existe-zzz')
    w._aplicar_filtro()
    assert w._tiles == {} and w._vazio.isVisible()
    w._campo.setText('')
    w._aplicar_filtro()
    assert len(w._tiles) == 2 and not w._vazio.isVisible()


def test_pesquisa_ignora_acento_e_maiusculas(central):
    w, _ = central
    w._campo.setText('BIBLIOTECA')
    w._aplicar_filtro()
    assert list(w._tiles) == ['biblioteca']
    w._campo.setText('informacoes')
    w._aplicar_filtro()
    assert list(w._tiles) == ['pesquisa']


def test_categorias_e_favoritos(central):
    w, _ = central
    w.definir_categoria('conhecimento')
    assert list(w._tiles) == ['biblioteca']
    w.definir_categoria('todos')
    w.definir_favoritos({'biblioteca'})
    w.definir_categoria('favoritos')
    assert list(w._tiles) == ['biblioteca']


def test_abrir_app_com_interface_e_habilidade_sem_interface(central):
    w, ger = central
    abertos = []
    solicitadas = []
    w.app_aberto.connect(abertos.append)
    w.ferramenta_solicitada.connect(lambda *a: solicitadas.append(a))
    w.abrir_app('pesquisa')
    assert ger.abertos == ['pesquisa'] and abertos == ['pesquisa']
    w.abrir_app('resumo')
    assert solicitadas and solicitadas[0][0] == 'habilidades'


def test_abrir_fechamento_e_teclado(central, app):
    w, _ = central
    fechadas = []
    w.fechada.connect(lambda: fechadas.append(True))
    QTest.keyClick(w, Qt.Key.Key_Escape)
    app.processEvents()
    assert not w.aberta and fechadas == [True]
    w.abrir()
    assert w.aberta and w._campo.hasFocus()
    w.definir_categoria('todos')
    primeiro = next(iter(w._tiles.values()))
    primeiro.setFocus()
    QTest.keyClick(primeiro, Qt.Key.Key_Right)
    app.processEvents()
    assert any(tile.hasFocus() for tile in w._tiles.values())


def test_contextual_emite_acoes(central):
    w, _ = central
    eventos = []
    w.acao_interface.connect(lambda *a: eventos.append(a))
    w._contextual('biblioteca', 'dock_fixar')
    w._contextual('biblioteca', 'informacoes')
    assert eventos[0][0] == 'dock_fixar' and eventos[1][0] == 'informacoes'


def test_colunas_responsivas_e_sem_webengine(central, app):
    w, _ = central
    w.resize(520, 600); app.processEvents()
    w._aplicar_filtro()
    assert w._grelha.columnCount() >= 2
    w.resize(1000, 800); app.processEvents()
    w._aplicar_filtro()
    assert 2 <= w._grelha.columnCount() <= 5
    w.resize(1400, 800); app.processEvents()
    w._aplicar_filtro()
    assert w._grelha.columnCount() <= 9
    assert not any('QtWebEngine' in m for m in sys.modules)


@pytest.fixture
def janela_real(app, tmp_path, monkeypatch):
    import ui
    monkeypatch.setattr(ui, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(ui.MainWindow, '_check_config', lambda self: True)
    for chave in ('NIA_PLANOS_DIR', 'NIA_AGENDA', 'NIA_PERFIL'):
        monkeypatch.setenv(chave, str(tmp_path / chave))
    w = ui.MainWindow('face.png')
    w.resize(1280, 820)
    w.show()
    app.processEvents()
    yield w
    if w._central.aberta:
        w._central_sig.emit(False)
    for timer in w.findChildren(__import__('PyQt6.QtCore', fromlist=['QTimer']).QTimer):
        timer.stop()
    w.hide(); w.deleteLater(); app.processEvents()


def test_botao_dock_abre_e_fecha_central(janela_real, app):
    w = janela_real
    botao = w._right_panel.buttons['central']
    anchor = w._stage.anchor
    botao.click(); app.processEvents()
    assert w._central.aberta and w._stage.anchor == 'bottom-left'
    assert botao.isDown()
    w._toggle_central(); app.processEvents()
    assert not w._central.aberta and w._stage.anchor == anchor
    assert not botao.isDown()


def test_aplicativos_da_central_tem_janela_registrada(janela_real, app):
    w = janela_real
    registros = w._janelas_ferramentas.registradas()
    assert set(('config', 'agenda', 'planos', 'globo')).issubset(set(registros))
    for chave in ('pesquisa', 'biblioteca', 'diagrama', 'integrador'):
        assert chave not in registros
        assert w._registro_aplicativos.por_id(chave) is None
    # Habilidade sem interface não gera ação inválida: prepõe o exemplo no chat.
    logs = []
    w._log_ferramenta = logs.append
    w._despachar_acao_central('habilidades', 'usar',
                              {'app': 'hab_secretaria'})
    assert 'abra a secretaria' in w._input.text().lower()
    assert any('pronta no chat' in str(x) for x in logs)


def test_config_parcial_ou_invalida_nao_quebra(app, tmp_path, monkeypatch):
    import json
    import ui
    (tmp_path / 'interface.json').write_text(json.dumps({
        'central_favoritos': 'invalido', 'hidden': 'ruim', 'order': None,
    }), encoding='utf-8')
    monkeypatch.setattr(ui, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(ui.MainWindow, '_check_config', lambda self: True)
    w = ui.MainWindow('face.png'); w.show(); app.processEvents()
    w._toggle_central(); app.processEvents()
    assert w._central.aberta and w._favoritos_central(w._prefs_central()) == set()
    w._toggle_central(); app.processEvents()
    w.hide(); w.deleteLater(); app.processEvents()


def test_favoritos_e_dock_persistem(janela_real, app):
    w = janela_real
    w._central_acao_interface('favorito_adicionar', 'pesquisa')
    w._central_acao_interface('dock_fixar', 'globo')
    dados = w._prefs_central().data
    assert 'pesquisa' in dados['central_favoritos']
    assert 'globo' in dados.get('order', ())
    # O aplicativo oculto no dock continua descoberto pela Central.
    assert w._registro_aplicativos.por_id('globo') is not None
    w._central_acao_interface('favorito_remover', 'pesquisa')
    assert 'pesquisa' not in w._prefs_central().data['central_favoritos']


def test_clique_mapeado_nao_abre_janela_pela_via_antiga(central):
    w, ger = central
    w.definir_acoes_dock({'mute', 'central'})
    dock_acao, ferramentas, abertos = [], [], []
    w.dock_acao_solicitada.connect(dock_acao.append)
    w.ferramenta_solicitada.connect(lambda *a: ferramentas.append(a))
    w.app_aberto.connect(abertos.append)
    w.abrir_app('mute')
    assert dock_acao == ['mute']
    assert ferramentas == [] and abertos == [] and ger.abertos == []


def test_bloco_nao_tem_indicador_verde(central):
    w, _ = central
    from PyQt6.QtWidgets import QLabel
    tiles = list(w._tiles.values())
    assert tiles
    for tile in tiles:
        assert not [l for l in tile.findChildren(QLabel)
                    if l.text() in ('●', '○')]


def test_bloco_central_fecha_a_bandeja(janela_real, app):
    w = janela_real
    w._toggle_central()
    app.processEvents()
    assert w._central.aberta
    w._executar_dock_pela_central('central')
    app.processEvents()
    assert not w._central.aberta
    assert not w._central_btn.isDown()


def test_ponte_clica_botao_oculto_do_dock(janela_real, app):
    from PyQt6.QtWidgets import QPushButton
    w = janela_real
    assert {'central', 'mute', 'webcam'}.issubset(w._central._acoes_dock)
    botao = QPushButton()
    cliques = []
    botao.clicked.connect(lambda _=False: cliques.append(True))
    w._right_panel.buttons['fake_teste'] = botao
    try:
        w._executar_dock_pela_central('fake_teste')
        app.processEvents()
        assert len(cliques) == 1
    finally:
        del w._right_panel.buttons['fake_teste']
        botao.deleteLater()

