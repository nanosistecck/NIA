# -*- coding: utf-8 -*-
"""Consulta local do Canvas: cards, texto, conexões e alvo correto."""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import main
from core import assistencia_planos as AP
from core import comandos_planos as CP
from core import planos as BP

TEXTO = ("Primeira ideia: feiras regionais.\n"
         "\n"
         "Segunda ideia:\n"
         "- parceria com associações")


@pytest.fixture
def plano(tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    p = BP.inicializar_mapa(BP.criar("Projeto dos lojistas", "Objetivo", "Geral").id)
    m = p.mapa
    m["cards"] += [
        {"id": "pub", "tipo": "ideia", "titulo": "Público-alvo", "resumo": "Lojistas",
         "descricao": "", "status": "", "x": 0.0, "y": 0.0, "modelo": "", "estado": "",
         "valor": None, "acumulado": None, "restrito": False, "financeiro": False},
        {"id": "div", "tipo": "ideia", "titulo": "Divulgação", "resumo": "Canais",
         "descricao": TEXTO, "status": "", "x": 260.0, "y": 0.0, "modelo": "", "estado": "",
         "valor": None, "acumulado": None, "restrito": False, "financeiro": False},
    ]
    m["conexoes"].append({"id": "l1", "origem": "div", "destino": "pub",
                          "rotulo": "alcança"})
    return BP.atualizar(p.id, {"mapa": m}, p.revisao)


@pytest.fixture
def nia(plano):
    registros = []
    obj = object.__new__(main.NiaLive)
    obj._modo_local = True
    obj._provedor_assistido = None
    obj._sessao_planos = CP.SessaoComandosPlanos()
    obj.ui = SimpleNamespace(
        contexto_canvas=lambda: {"plano_id": plano.id, "card_id": "div",
                                 "plano": BP.carregar(plano.id)},
        write_log=lambda t: registros.append(t),
        abrir_plano=lambda _: None,
        abrir_planos=lambda: None,
        aplicar_lote_assistido=lambda *a: None,
        desfazer_lote_assistido=lambda: None,
        destacar_card=lambda *a: None,
    )
    for nome in ("_contexto_planos", "_aplicar_resultado_planos",
                 "_processar_pedido_assistido", "_resposta_assistida_local",
                 "_processar_pedido_lembrete", "_executar_frase_habilidade"):
        setattr(obj, nome, getattr(main.NiaLive, nome).__get__(obj, main.NiaLive))
    return obj, registros


def test_intencoes_de_consulta_sao_reconhecidas():
    for frase, tipo in (
        ("Quais cards existem neste plano?", "LISTAR_CARDS"),
        ("Leia o que escrevi neste card.", "LER_CARD"),
        ("O que escrevi neste card?", "LER_CARD"),
        ("Com quais cards Divulgação está conectado?", "CONEXOES_CARD"),
        ("O que escrevi em Divulgação no Projeto dos lojistas?", "LER_CARD"),
        ("Explique esse card e como ele se liga aos outros.", "EXPLICAR_CARD"),
    ):
        assert AP.reconhecer_intencao(frase) == tipo, frase


def test_listar_cards_local(nia, plano):
    obj, registros = nia
    assert obj._executar_frase_habilidade("Quais cards existem neste plano?", "texto")
    resposta = " ".join(registros)
    assert "Público-alvo" in resposta and "Divulgação" in resposta
    assert "3" in resposta


def test_ler_texto_e_conexoes_locais(nia):
    obj, registros = nia
    assert obj._executar_frase_habilidade("O que escrevi neste card?", "texto")
    resposta = " ".join(registros)
    assert "Primeira ideia" in resposta and "parceria" in resposta

    registros.clear()
    assert obj._executar_frase_habilidade(
        "Com quais cards Divulgação está conectado?", "texto")
    resposta = " ".join(registros)
    assert "Público-alvo" in resposta and "alcança" in resposta


def test_plano_fechado_por_nome(nia, plano, monkeypatch):
    obj, registros = nia
    obj.ui.contexto_canvas = lambda: {"plano_id": None, "card_id": None, "plano": None}
    assert obj._executar_frase_habilidade(
        "O que escrevi em Divulgação no Projeto dos lojistas?", "texto")
    resposta = " ".join(registros)
    assert "Primeira ideia" in resposta and "Divulgação" in resposta


def test_explicacao_distingue_registrado_de_interpretacao(nia):
    obj, registros = nia
    obj._provedor_assistido = lambda pedido, ctx: "Interpretação de exemplo."
    assert obj._executar_frase_habilidade(
        "Explique esse card e como ele se liga aos outros.", "texto")
    resposta = " ".join(registros)
    assert "Primeira ideia" in resposta
    assert "Interpretação" in resposta or "interpretação" in resposta.lower() or \
        "sugestão" in resposta.lower()


def test_voz_e_texto_usam_mesmo_caminho(nia):
    obj, registros = nia
    obj._executar_frase_habilidade("Leia o que escrevi neste card.", "texto")
    texto = list(registros)
    registros.clear()
    obj._executar_frase_habilidade("Leia o que escrevi neste card.", "voz")
    assert registros == texto


def test_sem_selecao_pede_alvo(nia):
    obj, registros = nia
    obj.ui.contexto_canvas = lambda: {"plano_id": None, "card_id": None, "plano": None}
    assert obj._executar_frase_habilidade("Leia o que escrevi neste card.", "texto")
    assert any("selecione" in r.lower() or "qual card" in r.lower()
               for r in registros)


def test_card_restrito_nao_sai_no_contexto_externo(nia, plano):
    obj, registros = nia
    plano = BP.atualizar(plano.id, {"mapa": {
        **plano.mapa,
        "cards": [{**c, "restrito": True} if c["id"] == "div" else c
                  for c in plano.mapa["cards"]],
    }}, plano.revisao)
    obj.ui.contexto_canvas = lambda: {"plano_id": plano.id, "card_id": "div",
                                      "plano": plano}
    chamados = []
    obj._provedor_assistido = lambda pedido, ctx: (chamados.append(ctx) or "{}")
    obj._executar_frase_habilidade(
        "Explique esse card e como ele se liga aos outros.", "texto")
    assert chamados and chamados[0]["card"] is None
    assert "Primeira ideia" not in " ".join(registros)
