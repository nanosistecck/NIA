# -*- coding: utf-8 -*-
"""Pesquisa autônoma: lacuna → fontes → procedimento declarativo (F03).

Conteúdo externo é dado não confiável: nunca é executado. Nenhuma rede é
aberta por este módulo; a busca é injetada pelo adaptador de serviços reais.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from core.aprendizado_adaptativo import contratos as CT

_CODIGO = re.compile(
    r'(?i)\b(import|exec|eval|os\.system|subprocess|powershell|curl\s*\||'
    r'python\s+-c|<script|rm\s+-rf|format\s+c:)\b')


@dataclass(frozen=True)
class ResultadoPesquisa:
    sucesso: bool
    fontes: tuple[dict, ...]
    procedimento: dict | None
    pedir_ensino: bool
    tentativas: int
    eventos: tuple[CT.EventoAprendizado, ...]


class PesquisadorAutonomo:
    def __init__(self, *, buscar: Callable[[str], list] | None = None,
                 max_tentativas: int = 3, orcamento_tokens: int = 2000,
                 cancelamento: CT.ContextoCancelamento | None = None,
                 sessao_id: str = '', ator: str = 'nia'):
        self.buscar = buscar or (lambda texto: [])
        self.max_tentativas = max(1, int(max_tentativas))
        self.orcamento_tokens = max(1, int(orcamento_tokens))
        self.cancelamento = cancelamento or CT.ContextoCancelamento()
        self.sessao_id = sessao_id or CT.novo_id()
        self.ator = ator

    def pesquisar(self, lacuna: str, contexto: str = '', *,
                  correlation_id: str = '') -> ResultadoPesquisa:
        self.cancelamento.verificar()
        correlation_id = correlation_id or CT.novo_id()
        eventos: list[CT.EventoAprendizado] = []

        def emitir(tipo: str, detalhes: str) -> None:
            eventos.append(CT.EventoAprendizado(
                tipo=tipo, sessao_id=self.sessao_id, ator=self.ator,
                correlation_id=correlation_id, timestamp=CT.agora(),
                schema_version=CT.SCHEMA_VERSION,
                cancel_generation=self.cancelamento.geracao,
                detalhes=str(detalhes)[:160]))

        emitir('lacuna_detectada', lacuna)
        fontes: list[dict] = []
        tokens = 0
        tentativas = 0
        consulta = f'{lacuna} {contexto}'.strip()

        for _ in range(self.max_tentativas):
            self.cancelamento.verificar()
            tentativas += 1
            brutos = self.buscar(consulta) or []
            for bruto in brutos:
                if not isinstance(bruto, dict):
                    continue
                fonte = dict(bruto)
                fonte.setdefault('url', '')
                fonte.setdefault('titulo', '')
                fonte.setdefault('trecho', '')
                fonte.setdefault('consultado_em', CT.agora())
                fontes.append(fonte)
                tokens += len(str(fonte.get('trecho', ''))) // 4 + 8
                emitir('fonte_registrada', str(fonte.get('url', ''))[:120])
            if tokens > self.orcamento_tokens:
                emitir('orcamento_excedido', f'{tokens}/{self.orcamento_tokens}')
                break
            if fontes:
                break

        self.cancelamento.verificar()
        etapas = self._converter(fontes)
        if not fontes or not etapas:
            emitir('pedir_ensino', 'sem solução confiável')
            return ResultadoPesquisa(False, tuple(fontes), None, True,
                                     tentativas, tuple(eventos))

        procedimento = {
            'objetivo': str(lacuna),
            'etapas': etapas,
            'ferramentas': (),
            'origem': 'pesquisa',
            'fontes': tuple(fontes),
            'estado': CT.EstadoProcedimento.DESCOBERTO.value,
        }
        emitir('pesquisa_concluida', f'{len(etapas)} etapas')
        return ResultadoPesquisa(True, tuple(fontes), procedimento, False,
                                 tentativas, tuple(eventos))

    @staticmethod
    def _converter(fontes: list[dict]) -> tuple[dict, ...]:
        """Transforma trechos em ações declarativas, nunca em código."""
        etapas: list[dict] = []
        for fonte in fontes:
            trecho = str(fonte.get('trecho', '')).strip()
            if not trecho or _CODIGO.search(trecho):
                continue
            partes = [p.strip(' .;:') for p in re.split(r'[\n;]|\s+e\s+', trecho)]
            for parte in partes:
                if not parte or len(parte) < 4 or _CODIGO.search(parte):
                    continue
                etapas.append({
                    'alvo': str(fonte.get('titulo', ''))[:80],
                    'acao': parte[:180],
                    'evidencia': str(fonte.get('url', ''))[:200],
                })
            if len(etapas) >= 12:
                break
        return tuple(etapas)
