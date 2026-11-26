# -*- coding: utf-8 -*-
"""Política de segurança independente do LLM (F12)."""
from __future__ import annotations

import re
from uuid import uuid4

LEITURA = 'leitura'
PESQUISA = 'pesquisa'
DOCUMENTO_LOCAL = 'documento_local'
CONTROLE_FISICO = 'controle_fisico'
ALTERACAO_EXTERNA = 'alteracao_externa'
ACAO_SENSIVEL = 'acao_sensivel'

_ABERTOS = frozenset((LEITURA, PESQUISA, DOCUMENTO_LOCAL))
_CONFIRMAVEIS = frozenset((CONTROLE_FISICO, ALTERACAO_EXTERNA, ACAO_SENSIVEL))
_SEGREDO = re.compile(
    r'(?i)\b(senha|password|passwd|token|api[_-]?key|secret|cvv|cartao)\b'
    r'\s*[:=]?\s*\S+')


class ConfirmacaoNecessaria(RuntimeError):
    """Ação exige confirmação humana específica."""


class PoliticaAprendizado:
    def __init__(self):
        self._tokens: dict[str, tuple[str, str]] = {}
        self.cancelado = False
        self.lease: str | None = None

    def exigir(self, escopo: str, acao: str, *, origem: str = 'usuario') -> None:
        if escopo in _CONFIRMAVEIS and origem != 'confirmacao':
            raise ConfirmacaoNecessaria(
                f'{escopo}/{acao} exige confirmação explícita')

    def confirmar(self, escopo: str, acao: str) -> str:
        token = uuid4().hex
        self._tokens[token] = (str(escopo), str(acao))
        self.lease = token
        return token

    def revogar(self, token: str) -> bool:
        return self._tokens.pop(str(token), None) is not None

    def permite(self, escopo: str, acao: str, *, origem: str = 'usuario',
                token: str | None = None) -> bool:
        if self.cancelado:
            return False
        if origem == 'llm':
            return escopo in (LEITURA, PESQUISA)
        if escopo in _ABERTOS:
            return True
        if escopo not in _CONFIRMAVEIS:
            return False
        if token is None:
            return False
        return self._tokens.get(str(token)) == (str(escopo), str(acao))

    def esc(self) -> None:
        """Cancela filas, revoga lease e impede callbacks tardios."""
        self.cancelado = True
        self.lease = None
        self._tokens.clear()

    @staticmethod
    def redigir(texto: str) -> str:
        return _SEGREDO.sub(lambda m: f'{m.group(1)}: ***', str(texto or ''))


class Escopo:
    LEITURA = LEITURA
    PESQUISA = PESQUISA
    DOCUMENTO_LOCAL = DOCUMENTO_LOCAL
    CONTROLE_FISICO = CONTROLE_FISICO
    ALTERACAO_EXTERNA = ALTERACAO_EXTERNA
    ACAO_SENSIVEL = ACAO_SENSIVEL
