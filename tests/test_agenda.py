# -*- coding: utf-8 -*-
"""Persistencia e regras da Agenda (modulo puro, sem Qt)."""
import json

import pytest

from core import agenda


@pytest.fixture
def isolado(tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_AGENDA", str(tmp_path / "agenda.json"))
    monkeypatch.setenv("NIA_PERFIL", "teste")
    return tmp_path / "agenda.json"


def test_criar_e_proximo(isolado):
    item = agenda.criar("Reunião", "2026-11-27T15:00:00-03:00", "reuniao")
    assert item["preparo_minutos"] == 15
    assert item["estado"] == "pendente"
    assert agenda.proximo(agora="2026-11-27T14:00:00-03:00")["id"] == item["id"]
    assert agenda.proximo(agora="2026-11-27T16:00:00-03:00") is None
    assert agenda.listar()[0]["estado"] == "pendente"


def test_gravacao_atomica_e_por_perfil(isolado, monkeypatch):
    agenda.criar("Um", "2026-11-27T10:00:00-03:00")
    dados = json.loads(isolado.read_text(encoding="utf-8"))
    assert "teste" in dados and len(dados["teste"]["itens"]) == 1
    assert not (isolado.parent / "agenda.tmp").exists()
    monkeypatch.setenv("NIA_PERFIL", "outro")
    assert agenda.listar() == []


def test_sugerir_preparo_por_tipo():
    assert agenda.sugerir_preparo("reuniao") == 15
    assert agenda.sugerir_preparo("chamada") == 15
    assert agenda.sugerir_preparo("tarefa") == 30
    assert agenda.sugerir_preparo("entrega") == 30
    assert agenda.sugerir_preparo("viagem") == 60
    assert agenda.sugerir_preparo("aniversario") == 120
    assert agenda.sugerir_preparo("outro") == 30


def test_preparo_editavel_e_valores_validos(isolado):
    item = agenda.criar("Consulta", "2026-11-27T09:00:00-03:00",
                        "chamada", preparo_minutos=45)
    assert item["preparo_minutos"] == 45
    assert item["inicio"] == "2026-11-27T09:00:00-03:00"


def test_editar_mover_concluir_e_cancelar(isolado):
    item = agenda.criar("Entrega", "2026-11-27T09:00:00-03:00", "entrega")
    agenda.editar(item["id"], {"titulo": "Entrega final"})
    assert agenda.listar()[0]["titulo"] == "Entrega final"
    agenda.mover(item["id"], "2026-11-28T11:00:00-03:00")
    assert agenda.listar()[0]["inicio"] == "2026-11-28T11:00:00-03:00"
    agenda.concluir(item["id"])
    assert agenda.listar()[0]["estado"] == "concluido"
    assert agenda.proximo() is None
    item2 = agenda.criar("Outra", "2026-11-29T10:00:00-03:00")
    agenda.cancelar(item2["id"])
    assert agenda.listar()[1]["estado"] == "cancelado"


def test_interpretar_data_e_hora(isolado):
    agora = "2026-11-23T10:00:00-03:00"
    valor = agenda.interpretar("amanhã às 15h", agora=agora)
    assert valor is not None and "2026-11-24T15:00" in valor
    assert agenda.interpretar("qualquer coisa", agora=agora) is None


def test_resumo_proximo(isolado):
    assert "nenhum compromisso" in agenda.resumo_proximo().lower()
    agenda.criar("Reunião com João", "2026-11-27T15:00:00-03:00", "reuniao")
    texto = agenda.resumo_proximo(agora="2026-11-27T14:00:00-03:00")
    assert "Reunião com João" in texto and "14:45" in texto


def test_vencido_aparece_na_lista_mas_nao_no_proximo(isolado):
    agenda.criar("Antigo", "2026-11-20T10:00:00-03:00")
    assert len(agenda.listar()) == 1
    assert agenda.proximo(agora="2026-11-23T10:00:00-03:00") is None
