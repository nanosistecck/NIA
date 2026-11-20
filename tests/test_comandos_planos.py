# -*- coding: utf-8 -*-
"""Comandos de planejamento porchat/voz: intenção, sessão e dedup."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.comandos_planos import SessaoComandosPlanos, normalizar, reconhecer
from core.planos import arquivar, atualizar, criar, inicializar_mapa, listar


@pytest.fixture
def sessao(tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    return SessaoComandosPlanos()


@pytest.mark.parametrize("frase,tipo", [
    ("Vamos planejar um produto para pequenos lojistas.", "CRIAR"),
    ("Quero criar um projeto.", "CRIAR"),
    ("Quero continuar meus estudos.", "RETOMAR"),
    ("Continua meu estudo de fotografia.", "RETOMAR"),
    ("Abre o projeto do aplicativo de estoque.", "ABRIR"),
    ("Qual era meu objetivo no plano de fotografia?", "OBJETIVO"),
    ("O que falta nesse projeto?", "PROGRESSO"),
    ("Qual é o título desse card?", "CARD_TITULO"),
    ("Me explica como planejar um produto.", "EXPLICAR"),
    ("Ainda não quero começar o projeto.", "NEGAR"),
])
def test_reconhecer_frases_do_prompt(frase, tipo):
    assert reconhecer(frase, {}).tipo == tipo


def test_normalizar_tira_acento_e_caixa():
    assert normalizar("Fotografia ÉÉÁ") == "fotografia eea"


def test_criacao_completa_por_texto_e_voz(sessao):
    frase = "Vamos planejar um produto para pequenos lojistas."
    r1 = sessao.processar(frase, "texto")
    assert r1.tratado and r1.acoes and r1.acoes[0]["tipo"] == "abrir_canvas"
    planos, _ = listar()
    assert len(planos) == 1
    assert planos[0].tipo == "Produto"
    assert "pequenos lojistas" in planos[0].titulo
    assert planos[0].objetivo == frase

    sessao2 = SessaoComandosPlanos()
    r2 = sessao2.processar(frase, "voz")
    assert r2.tratado and len(listar()[0]) == 2


def test_criacao_incompleta_e_cancelamento(sessao):
    r = sessao.processar("Quero criar um projeto.", "texto")
    assert r.pendente and "qual" in r.resposta.lower()
    assert listar()[0] == []
    r2 = sessao.processar("cancelar", "texto")
    assert r2.tratado and not r2.pendente and listar()[0] == []


def test_escolha_por_ordinal_usa_id_da_lista(sessao):
    a = criar("Estudo de fotografia", "Luz", "Estudos")
    b = criar("Estudo de fotografia avançada", "Cor", "Estudos")
    r = sessao.processar("Continua meu estudo de fotografia.", "texto")
    assert r.opcoes and len(r.opcoes) == 2
    esperado = r.opcoes[1]["plano_id"]
    r2 = sessao.processar("o segundo", "texto")
    assert r2.acoes and r2.acoes[0]["plano_id"] == esperado


def test_plano_arquivado_ofere_visualizar_ou_restaurar(sessao):
    p = criar("Aplicativo de estoque", "Controlar estoque", "Projeto")
    arquivar(p.id, p.revisao)
    r = sessao.processar("Abre o projeto do aplicativo de estoque.", "texto")
    assert "arquivado" in r.resposta.lower()
    assert any(o.get("acao") == "restaurar" for o in r.opcoes)


def test_nenhum_resultado_nao_cria_plano(sessao):
    r = sessao.processar("Abre o projeto inexistente.", "texto")
    assert "não encontrei" in r.resposta.lower()
    assert listar()[0] == []


def test_reentrega_de_transcricao_nao_cria_dois(sessao):
    frase = "Vamos planejar um produto para pequenos lojistas."
    r1 = sessao.processar(frase, "voz")
    r2 = sessao.processar(frase, "voz")
    assert r1.tratado and r2.tratado and r2.resposta == ""
    assert len(listar()[0]) == 1


def test_consultas_contextuais(sessao):
    sessao.processar("Vamos planejar um produto para pequenos lojistas.", "texto")
    plano = inicializar_mapa(listar()[0][0].id)
    card = plano.mapa["cards"][0]
    contexto = {"plano_id": plano.id, "card_id": card["id"], "plano": plano}
    r1 = sessao.processar("Qual é o título desse card?", "texto", contexto)
    assert card["titulo"] in r1.resposta
    plano2 = atualizar(plano.id, {"mapa": {**plano.mapa, "cards": [
        {**card, "tipo": "tarefa", "status": "bloqueado"}]}}, plano.revisao)
    r2 = sessao.processar("O que falta nesse projeto?", "texto",
                          {**contexto, "plano": plano2})
    assert "bloquead" in r2.resposta.lower()


def test_negacao_e_explicativo(sessao):
    r1 = sessao.processar("Ainda não quero começar o projeto.", "texto")
    assert r1.tratado and r1.acoes == []
    r2 = sessao.processar("Me explica como planejar um produto.", "texto")
    assert not r2.tratado
