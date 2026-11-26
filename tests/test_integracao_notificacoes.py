# -*- coding: utf-8 -*-
"""Ponte aditiva entre o agendador existente e o outbox da Fase 14."""
from __future__ import annotations

import pytest

from core import integracao_notificacoes as IN
from core import outbox_notificacoes as ON


def test_notificador_entrega_pelo_canal_injetado(tmp_path):
    """Quebra: agendador e outbox nao tinham ponte reutilizavel."""
    enviados = []
    outbox = ON.Outbox(caminho=tmp_path / 'o.json',
                       canais={'painel': lambda t: enviados.append(t) or 'ok'})
    notificador = IN.notificador_outbox(outbox, canal='painel', destino='agendador')
    assert notificador('Rotina venceu') is True
    assert enviados == ['Rotina venceu']


def test_falha_do_canal_e_reportada_ao_agendador(tmp_path):
    """Quebra: falha do outbox parecia sucesso para quem notificava."""
    outbox = ON.Outbox(caminho=tmp_path / 'o.json',
                       canais={'painel': lambda t: (_ for _ in ()).throw(OSError('offline'))})
    notificador = IN.notificador_outbox(outbox, canal='painel', destino='agendador')
    assert notificador('Rotina venceu') is False


def test_mensagem_repetida_nao_reenvia(tmp_path):
    """Quebra: reenvio duplicava aviso de rotina."""
    enviados = []
    outbox = ON.Outbox(caminho=tmp_path / 'o.json',
                       canais={'painel': lambda t: enviados.append(t) or 'ok'})
    notificador = IN.notificador_outbox(outbox, canal='painel', destino='agendador')
    assert notificador('Aviso') is True
    assert notificador('Aviso') is True
    assert enviados == ['Aviso']
