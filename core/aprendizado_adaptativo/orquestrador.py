# -*- coding: utf-8 -*-
"""Fila priorizada com limites, cancelamento e descarte de resultados tardios (F08)."""
from __future__ import annotations

from dataclasses import dataclass, field
import threading
import time
from uuid import uuid4


@dataclass(frozen=True)
class ResultadoTardio:
    tarefa_id: str
    valor: object
    descartado: bool


@dataclass
class Tarefa:
    id: str
    descricao: str
    prioridade: int
    tipo: str
    funcao: object
    estado: str = 'PENDENTE'
    cancel_generation: int = 0
    criado_em: float = field(default_factory=time.time)
    resultado: object = None


class OrquestradorTarefas:
    def __init__(self, *, max_pesquisas: int = 3):
        self.max_pesquisas = max(1, int(max_pesquisas))
        self._trava = threading.RLock()
        self._tarefas: dict[str, Tarefa] = {}
        self._encerrado = False

    def agendar(self, descricao: str, *, prioridade: int = 50,
                tipo: str = 'comando', funcao=None) -> str | None:
        with self._trava:
            if self._encerrado:
                return None
            if tipo == 'pesquisa':
                ativas = [t for t in self._tarefas.values()
                          if t.tipo == 'pesquisa'
                          and t.estado in ('PENDENTE', 'EXECUTANDO')]
                if len(ativas) >= self.max_pesquisas:
                    return None
            tid = uuid4().hex
            self._tarefas[tid] = Tarefa(
                id=tid, descricao=str(descricao), prioridade=int(prioridade),
                tipo=tipo, funcao=funcao)
            return tid

    def obter(self, tarefa_id: str) -> dict | None:
        with self._trava:
            t = self._tarefas.get(str(tarefa_id))
            if t is None:
                return None
            return {'id': t.id, 'descricao': t.descricao,
                    'prioridade': t.prioridade, 'tipo': t.tipo,
                    'estado': t.estado, 'cancel_generation': t.cancel_generation,
                    'resultado': t.resultado}

    def executar_proximo(self) -> dict | None:
        with self._trava:
            pendentes = [t for t in self._tarefas.values()
                         if t.estado == 'PENDENTE']
            if not pendentes:
                return None
            escolhida = min(pendentes, key=lambda t: (-t.prioridade, t.criado_em))
            return self.executar(escolhida.id)

    def executar(self, tarefa_id: str) -> dict | None:
        with self._trava:
            t = self._tarefas.get(str(tarefa_id))
            if t is None or t.estado == 'CANCELADA':
                raise RuntimeError('tarefa cancelada ou inexistente')
            if self._encerrado:
                raise RuntimeError('orquestrador encerrado')
            t.estado = 'EXECUTANDO'
            geracao = t.cancel_generation
        if callable(t.funcao):
            try:
                valor = t.funcao()
            except Exception as exc:  # falha vira resultado, não exceção solta
                valor = {'erro': type(exc).__name__}
        else:
            valor = None
        with self._trava:
            if t.cancel_generation != geracao or t.estado == 'CANCELADA':
                return None
            t.resultado = valor
            t.estado = 'CONCLUIDA'
        return self.obter(t.id)

    def cancelar(self, tarefa_id: str) -> bool:
        with self._trava:
            t = self._tarefas.get(str(tarefa_id))
            if t is None:
                return False
            t.cancel_generation += 1
            t.estado = 'CANCELADA'
            return True

    def registrar_resultado(self, tarefa_id: str, geracao: int,
                            valor: object) -> ResultadoTardio:
        with self._trava:
            t = self._tarefas.get(str(tarefa_id))
            descartado = (t is None or t.estado == 'CANCELADA'
                          or t.cancel_generation != int(geracao))
            if not descartado:
                t.resultado = valor
            return ResultadoTardio(tarefa_id, valor, descartado)

    def encerrar(self) -> None:
        with self._trava:
            self._encerrado = True
            for t in self._tarefas.values():
                if t.estado in ('PENDENTE', 'EXECUTANDO'):
                    t.cancel_generation += 1
                    t.estado = 'CANCELADA'
