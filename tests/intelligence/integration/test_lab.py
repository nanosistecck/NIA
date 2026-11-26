# -*- coding: utf-8 -*-
"""Integração do laboratório com a suíte pytest da NIA."""
from __future__ import annotations

import pytest

from tests.intelligence.datasets.scenarios import CENARIOS, selecionar
from tests.intelligence.runners.engine import executar


@pytest.mark.parametrize('cenario', selecionar('quick'), ids=lambda c: c.id)
def test_cenario_quick(cenario):
    avaliacao = executar(cenario)
    assert avaliacao.ok, (avaliacao.details, avaliacao.observed)


@pytest.mark.parametrize('cenario', tuple(
    c for c in CENARIOS if c.category in ('learning', 'automation') and not c.blocked),
    ids=lambda c: c.id)
def test_cenario_aprendizado_e_automacao(cenario):
    avaliacao = executar(cenario)
    assert avaliacao.ok, (avaliacao.details, avaliacao.observed)


def test_todos_os_cenarios_tem_contrato():
    assert CENARIOS
    assert len({c.id for c in CENARIOS}) == len(CENARIOS)
    for c in CENARIOS:
        assert c.id and c.category and c.kind and c.message
