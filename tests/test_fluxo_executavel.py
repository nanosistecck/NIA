# -*- coding: utf-8 -*-
"""Fase 11 — workflow persistente com DAG, orçamento, tentativas e aprovação."""
from __future__ import annotations

import json

import pytest

from core import fluxo_executavel as FX


def _plano(tmp_path, **kw):
    return FX.PlanoExecutavel(caminho=tmp_path / 'plano.json', **kw)


def _etapa(id, dependencias=(), **kw):
    return FX.Etapa(id=id, tipo='ferramenta', ferramenta='hora_agora',
                    argumentos={}, dependencias=dependencias, **kw)


def test_ciclo_no_dag_e_recusado(tmp_path):
    """Quebra: dependências circulares eram aceitas."""
    plano = _plano(tmp_path)
    plano.adicionar(_etapa('a', dependencias=('b',)))
    with pytest.raises(ValueError, match='ciclo'):
        plano.adicionar(_etapa('b', dependencias=('a',)))


def test_dependencia_pendente_bloqueia_execucao(tmp_path):
    """Quebra: etapa podia rodar antes da dependência."""
    plano = _plano(tmp_path)
    plano.adicionar(_etapa('a'))
    plano.adicionar(_etapa('b', dependencias=('a',)))
    chamadas = []
    with pytest.raises(ValueError, match='depend'):
        plano.executar('b', lambda f, a: chamadas.append(f))
    assert chamadas == []


def test_execucao_persiste_estado_e_permite_retomada(tmp_path):
    """Quebra: plano executável não sobrevivia a uma nova instância."""
    caminho = tmp_path / 'plano.json'
    plano = FX.PlanoExecutavel(caminho=caminho)
    plano.adicionar(_etapa('a'))
    resultado = plano.executar('a', lambda f, a: 'ok')
    assert resultado.ok is True
    assert json.loads(caminho.read_text(encoding='utf-8'))['etapas']['a']['estado'] == 'concluida'
    assert FX.PlanoExecutavel(caminho=caminho).estado('a') == 'concluida'


def test_etapa_concluida_nao_executa_de_novo(tmp_path):
    """Quebra: retomada repetia efeito já aplicado."""
    plano = _plano(tmp_path)
    plano.adicionar(_etapa('a'))
    chamadas = []
    executor = lambda f, a: chamadas.append(f) or 'ok'
    plano.executar('a', executor)
    segundo = plano.executar('a', executor)
    assert segundo.pulada is True
    assert chamadas == ['hora_agora']


def test_orcamento_limita_acoes(tmp_path):
    """Quebra: plano podia executar além do orçamento."""
    plano = _plano(tmp_path, orcamento=1)
    plano.adicionar(_etapa('a'))
    plano.adicionar(_etapa('b'))
    plano.executar('a', lambda f, a: 'ok')
    resultado = plano.executar('b', lambda f, a: 'ok')
    assert resultado.ok is False
    assert 'orcamento' in resultado.motivo


def test_cancelamento_impede_execucao(tmp_path):
    """Quebra: cancelar não mudava o estado da etapa."""
    plano = _plano(tmp_path)
    plano.adicionar(_etapa('a'))
    assert plano.cancelar('a') is True
    chamadas = []
    resultado = plano.executar('a', lambda f, a: chamadas.append(f))
    assert resultado.ok is False
    assert chamadas == []


def test_etapa_com_aprovacao_exige_decisao_explicita(tmp_path):
    """Quebra: ação sensível podia rodar sem aprovação."""
    plano = _plano(tmp_path)
    plano.adicionar(_etapa('a', exige_aprovacao=True))
    chamadas = []
    resultado = plano.executar('a', lambda f, a: chamadas.append(f), aprovador=lambda e: False)
    assert resultado.ok is False
    assert 'aprovacao' in resultado.motivo
    assert chamadas == []
