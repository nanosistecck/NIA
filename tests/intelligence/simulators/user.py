# -*- coding: utf-8 -*-
"""Simulador de usuário: turnos, correções e histórico de conversa."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UsuarioSimulado:
    nome: str = 'usuario-teste'
    turnos: list = field(default_factory=list)

    def dizer(self, mensagem: str) -> str:
        self.turnos.append(('usuario', str(mensagem)))
        return str(mensagem)

    def responder(self, mensagem: str) -> None:
        self.turnos.append(('nia', str(mensagem)))

    def historico(self) -> tuple:
        return tuple(self.turnos)
