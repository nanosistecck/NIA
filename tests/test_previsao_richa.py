# -*- coding: utf-8 -*-
"""Card de previsão rico: métricas, horários e período do dia."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QLabel

from actions import weather_report as WR
from core.canvas_brief import WeatherBrief


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


DADOS = {
    "timezone": "America/Sao_Paulo",
    "current": {
        "temperature_2m": 26.0, "weather_code": 95,
        "apparent_temperature": 33.0, "relative_humidity_2m": 95,
        "wind_speed_10m": 4.0, "pressure_msl": 1008.0, "visibility": 6000.0,
        "uv_index": 11.0,
    },
    "daily": {
        "time": ["2026-11-21", "2026-11-22"],
        "weather_code": [95, 61],
        "temperature_2m_min": [24.0, 23.0],
        "temperature_2m_max": [33.0, 30.0],
        "precipitation_probability_max": [85, 70],
        "sunrise": ["05:38", "05:39"],
        "sunset": ["18:02", "18:02"],
        "uv_index_max": [11.0, 6.0],
    },
    "hourly": {
        "time": ["2026-11-21T20:00", "2026-11-21T21:00", "2026-11-21T08:00",
                 "2026-11-21T14:00"],
        "temperature_2m": [26.0, 25.0, 22.0, 30.0],
        "precipitation_probability": [85, 80, 40, 60],
        "weather_code": [95, 61, 3, 2],
    },
}


def test_card_traz_metricas_e_horarios():
    card = WR._card_do_tempo(DADOS, "Santa Maria", "hoje", False)
    dest = card["destaque"]
    assert dest["pressao"] == 1008.0
    assert dest["visibilidade"] == 6.0  # km
    assert dest["uv"] == 11.0
    assert dest["nascer"] == "05:38" and dest["poente"] == "18:02"
    assert dest["alerta"]
    assert len(card["horas"]) == 4
    assert card["horas"][0]["hora"] == "20:00"


def test_periodo_da_manha_tarde_e_hora():
    assert WR._qual_turno("de manhã") == "manha"
    assert WR._qual_turno("da tarde") == "tarde"
    assert WR._qual_turno("às 20h") == "20"
    assert WR._qual_turno("às 20:30") == "20"


def test_filtrar_horas_por_turno():
    horas = [
        {"hora": "08:00", "temp": 22}, {"hora": "14:00", "temp": 30},
        {"hora": "20:00", "temp": 26},
    ]
    assert [h["hora"] for h in WR._filtrar_horas(horas, "manha")] == ["08:00"]
    assert [h["hora"] for h in WR._filtrar_horas(horas, "tarde")] == ["14:00"]
    assert [h["hora"] for h in WR._filtrar_horas(horas, "20")] == ["20:00"]


def test_weather_brief_mostra_metricas(app):
    card = WR._card_do_tempo(DADOS, "Santa Maria", "hoje", False)
    w = WeatherBrief()
    w.set_data({**card, "destaque": card["destaque"]})
    app.processEvents()
    texto = " ".join(x.text() for x in w.findChildren(QLabel))
    assert "1008" in texto and "UV" in texto
    assert "05:38" in texto or "18:02" in texto
    w.hide(); w.deleteLater(); app.processEvents()
