# -*- coding: utf-8 -*-
"""Interacao completa com o Canvas: pedido generativo, contexto e retomada."""
import json
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

import main
import ui
from core import assistencia_planos as AP
from core import comandos_planos as CP
from core import controle_canvas as CC
from core import planos as BP


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def sessao(app, tmp_path, monkeypatch):
    monkeypatch.setenv('NIA_PLANOS_DIR', str(tmp_path / 'dados'))
    monkeypatch.setattr(ui, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(ui.MainWindow, '_check_config', lambda self: True)
    w = ui.MainWindow('face.png')
    w.resize(1280, 820)
    w.show()
    app.processEvents()
    p = BP.inicializar_mapa(BP.criar('Produto aberto', 'Validar o produto', 'Produto').id)
    w._abrir_canvas_do_plano(p.id)
    app.processEvents()
    casca = object.__new__(ui.NiaUI)
    casca._win = w
    registros, falas = [], []
    casca.write_log = registros.append
    nia = object.__new__(main.NiaLive)
    nia.ui = casca
    nia._modo_local = True
    nia._sessao_planos = CP.SessaoComandosPlanos()
    nia._provedor_assistido = None
    nia._falar_resposta_comando = lambda m, o: falas.append((m, o))
    yield nia, w._canvas_editor, registros, falas
    for timer in w.findChildren(QTimer):
        timer.stop()
    editor = w._canvas_editor.editor_internal
    editor._timer.stop()
    editor.cena.itens_cards.clear()
    editor.cena.itens_conexoes.clear()
    editor.cena.clear()
    w.hide()
    w.deleteLater()
    app.processEvents()


def pedir(nia, app, texto, origem='texto'):
    resultado = nia._executar_frase_habilidade(texto, origem)
    app.processEvents()
    return resultado


def cartoes(overlay):
    return overlay.editor_internal.plano_atual().mapa['cards']


# ── conteúdo local sobre a NIA ──────────────────────────────────────────────

FRASE_REAL = ('vc consegue criar cards relacionados ao seu funcionamento '
              'e inserir nesse plano?')


def test_frase_real_e_reconhecida_como_funcionamento():
    assert CC.pedido_funcionamento_nia(FRASE_REAL)


@pytest.mark.parametrize('frase', [
    'crie cards sobre como você funciona',
    'monte cards com o seu funcionamento e evolução',
    'cards sobre a arquitetura da NIA',
])
def test_variantes_de_funcionamento(frase):
    assert CC.pedido_funcionamento_nia(frase)


def test_funcionamento_gera_cards_no_plano_aberto(sessao, app):
    nia, overlay, registros, _ = sessao
    assert pedir(nia, app, 'Ative o modo NIA')
    assert pedir(nia, app, FRASE_REAL)
    titulos = [c['titulo'] for c in cartoes(overlay)]
    assert 'Como a NIA funciona' in titulos
    assert 'Canvas Infinito' in titulos
    assert 'Evolução proposta' in titulos
    assert all(c.get('descricao') for c in cartoes(overlay)
               if c['titulo'] != 'Produto aberto')
    assert 'O plano mudou' not in ' '.join(registros)


# ── contexto pos-provedor ───────────────────────────────────────────────────

def test_espelho_vazio_nao_descarta_lote_valido(sessao, app, monkeypatch):
    nia, overlay, registros, _ = sessao
    assert pedir(nia, app, 'Ative o modo NIA')
    plano_id = overlay.editor_internal.plano_atual().id
    monkeypatch.setattr(nia.ui, 'estado_canvas_vivo', lambda: None)

    def provedor(pedido, contexto):
        return json.dumps({'operacoes': [
            {'tipo': 'criar_card', 'titulo': 'Funcionamento da NIA'}]})

    nia._provedor_assistido = provedor
    assert pedir(nia, app, 'Crie uma proposta detalhada para este cenário')
    assert any(c['titulo'] == 'Funcionamento da NIA' for c in cartoes(overlay))
    assert overlay.editor_internal.plano_atual().id == plano_id
    assert not any('O plano mudou' in item for item in registros)


def test_plano_real_trocado_ainda_descarta(sessao, app):
    nia, overlay, registros, _ = sessao
    assert pedir(nia, app, 'Ative o modo NIA')

    def provedor(pedido, contexto):
        outro = BP.inicializar_mapa(BP.criar('Outro', 'Objetivo').id)
        overlay.window()._abrir_canvas_do_plano(outro.id)
        app.processEvents()
        return json.dumps({'operacoes': [
            {'tipo': 'criar_card', 'titulo': 'Tardia'}]})

    nia._provedor_assistido = provedor
    assert pedir(nia, app, 'Crie uma proposta detalhada para este cenário')
    assert not any(c['titulo'] == 'Tardia' for c in cartoes(overlay))
    assert any('mudou' in item.lower() for item in registros)


# ── memória do último pedido ────────────────────────────────────────────────

@pytest.mark.parametrize('frase', [
    'tenta fazer meu pedido',
    'faz de novo',
    'tenta de novo',
    'repete o pedido',
    'faz isso de novo',
])
def test_frase_de_retomada_e_reconhecida(frase):
    assert CC.pedido_retomada(frase)


def test_retomada_reprocessa_ultimo_pedido(sessao, app, monkeypatch):
    nia, overlay, _, _ = sessao
    assert pedir(nia, app, 'Ative o modo NIA')
    assert pedir(nia, app, FRASE_REAL)
    antes = len(cartoes(overlay))
    habilidades = []
    monkeypatch.setattr(main.CH, 'reconhecer',
                        lambda t: habilidades.append(t) or (None, ''))
    assert pedir(nia, app, 'tenta fazer meu pedido')
    assert not habilidades
    assert len(cartoes(overlay)) > antes


def test_retomada_sem_pedido_responde_localmente(sessao, app, monkeypatch):
    nia, _, registros, _ = sessao
    habilidades = []
    monkeypatch.setattr(main.CH, 'reconhecer',
                        lambda t: habilidades.append(t) or (None, ''))
    assert pedir(nia, app, 'tenta fazer meu pedido')
    assert not habilidades
    assert any('pedido' in item.lower() for item in registros)
