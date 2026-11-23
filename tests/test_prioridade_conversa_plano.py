# -*- coding: utf-8 -*-
"""Prioridade da conversa sobre o plano no chat do Canvas e resumo legível.

Reproducao do pedido real (22/11/2026): falar do plano abria pasta/criava
arquivo/pesquisava internet, e a confirmacao mostrava IDs de 32 caracteres.
"""
import os
import re

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

import main
import ui
from core import assistencia_planos as AP
from core import comandos_planos as CP
from core import planos as BP

ID_TECNICO = re.compile(r'\b[0-9a-f]{32}\b')


@pytest.fixture
def plano(tmp_path, monkeypatch):
    monkeypatch.setenv('NIA_PLANOS_DIR', str(tmp_path / 'dados'))
    p = BP.inicializar_mapa(BP.criar('sobre inteligencia artificial',
                                     'Mapear a IA para o produto', 'Produto').id)
    mapa = p.mapa
    for ident, titulo in (('fund', 'Fundamentos'), ('ml', 'Machine Learning'),
                          ('deep', 'Deep Learning'), ('val', 'Validação')):
        mapa['cards'].append({'id': ident, 'tipo': 'ideia', 'titulo': titulo,
                              'resumo': '', 'descricao': '', 'status': '',
                              'x': 0.0, 'y': 0.0, 'modelo': '', 'estado': '',
                              'valor': None, 'acumulado': None,
                              'restrito': False, 'financeiro': False})
    return BP.atualizar(p.id, {'mapa': mapa}, p.revisao)


def contexto(plano, card_id=None):
    ctx = AP.montar_contexto(plano, card_id)
    ctx.update({'plano': plano, 'cartoes': plano.mapa['cards']})
    return ctx


# ── reconhecimento da conversa sobre o plano ────────────────────────────────

@pytest.mark.parametrize('frase', [
    'me fala sobre o plano que estamos criando',
    'e a Validação?',
    'o que tem nesse card?',
    'vamos melhorar as ideias do mapa',
    'sobre inteligencia artificial',
    'qual o objetivo do projeto?',
])
def test_conversa_sobre_plano_e_reconhecida(plano, frase):
    assert AP.conversa_sobre_plano(frase, contexto(plano)), frase


@pytest.mark.parametrize('frase', [
    'que horas são?',
    'como está o clima hoje?',
    'abra o bloco de notas',
    'procure nos meus arquivos por garantia',
])
def test_comandos_de_sistema_nao_sao_capturados(plano, frase):
    assert not AP.conversa_sobre_plano(frase, contexto(plano)), frase


def test_sem_plano_aberto_nao_e_conversa_de_plano():
    assert not AP.conversa_sobre_plano('fala sobre o plano', {})


# ── resumo da conversa ──────────────────────────────────────────────────────

def test_resumo_conversa_cita_plano_e_objetivo_sem_ids(plano):
    resposta = AP.resumo_conversa_plano(
        'me fala sobre o plano que estamos criando', contexto(plano))
    assert 'sobre inteligencia artificial' in resposta
    assert 'Mapear a IA' in resposta
    assert not ID_TECNICO.search(resposta)


def test_resumo_conversa_sobre_card_usar_titulo(plano):
    ctx = contexto(plano, 'val')
    resposta = AP.resumo_conversa_plano('o que tem neste card?', ctx)
    assert 'Validação' in resposta
    assert not ID_TECNICO.search(resposta)


# ── resumo do lote ──────────────────────────────────────────────────────────

def test_resumo_lote_usa_titulos_e_nao_ids(plano):
    operacoes = [
        {'tipo': 'criar_card', 'titulo': 'Fundamentos', 'temp_id': 'a'},
        {'tipo': 'criar_card', 'titulo': 'Machine Learning', 'temp_id': 'b'},
        {'tipo': 'criar_card', 'titulo': 'Deep Learning', 'temp_id': 'c'},
        {'tipo': 'editar_campos', 'card_id': 'fund',
         'campos': {'resumo': 'x'}},
        {'tipo': 'conectar', 'origem': 'ml', 'destino': 'deep'},
    ]
    mensagem = AP.resumo_lote(operacoes, plano)
    assert 'Alteração concluída em sobre inteligencia artificial' in mensagem
    assert 'Fundamentos' in mensagem
    assert 'Machine Learning' in mensagem
    assert not ID_TECNICO.search(mensagem)


def test_resumo_lote_limita_a_tres_nomes_e_diz_quantos_sobram(plano):
    operacoes = [{'tipo': 'criar_card', 'titulo': titulo, 'temp_id': str(i)}
                 for i, titulo in enumerate(('Fundamentos', 'Machine Learning',
                                             'Deep Learning', 'Validação'))]
    mensagem = AP.resumo_lote(operacoes, plano)
    assert 'e mais 1' in mensagem
    assert 'Validação' not in mensagem


def test_resumo_lote_sem_alvo_nomeado_e_curto(plano):
    mensagem = AP.resumo_lote([{'tipo': 'zoom', 'valor': 1.2}], plano)
    assert 'Alteração concluída' in mensagem
    assert not ID_TECNICO.search(mensagem)


# ── rota real de chat ───────────────────────────────────────────────────────

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
    p = BP.inicializar_mapa(
        BP.criar('sobre inteligencia artificial', 'Mapear a IA', 'Produto').id)
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
    yield nia, registros, falas
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


def test_chat_prioriza_conversa_do_plano(sessao, app, monkeypatch):
    nia, registros, falas = sessao
    habilidades = []
    monkeypatch.setattr(main.CH, 'reconhecer',
                        lambda texto: habilidades.append(texto) or (None, ''))
    assert nia._executar_frase_habilidade(
        'me fala sobre o plano que estamos criando', 'texto')
    app.processEvents()
    assert not habilidades
    assert 'sobre inteligencia artificial' in registros[-1]
    assert not ID_TECNICO.search(registros[-1])
    assert falas[-1][1] == 'texto'


def test_chat_nao_prioriza_frase_fora_do_plano(sessao, app, monkeypatch):
    nia, registros, _ = sessao
    chamadas = []
    monkeypatch.setattr(main.CH, 'reconhecer',
                        lambda texto: chamadas.append(texto) or (None, ''))
    assert not nia._executar_frase_habilidade('que horas são?', 'texto')
    assert chamadas
