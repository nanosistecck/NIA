# -*- coding: utf-8 -*-
"""Troca rapida de assunto: a nova fala nao espera a geracao anterior."""
import threading
import time
from types import SimpleNamespace

import main


def make_nia():
    obj = object.__new__(main.NiaLive)
    obj.ui = SimpleNamespace(
        write_log=lambda texto: None,
        set_state=lambda estado: None,
        muted=False,
    )
    obj._speaking_lock = threading.Lock()
    obj._is_speaking = False
    obj._tool_busy = False
    obj._interrupted = False
    obj._interruptivel = True
    obj._turno_seq = 0
    obj._fala_seq = 0
    obj._boca_bypass = False
    obj._ferramenta_futuro = None
    obj.audio_in_queue = None
    obj._loop = None
    obj._turn_done_event = None
    obj._mic_fechado_ate = 0.0
    obj._falar_resposta_comando = lambda mensagem, origem: None
    return obj


def test_timeout_normal_sem_interrupcao():
    nia = make_nia()
    assert nia._timeout_boca(10.0) == 10.0
    assert nia._timeout_boca(25.0) == 25.0


def test_timeout_zero_apos_interrupcao():
    nia = make_nia()
    nia._boca_bypass = True
    assert nia._timeout_boca(10.0) == 0.0
    assert nia._timeout_boca(25.0) == 0.0


def test_interrupt_marca_bypass_da_boca():
    nia = make_nia()
    nia.interrupt(silencioso=True)
    assert nia._boca_bypass is True
    assert nia._fala_seq == 1


def test_bypass_consumido_pela_proxima_fala():
    nia = make_nia()
    trava = threading.Lock()
    nia._trava_da_boca = trava
    nia._boca_bypass = True
    assert nia._adquirir_boca(10.0) is True
    assert nia._boca_bypass is False
    trava.release()


def test_nova_fala_nao_espera_trava_antiga():
    nia = make_nia()
    trava = threading.Lock()
    trava.acquire()   # geracao antiga ainda segura a boca
    nia._trava_da_boca = trava
    nia._boca_bypass = True
    inicio = time.monotonic()
    pegou = nia._adquirir_boca(10.0)
    decorrido = time.monotonic() - inicio
    trava.release()
    assert pegou is False
    assert decorrido < 0.5, decorrido
    assert nia._boca_bypass is False


def test_sem_interrupcao_trava_e_esperada():
    nia = make_nia()
    trava = threading.Lock()
    nia._trava_da_boca = trava
    assert nia._adquirir_boca(1.0) is True
    trava.release()
