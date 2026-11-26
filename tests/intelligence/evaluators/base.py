# -*- coding: utf-8 -*-
"""Avaliadores independentes por dimensão comportamental."""
from __future__ import annotations

from tests.intelligence.contracts import Evaluation

ALIASES = {
    'consultar': ('listar', 'proximo', 'agenda_consultar'),
    'agenda_consultar': ('listar', 'proximo', 'agenda_consultar'),
    'criar': ('criar', 'agenda_criar', 'plano_criar'),
    'editar': ('editar', 'agenda_editar', 'mover'),
    'excluir': ('excluir', 'agenda_excluir', 'plano_excluir'),
    'concluir': ('concluir', 'agenda_concluir'),
    'tarefa_cancelar': ('tarefa_cancelar', 'cancelar'),
    'plano_abrir': ('plano_abrir',),
    'plano_criar': ('plano_criar',),
    'plano_arquivar': ('plano_arquivar',),
}


def _esperado(cenario):
    return ALIASES.get(cenario.expected, (cenario.expected,))


def avaliar(cenario, observado, respostas=(), argumentos=(), detalhes=''):
    observado = tuple(observado)
    permitidas = set(cenario.allowed)
    proibidas = set(cenario.forbidden)
    indevidas = [n for n in observado if proibidas and n in proibidas]
    alvo = [n for n in observado if any(e in n for e in _esperado(cenario))]

    if cenario.kind == 'phrase' and not cenario.expected:
        ok = not observado
    elif cenario.kind == 'tool' and not cenario.expected:
        ok = not observado
    else:
        ok = bool(alvo)

    if proibidas and indevidas:
        ok = False
    if cenario.allowed and any(n not in permitidas for n in observado):
        ok = False

    return Evaluation(
        scenario_id=cenario.id, ok=ok,
        intent_ok=bool(alvo) or (not cenario.expected and not observado),
        tool_ok=bool(alvo),
        params_ok=True,
        effect_ok=bool(alvo) or not cenario.expected,
        response_ok=bool(respostas) or not cenario.expected,
        security_ok=not indevidas,
        observed=observado,
        details='; '.join(filter(None, (detalhes,
            ('indevidas: ' + ','.join(indevidas)) if indevidas else ''))),
    )
