# -*- coding: utf-8 -*-
"""Regressão: pedido de controle/arquivo no PC não pode virar pedido de plano."""
from __future__ import annotations

import os
import threading
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

import main
from core import assistencia_planos as AP


FRASE_REAL = 'nia controle o computador agora vá na area de trabalho e crie um arquivo txt'


def _nia_minima():
    obj = object.__new__(main.NiaLive)
    registros = []
    obj.ui = SimpleNamespace(
        contexto_canvas=lambda: {'plano_id': None, 'card_id': None, 'plano': None},
        write_log=registros.append,
    )
    obj._modo_local = True
    obj._usando_pc = False
    obj._parou_pc_em = 0.0
    obj._pc_liberado_ate = 0.0
    obj._esperando_tarefa_pc_ate = 0.0
    obj._parar_pc = False
    obj._pending_delete_args = None
    obj._pending_delete_label = ""
    obj._pergunta_pendente = False
    obj._correcoes_pc = []
    obj._falar_resposta_comando = lambda mensagem, origem: None
    for nome in ("_retomar_pedido_canvas", "_processar_pedido_assistido",
                 "_processar_pedido_agenda", "_processar_pedido_lembrete",
                 "_responder_conversa_plano", "_executar_frase_habilidade",
                 "_redes_do_pc"):
        setattr(obj, nome, getattr(main.NiaLive, nome).__get__(obj, main.NiaLive))
    return obj, registros


def test_pedido_de_arquivo_no_desktop_nao_e_edicao_de_plano():
    """Quebra: 'crie um arquivo txt' caía no EDITAR do Canvas."""
    assert AP.reconhecer_intencao(FRASE_REAL) == 'NENHUMA'
    assert AP.reconhecer_intencao('crie um arquivo txt na area de trabalho') == 'NENHUMA'


def test_criar_card_continua_sendo_edicao_de_plano():
    """Contraprova: a correção não pode desligar o assistente do Canvas."""
    assert AP.reconhecer_intencao('crie um card para testar') == 'EDITAR'


def test_frase_de_controle_nao_e_consumida_pela_habilidade():
    """Quebra: o assistente respondia 'Abra um plano...' antes da rota de PC."""
    obj, registros = _nia_minima()
    assert obj._executar_frase_habilidade(FRASE_REAL, 'voz') is False
    assert not any('Abra um plano' in item for item in registros)


def test_plano_aberto_nao_sequestra_pedido_de_pc():
    """Quebra: com plano aberto, o respondia 'Abra um plano e selecione...'."""
    obj, registros = _nia_minima()
    plano = SimpleNamespace(id='p1', titulo='Teste', tipo='Estudo', objetivo='',
                            mapa={'cards': [], 'conexoes': [], 'raiz_id': None})
    obj.ui.contexto_canvas = lambda: {
        'plano_id': 'p1', 'card_id': None, 'plano': plano,
        'modo_assistido': False, 'sessao_id': 's1'}
    assert obj._executar_frase_habilidade(FRASE_REAL, 'voz') is False
    assert not any('Abra um plano' in item for item in registros)


def test_controle_o_computador_dispara_a_tarefa_no_pc(monkeypatch):
    """Quebra: só 'ativar computador' ligava o olhar-e-clicar."""
    obj, _ = _nia_minima()
    tarefas = []

    class ThreadSincrono:
        def __init__(self, target=None, args=(), kwargs=None, **_extra):
            self._target = target
            self._args = args
            self._kwargs = kwargs or {}

        def start(self):
            self._target(*self._args, **self._kwargs)

    monkeypatch.setattr(main, 'threading', SimpleNamespace(
        Thread=ThreadSincrono, Event=threading.Event))
    monkeypatch.setattr(obj, '_olhar_e_clicar', tarefas.append)
    assert obj._redes_do_pc(FRASE_REAL) is True
    assert len(tarefas) == 1
    assert 'crie um arquivo txt' in tarefas[0]
