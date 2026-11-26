# -*- coding: utf-8 -*-
"""Sessão colaborativa com proprietário do controle e retomada segura (F06)."""
from __future__ import annotations

import re
import time
from typing import Callable

_REFERENCIA = re.compile(r'\b(essa|este|esta|isso|esse)\b', re.I)


class _ControlePadrao:
    def __init__(self):
        self.ativo = True
        self.lease = None

    def assumir(self, dono):
        if self.lease not in (None, dono):
            return False
        self.lease = dono
        return True

    def revogar(self):
        self.lease = None


class SessaoColaborativa:
    def __init__(self, *, objetivo: str = '', documento_id: str = '',
                 janela: str = '', controle=None, relogio=None,
                 estado: str = 'ATIVA'):
        self.objetivo = str(objetivo or '')
        self.documento_id = documento_id
        self.janela = janela
        self.controle = controle or _ControlePadrao()
        self.relogio = relogio or time.time
        self.estado = estado
        self.proprietario = 'nia'
        self.etapa = ''
        self.decisoes: list[str] = []
        self.tarefas: list[dict] = []
        self.selecao: dict | None = None
        self.precisa_esclarecer = False
        self.acoes_pendentes: tuple[str, ...] = ()

    @classmethod
    def retomar(cls, dados: dict) -> "SessaoColaborativa":
        """Reconstrói estado sem executar nada automaticamente."""
        return cls(objetivo=dados.get('objetivo', ''),
                   estado=dados.get('estado', 'PAUSADA'))

    def ativo(self) -> bool:
        return self.estado == 'ATIVA'

    def assumir_controle(self, dono: str) -> bool:
        if dono not in ('usuario', 'nia'):
            return False
        if not self.controle.assumir(dono):
            return False
        self.proprietario = dono
        self.precisa_esclarecer = False
        return True

    def registrar_selecao(self, texto: str, *, origem: str = 'usuario',
                          timestamp: float | None = None) -> None:
        self.selecao = {'texto': str(texto), 'origem': origem,
                        'timestamp': float(timestamp if timestamp is not None
                                           else self.relogio())}

    def resolver_referencia(self, texto: str, *, janela_s: float = 30.0) -> str | None:
        if not _REFERENCIA.search(str(texto or '')) or self.selecao is None:
            self.precisa_esclarecer = True
            return None
        idade = self.relogio() - float(self.selecao.get('timestamp', 0))
        if idade < 0 or idade > janela_s:
            self.precisa_esclarecer = True
            return None
        self.precisa_esclarecer = False
        return str(self.selecao.get('texto', '')) or None

    def registrar_decisao(self, descricao: str) -> None:
        self.decisoes.append(str(descricao))

    def adicionar_tarefa(self, descricao: str, *, prioridade: int = 50) -> None:
        self.tarefas.append({'descricao': str(descricao),
                             'prioridade': int(prioridade), 'estado': 'PENDENTE'})

    def pausar(self) -> None:
        self.estado = 'PAUSADA'
        self.controle.revogar()

    def retomar_sessao(self) -> None:
        if self.estado == 'PAUSADA':
            self.estado = 'ATIVA'

    def concluir(self) -> None:
        self.estado = 'CONCLUIDA'
        self.controle.revogar()
        self.acoes_pendentes = ()
