# -*- coding: utf-8 -*-
"""Previsão do tempo: current=time é inválido no Open-Meteo (HTTP 400)."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from actions import weather_report as WR


def _dados():
    return {
        'utc_offset_seconds': -10800,
        'current': {'temperature_2m': 22, 'weather_code': 1},
        'hourly': {'time': [], 'temperature_2m': [],
                   'precipitation_probability': [], 'weather_code': []},
        'daily': {
            'time': ['2026-11-26'],
            'weather_code': [1], 'temperature_2m_max': [28],
            'temperature_2m_min': [18], 'precipitation_probability_max': [10],
            'sunrise': ['2026-11-26T06:00'], 'sunset': ['2026-11-26T19:00'],
            'uv_index_max': [6],
        },
    }


def test_url_nao_pede_current_time(monkeypatch):
    """Quebra: HTTP 400 da API ao pedir current=...,time."""
    urls = []

    def falso(url):
        urls.append(url)
        return _dados()

    monkeypatch.setattr(WR, '_onde', lambda cidade: (-23.5, -46.6, 'Sao Paulo'))
    monkeypatch.setattr(WR, '_baixar', falso)
    monkeypatch.setattr(WR, '_card_do_tempo', lambda *a, **k: None)
    monkeypatch.setattr(WR, '_frase_do_dia', lambda *a, **k: 'ok')
    monkeypatch.setattr(WR, '_log', lambda *a, **k: None)
    monkeypatch.setattr(WR, '_emitir_card', lambda *a, **k: None)
    resultado = WR.weather_action({'city': 'Sao Paulo'})
    assert 'não consegui' not in resultado.lower()
    previsao = [u for u in urls if 'api.open-meteo.com/v1/forecast' in u]
    assert len(previsao) == 1
    assert 'current=time' not in previsao[0]
    assert ',time' not in previsao[0].split('&hourly=')[0]


def test_hora_local_vem_do_offset_do_servidor():
    """Quebra: sem current=time, a hora local some e 'agora' para de funcionar."""
    dados = {'utc_offset_seconds': -10800}
    esperado = (datetime.now(timezone.utc) + timedelta(seconds=-10800)).hour
    assert WR._hora_local_atual(dados) == esperado
