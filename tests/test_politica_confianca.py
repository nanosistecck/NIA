# -*- coding: utf-8 -*-
"""Fase 16 — política de confiança consolidada, com testes negativos."""
from __future__ import annotations

import pytest

from core import politica_confianca as PC

DECLARACOES = [{
    'name': 'hora_agora',
    'description': 'Hora local',
    'parameters': {'type': 'OBJECT', 'properties': {}},
}]


def test_origem_desconhecida_e_negada():
    """Quebra: origem fora das quatro conhecidas era aceita."""
    politica = PC.PoliticaConfianca(declaracoes=DECLARACOES)
    decisao = politica.avaliar('email', 'hora_agora', {})
    assert decisao.permitido is False
    assert 'origem' in decisao.motivo.lower()


def test_ferramenta_sem_politica_e_negada():
    """Quebra: ferramenta fora da tabela podia executar por fallback."""
    politica = PC.PoliticaConfianca(declaracoes=DECLARACOES)
    decisao = politica.avaliar('chat', 'shell_inventado', {})
    assert decisao.permitido is False


def test_segredo_em_argumentos_e_negado_e_redigido():
    """Quebra: token em argumento seguia para o executor e para o log."""
    politica = PC.PoliticaConfianca(declaracoes=DECLARACOES)
    texto = 'api_key=sk-abcdefghijklmnoBearer token'
    decisao = politica.avaliar('chat', 'hora_agora', {'texto': texto})
    assert decisao.permitido is False
    redigido = politica.redigir(texto)
    assert 'sk-abcdef' not in redigido
    assert 'Bearer' not in redigido


def test_traversal_de_caminho_e_negado():
    """Quebra: caminho com .. passava pela política."""
    politica = PC.PoliticaConfianca(declaracoes=DECLARACOES)
    assert politica.caminho_seguro('../config/api_keys.json') is False
    assert politica.caminho_seguro('relatorio.txt') is True


def test_ipc_local_exige_token_valido():
    """Quebra: canal local aceitava qualquer chamador."""
    politica = PC.PoliticaConfianca(declaracoes=DECLARACOES, token_ipc='token-local-teste')
    assert politica.ipc_autenticado('token-local-teste') is True
    assert politica.ipc_autenticado('errado') is False


def test_limites_de_recurso_sao_aplicados():
    """Quebra: não havia tetos para_argumentos/resultado."""
    politica = PC.PoliticaConfianca(declaracoes=DECLARACOES)
    assert politica.dentro_dos_limites('x' * 10, 'y' * 10) is True
    assert politica.dentro_dos_limites('x' * 100000, '') is False
