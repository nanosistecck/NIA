# -*- coding: utf-8 -*-
"""Fase 13 — barramento leve com dedupe, fila limitada e recuperação."""
from __future__ import annotations

import json

import pytest

from core import barramento_eventos as BE


def test_evento_duplicado_nao_entra_na_fila():
    """Quebra: o mesmo evento podia ser publicado várias vezes."""
    barramento = BE.Barramento(max_fila=10)
    evento = BE.Evento(tipo='mensagem', origem='whatsapp', perfil='p1',
                       chave='abc', dados={'texto': 'oi'})
    assert barramento.publicar(evento) is True
    assert barramento.publicar(evento) is False
    assert len(barramento.fila) == 1


def test_fila_cheia_aplica_backpressure(tmp_path):
    """Quebra: fila ilimitada crescia sem controle."""
    barramento = BE.Barramento(max_fila=2)
    for i in range(2):
        assert barramento.publicar(BE.Evento(
            tipo='t', origem='agenda', perfil='p1', chave=str(i))) is True
    assert barramento.publicar(BE.Evento(
        tipo='t', origem='agenda', perfil='p1', chave='terceiro')) is False


def test_consumidores_recebem_em_ordem():
    """Quebra: ordem de publicação não era preservada."""
    barramento = BE.Barramento(max_fila=10)
    for i in range(3):
        barramento.publicar(BE.Evento(tipo='t', origem='local', perfil='p1',
                                      chave=str(i), dados={'n': i}))
    vistos = []
    barramento.consumir(lambda ev: vistos.append(ev.dados['n']))
    assert vistos == [0, 1, 2]


def test_falha_do_consumidor_faz_retry_limitado():
    """Quebra: consumidor com falha era descartado ou repetido infinitamente."""
    barramento = BE.Barramento(max_fila=10, max_tentativas=2)
    barramento.publicar(BE.Evento(tipo='t', origem='local', perfil='p1', chave='x'))
    chamadas = []

    def falha(_):
        chamadas.append(1)
        raise RuntimeError('falha')

    barramento.consumir(falha)
    barramento.consumir(falha)
    barramento.consumir(falha)
    assert len(chamadas) == 2
    assert barramento.estado()['mortos'] == 1


def test_eventos_criticos_sobrevivem_a_reinicio(tmp_path):
    """Quebra: eventos críticos não eram persistidos."""
    caminho = tmp_path / 'eventos.json'
    barramento = BE.Barramento(max_fila=10, caminho=caminho)
    barramento.publicar(BE.Evento(tipo='critico', origem='agenda', perfil='p1',
                                  chave='k', critico=True))
    novo = BE.Barramento(max_fila=10, caminho=caminho)
    assert len(novo.fila) == 1
    assert json.loads(caminho.read_text(encoding='utf-8'))['eventos'][0]['tipo'] == 'critico'
