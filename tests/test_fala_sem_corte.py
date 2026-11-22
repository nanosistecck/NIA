# -*- coding: utf-8 -*-
"""Fala sem corte: silêncio longo e régua rígida para áudio incompleto."""
import threading

import main
from core import gemini_voice


def test_silencio_entre_pedacos_nao_corta_a_frase():
    assert gemini_voice.SILENCIO_MAX_S >= 20.0


def test_regua_de_fala_completa_e_rigorosa():
    assert main.NiaLive._INTEIRA_PARA_TOCAR >= 0.85
    assert main.NiaLive._INTEIRA_PARA_GRAVAR >= 0.90


def test_fala_completa_rejeita_corte_e_aceita_quase_inteira():
    obj = object.__new__(main.NiaLive)
    texto = "x" * 140          # ~10 s esperados
    esperado = obj._fala_esperada_s(texto)
    assert not obj._fala_completa(texto, esperado * 0.70,
                                  obj._INTEIRA_PARA_TOCAR)
    assert obj._fala_completa(texto, esperado * 0.95,
                              obj._INTEIRA_PARA_TOCAR)


class MotorCortado:
    """Entrega só a metade do áudio esperado."""

    def __init__(self, fracao=0.5):
        self.fracao = fracao

    def speak_para_fila(self, texto, on_chunk):
        obj = object.__new__(main.NiaLive)
        esperado = obj._fala_esperada_s(texto)
        pedacos = max(1, int(esperado * self.fracao / 0.05))
        for _ in range(pedacos):
            on_chunk(b"\x00" * 2400)


def test_gerar_inteiro_nao_devolve_audio_cortado():
    obj = object.__new__(main.NiaLive)
    obj._trava_da_boca = threading.RLock()
    obj._boca_bypass = False
    resultado = obj._gerar_inteiro(MotorCortado(0.5), "x" * 140)
    assert resultado == b""


def test_gerar_inteiro_devolve_audio_completo():
    obj = object.__new__(main.NiaLive)
    obj._trava_da_boca = threading.RLock()
    obj._boca_bypass = False
    resultado = obj._gerar_inteiro(MotorCortado(1.0), "x" * 140)
    assert resultado
