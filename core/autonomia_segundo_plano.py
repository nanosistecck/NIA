# -*- coding: utf-8 -*-
"""Autonomia em segundo plano (Fase 15).

Máquina de estados pequena sobre o sinal F9 já existente. Nunca abre
microfone, não cria timers/threads e não mexe no tray. Processos registrados
são explicitamente encerrados para não deixar órfãos.
"""
from __future__ import annotations

import threading

from core import segundo_plano as SP


class GerenciadorSegundoPlano:
    def __init__(self, evento=None, notificador=None):
        self.evento = evento if evento is not None else SP.EVENTO
        self._notificador = notificador
        self._modo = 'ativo'
        self._microfone = False
        self._notificacoes_autorizadas = False
        self._processos: list = []
        self._trava = threading.RLock()

    def estado(self) -> dict:
        with self._trava:
            return {
                'modo': self._modo,
                'microfone': self._microfone,
                'notificacoes_autorizadas': self._notificacoes_autorizadas,
                'processos': len(self._processos),
                'sinal': self.evento.is_set(),
            }

    def ativar(self, autorizado: bool = False,
               notificacoes_autorizadas: bool = False) -> bool:
        if autorizado is not True:
            raise PermissionError('Ativação em segundo plano exige autorização explícita.')
        with self._trava:
            self._modo = 'segundo_plano'
            self._microfone = False
            self._notificacoes_autorizadas = notificacoes_autorizadas is True
            self.evento.set()
        return True

    def suspender(self) -> bool:
        with self._trava:
            if self._modo != 'segundo_plano':
                return False
            self._modo = 'suspenso'
            self._microfone = False
        return True

    def retomar(self) -> bool:
        with self._trava:
            self._modo = 'ativo'
            self._microfone = False
            self._notificacoes_autorizadas = False
            self.evento.clear()
        return True

    def revogar(self) -> bool:
        return self.retomar()

    def processar_tecla(self) -> str:
        """F9 é uma ação explícita do dono, portanto já autoriza a alternância."""
        if self.evento.is_set():
            self.retomar()
        else:
            self.ativar(autorizado=True)
        return self._modo

    def registrar_processo(self, processo) -> None:
        with self._trava:
            self._processos.append(processo)

    def notificar(self, texto: str) -> bool:
        with self._trava:
            if self._modo != 'segundo_plano' or not self._notificacoes_autorizadas:
                return False
            notificador = self._notificador
        if notificador is None:
            return False
        try:
            notificador(str(texto))
        except Exception:
            return False
        return True

    def encerrar(self) -> int:
        with self._trava:
            processos = list(self._processos)
            self._processos.clear()
            self._modo = 'encerrado'
            self._microfone = False
            self._notificacoes_autorizadas = False
            self.evento.clear()
        encerrados = 0
        for processo in processos:
            try:
                processo.terminate()
                processo.wait(timeout=2)
                encerrados += 1
            except Exception:
                continue
        return encerrados
