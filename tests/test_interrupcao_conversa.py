# -*- coding: utf-8 -*-
"""Interrupção conversacional: nova mensagem cala a atividade anterior."""
import os
import threading
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

import main
import ui


@pytest.fixture
def nia():
    obj = object.__new__(main.NiaLive)
    registros, falas, interrupcoes = [], [], []
    obj.ui = SimpleNamespace(
        write_log=registros.append,
        set_state=lambda estado: None,
        muted=False,
        on_interrupt=lambda **kw: interrupcoes.append(kw),
    )
    obj._speaking_lock = threading.Lock()
    obj._is_speaking = False
    obj._tool_busy = False
    obj._interrupted = False
    obj._interruptivel = True
    obj._turno_seq = 0
    obj._fala_seq = 0
    obj._mic_fechado_ate = 0.0
    obj.audio_in_queue = None
    obj._loop = None
    obj._turn_done_event = None
    obj._ferramenta_futuro = None
    obj._falar_resposta_comando = lambda m, o: falas.append((m, o))
    return obj, registros, falas, interrupcoes


@pytest.mark.parametrize('frase', [
    'faz até o final',
    'deixa terminar',
    'não interrompa',
    'sem interrupção, termina aí',
    'continua até acabar',
    'deixa a tarefa ir até o fim',
])
def test_pedido_ate_o_final(nia, frase):
    obj, _, _, _ = nia
    assert obj.pedido_ate_o_final(frase), frase


@pytest.mark.parametrize('frase', [
    'cria um card novo',
    'tenta fazer meu pedido',
    'fala sobre o plano',
    'pare e fala outra coisa',
])
def test_frase_comum_nao_e_ate_o_final(nia, frase):
    obj, _, _, _ = nia
    assert not obj.pedido_ate_o_final(frase), frase


def test_atividade_em_andamento(nia):
    obj, _, _, _ = nia
    assert not obj.atividade_em_andamento()
    obj._is_speaking = True
    assert obj.atividade_em_andamento()
    obj._is_speaking = False
    obj._tool_busy = True
    assert obj.atividade_em_andamento()


def test_nova_mensagem_interrompe_atividade(nia, monkeypatch):
    obj, registros, _, interrupcoes = nia
    obj._is_speaking = True
    chamadas = []
    monkeypatch.setattr(obj, 'interrupt',
                        lambda **kw: chamadas.append(kw))
    assert obj._tratar_interrupcao('fala sobre outra coisa', 'texto') is False
    assert chamadas == [{'silencioso': True}]
    assert obj._interruptivel is True


def test_sem_atividade_nao_interrompe(nia, monkeypatch):
    obj, _, _, _ = nia
    chamadas = []
    monkeypatch.setattr(obj, 'interrupt',
                        lambda **kw: chamadas.append(kw))
    assert obj._tratar_interrupcao('fala sobre outra coisa', 'texto') is False
    assert not chamadas


def test_ate_o_final_consumemensagem_e_bloqueia_interrupcao(nia, monkeypatch):
    obj, registros, falas, _ = nia
    obj._is_speaking = True
    chamadas = []
    monkeypatch.setattr(obj, 'interrupt',
                        lambda **kw: chamadas.append(kw))
    assert obj._tratar_interrupcao('faz até o final', 'voz') is True
    assert not chamadas
    assert obj._interruptivel is False
    assert any('terminar' in item.lower() for item in registros)
    assert falas[-1][1] == 'voz'


def test_interrupt_respeita_flag_ate_o_final(nia):
    obj, _, _, _ = nia
    obj._interruptivel = False
    obj.interrupt()
    assert obj._interrupted is False
    assert obj._turno_seq == 0


def test_interrupt_avanca_token_e_cancela_ferramenta(nia):
    obj, _, _, _ = nia
    cancelado = []

    class Futuro:
        def done(self):
            return False

        def cancel(self):
            cancelado.append(True)

    obj._ferramenta_futuro = Futuro()
    obj._turno_seq = 4
    obj._fala_seq = 7
    obj.interrupt(silencioso=True)
    assert obj._turno_seq == 5
    assert obj._fala_seq == 8
    assert cancelado == [True]
    assert obj._interrupted is True


# ── chat real ──────────────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_enviar_no_chat_interrompe_quando_há_atividade(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(ui.MainWindow, '_check_config', lambda self: True)
    w = ui.MainWindow('face.png')
    chamadas = []
    w.on_interrupt = lambda **kw: chamadas.append(kw)
    w.on_atividade = lambda: True
    w.on_text_command = lambda texto: None
    w._input.setText('outra coisa')
    w._send()
    assert chamadas == [{'silencioso': True}]
    assert w._input.text() == ''


def test_enviar_no_chat_sem_atividade_nao_interrompe(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(ui.MainWindow, '_check_config', lambda self: True)
    w = ui.MainWindow('face.png')
    chamadas = []
    w.on_interrupt = lambda **kw: chamadas.append(kw)
    w.on_atividade = lambda: False
    w.on_text_command = lambda texto: None
    w._input.setText('outra coisa')
    w._send()
    assert not chamadas
