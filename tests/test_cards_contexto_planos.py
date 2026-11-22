# -*- coding: utf-8 -*-
"""Criacao de cards x criacao de planos e comandos locais do Canvas.

Frase real do dono (22/11/2026): "criar um novo card" era classificado como
criacao de plano e a NIA perguntava "qual plano". Estes testes cobrem a rota
real de chat/voz e a gramatica local, sem provedor externo.
"""
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
from core import planos as BP


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def plano(tmp_path, monkeypatch):
    monkeypatch.setenv('NIA_PLANOS_DIR', str(tmp_path / 'dados'))
    p = BP.inicializar_mapa(BP.criar('Produto aberto', 'Validar o produto', 'Produto').id)
    return BP.carregar(p.id)


def contexto(plano, card_id=None):
    ctx = AP.montar_contexto(plano, card_id)
    ctx.update({'plano': plano, 'cartoes': plano.mapa['cards']})
    return ctx


# ── roteamento: card nao e plano ────────────────────────────────────────────

@pytest.mark.parametrize('frase', [
    'criar um novo card',
    'criar um card',
    'criar um card chamado Pesquisa',
    'criar um card sobre marketing',
    'criar um card com ideias sobre lançamento',
    'quero criar um card',
    'quero criar um card sobre marketing',
    'criar cards sobre o sistema',
    'adicione um card com ideias sobre lançamento',
])
def test_pedido_de_card_nao_e_classificado_como_criar_plano(frase):
    assert CP.reconhecer(frase, {}).tipo != 'CRIAR', frase


@pytest.mark.parametrize('frase,tipo', [
    ('Vamos planejar um produto para pequenos lojistas.', 'CRIAR'),
    ('Quero criar um projeto.', 'CRIAR'),
    ('criar um novo plano', 'CRIAR'),
    ('criar um projeto para lojistas', 'CRIAR'),
    ('quais planos eu tenho', 'LISTAR_PLANOS'),
    ('liste meus planos', 'LISTAR_PLANOS'),
    ('gerenciar os planos', 'GERENCIADOR'),
])
def test_intencoes_de_plano_preservadas(frase, tipo):
    assert CP.reconhecer(frase, {}).tipo == tipo


# ── gramatica local de criacao de cards ─────────────────────────────────────

@pytest.mark.parametrize('frase,titulo', [
    ('crie um card chamado Pesquisa', 'Pesquisa'),
    ('crie um card com o título Pesquisa de mercado', 'Pesquisa de mercado'),
    ('criar um card sobre marketing', 'Marketing'),
    ('criar um novo card de ideias', 'Ideias'),
    ('criar um card com ideias sobre lançamento', 'Ideias sobre lançamento'),
    ('criar um card com ideias para o lançamento', 'Ideias para o lançamento'),
    ('adicione um card com ideias sobre lançamento', 'Ideias sobre lançamento'),
    ('criar um novo card', 'Novo card'),
])
def test_criacao_local_extrai_titulo(plano, frase, titulo):
    ops, erros = AP.intencao_para_lote(frase, contexto(plano))
    assert not erros, erros
    criados = [o for o in ops if o.get('tipo') == 'criar_card']
    assert len(criados) == 1
    assert criados[0]['titulo'] == titulo


def test_criacao_local_tipo_status_descricao_e_posicao(plano):
    frase = ('crie um card chamado Validação como tarefa com status concluído '
             'com a descrição Testar com lojistas em 420, 180')
    ops, erros = AP.intencao_para_lote(frase, contexto(plano))
    assert not erros, erros
    op = next(o for o in ops if o.get('tipo') == 'criar_card')
    assert op['titulo'] == 'Validação'
    assert op['tipo_card'] == 'tarefa'
    assert op['status'] == 'concluido'
    assert op['descricao'] == 'Testar com lojistas'
    assert (op['x'], op['y']) == (420.0, 180.0)


def test_criacao_local_de_varios_cards_em_um_lote(plano):
    ops, erros = AP.intencao_para_lote(
        'crie três cards: Pesquisa, Protótipo, Validação', contexto(plano))
    assert not erros, erros
    titulos = [o['titulo'] for o in ops if o.get('tipo') == 'criar_card']
    assert titulos == ['Pesquisa', 'Protótipo', 'Validação']
    assert len({o['temp_id'] for o in ops if o.get('tipo') == 'criar_card'}) == 3


def test_criacao_local_conecta_ao_card_nomeado(plano):
    origem = plano.mapa['cards'][0]
    ops, erros = AP.intencao_para_lote(
        'crie um card chamado Métricas e conecte ao card ' + origem['titulo'],
        contexto(plano))
    assert not erros, erros
    criado = next(o for o in ops if o.get('tipo') == 'criar_card')
    conexao = next(o for o in ops if o.get('tipo') == 'conectar')
    assert criado['titulo'] == 'Métricas'
    assert conexao['origem'] == origem['id']
    assert conexao['destino_ref'] == criado['temp_id']


