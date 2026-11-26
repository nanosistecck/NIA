# -*- coding: utf-8 -*-
"""Consolidação de memória (Fase 09).

Opera sobre registros explícitos, sem inferência contínua e sem transformar
conteúdo externo em instrução. Preferências e compromissos são preservados;
contradições são apenas apontadas, nunca resolvidas automaticamente.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from core import registro_aplicativos as RA

PROTEGIDOS = frozenset(('preferencia', 'compromisso'))


@dataclass(frozen=True)
class ItemMemoria:
    id: str
    texto: str
    tipo: str
    criado_em: str
    fonte: str
    referencias: tuple = ()


def _chave(texto: str) -> str:
    return RA.normalizar(texto).casefold()


def _assunto(texto: str) -> str:
    return _chave(texto.split(':', 1)[0])


def _instante(item: ItemMemoria):
    try:
        return datetime.fromisoformat(item.criado_em).timestamp()
    except (TypeError, ValueError):
        return 0.0


def deduplicar(itens) -> tuple:
    melhores: dict[str, ItemMemoria] = {}
    for item in itens:
        chave = _chave(item.texto)
        atual = melhores.get(chave)
        if atual is None or _instante(item) > _instante(atual):
            melhores[chave] = item
    escolhidos = {id(item) for item in melhores.values()}
    mantidos = tuple(item for item in itens if id(item) in escolhidos)
    removidos = tuple(item.id for item in itens if id(item) not in escolhidos)
    return mantidos, removidos


def retencao(itens, dias: int = 90, agora=None) -> tuple:
    referencia = agora or datetime.now(timezone.utc)
    limite = float(dias) * 86400.0
    mantidos = []
    for item in itens:
        if item.tipo in PROTEGIDOS:
            mantidos.append(item)
            continue
        idade = referencia.timestamp() - _instante(item)
        if idade <= limite:
            mantidos.append(item)
    return tuple(mantidos)


def contradicoes(itens) -> tuple:
    encontradas = []
    lista = tuple(itens)
    for pos, primeiro in enumerate(lista):
        for segundo in lista[pos + 1:]:
            if _assunto(primeiro.texto) != _assunto(segundo.texto):
                continue
            primeiro_negativo = 'nao' in _chave(primeiro.texto).split()
            segundo_negativo = 'nao' in _chave(segundo.texto).split()
            if primeiro_negativo != segundo_negativo:
                encontradas.append((primeiro.id, segundo.id))
    return tuple(encontradas)


def construir_indice(itens) -> dict:
    return {_chave(item.texto): item.id for item in itens}


def excluir(itens, indice, identificador: str) -> tuple:
    novos = tuple(item for item in itens if item.id != identificador)
    return novos, construir_indice(novos)


def resumo(itens, limite: int = 2000) -> str:
    partes = [f'{item.texto} [ref:{item.id}]' for item in itens]
    return '; '.join(partes)[:max(0, int(limite))]
