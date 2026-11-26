# -*- coding: utf-8 -*-
"""Avaliador de capacidade: intenção → etapas com estado baseado em evidência.

Não usa confiança do LLM como prova e não executa nenhuma ferramenta.
"""
from __future__ import annotations

import re
import time
from typing import Callable

from core.aprendizado_adaptativo import contratos as CT

_SEPARADOR = re.compile(r'\s+(?:e|depois|então|entao)\s+', re.I)


class AvaliadorCapacidade:
    def __init__(self, *, resolver: Callable[[str], object] | None = None,
                 evidencias: dict | None = None,
                 permitido: Callable[[str], bool] | None = None,
                 relogio: Callable[[], float] | None = None,
                 max_idade_s: float = 7 * 24 * 3600.0,
                 cancelamento: CT.ContextoCancelamento | None = None,
                 sessao_id: str = '', ator: str = 'usuario'):
        self.resolver = resolver or (lambda texto: None)
        self.evidencias = dict(evidencias or {})
        self.permitido = permitido or (lambda capacidade: True)
        self.relogio = relogio or time.time
        self.max_idade_s = float(max_idade_s)
        self.cancelamento = cancelamento or CT.ContextoCancelamento()
        self.sessao_id = sessao_id or CT.novo_id()
        self.ator = ator

    @staticmethod
    def decompor(intencao: str) -> tuple[str, ...]:
        partes = [p.strip(' .,!?;:') for p in _SEPARADOR.split(str(intencao or ''))]
        return tuple(p for p in partes if p)

    def avaliar(self, intencao: str, *, confianca: float = 0.0,
                correlation_id: str = '', geracao: int | None = None) -> CT.Avaliacao:
        """Avalia cada etapa. `confianca` é ignorada: não é evidência."""
        self.cancelamento.verificar(geracao)
        correlation_id = correlation_id or CT.novo_id()
        eventos: list[CT.EventoAprendizado] = []
        etapas: list[CT.EtapaAvaliada] = []

        def emitir(tipo: str, detalhes: str) -> None:
            eventos.append(CT.EventoAprendizado(
                tipo=tipo, sessao_id=self.sessao_id, ator=self.ator,
                correlation_id=correlation_id, timestamp=self.relogio(),
                schema_version=CT.SCHEMA_VERSION,
                cancel_generation=self.cancelamento.geracao,
                detalhes=detalhes))

        emitir('avaliacao_iniciada', str(intencao)[:120])
        for descricao in self.decompor(intencao):
            self.cancelamento.verificar(geracao)
            resolvido = self.resolver(descricao)
            if isinstance(resolvido, (list, tuple, set)):
                candidatos = tuple(str(c) for c in resolvido)
                etapas.append(CT.EtapaAvaliada(
                    descricao, '', CT.EstadoAvaliacao.AMBIGUO,
                    motivo='múltiplos candidatos: ' + ', '.join(candidatos[:5])))
                emitir('etapa_ambigua', descricao)
                continue
            capacidade = str(resolvido) if resolvido else ''
            if not capacidade:
                etapas.append(CT.EtapaAvaliada(
                    descricao, '', CT.EstadoAvaliacao.DESCONHECIDO,
                    motivo='nenhuma capacidade registrada para esta etapa'))
                emitir('lacuna_detectada', descricao)
                continue
            if not self.permitido(capacidade):
                etapas.append(CT.EtapaAvaliada(
                    descricao, capacidade, CT.EstadoAvaliacao.BLOQUEADO,
                    motivo='permissão negada'))
                emitir('etapa_bloqueada', descricao)
                continue
            evidencia = dict(self.evidencias.get(capacidade) or {})
            if not evidencia:
                etapas.append(CT.EtapaAvaliada(
                    descricao, capacidade, CT.EstadoAvaliacao.NAO_CONFIRMADO,
                    motivo='sem evidência de validação'))
                emitir('etapa_nao_confirmada', descricao)
                continue
            confirmado = float(evidencia.get('confirmado_em', 0.0))
            if confirmado <= 0 or (self.relogio() - confirmado) > self.max_idade_s:
                etapas.append(CT.EtapaAvaliada(
                    descricao, capacidade, CT.EstadoAvaliacao.DESATUALIZADO,
                    evidencia=evidencia, motivo='evidência antiga ou sem data'))
                emitir('etapa_desatualizada', descricao)
                continue
            etapas.append(CT.EtapaAvaliada(
                descricao, capacidade, CT.EstadoAvaliacao.CONHECIDO,
                evidencia=evidencia, motivo='capacidade, permissão e evidência válidas'))
            emitir('etapa_conhecida', descricao)

        self.cancelamento.verificar(geracao)
        estados = [e.estado for e in etapas]
        if not estados:
            estado = CT.EstadoAvaliacao.DESCONHECIDO
        elif CT.EstadoAvaliacao.BLOQUEADO in estados:
            estado = CT.EstadoAvaliacao.BLOQUEADO
        elif CT.EstadoAvaliacao.AMBIGUO in estados:
            estado = CT.EstadoAvaliacao.AMBIGUO
        elif CT.EstadoAvaliacao.DESATUALIZADO in estados:
            estado = CT.EstadoAvaliacao.DESATUALIZADO
        elif CT.EstadoAvaliacao.NAO_CONFIRMADO in estados:
            estado = CT.EstadoAvaliacao.NAO_CONFIRMADO
        elif CT.EstadoAvaliacao.DESCONHECIDO in estados:
            estado = (CT.EstadoAvaliacao.PARCIAL
                      if CT.EstadoAvaliacao.CONHECIDO in estados
                      else CT.EstadoAvaliacao.DESCONHECIDO)
        else:
            estado = CT.EstadoAvaliacao.CONHECIDO
        emitir('avaliacao_concluida', estado.value)
        return CT.Avaliacao(
            intencao=str(intencao), estado=estado, etapas=tuple(etapas),
            eventos=tuple(eventos), sessao_id=self.sessao_id,
            correlation_id=correlation_id)
