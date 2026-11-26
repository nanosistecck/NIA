# -*- coding: utf-8 -*-
"""Ponte opcional agendador → outbox (continuação da Fase 14).

Não altera `core/rotinas.py`: apenas devolve um callable compatível com o
`notificador` que o agendador já aceita. O host decide se injeta a ponte.
"""
from __future__ import annotations

from core import outbox_notificacoes as ON


def notificador_outbox(outbox, canal: str, destino: str = 'agendador'):
    """Cria `notificador(mensagem) -> bool` sobre um outbox com canais injetados."""
    if not isinstance(outbox, ON.Outbox):
        raise TypeError('Outbox inválido.')
    if not isinstance(canal, str) or not canal.strip():
        raise ValueError('Canal inválido.')

    def notificar(mensagem) -> bool:
        registro = outbox.enviar(ON.Mensagem(
            canal=canal, destino=destino, texto=str(mensagem or '')))
        return registro['estado'] in ('enviado', 'confirmado', 'duplicada')

    return notificar