def test_anexar_ideias_a_card_nomeado(plano):
    card = plano.mapa['cards'][0]
    ops, erros = AP.intencao_para_lote(
        'adicione estas ideias ao card ' + card['titulo'] + ': feiras; parcerias',
        contexto(plano))
    assert not erros, erros
    op = next(o for o in ops if o.get('tipo') == 'anexar_texto')
    assert op['card_id'] == card['id']
    assert op['ideias'] == ['feiras', 'parcerias']


def test_renomear_rotulo_de_conexao(plano):
    a, b = plano.mapa['cards'][0], None
    # Cria um segundo card e uma conexao reais no mapa de teste.
    ops, erros = AP.intencao_para_lote('crie um card chamado Entrega', contexto(plano))
    assert not erros, erros
    b = BP.novo_id()
    mapa = json.loads(json.dumps(plano.mapa))
    mapa['cards'].append({'id': b, 'tipo': 'ideia', 'titulo': 'Entrega',
                          'resumo': '', 'descricao': '', 'status': '',
                          'x': 300.0, 'y': 100.0, 'modelo': '', 'estado': '',
                          'valor': None, 'acumulado': None,
                          'restrito': False, 'financeiro': False})
    mapa['conexoes'].append({'id': 'lig1', 'origem': a['id'], 'destino': b,
                             'rotulo': ''})
    plano2 = BP.atualizar(plano.id, {'mapa': mapa}, plano.revisao)
    ops, erros = AP.intencao_para_lote(
        'renomeie a conexão entre ' + a['titulo'] + ' e Entrega para depende de',
        contexto(plano2))
    assert not erros, erros
    op = next(o for o in ops if o.get('tipo') == 'editar_conexao')
    assert op['conexao_id'] == 'lig1'
    assert op['rotulo'] == 'depende de'


# ── rota real de chat/voz ───────────────────────────────────────────────────

@pytest.fixture
def sessao(app, tmp_path, monkeypatch):
    monkeypatch.setenv('NIA_PLANOS_DIR', str(tmp_path / 'dados'))
    monkeypatch.setattr(ui, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(ui.MainWindow, '_check_config', lambda self: True)
    w = ui.MainWindow('face.png')
    w.resize(1280, 820)
    w.show()
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
    nia._falar_resposta_comando = lambda mensagem, origem: falas.append((mensagem, origem))
    yield nia, w._canvas_editor, registros, falas
    for timer in w.findChildren(QTimer):
        timer.stop()
    editor = w._canvas_editor.editor_internal
    editor.cena.itens_cards.clear()
    editor.cena.itens_conexoes.clear()
    editor.cena.clear()
    w.hide()
    w.deleteLater()
    app.processEvents()


def pedir(nia, app, texto, origem='texto'):
    assert nia._executar_frase_habilidade(texto, origem), texto
    app.processEvents()


def mapa(overlay):
    return overlay.editor_internal.plano_atual().mapa


def test_frase_real_criar_um_novo_card_cria_card_no_plano_aberto(sessao, app):
    nia, overlay, registros, falas = sessao
    pedir(nia, app, 'Ative o modo NIA')
    pedir(nia, app, 'criar um novo card')
    cartoes = mapa(overlay)['cards']
    assert len(cartoes) == 2
    assert any(c['titulo'] == 'Novo card' for c in cartoes)
    assert 'Qual é o plano' not in registros[-1]
    assert 'concluída' in registros[-1]
    assert falas[-1][1] == 'texto'


def test_frase_real_quero_criar_um_card_sobre_marketing(sessao, app):
    nia, overlay, registros, _ = sessao
    pedir(nia, app, 'Ative o modo NIA')
    pedir(nia, app, 'quero criar um card sobre marketing')
    assert any(c['titulo'] == 'Marketing' for c in mapa(overlay)['cards'])
    assert 'Qual é o plano' not in registros[-1]


def test_criar_card_com_ideias_e_anexar_mais_ideias(sessao, app):
    nia, overlay, _, _ = sessao
    pedir(nia, app, 'Ative o modo NIA')
    pedir(nia, app, 'criar um card com ideias sobre lançamento')
    card = next(c for c in mapa(overlay)['cards']
                if c['titulo'] == 'Ideias sobre lançamento')
    pedir(nia, app, 'adicione estas ideias ao card Ideias sobre lançamento: '
                    'convidar parceiros; preparar landing page')
    card = next(c for c in mapa(overlay)['cards'] if c['id'] == card['id'])
    assert 'convidar parceiros' in card['descricao']
    assert 'preparar landing page' in card['descricao']


def test_sem_plano_aberto_pedir_card_orienta_abrir_plano(sessao, app):
    nia, overlay, registros, falas = sessao
    overlay.window()._voltar_dos_planos()
    app.processEvents()
    pedir(nia, app, 'criar um novo card')
    assert 'Abra um plano' in registros[-1]
    assert 'Qual é o plano' not in registros[-1]
    assert BP.listar()[0]  # o plano existente continua; nenhum novo plano criado
    assert falas[-1][1] == 'texto'


def test_quais_planos_e_falado_e_lista_titulos(sessao, app):
    nia, _, registros, falas = sessao
    pedir(nia, app, 'quais planos eu tenho', 'voz')
    assert 'Produto aberto' in registros[-1]
    assert falas[-1][1] == 'voz'
