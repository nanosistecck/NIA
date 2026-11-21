# -*- coding: utf-8 -*-
"""Edição assistida: contexto, lotes atômicos e filtro de saída."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from core import assistencia_planos as AP
from core import planos as BP
from core.interface_mapa import EditorMapa
from core.planos import carregar, criar, inicializar_mapa


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def plano(tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    plano = inicializar_mapa(criar("Produto", "Vender para lojistas", "Produto").id)
    raiz = plano.mapa["raiz_id"]
    mapa = plano.mapa
    mapa["cards"].append({"id": "sol0", "tipo": "ideia",
                          "titulo": "Ideia base", "resumo": "Uma ideia",
                          "descricao": "Primeira frase. Segunda frase.",
                          "status": "", "x": 200.0, "y": 0.0})
    mapa["conexoes"].append({"id": "lx", "origem": raiz,
                             "destino": "sol0", "rotulo": ""})
    return BP.atualizar(plano.id, {"mapa": mapa}, plano.revisao)


@pytest.fixture
def editor(app, plano):
    ed = EditorMapa()
    ed.carregar(plano)
    yield ed
    ed._timer.stop()
    ed.cena.itens_cards.clear()
    ed.cena.itens_conexoes.clear()
    ed.cena.clear()
    ed.hide()
    ed.deleteLater()
    app.processEvents()


def test_montar_contexto_traz_card_e_vizinhos(plano):
    ctx = AP.montar_contexto(plano, "sol0")
    assert ctx["card"]["id"] == "sol0"
    assert plano.mapa["raiz_id"] in [c["id"] for c in ctx["vizinhos"]]
    assert ctx["plano_id"] == plano.id
    assert ctx["fingerprint"] == AP.fingerprint(plano)


def test_filtro_de_saida_externo_remove_restrito_e_financeiro(plano):
    ctx = AP.montar_contexto(plano, "sol0")
    ctx["card"]["restrito"] = True
    ctx["vizinhos"][0]["financeiro"] = True
    externo = AP.filtrar_contexto(ctx, AP.Destino(local=False, provedor="openai"))
    assert externo["card"] is None
    assert all(not c.get("financeiro") for c in externo["vizinhos"])
    local = AP.filtrar_contexto(ctx, AP.Destino(local=True, provedor="ollama"))
    assert local["card"]["restrito"] is True


def test_lote_local_cria_tres_solucoes_e_desfaz_de_uma_vez(editor, plano):
    ctx = AP.montar_contexto(plano, "sol0")
    ops, _ = AP.pedido_local("Adicione três soluções a este card.", ctx)
    assert len(ops) == 6  # 3 cards + 3 conexões
    validas, erros = AP.validar_lote(ops, editor.plano_atual(), ctx)
    assert not erros and len(validas) == 6

    contador = editor.pilha.count()
    AP.aplicar_lote(editor, validas, "Adicionar soluções")
    mapa = editor.plano_atual().mapa
    assert len(mapa["cards"]) == 2 + 3
    assert sum(1 for c in mapa["conexoes"] if c["origem"] == "sol0") == 3
    assert editor.pilha.count() == contador + 1

    editor.desfazer()
    assert len(editor.plano_atual().mapa["cards"]) == 2
    editor.refazer()
    assert len(editor.plano_atual().mapa["cards"]) == 5


def test_lote_invalido_preserva_mapa(editor, plano):
    ctx = AP.montar_contexto(plano, "sol0")
    antes = editor.plano_atual()
    ops = [{"tipo": "conectar", "origem": "sol0", "destino": "inexistente"}]
    validas, erros = AP.validar_lote(ops, antes, ctx)
    assert erros and not validas
    assert editor.plano_atual().mapa == antes.mapa


def test_conflito_com_edicao_local_em_memoria(editor, plano):
    ctx = AP.montar_contexto(plano, "sol0")
    editor.editar_card("sol0", {"resumo": "Edição manual local"})
    ops = [{"tipo": "editar_campos", "card_id": "sol0",
            "campos": {"resumo": "Resumo proposto pela NIA"}}]
    validas, erros = AP.validar_lote(ops, editor.plano_atual(), ctx)
    assert erros and not validas
    assert editor.plano_atual().mapa["cards"][1]["resumo"] == "Edição manual local"


def test_resposta_atrasada_troca_de_plano_descartada(editor, plano):
    ctx = AP.montar_contexto(plano, "sol0")
    outro = inicializar_mapa(criar("Outro", "Objetivo", "Projeto").id)
    editor.carregar(outro)
    ops = [{"tipo": "criar_card", "titulo": "Tardia", "origem": "sol0"}]
    validas, erros = AP.validar_lote(ops, editor.plano_atual(), ctx)
    assert erros and not validas


def test_reescrever_resumo_mantem_demais_campos(editor, plano):
    ctx = AP.montar_contexto(plano, "sol0")
    ops, erros = AP.pedido_local("Reescreva o resumo deste card em duas frases.", ctx)
    assert not erros and len(ops) == 1
    validas, erros = AP.validar_lote(ops, editor.plano_atual(), ctx)
    assert not erros
    AP.aplicar_lote(editor, validas, "Reescrever resumo")
    card = next(c for c in editor.plano_atual().mapa["cards"] if c["id"] == "sol0")
    assert card["resumo"] == "Primeira frase. Segunda frase."
    assert card["titulo"] == "Ideia base"
    assert card["descricao"] == "Primeira frase. Segunda frase."


def test_desfazer_lote_apenas_quando_ultima_operacao(editor, plano):
    ctx = AP.montar_contexto(plano, "sol0")
    ops, _ = AP.pedido_local("Adicione três soluções a este card.", ctx)
    validas, _ = AP.validar_lote(ops, editor.plano_atual(), ctx)
    AP.aplicar_lote(editor, validas, "Adicionar soluções")
    assert AP.desfazer_lote(editor) is True
    editor.refazer()
    editor.criar_card("Edição manual depois")
    assert AP.desfazer_lote(editor) is False
    assert len(editor.plano_atual().mapa["cards"]) == 6


def test_resposta_estruturada_do_provedor_e_validada(plano, editor):
    ctx = AP.montar_contexto(plano, "sol0")
    bruto = ('{"operacoes":[{"tipo":"criar_card","titulo":"Da NIA",'
             '"origem":"sol0"}]}')
    ops, erros = AP.parse_resposta(bruto, ctx)
    assert not erros and ops[0]["titulo"] == "Da NIA"
    validas, erros = AP.validar_lote(ops, editor.plano_atual(), ctx)
    assert not erros
    AP.aplicar_lote(editor, validas, "Da NIA")
    assert any(c["titulo"] == "Da NIA" for c in editor.plano_atual().mapa["cards"])
