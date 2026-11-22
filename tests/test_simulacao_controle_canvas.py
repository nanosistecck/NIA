# -*- coding: utf-8 -*-
"""Simulações de ponta a ponta: a NIA controlando o Canvas pelo chat e pela voz.

Cada teste fala a frase como o dono falaria, passa pela rota real
(`_executar_frase_habilidade`) e confere o estado do mapa depois.
"""
import json
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

import main
import ui
from core import comandos_planos as CP, planos as BP


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
    plano = BP.inicializar_mapa(
        BP.criar('Produto aberto', 'Validar o produto', 'Produto').id)
    w._abrir_canvas_do_plano(plano.id)
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


def card(overlay, titulo):
    return next(c for c in mapa(overlay)['cards'] if c['titulo'] == titulo)


def ligados(overlay, origem, destino):
    return any(l['origem'] == origem and l['destino'] == destino
               for l in mapa(overlay)['conexoes'])


def test_simulacao_criar_projeto_com_tres_cards(sessao, app):
    nia, overlay, registros, falas = sessao
    pedir(nia, app, 'Ative o modo NIA')
    assert overlay.modo_assistido

    pedir(nia, app, 'Crie um card chamado Pesquisa')
    pedir(nia, app, 'Crie um card chamado Protótipo')
    pedir(nia, app, 'Crie um card chamado Validação')

    titulos = {c['titulo'] for c in mapa(overlay)['cards']}
    assert {'Pesquisa', 'Protótipo', 'Validação'} <= titulos
    assert 'concluída' in registros[-1]
    assert falas[-1][1] == 'texto'


def test_simulacao_criar_card_ja_conectado_ao_projeto(sessao, app):
    nia, overlay, _, _ = sessao
    pedir(nia, app, 'Ative o modo NIA')
    pedir(nia, app, 'Crie um card chamado Pesquisa')
    pedir(nia, app, 'Crie um card chamado Métricas e conecte ao card Pesquisa')

    pesquisa = card(overlay, 'Pesquisa')
    metricas = card(overlay, 'Métricas')
    assert ligados(overlay, pesquisa['id'], metricas['id'])


def test_simulacao_modificar_titulo_descricao_e_status(sessao, app):
    nia, overlay, _, _ = sessao
    pedir(nia, app, 'Ative o modo NIA')
    pedir(nia, app, 'Crie um card chamado Pesquisa')
    pedir(nia, app, 'Crie um card chamado Protótipo')
    pedir(nia, app, 'Crie um card chamado Validação')

    pedir(nia, app, 'Renomeie o card Pesquisa para Pesquisa de mercado')
    pedir(nia, app, 'Altere a descrição do card Validação para Testar com cinco lojistas')
    pedir(nia, app, 'Marque o card Protótipo como concluído')

    assert card(overlay, 'Pesquisa de mercado')
    assert card(overlay, 'Validação')['descricao'] == 'Testar com cinco lojistas'
    assert card(overlay, 'Protótipo')['status'] == 'concluido'


def test_simulacao_mover_cards_e_desfazer(sessao, app):
    nia, overlay, _, _ = sessao
    pedir(nia, app, 'Ative o modo NIA')
    pedir(nia, app, 'Crie um card chamado Protótipo')
    pedir(nia, app, 'Crie um card chamado Validação')

    pedir(nia, app, 'Mova o card Protótipo para 420, 180')
    pedir(nia, app, 'Mova o card Validação para -120, 60')
    assert (card(overlay, 'Protótipo')['x'], card(overlay, 'Protótipo')['y']) == (420, 180)
    assert (card(overlay, 'Validação')['x'], card(overlay, 'Validação')['y']) == (-120, 60)

    pedir(nia, app, 'Desfazer')
    assert (card(overlay, 'Validação')['x'], card(overlay, 'Validação')['y']) != (-120, 60)


