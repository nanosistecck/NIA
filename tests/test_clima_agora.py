# -*- coding: utf-8 -*-
"""Clima com 'agora': usar a hora local da cidade, não a do PC."""
from unittest.mock import patch

from actions import weather_report as wr


def test_hora_local_vem_do_current_time():
    dados = {"current": {"time": "2026-11-22T16:15"}}
    assert wr._hora_local_atual(dados) == 16


def test_hora_local_ausente_nao_inventa():
    assert wr._hora_local_atual({}) is None
    assert wr._hora_local_atual({"current": {"time": "invalid"}}) is None


def test_filtrar_so_horas_restantes_do_turno():
    horas = [{"hora": f"{h:02}:00"} for h in range(12, 18)]
    restantes = wr._filtrar_horas(horas, "tarde", desde=16)
    assert [item["hora"] for item in restantes] == ["16:00", "17:00"]


def test_antes_do_turno_mantem_o_intervalo_completo():
    horas = [{"hora": f"{h:02}:00"} for h in range(12, 18)]
    assert len(wr._filtrar_horas(horas, "tarde", desde=10)) == 6


def test_sem_desde_mantem_comportamento_atual():
    horas = [{"hora": f"{h:02}:00"} for h in range(12, 18)]
    assert len(wr._filtrar_horas(horas, "tarde")) == 6


def dados_16h():
    dias = ["2026-11-22"]
    horas = [f"{dias[0]}T{h:02}:00" for h in range(24)]
    return {
        "timezone": "America/Belem",
        "daily": {
            "time": dias, "weather_code": [61],
            "temperature_2m_min": [20], "temperature_2m_max": [30],
            "precipitation_probability_max": [80],
        },
        "current": {"time": "2026-11-22T16:00", "temperature_2m": 28},
        "hourly": {
            "time": horas,
            "temperature_2m": [20 if h < 12 else 28 for h in range(24)],
            # Chuva forte antes das 16h, limpo depois.
            "precipitation_probability": [80 if h < 16 else 0 for h in range(24)],
            "weather_code": [61 if h < 16 else 0 for h in range(24)],
        },
    }


def consultar(dados, pedido):
    with patch.object(wr, "_em_ingles", return_value=False), \
         patch.object(wr, "_onde", return_value=(0, 0, "Cidade")), \
         patch.object(wr, "_baixar", return_value=dados):
        return wr.weather_action({"city": "Cidade", "time": pedido})


def test_agora_a_tarde_so_fala_das_horas_restantes():
    fala = consultar(dados_16h(), "agora a tarde")
    assert "0% de chance" in fala
    assert "80% de chance" not in fala


def test_tarde_sem_agora_continua_completo():
    fala = consultar(dados_16h(), "hoje à tarde")
    assert "80% de chance" in fala


def test_sem_hora_local_cai_para_o_turno_completo():
    dados = dados_16h()
    dados["current"].pop("time")
    fala = consultar(dados, "agora a tarde")
    assert "80% de chance" in fala


def test_url_pede_o_campo_time_no_current():
    chamadas = []

    def falso_baixar(url):
        chamadas.append(url)
        return dados_16h()

    with patch.object(wr, "_em_ingles", return_value=False), \
         patch.object(wr, "_onde", return_value=(0, 0, "Cidade")), \
         patch.object(wr, "_baixar", side_effect=falso_baixar):
        wr.weather_action({"city": "Cidade", "time": "agora a tarde"})
    assert "current=" in chamadas[0] and "time" in chamadas[0]
