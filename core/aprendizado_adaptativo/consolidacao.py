# -*- coding: utf-8 -*-
"""Consolidação de experiências com preservação da última versão válida (F09)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from core.aprendizado_adaptativo import contratos as CT


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


class Consolidador:
    def __init__(self, memoria):
        self.memoria = memoria

    def obter(self, conhecimento_id: str) -> dict | None:
        return self.memoria.obter('knowledge', conhecimento_id)

    def excluir(self, conhecimento_id: str) -> bool:
        with self.memoria.con:
            self.memoria.con.execute(
                'DELETE FROM sources WHERE knowledge_id=?', (conhecimento_id,))
            cursor = self.memoria.con.execute(
                'DELETE FROM knowledge WHERE id=?', (conhecimento_id,))
        return cursor.rowcount > 0

    def consolidar(self, experiencia: dict) -> dict:
        pid = str(experiencia.get('procedimento_id') or '')
        resultado = str(experiencia.get('resultado') or '').lower()
        if resultado not in ('sucesso', 'validado', 'concluido') or not pid:
            return {'consolidado': False, 'motivo': 'experiência sem evidência de sucesso'}
        if self.memoria.obter('procedures', pid) is None:
            return {'consolidado': False, 'motivo': 'procedimento inexistente'}
        evidencia = experiencia.get('evidencia') or {}
        kid = self.memoria.registrar_conhecimento(
            titulo=f'Experiência validada: {pid[:8]}',
            conteudo=json.dumps(experiencia, ensure_ascii=False, default=str),
            origem=str(experiencia.get('origem') or 'execucao'),
            tipo='experiencia', evidencia=evidencia)
        proc = self.memoria.obter_procedimento(pid) or {}
        versao = int(proc.get('versao', 0)) + 1
        self.memoria.registrar_versao(
            pid, versao=versao,
            payload={'evidencia': evidencia, 'resultado': resultado},
            motivo='experiência validada', estado='CONSOLIDADO')
        with self.memoria.con:
            self.memoria.con.execute(
                'INSERT INTO experiences (id, procedimento_id, resultado, '
                'evidencia, criado_em) VALUES (?,?,?,?,?)',
                (uuid4().hex, pid, resultado,
                 json.dumps(evidencia, ensure_ascii=False, default=str), _agora()))
        return {'consolidado': True, 'knowledge_id': kid, 'versao': versao,
                'estado': CT.EstadoProcedimento.CONSOLIDADO.value}

    def aplicar_correcao(self, procedimento_id: str, descricao: str, *,
                         versao: int, payload: dict | None = None) -> str:
        return self.memoria.registrar_correcao(
            procedimento_id, descricao, versao=versao, payload=payload or {})
