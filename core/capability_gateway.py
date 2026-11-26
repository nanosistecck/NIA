# -*- coding: utf-8 -*-
"""Capability Gateway — normalização das chamadas de chat, voz, Canvas e remoto.

Este módulo **não** é um segundo motor: apenas valida e correlaciona a chamada
antes de entregá-la ao executor único registrado em ``main.py``. A política de
permissões e o contexto de ação tipada são reaproveitados de módulos existentes.
Nenhuma instância é ligada automaticamente ao produto; a integração permanece
desligada até homologação (feature flag implícita por não registro).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import threading

from core import contexto_ferramentas as CF
from core import permissoes_ferramentas as PF

ORIGENS = frozenset(('chat', 'voz', 'canvas', 'remoto'))


class Cancelamento(Exception):
    """A chamada foi cancelada antes de chegar ao executor."""


@dataclass(frozen=True)
class Solicitacao:
    ferramenta: str
    argumentos: dict = field(default_factory=dict)
    origem: str = 'chat'
    perfil: str = ''
    timeout: float = 30.0
    cancelamento: threading.Event | None = None


@dataclass(frozen=True)
class ResultadoGateway:
    ok: bool
    mensagem: str
    origem: str
    ferramenta: str
    sequencia: int


def _normalizar_resultado(bruto) -> tuple[bool, str]:
    if isinstance(bruto, dict) and 'result' in bruto:
        bruto = bruto['result']
    if isinstance(bruto, tuple) or isinstance(bruto, list):
        if len(bruto) == 2 and type(bruto[0]) is bool:
            return bruto[0], str(bruto[1] or '')
        return False, 'Resultado do executor inválido.'
    if isinstance(bruto, str):
        return True, bruto
    if type(bruto) is bool:
        return bruto, ''
    return False, 'Resultado do executor inválido.'


class CapabilityGateway:
    def __init__(self, declaracoes=(), contexto=None):
        self._declaracoes = tuple(declaracoes or ())
        self._contexto = contexto or CF.ContextoFerramentas()
        self._trava = threading.RLock()
        self._em_voo: set[tuple] = set()
        self._sequencia = 0

    def validar(self, solicitacao: Solicitacao) -> tuple[str, ...]:
        if not isinstance(solicitacao, Solicitacao):
            raise TypeError('Solicitação inválida.')
        if solicitacao.origem not in ORIGENS:
            raise PermissionError('Origem não autorizada para capacidades.')
        if not isinstance(solicitacao.ferramenta, str) or not solicitacao.ferramenta.strip():
            raise ValueError('Ferramenta inválida.')
        if not isinstance(solicitacao.argumentos, dict):
            raise ValueError('Argumentos devem ser um objeto.')
        if (isinstance(solicitacao.timeout, bool)
                or not isinstance(solicitacao.timeout, (int, float))
                or solicitacao.timeout <= 0):
            raise ValueError('Timeout inválido.')
        return PF.validar_chamada(
            solicitacao.ferramenta, solicitacao.argumentos, self._declaracoes)

    def executar(self, solicitacao: Solicitacao, executador) -> ResultadoGateway:
        self.validar(solicitacao)
        if solicitacao.cancelamento is not None and solicitacao.cancelamento.is_set():
            raise Cancelamento('Chamada cancelada antes da execução.')
        try:
            assinatura = json.dumps(solicitacao.argumentos, sort_keys=True,
                                    ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError, RecursionError):
            raise ValueError('Argumentos devem ser JSON finito.') from None
        chave = (solicitacao.ferramenta, assinatura, solicitacao.origem,
                 solicitacao.perfil)
        with self._trava:
            if chave in self._em_voo:
                raise RuntimeError('Chamada duplicada em voo: ' + solicitacao.ferramenta)
            self._em_voo.add(chave)
            self._sequencia += 1
            sequencia = self._sequencia
        try:
            self._contexto.iniciar(solicitacao.ferramenta, dict(solicitacao.argumentos))
            bruto = executador(solicitacao.ferramenta, dict(solicitacao.argumentos))
            ok, mensagem = _normalizar_resultado(bruto)
            self._contexto.concluir(ok, mensagem)
            return ResultadoGateway(ok, mensagem, solicitacao.origem,
                                    solicitacao.ferramenta, sequencia)
        finally:
            with self._trava:
                self._em_voo.discard(chave)

    def resumo(self) -> tuple:
        """Não devolve catálogo ao modelo — apenas o resultado da chamada atual."""
        return ()
