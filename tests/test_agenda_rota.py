# -*- coding: utf-8 -*-
"""Rota dos comandos de Agenda no fluxo real de chat/voz do NiaLive."""
import os
from types import SimpleNamespace

import pytest

import main
from core import agenda, comandos_planos as CP


@pytest.fixture
def nia(tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_AGENDA", str(tmp_path / "agenda.json"))
    monkeypatch.setenv("NIA_PERFIL", "teste-rota")
    registros, falas = [], []
    obj = object.__new__(main.NiaLive)
    obj.ui = SimpleNamespace(
        contexto_canvas=lambda: {"plano_id": None, "card_id": None, "plano": None},
        write_log=registros.append,
        abrir_plano=lambda _: None,
        abrir_planos=lambda: None,
        abrir_agenda=lambda: None,
        muted=False,
    )
    for nome in ("_contexto_planos", "_aplicar_resultado_planos",
                 "_processar_pedido_assistido", "_processar_pedido_lembrete",
                 "_responder_conversa_plano", "_falar_resposta_comando",
                 "_executar_frase_habilidade"):
        setattr(obj, nome, getattr(main.NiaLive, nome).__get__(obj, main.NiaLive))
    obj._modo_local = True
    obj._sessao_planos = CP.SessaoComandosPlanos()
    return obj, registros, falas


def test_pedido_de_agenda_nao_cai_no_modelo(nia, monkeypatch):
    obj, _, _ = nia
    chamados = []
    monkeypatch.setattr(main.CH, "reconhecer",
                        lambda t: chamados.append(t) or (None, ""))
    assert obj._executar_frase_habilidade("qual o próximo compromisso?", "texto")
    assert not chamados


def test_bom_dia_responde_sem_compromisso(nia, monkeypatch):
    obj, registros, _ = nia
    chamados = []
    monkeypatch.setattr(main.CH, "reconhecer",
                        lambda t: chamados.append(t) or (None, ""))
    assert obj._executar_frase_habilidade("bom dia", "texto")
    assert not chamados
    assert "compromisso" in " ".join(registros).lower()


def test_criar_compromisso_pela_rota(nia):
    obj, registros, _ = nia
    assert obj._executar_frase_habilidade(
        "agende uma reunião com o João amanhã às 15h", "voz")
    assert any("reunião com o João" in item for item in registros)
    assert len(agenda.listar()) == 1
    assert agenda.listar()[0]["titulo"] == "reunião com o João"


def test_saudacao_da_abertura_inclui_proximo(nia, monkeypatch):
    obj, registros, _ = nia
    agenda.criar("Consulta", "2026-11-27T10:00:00-03:00", "chamada")
    monoc = SimpleNamespace(lido=[], falas=[])
    monkeypatch.setattr(obj, "_falar_local",
                        lambda texto, **kw: monoc.falas.append(texto))
    monkeypatch.setattr(obj, "_contexto_planos", lambda: {})
    obj._ja_saudou = False
    obj.ui.persona_atual = {"saudacao": True, "personagem": ""}
    obj._saudar_na_abertura()
    assert any("Consulta" in f for f in monoc.falas)
