# -*- coding: utf-8 -*-
"""RED: contratos tipados e avaliacao de capacidade (F01)."""
from __future__ import annotations

import time

import pytest

from core.aprendizado_adaptativo import avaliador as AV
from core.aprendizado_adaptativo import contratos as CT


def test_evento_tipado_carrega_correlacao_e_geracao():
    ev = CT.EventoAprendizado(
        tipo='avaliacao', sessao_id='s1', ator='voz', correlation_id='c1',
        timestamp=1000.0, schema_version=1, cancel_generation=3)
    assert ev.sessao_id == 's1' and ev.ator == 'voz'
    assert ev.correlation_id == 'c1' and ev.schema_version == 1
    assert ev.cancel_generation == 3


def test_contexto_de_cancelamento_invalida_callback_tardio():
    ctx = CT.ContextoCancelamento()
    assert ctx.geracao == 0
    ctx.cancelar()
    assert ctx.cancelado is True
    with pytest.raises(CT.Cancelado):
        ctx.verificar()
    assert ctx.geracao == 1


def test_capacidade_conhecida_com_evidencia_valida():
    a = AV.AvaliadorCapacidade(
        resolver=lambda texto: 'pesquisa.local' if 'pesquisa' in texto else None,
        evidencias={'pesquisa.local': {'confirmado_em': time.time()}},
    )
    r = a.avaliar('faça uma pesquisa local')
    assert r.estado is CT.EstadoAvaliacao.CONHECIDO
    assert r.pode_executar() is True


def test_capacidade_desconhecida_nao_e_conhecido_por_confianca():
    a = AV.AvaliadorCapacidade(resolver=lambda texto: None)
    r = a.avaliar('faça algo nunca visto', confianca=0.99)
    assert r.estado is CT.EstadoAvaliacao.DESCONHECIDO
    assert r.pode_executar() is False


def test_permissao_negada_bloqueia_mesmo_com_conhecimento():
    a = AV.AvaliadorCapacidade(
        resolver=lambda texto: 'controle.fisico',
        evidencias={'controle.fisico': {'confirmado_em': time.time()}},
        permitido=lambda capacidade: False,
    )
    r = a.avaliar('mexa no computador')
    assert r.estado is CT.EstadoAvaliacao.BLOQUEADO
    assert r.pode_executar() is False


def test_evidencia_antiga_fica_desatualizada():
    a = AV.AvaliadorCapacidade(
        resolver=lambda texto: 'planos.criar',
        evidencias={'planos.criar': {'confirmado_em': 1.0}},
        relogio=lambda: time.time(),
        max_idade_s=60.0,
    )
    r = a.avaliar('crie um plano')
    assert r.estado is CT.EstadoAvaliacao.DESATUALIZADO


def test_partes_conhecidas_seguem_e_lacuna_e_preservada():
    a = AV.AvaliadorCapacidade(
        resolver=lambda texto: 'agenda.criar' if 'agenda' in texto else None,
        evidencias={'agenda.criar': {'confirmado_em': time.time()}},
    )
    r = a.avaliar('adicione na agenda e configure o novo fluxo')
    assert r.estado is CT.EstadoAvaliacao.PARCIAL
    assert r.partes_seguras == ('agenda.criar',)
    assert any(e.estado is CT.EstadoAvaliacao.DESCONHECIDO for e in r.etapas)


def test_cancelamento_durante_avaliacao_descarta_resultado():
    ctx = CT.ContextoCancelamento()
    a = AV.AvaliadorCapacidade(
        resolver=lambda texto: 'agenda.criar' if 'agenda' in texto else None,
        evidencias={'agenda.criar': {'confirmado_em': time.time()}},
        cancelamento=ctx,
    )
    ctx.cancelar()
    with pytest.raises(CT.Cancelado):
        a.avaliar('adicione na agenda')
