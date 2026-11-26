# -*- coding: utf-8 -*-
"""Contexto da ferramenta ativa: ações tipadas e resultados correlacionados.

Não é motor de execução nem interpretador de linguagem natural. Apenas guarda
qual ação tipada está em curso, publica o resultado real correspondente e
recusa seguimentos ambíguos — em particular, nunca transforma "faz isso" em
comando de shell. A execução continua exclusivamente em ``NiaLive._execute_tool``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
import threading
import time
import unicodedata

# Nomes que o contexto nunca produz sozinho: shell não é ação tipada.
_SHELL = re.compile(r'(?i)(shell|powershell|cmd|bash|terminal|executar_comando)')
_SEGUIR = {
    'repita', 'repete', 'novamente', 'de novo', 'outra vez', 'faca de novo',
    'faça de novo', 'faz de novo', 'refaça', 'refaca',
}
_PARAR = {'pare', 'parar', 'cancele', 'cancelar', 'nao', 'não', 'interrompa'}


_POLIDO = re.compile(r'\b(?:por favor|porfavor|favor|por|ai|entao|agora|mesmo)\b')


def _normalizar(texto) -> str:
    bruto = unicodedata.normalize('NFKD', str(texto or '').lower())
    sem_acento = ''.join(c for c in bruto if not unicodedata.combining(c))
    limpo = re.sub(r'[^\w\s]', ' ', sem_acento)
    limpo = _POLIDO.sub(' ', limpo)
    return re.sub(r'\s+', ' ', limpo).strip()


@dataclass(frozen=True)
class AcaoTipada:
    ferramenta: str
    argumentos: dict = field(default_factory=dict)
    sequencia: int = 0


@dataclass(frozen=True)
class ResultadoTipado:
    sequencia: int
    ferramenta: str
    ok: bool
    resumo: str = ''


class ContextoFerramentas:
    """Uma ação ativa por vez; resultados velhos não contaminam a atual."""

    def __init__(self, *, ttl: float = 120.0, relogio=None):
        self._trava = threading.RLock()
        self._sequencia = 0
        self._ativo: AcaoTipada | None = None
        self._inicio = 0.0
        self._ultimo: ResultadoTipado | None = None
        self._ttl = max(1.0, float(ttl))
        self._relogio = relogio if callable(relogio) else time.monotonic

    # ── ciclo ───────────────────────────────────────────────────────────────
    def iniciar(self, ferramenta: str, argumentos: dict | None = None) -> AcaoTipada:
        if not isinstance(ferramenta, str) or not ferramenta.strip():
            raise ValueError('Ferramenta inválida.')
        if _SHELL.search(ferramenta):
            raise PermissionError('Comando de shell não é ação tipada.')
        args = dict(argumentos or {})
        if not isinstance(argumentos, (dict, type(None))):
            raise ValueError('Argumentos devem ser um objeto.')
        try:
            json.dumps(args, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError, RecursionError):
            raise ValueError('Argumentos devem ser JSON finito.') from None
        with self._trava:
            self._sequencia += 1
            self._ativo = AcaoTipada(ferramenta.strip(), args, self._sequencia)
            self._inicio = self._relogio()
            return self._ativo

    def concluir(self, ok: bool, resumo: str = '') -> ResultadoTipado | None:
        """Correlaciona com a ação ativa. Resultado atrasado é descartado."""
        with self._trava:
            acao = self._ativo
            if acao is None:
                return None
            self._ativo = None
            resultado = ResultadoTipado(acao.sequencia, acao.ferramenta,
                                        bool(ok), str(resumo or '')[:400])
            self._ultimo = resultado
            return resultado

    def falhar(self, motivo: str) -> ResultadoTipado | None:
        return self.concluir(False, motivo)

    def cancelar(self) -> None:
        """Interrupção/troca de assunto: ação ativa não recebe mais resultado."""
        with self._trava:
            self._ativo = None

    # ── consulta ────────────────────────────────────────────────────────────
    @property
    def ativo(self) -> AcaoTipada | None:
        with self._trava:
            if self._ativo is None:
                return None
            if self._relogio() - self._inicio > self._ttl:
                self._ativo = None
                return None
            return self._ativo

    @property
    def ultimo_resultado(self) -> ResultadoTipado | None:
        with self._trava:
            return self._ultimo

    @property
    def sequencia(self) -> int:
        with self._trava:
            return self._sequencia

    # ── seguimentos ─────────────────────────────────────────────────────────
    def resolver(self, frase: str) -> AcaoTipada | None:
        """Repete SOMENTE a ação tipada ativa; ambiguidade nunca vira shell."""
        texto = _normalizar(frase)
        with self._trava:
            acao = self.ativo
            if acao is None or not texto:
                return None
            if any(palavra in _PARAR for palavra in texto.split()):
                self.cancelar()
                return None
            if texto in _SEGUIR:
                return AcaoTipada(acao.ferramenta, dict(acao.argumentos),
                                  acao.sequencia)
            # "isso", "aquilo", "roda", "executa" ficam sem ação: o modelo
            # pode pedir detalhes, mas o contexto não inventa comando.
            return None
