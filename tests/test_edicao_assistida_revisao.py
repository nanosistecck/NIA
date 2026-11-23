# -*- coding: utf-8 -*-
"""Edição assistida com alvo fixo, lote validado e conflito detectado."""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import main
from core import assistencia_planos as AP
from core import planos as BP

IDLE = "Ideias existentes de divulgação."


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
         "descricao": IDLE, "status": "", "x": 260.0, "y": 0.0, "modelo": "", "estado": "",
         "valor": None, "acumulado": None, "restrito": False, "financeiro": False},
    ]
    m["conexoes"].append({"id": "l1", "origem": "div", "destino": "pub", "rotulo": ""})
    return BP.atualizar(p.id, {"mapa": m}, p.revisao)


@pytest.fixture
def nia(plano):
    aplicados = []
    registros = []
    obj = object.__new__(main.NiaLive)
    obj._modo_local = True
    obj._provedor_assistido = None
    obj.ui = SimpleNamespace(
        contexto_canvas=lambda: {"plano_id": plano.id, "card_id": "div",
                                 "plano": BP.carregar(plano.id), "modo_assistido": True},
        write_log=lambda t: registros.append(t),
        abrir_plano=lambda _: None,
        abrir_planos=lambda: None,
        aplicar_lote_assistido=lambda ops, rotulo: aplicados.append((ops, rotulo)),
        desfazer_lote_assistido=lambda: aplicados.append("desfazer"),
        destacar_card=lambda *a: None,
        estado_canvas_vivo=lambda: BP.carregar(plano.id),
    )
    for nome in ("_contexto_planos", "_aplicar_resultado_planos",
                 "_processar_pedido_assistido", "_resposta_assistida_local",
                 "_resolver_alvo_canvas", "_processar_pedido_lembrete",
                 "_executar_frase_habilidade"):
        setattr(obj, nome, getattr(main.NiaLive, nome).__get__(obj, main.NiaLive))
    return obj, aplicados, registros


def test_intencoes_de_edicao():
    for frase, tipo in (
        ("Que ideias posso acrescentar a Divulgação?", "SUGERIR"),
        ("Acrescente estas duas ideias ao texto deste card.", "EDITAR"),
        ("Crie três cards de divulgação gratuita ligados a este.", "EDITAR"),
        ("Reescreva o resumo deste card em duas frases.", "EDITAR"),
        ("Conecte este card a Público-alvo.", "EDITAR"),
        ("Desfaça o que você acabou de adicionar.", "DESFAZER"),
    ):
        assert AP.reconhecer_intencao(frase) == tipo, frase


def test_acrescentar_ideias_ao_texto_preserva_paragrafos(nia):
    obj, aplicados, registros = nia
    assert obj._executar_frase_habilidade(
        "Acrescente estas duas ideias ao texto deste card: feiras e parcerias.",
        "texto")
    assert aplicados
    ops = aplicados[0][0]
    assert any(o.get("tipo") == "anexar_texto" and o.get("card_id") == "div"
               for o in ops)


def test_criar_tres_cards_conectados_e_um_lote(nia):
    obj, aplicados, _ = nia
    assert obj._executar_frase_habilidade(
        "Crie três cards de divulgação gratuita ligados a este.", "texto")
    ops = aplicados[0][0]
    assert sum(1 for o in ops if o.get("tipo") == "criar_card") == 3
    assert sum(1 for o in ops if o.get("tipo") == "conectar") == 3


def test_conectar_por_nome(nia):
    obj, aplicados, _ = nia
    assert obj._executar_frase_habilidade(
        "Conecte este card a Público-alvo.", "texto")
    ops = aplicados[0][0]
    assert any(o.get("tipo") == "conectar" and o.get("origem") == "div"
               and o.get("destino") == "pub" for o in ops)


def test_conflito_com_edicao_manual_preservada(nia, plano):
    obj, aplicados, registros = nia
    vivo = BP.atualizar(plano.id, {"mapa": {
        **plano.mapa,
        "cards": [{**c, "resumo": "Edição manual"} if c["id"] == "div" else c
                  for c in plano.mapa["cards"]],
    }}, plano.revisao)
    # Pedido capturado com o plano original; edição manual aplicada depois.
    obj.ui.contexto_canvas = lambda: {"plano_id": plano.id, "card_id": "div",
                                      "plano": plano, "modo_assistido": True}
    obj.ui.estado_canvas_vivo = lambda: vivo
    obj._provedor_assistido = lambda pedido, ctx: (
        '{"operacoes":[{"tipo":"editar_campos","card_id":"div",'
        '"campos":{"resumo":"Resumo da NIA"}}]}')
    obj._executar_frase_habilidade("Reescreva o resumo deste card em duas frases.",
                                   "texto")
    assert not aplicados
    assert registros


def test_troca_de_plano_descarta_resposta_atrasada(nia, tmp_path, plano):
    obj, aplicados, registros = nia
    outro = BP.inicializar_mapa(BP.criar("Outro plano", "Obj", "Geral").id)
    obj.ui.contexto_canvas = lambda: {"plano_id": outro.id, "card_id": None,
                                      "plano": outro, "modo_assistido": True}
    obj.ui.estado_canvas_vivo = lambda: plano
    obj._executar_frase_habilidade(
        "Crie três cards de divulgação gratuita ligados a este.", "texto")
    assert not aplicados
    assert any("mudou" in r.lower() or "nao foi aplicada" in r.lower()
               for r in registros)


def test_lote_invalido_nao_aplica(nia):
    obj, aplicados, registros = nia
    obj._provedor_assistido = lambda pedido, ctx: (
        '{"operacoes":[{"tipo":"conectar","origem":"div",'
        '"destino":"inexistente"}]}')
    obj._executar_frase_habilidade(
        "Monte um ramo de validação para Divulgação.", "texto")
    assert not aplicados


def test_destino_duplicado_pede_escolha(nia, plano):
    obj, aplicados, registros = nia
    vivo = BP.atualizar(plano.id, {"mapa": {
        **plano.mapa,
        "cards": [*plano.mapa["cards"],
                  {**next(c for c in plano.mapa["cards"] if c["id"] == "pub"),
                   "id": "pub2", "titulo": "Público-alvo"}],
    }}, plano.revisao)
    obj.ui.contexto_canvas = lambda: {"plano_id": vivo.id, "card_id": "div",
                                      "plano": vivo, "modo_assistido": True}
    obj._executar_frase_habilidade("Conecte este card a Público-alvo.", "texto")
    assert not aplicados
    assert any("varios" in r.lower() or "destinos" in r.lower()
               for r in registros)
