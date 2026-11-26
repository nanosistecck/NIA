# -*- coding: utf-8 -*-
"""Execução declarativa de procedimentos sem eval/shell/código arbitrário (F05)."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Callable

from core.aprendizado_adaptativo import contratos as CT

_CODIGO = re.compile(
    r'(?i)\b(import|exec|eval|os\.system|subprocess|powershell|curl\s*\||'
    r'python\s+-c|<script|rm\s+-rf|format\s+c:)\b')


def _assinatura(proc: dict, parametros: dict) -> str:
    bruto = json.dumps({'id': proc.get('id'),
                        'parametros': parametros}, ensure_ascii=False,
                       sort_keys=True, default=str)
    return hashlib.sha256(bruto.encode('utf-8')).hexdigest()[:16]


class ExecutorProcedimento:
    def __init__(self, *, memoria, executar: Callable[[dict], bool] | None = None,
                 validar: Callable[[dict], bool] | None = None,
                 cancelamento: CT.ContextoCancelamento | None = None):
        self.memoria = memoria
        self._executar = executar or (lambda etapa: False)
        self._validar = validar or (lambda etapa: False)
        self.cancelamento = cancelamento or CT.ContextoCancelamento()

    def executar(self, procedimento_id: str, parametros: dict | None = None) -> dict:
        self.cancelamento.verificar()
        parametros = dict(parametros or {})
        proc = self.memoria.obter_procedimento(str(procedimento_id))
        if proc is None:
            return {'estado': 'INEXISTENTE', 'repetido': False, 'etapas': ()}
        assinatura = _assinatura(proc, parametros)
        anterior = self.memoria.obter_checkpoint(str(procedimento_id))
        if (anterior and anterior.get('payload', {}).get('assinatura') == assinatura
                and anterior['payload'].get('estado') == 'VALIDADO'):
            return {'estado': 'VALIDADO', 'repetido': True,
                    'etapas': tuple(e['acao'] for e in proc.get('etapas', ()))}

        permitidas = set(proc.get('ferramentas') or ())
        feitos = []
        for etapa in proc.get('etapas', ()):
            self.cancelamento.verificar()
            acao = str(parametros.get('acao') or etapa.get('acao') or '')
            if not acao or _CODIGO.search(acao):
                self._salvar(proc, assinatura, 'REJEITADO')
                return {'estado': 'REJEITADO', 'repetido': False,
                        'etapas': tuple(feitos)}
            if permitidas and acao not in permitidas:
                self._salvar(proc, assinatura, 'BLOQUEADO')
                return {'estado': 'BLOQUEADO', 'repetido': False,
                        'etapas': tuple(feitos)}
            item = dict(etapa)
            item['parametros'] = {**(item.get('parametros') or {}),
                                  **{k: v for k, v in parametros.items()
                                     if k != 'acao'}}
            if not self._executar(item):
                self._salvar(proc, assinatura, 'FALHOU')
                return {'estado': 'FALHOU', 'repetido': False,
                        'etapas': tuple(feitos)}
            if not self._validar(item):
                self._salvar(proc, assinatura, 'FALHOU')
                return {'estado': 'FALHOU', 'repetido': False,
                        'etapas': tuple(feitos + [acao])}
            feitos.append(acao)

        self._salvar(proc, assinatura, 'VALIDADO')
        return {'estado': 'VALIDADO', 'repetido': False, 'etapas': tuple(feitos)}

    def _salvar(self, proc: dict, assinatura: str, estado: str) -> None:
        self.memoria.salvar_checkpoint(
            str(proc.get('id')), {'assinatura': assinatura, 'estado': estado,
                                  'validado_em': CT.agora()})