def test_simulacao_conectar_e_desconectar(sessao, app):
    nia, overlay, _, _ = sessao
    pedir(nia, app, 'Ative o modo NIA')
    pedir(nia, app, 'Crie um card chamado Pesquisa')
    pedir(nia, app, 'Crie um card chamado Validação')

    pedir(nia, app, 'Conecte o card Pesquisa ao card Validação')
    pesquisa, validacao = card(overlay, 'Pesquisa'), card(overlay, 'Validação')
    assert ligados(overlay, pesquisa['id'], validacao['id'])

    pedir(nia, app, 'Desconecte o card Pesquisa do card Validação')
    assert not ligados(overlay, pesquisa['id'], validacao['id'])


def test_simulacao_excluir_card_nomeado_preserva_os_outros(sessao, app):
    nia, overlay, _, _ = sessao
    pedir(nia, app, 'Ative o modo NIA')
    pedir(nia, app, 'Crie um card chamado Pesquisa')
    pedir(nia, app, 'Crie um card chamado Validação')

    pedir(nia, app, 'Exclua o card Validação')
    titulos = {c['titulo'] for c in mapa(overlay)['cards']}
    assert 'Validação' not in titulos
    assert 'Pesquisa' in titulos


def test_simulacao_consultar_cards_e_conexoes(sessao, app):
    nia, overlay, registros, _ = sessao
    pedir(nia, app, 'Ative o modo NIA')
    pedir(nia, app, 'Crie um card chamado Pesquisa')
    pedir(nia, app, 'Crie um card chamado Validação')
    pedir(nia, app, 'Conecte o card Pesquisa ao card Validação')

    pedir(nia, app, 'Quais cards existem?')
    assert 'Pesquisa' in registros[-1] and 'Validação' in registros[-1]
    pedir(nia, app, 'Com quais cards o card Pesquisa está conectado?')
    assert 'Validação' in registros[-1]


def test_simulacao_substituir_mapa_pelo_pedido_real(sessao, app):
    nia, overlay, registros, _ = sessao
    pedir(nia, app, 'Ative o modo NIA')
    pedir(nia, app, 'Crie um card chamado Antigo')
    raiz = mapa(overlay)['raiz_id']
    antigo = card(overlay, 'Antigo')
    overlay.editor_internal.conectar(raiz, antigo['id'])
    overlay.editor_internal.selecionar(antigo['id'])
    antes = json.loads(json.dumps(mapa(overlay)))

    operacoes = [
        {'tipo': 'editar_campos', 'card_id': raiz,
         'campos': {'titulo': 'Como a NIA funciona'}},
        {'tipo': 'criar_card', 'titulo': 'Funcionamento',
         'descricao': 'Chat, voz e Canvas.', 'temp_id': 'func'},
        {'tipo': 'criar_card', 'titulo': 'Plano de evolução',
         'descricao': 'Melhorias futuras a validar.', 'temp_id': 'evo'},
        {'tipo': 'conectar', 'origem': raiz, 'destino_ref': 'func'},
        {'tipo': 'conectar', 'origem': 'func', 'destino_ref': 'evo'},
    ]
    nia._provedor_assistido = lambda *args: json.dumps({'operacoes': operacoes})

    pedir(nia, app, 'agora apaga os outros cards, e modifique para como seu '
                    'sistema funciona e um plano de evolução')

    titulos = {c['titulo'] for c in mapa(overlay)['cards']}
    assert 'Antigo' not in titulos
    assert {'Como a NIA funciona', 'Funcionamento', 'Plano de evolução'} <= titulos
    assert mapa(overlay)['raiz_id'] == raiz
    assert 'concluída' in registros[-1]

    pedir(nia, app, 'Desfazer')
    assert mapa(overlay) == antes


def test_simulacao_por_voz_cria_e_move(sessao, app):
    nia, overlay, _, falas = sessao
    pedir(nia, app, 'Ative o modo NIA', origem='voz')
    pedir(nia, app, 'Crie um card chamado Lançamento', origem='voz')
    pedir(nia, app, 'Mova o card Lançamento para 300, 240', origem='voz')

    lancamento = card(overlay, 'Lançamento')
    assert (lancamento['x'], lancamento['y']) == (300, 240)
    assert falas[-1][1] == 'voz'
