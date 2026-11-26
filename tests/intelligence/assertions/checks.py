# -*- coding: utf-8 -*-
"""Asserções legíveis para evidências do laboratório."""
from __future__ import annotations

from tests.intelligence.contracts import Evaluation


def exigir_aprovado(avaliacao: Evaluation) -> None:
    if not avaliacao.ok:
        raise AssertionError(
            f'{avaliacao.scenario_id}: {avaliacao.details or "comportamento divergente"} '
            f'(observado={avaliacao.observed})')


def exigir_sem_acoes_proibidas(avaliacao: Evaluation, proibidas) -> None:
    indevidas = set(avaliacao.observed) & set(proibidas or ())
    if indevidas:
        raise AssertionError(f'acoes indevidas: {sorted(indevidas)}')
