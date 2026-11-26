# -*- coding: utf-8 -*-
"""Contratos do Motor de Aprendizado Adaptativo (F01).

Eventos tipados, geração de cancelamento e estados compartilhados por todas as
fases. Nenhuma função executa ação de desktop neste módulo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import threading
import time
import uuid

SCHEMA_VERSION = 1


class Cancelado(RuntimeError):
    """A gação foi cancelada; callbacks tardios devem ser descartados."""


class EstadoAvaliacao(str, Enum):
    CONHECIDO = 'CONHECIDO'
    PARCIAL = 'PARCIAL'
    DESCONHECIDO = 'DESCONHECIDO'
    DESATUALIZADO = 'DESATUALIZADO'
    INDISPONIVEL = 'INDISPONIVEL'
    AMBIGUO = 'AMBIGUO'
    BLOQUEADO = 'BLOQUEADO'
    NAO_CONFIRMADO = 'NAO_CONFIRMADO'


class EstadoProcedimento(str, Enum):
    DESCOBERTO = 'DESCOBERTO'
    INTERPRETADO = 'INTERPRETADO'
    TESTADO = 'TESTADO'
    VALIDADO = 'VALIDADO'
    CONSOLIDADO = 'CONSOLIDADO'
    EM_REVISAO = 'EM_REVISAO'
    OBSOLETO = 'OBSOLETO'


@dataclass(frozen=True)
class EventoAprendizado:
    tipo: str
    sessao_id: str
    ator: str
    correlation_id: str
    timestamp: float
    schema_version: int
    cancel_generation: int
    detalhes: str = ''


@dataclass(frozen=True)
class EtapaAvaliada:
    descricao: str
    capacidade: str
    estado: EstadoAvaliacao
    evidencia: dict = field(default_factory=dict)
    motivo: str = ''


@dataclass(frozen=True)
class Avaliacao:
    intencao: str
    estado: EstadoAvaliacao
    etapas: tuple[EtapaAvaliada, ...]
    eventos: tuple[EventoAprendizado, ...]
    sessao_id: str = ''
    correlation_id: str = ''

    @property
    def partes_seguras(self) -> tuple[str, ...]:
        return tuple(e.capacidade for e in self.etapas
                     if e.estado is EstadoAvaliacao.CONHECIDO and e.capacidade)

    def pode_executar(self) -> bool:
        return self.estado in (EstadoAvaliacao.CONHECIDO,
                               EstadoAvaliacao.PARCIAL)


class ContextoCancelamento:
    """Geração monotonicamente crescente; callbacks antigos são descartados."""

    def __init__(self) -> None:
        self._trava = threading.RLock()
        self._geracao = 0
        self._cancelado = False

    @property
    def geracao(self) -> int:
        with self._trava:
            return self._geracao

    @property
    def cancelado(self) -> bool:
        with self._trava:
            return self._cancelado

    def cancelar(self) -> None:
        with self._trava:
            self._cancelado = True
            self._geracao += 1

    def verificar(self, geracao: int | None = None) -> None:
        with self._trava:
            if self._cancelado or (geracao is not None
                                   and geracao != self._geracao):
                raise Cancelado('operação cancelada')

    def nova_operacao(self) -> int:
        """Inicia uma operação e devolve a geração a conferir depois."""
        with self._trava:
            if self._cancelado:
                raise Cancelado('contexto já cancelado')
            self._geracao += 1
            return self._geracao


def novo_id() -> str:
    return uuid.uuid4().hex[:12]


def agora() -> float:
    return time.time()
