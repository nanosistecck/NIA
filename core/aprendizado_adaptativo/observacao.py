# -*- coding: utf-8 -*-
"""Observação autorizada: eventos só existem dentro de sessão explícita (F04)."""
from __future__ import annotations

import re
from typing import Any

from core.aprendizado_adaptativo import contratos as CT

_PROTEGIDO = re.compile(
    r'(?i)(senha|password|passwd|otp|codigo|token|api[_-]?key|secret|cvv|cartao|'
    r'credencial|chave)')
_VALOR_SEGREDO = re.compile(
    r'(?i)\b(senha|password|passwd|otp|token|api[_-]?key|secret|cvv|cartao)\b'
    r'\s*[:=]?\s*\S+')


class FiltroPrivacidade:
    """Falha fechada: qualquer incerteza descarta o evento."""

    def permite(self, alvo: str, dados: Any) -> bool:
        if _PROTEGIDO.search(str(alvo or '')):
            return False
        return not self._tem_segredo(dados)

    @staticmethod
    def _tem_segredo(valor: Any) -> bool:
        if isinstance(valor, str):
            return bool(_VALOR_SEGREDO.search(valor))
        if isinstance(valor, dict):
            return any(FiltroPrivacidade._tem_segredo(v) for v in valor.values())
        if isinstance(valor, (list, tuple)):
            return any(FiltroPrivacidade._tem_segredo(v) for v in valor)
        return False


class ObservadorAutorizado:
    def __init__(self, *, sessao, filtro=None, ator_padrao: str = 'usuario',
                 sessao_id: str = ''):
        self.sessao = sessao
        self.filtro = filtro
        self.ator_padrao = ator_padrao
        self.sessao_id = sessao_id or CT.novo_id()
        self._eventos: list[CT.EventoAprendizado] = []
        self._ultimo = None

    @staticmethod
    def _ativo(sessao) -> bool:
        valor = getattr(sessao, 'ativo', False)
        return bool(valor() if callable(valor) else valor)

    @property
    def eventos(self) -> tuple[CT.EventoAprendizado, ...]:
        return tuple(self._eventos)

    def registrar(self, tipo: str, *, alvo: str = '', dados: Any = None,
                   ator: str = '') -> bool:
        if not self._ativo(self.sessao) or self.filtro is None:
            return False
        if not self.filtro.permite(alvo, dados):
            return False
        assinatura = (str(tipo), str(alvo), repr(dados))
        if assinatura == self._ultimo:
            return False
        self._ultimo = assinatura
        self._eventos.append(CT.EventoAprendizado(
            tipo=str(tipo), sessao_id=self.sessao_id,
            ator=ator or self.ator_padrao, correlation_id=CT.novo_id(),
            timestamp=CT.agora(), schema_version=CT.SCHEMA_VERSION,
            cancel_generation=0, detalhes=json_resumo(dados)))
        return True

    def parar(self) -> None:
        """Encerra o observador; não há reativação silenciosa."""
        self._ultimo = None
        self._eventos.append(CT.EventoAprendizado(
            tipo='observacao_encerrada', sessao_id=self.sessao_id,
            ator=self.ator_padrao, correlation_id=CT.novo_id(),
            timestamp=CT.agora(), schema_version=CT.SCHEMA_VERSION,
            cancel_generation=0, detalhes=''))


def json_resumo(dados: Any, limite: int = 120) -> str:
    import json  # noqa: PLC0415
    try:
        return json.dumps(dados, ensure_ascii=False, sort_keys=True,
                          default=str)[:limite]
    except Exception:
        return str(dados)[:limite]
