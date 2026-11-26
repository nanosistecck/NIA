# -*- coding: utf-8 -*-
"""Política de confiança consolidada (Fase 16).

Reaproveita as decisões já existentes — escopos de `permissoes_ferramentas`,
origens do `capability_gateway`, validação de `.niateck` e redação de logs —
sem criar autorização paralela. Nenhum segredo é gravado aqui.
"""
from __future__ import annotations

from dataclasses import dataclass
import hmac
import json

from core import capability_gateway as CG
from core import permissoes_ferramentas as PF

LIMITE_ARGUMENTOS = 64000
LIMITE_RESULTADO = 64000


@dataclass(frozen=True)
class Decisao:
    permitido: bool
    motivo: str = ''
    escopos: tuple = ()


class PoliticaConfianca:
    def __init__(self, declaracoes=(), token_ipc=None):
        self.declaracoes = tuple(declaracoes or ())
        self._token_ipc = token_ipc if isinstance(token_ipc, str) and len(token_ipc) >= 8 else None

    def redigir(self, texto) -> str:
        return PF.redigir_diagnostico(str(texto or ''))

    def avaliar(self, origem: str, capacidade: str, argumentos: dict) -> Decisao:
        if origem not in CG.ORIGENS:
            return Decisao(False, 'origem não autorizada')
        if not isinstance(argumentos, dict):
            return Decisao(False, 'argumentos inválidos')
        try:
            serializado = json.dumps(argumentos, sort_keys=True,
                                     ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError, RecursionError):
            return Decisao(False, 'argumentos não serializáveis')
        if self.redigir(serializado) != serializado:
            return Decisao(False, 'segredo detectado nos argumentos')
        if not self.dentro_dos_limites(serializado, ''):
            return Decisao(False, 'argumentos acima do limite')
        try:
            escopos = PF.validar_chamada(capacidade, argumentos, self.declaracoes)
        except (ValueError, TypeError, PermissionError, OSError) as exc:
            return Decisao(False, 'recusado: ' + type(exc).__name__)
        return Decisao(True, 'permitido', tuple(escopos))

    def caminho_seguro(self, caminho: str) -> bool:
        try:
            PF.validar_caminho_operacao(str(caminho or ''))
        except (PermissionError, ValueError):
            return False
        return True

    def ipc_autenticado(self, token: str) -> bool:
        if self._token_ipc is None or not isinstance(token, str):
            return False
        return hmac.compare_digest(token, self._token_ipc)

    def dentro_dos_limites(self, argumentos, resultado) -> bool:
        return (len(str(argumentos or '')) <= LIMITE_ARGUMENTOS
                and len(str(resultado or '')) <= LIMITE_RESULTADO)
