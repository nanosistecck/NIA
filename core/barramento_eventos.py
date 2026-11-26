# -*- coding: utf-8 -*-
"""Barramento de eventos leve (Fase 13).

Fila em memória com deduplicação, backpressure e retries limitados. Eventos
marcados como críticos são persistidos em JSON para sobreviver a um reinício.
Nenhum timer, thread ou serviço residente é criado aqui.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import os
import tempfile
from uuid import uuid4


@dataclass(frozen=True)
class Evento:
    tipo: str
    origem: str
    perfil: str
    chave: str
    dados: dict = field(default_factory=dict)
    critico: bool = False
    id: str = field(default_factory=lambda: uuid4().hex)
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def como_dict(self) -> dict:
        return asdict(self)

    def dedupe(self) -> tuple:
        return (self.tipo, self.origem, self.perfil, self.chave)


class Barramento:
    def __init__(self, max_fila: int = 100, max_tentativas: int = 3, caminho=None):
        self.max_fila = max(1, int(max_fila))
        self.max_tentativas = max(1, int(max_tentativas))
        self.caminho = Path(caminho) if caminho else None
        self.fila: list[Evento] = []
        self._vistos: set[tuple] = set()
        self._tentativas: dict[str, int] = {}
        self._mortos: list[Evento] = []
        self._persistidos: list[dict] = self._carregar()
        for dados in self._persistidos:
            try:
                evento = Evento(**dados)
            except TypeError:
                continue
            if evento.dedupe() not in self._vistos and len(self.fila) < self.max_fila:
                self.fila.append(evento)
                self._vistos.add(evento.dedupe())

    def _carregar(self) -> list:
        if self.caminho is None or not self.caminho.is_file():
            return []
        try:
            dados = json.loads(self.caminho.read_text(encoding='utf-8'))
            eventos = dados.get('eventos', [])
            return eventos if isinstance(eventos, list) else []
        except (ValueError, OSError):
            return []

    def _salvar(self) -> None:
        if self.caminho is None:
            return
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        fd, temporario = tempfile.mkstemp(prefix='eventos-', suffix='.json',
                                          dir=str(self.caminho.parent))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as arquivo:
                json.dump({'eventos': self._persistidos}, arquivo,
                          ensure_ascii=False, indent=2)
                arquivo.write('\n')
                arquivo.flush()
                os.fsync(arquivo.fileno())
            os.replace(temporario, self.caminho)
        finally:
            if os.path.exists(temporario):
                os.unlink(temporario)

    def publicar(self, evento: Evento) -> bool:
        if not isinstance(evento, Evento):
            raise TypeError('Evento inválido.')
        chave = evento.dedupe()
        if chave in self._vistos or len(self.fila) >= self.max_fila:
            return False
        self.fila.append(evento)
        self._vistos.add(chave)
        if evento.critico:
            self._persistidos.append(evento.como_dict())
            self._salvar()
        return True

    def consumir(self, handler) -> None:
        if not callable(handler):
            raise TypeError('Consumidor inválido.')
        for evento in list(self.fila):
            try:
                handler(evento)
            except Exception:
                tentativas = self._tentativas.get(evento.id, 0) + 1
                self._tentativas[evento.id] = tentativas
                if tentativas >= self.max_tentativas:
                    self.fila.remove(evento)
                    self._mortos.append(evento)
                continue
            self.fila.remove(evento)
            self._tentativas.pop(evento.id, None)

    def estado(self) -> dict:
        return {'fila': len(self.fila), 'mortos': len(self._mortos)}
