# -*- coding: utf-8 -*-
"""Fala completa: explicações e raciocínio não podem ser cortados."""
import inspect

import pytest

from core import llm_client, personas
from core.cerebro_openrouter import CerebroOpenRouter


RESPOSTA_LONGA = " ".join(
    f"Frase número {i} com palavras suficientes para explicar o raciocínio."
    for i in range(12))


def cerebro(monkeypatch):
    obj = CerebroOpenRouter()
    monkeypatch.setattr(obj, "_ja_disse_assim", lambda saida: None)
    return obj


def test_explicacao_nao_e_cortada(monkeypatch):
    obj = cerebro(monkeypatch)
    saida = obj._fechar_resposta(
        "explique o raciocínio e me dê os detalhes", RESPOSTA_LONGA)
    assert len(saida.split()) == len(RESPOSTA_LONGA.split())


@pytest.mark.parametrize('pergunta', [
    'como funciona?',
    'me dê uma dica',
    'quais são as etapas?',
    'por que isso acontece?',
    'conte com detalhes',
])
def test_pedidos_que_pedem_conteudo_nao_sao_cortados(monkeypatch, pergunta):
    obj = cerebro(monkeypatch)
    saida = obj._fechar_resposta(pergunta, RESPOSTA_LONGA)
    assert len(saida.split()) == len(RESPOSTA_LONGA.split())


def test_conversa_trivial_continua_curta(monkeypatch):
    obj = cerebro(monkeypatch)
    saida = obj._fechar_resposta("oi", RESPOSTA_LONGA)
    assert 0 < len(saida.split()) < len(RESPOSTA_LONGA.split())


def test_limite_padrao_de_tokens_permite_resposta_longa():
    padrao = inspect.signature(llm_client.call_llm).parameters["max_tokens"].default
    assert padrao >= 512, padrao


def test_prompt_de_personas_nao_impoe_doze_palavras():
    texto = personas.REGRAS_FIXAS
    assert "CONVERSA E CURTA: doze palavras" not in texto
    assert "SEJA CURTO. Este e o limite mais importante" not in texto


def test_prompt_de_personas_pede_tamanho_adequado():
    texto = personas.REGRAS_FIXAS
    normalizado = " ".join(texto.lower().split())
    assert "tamanho" in normalizado
    assert ("até o fim" in normalizado or "ate o fim" in normalizado
            or "sem limite" in normalizado)
