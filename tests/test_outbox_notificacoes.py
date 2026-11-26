# -*- coding: utf-8 -*-
"""Fase 14 — outbox persistente com canais simulados e deduplicação."""
from __future__ import annotations

import json

import pytest

from core import outbox_notificacoes as ON


def test_mensagem_e_entregue_pelo_canal_simulado(tmp_path):
    """Quebra: não havia registro persistente de entrega."""
    enviados = []
    outbox = ON.Outbox(caminho=tmp_path / 'outbox.json',
                       canais={'painel': lambda m: enviados.append(m) or 'ok'})
    mensagem = outbox.enviar(ON.Mensagem(canal='painel', destino='ui', texto='Oi'))
    assert mensagem['estado'] == 'enviado'
    assert enviados == ['Oi']
    assert json.loads((tmp_path / 'outbox.json').read_text(encoding='utf-8'))['mensagens']


def test_falha_do_canal_fica_registrada_e_pode_ser_retryada(tmp_path):
    """Quebra: falha de envio era silenciosa."""
    chamadas = []

    def canal(_):
        chamadas.append(1)
        if len(chamadas) == 1:
            raise ConnectionError('sem rede')
        return 'ok'

    outbox = ON.Outbox(caminho=tmp_path / 'o.json', canais={'painel': canal})
    primeiro = outbox.enviar(ON.Mensagem(canal='painel', destino='ui', texto='Oi'))
    assert primeiro['estado'] == 'falhou'
    assert outbox.reenviar_pendentes()[0]['estado'] == 'enviado'


def test_deduplicacao_evita_envio_repetido(tmp_path):
    """Quebra: o mesmo texto era enviado duas vezes."""
    enviados = []
    outbox = ON.Outbox(caminho=tmp_path / 'o.json',
                       canais={'painel': lambda m: enviados.append(m) or 'ok'})
    mensagem = ON.Mensagem(canal='painel', destino='ui', texto='Oi')
    assert outbox.enviar(mensagem)['estado'] == 'enviado'
    assert outbox.enviar(mensagem)['estado'] == 'duplicada'
    assert enviados == ['Oi']


def test_confirmacao_quando_o_canal_a_fornece(tmp_path):
    """Quebra: envio e confirmação eram o mesmo estado."""
    outbox = ON.Outbox(caminho=tmp_path / 'o.json',
                       canais={'painel': lambda m: {'confirmado': True, 'id': 'abc'}})
    mensagem = outbox.enviar(ON.Mensagem(canal='painel', destino='ui', texto='Oi'))
    assert mensagem['estado'] == 'confirmado'
    assert mensagem['confirmacao'] == 'abc'


def test_outbox_sobrevive_a_reinicio(tmp_path):
    """Quebra: estado da fila não era recuperado."""
    caminho = tmp_path / 'o.json'
    ON.Outbox(caminho=caminho, canais={}).enviar(
        ON.Mensagem(canal='ausente', destino='ui', texto='Oi'))
    assert ON.Outbox(caminho=caminho, canais={}).listar()[0]['estado'] == 'falhou'
