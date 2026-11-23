# -*- coding: utf-8 -*-
"""CRUD completo da Agenda: validacao, novos comandos e rota."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import main
from core import agenda, comandos_agenda as CA, comandos_planos as CP
from types import SimpleNamespace


@pytest.fixture
def isolado(tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_AGENDA", str(tmp_path / "agenda.json"))
    monkeypatch.setenv("NIA_PERFIL", "crud")
    return tmp_path / "agenda.json"


# ── Task 1: modelo ─────────────────────────────────────────────────────────

def test_editar_rejeita_titulo_vazio(isolado):
    item = agenda.criar("Consulta", "2026-11-24T09:00:00-03:00")
    with pytest.raises(ValueError):
        agenda.editar(item["id"], {"titulo": "   "})
    assert agenda.listar()[0]["titulo"] == "Consulta"


def test_editar_rejeita_tipo_e_data_invalidos(isolado):
    item = agenda.criar("Consulta", "2026-11-24T09:00:00-03:00")
    with pytest.raises(ValueError):
        agenda.editar(item["id"], {"tipo": "invalido"})
    with pytest.raises(ValueError):
        agenda.editar(item["id"], {"inicio": "xyz"})
    with pytest.raises(ValueError):
        agenda.editar(item["id"], {"estado": "inexistente"})


def test_criar_rejeita_tipo_invalido(isolado):
    with pytest.raises(ValueError):
        agenda.criar("Consulta", "2026-11-24T09:00:00-03:00", "invalido")


def test_reabrir_volta_para_pendente(isolado):
    item = agenda.criar("Consulta", "2026-11-24T09:00:00-03:00")
    agenda.concluir(item["id"])
    assert agenda.reabrir(item["id"])["estado"] == "pendente"


def test_editar_notas_e_tipo(isolado):
    item = agenda.criar("Consulta", "2026-11-24T09:00:00-03:00")
    agenda.editar(item["id"], {"notas": "levar exames", "tipo": "tarefa"})
    assert agenda.listar()[0]["notas"] == "levar exames"
    assert agenda.listar()[0]["tipo"] == "tarefa"


# ── Task 2: parser ─────────────────────────────────────────────────────────

def test_renomear():
    r = CA.processar("renomeie a consulta para Consulta particular")
    assert r["acao"] == "editar" and r["campos"] == {"titulo": "Consulta particular"}


def test_mudar_tipo():
    r = CA.processar("mude o tipo da reunião para tarefa")
    assert r["campos"] == {"tipo": "tarefa"}


def test_mudar_notas():
    r = CA.processar("mude as notas da consulta para levar exames")
    assert r["campos"] == {"notas": "levar exames"}


def test_reabrir_parser():
    assert CA.processar("reabra a consulta")["campos"] == {"estado": "pendente"}


# ── Task 3: rota ───────────────────────────────────────────────────────────

@pytest.fixture
def nia(isolado):
    registros = []
    obj = object.__new__(main.NiaLive)
    obj.ui = SimpleNamespace(
        contexto_canvas=lambda: {"plano_id": None, "card_id": None, "plano": None},
        write_log=registros.append,
        abrir_plano=lambda _: None, abrir_planos=lambda: None,
    )
    for nome in ("_contexto_planos", "_aplicar_resultado_planos",
                 "_processar_pedido_assistido", "_processar_pedido_lembrete",
                 "_responder_conversa_plano", "_falar_resposta_comando",
                 "_processar_pedido_agenda", "_executar_frase_habilidade"):
        setattr(obj, nome, getattr(main.NiaLive, nome).__get__(obj, main.NiaLive))
    obj._modo_local = True
    obj._sessao_planos = CP.SessaoComandosPlanos()
    return obj, registros


def test_renomear_pela_rota(nia):
    obj, registros = nia
    agenda.criar("Consulta", "2026-11-24T09:00:00-03:00")
    assert obj._executar_frase_habilidade("renomeie a consulta para Consulta nova", "texto")
    assert agenda.listar()[0]["titulo"] == "Consulta nova"
    assert "renomeado" in " ".join(registros).lower()


def test_reabrir_pela_rota(nia):
    obj, registros = nia
    item = agenda.criar("Consulta", "2026-11-24T09:00:00-03:00")
    agenda.concluir(item["id"])
    assert obj._executar_frase_habilidade("reabra a consulta", "texto")
    assert agenda.listar()[0]["estado"] == "pendente"
    assert "reaberto" in " ".join(registros).lower()
