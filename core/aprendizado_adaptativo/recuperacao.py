# -*- coding: utf-8 -*-
"""Recuperação segura: estados salvos voltam pausados, nunca ativos (F14)."""
from __future__ import annotations

_ATIVOS = frozenset(('CONTROLE_ATIVO', 'OBSERVANDO', 'EXECUTANDO'))


def salvar_estado(memoria, tarefa_id: str, estado: dict) -> None:
    memoria.salvar_checkpoint(str(tarefa_id), dict(estado or {}))


def restaurar_estado(memoria, tarefa_id: str) -> dict:
    dados = memoria.obter_checkpoint(str(tarefa_id))
    if dados is None:
        return {'estado': 'SEM_ESTADO', 'reativado': False, 'payload': {}}
    payload = dict(dados.get('payload') or {})
    estado = str(payload.get('estado', ''))
    if estado in _ATIVOS:
        payload['estado'] = 'PAUSADO'
        return {'estado': 'PAUSADO', 'reativado': False, 'payload': payload}
    return {'estado': estado or 'PAUSADO', 'reativado': False,
            'payload': payload}


def listar_pendentes(memoria) -> tuple[dict, ...]:
    """Checkpoints que exigem decisão humana antes de qualquer ação."""
    pendentes = []
    for cp in memoria.listar('checkpoints', limite=200):
        payload = cp.get('payload') or {}
        if str(payload.get('estado', '')) in _ATIVOS:
            pendentes.append(cp)
    return tuple(pendentes)
