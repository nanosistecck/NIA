# -*- coding: utf-8 -*-
"""Frase real: adicionar direto na agenda, com hora e sem data."""
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import main
from core import agenda, comandos_agenda as CA, comandos_planos as CP


@pytest.fixture
def nia(tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_AGENDA", str(tmp_path / "agenda.json"))
    monkeypatch.setenv("NIA_PERFIL", "frase-real")
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


AGORA = "2026-11-23T10:00:00-03:00"


def test_adicione_na_agenda_com_hora_hoje():
    r = CA.processar("adicione na agenda buscar a maria as 21:06", agora=AGORA)
    assert r["acao"] == "criar"
    assert r["titulo"] == "buscar a maria"
    assert "2026-11-23T21:06" in r["inicio"]


def test_hora_passada_vai_para_amanha():
    r = CA.processar("adicione na agenda buscar a maria as 08:30", agora=AGORA)
    assert "2026-11-24T08:30" in r["inicio"]


def test_com_data_explicita_respeita_data():
    r = CA.processar("adicione na agenda buscar a maria amanhã às 21:06", agora=AGORA)
    assert r["titulo"] == "buscar a maria"
    assert "2026-11-24T21:06" in r["inicio"]


def test_sem_hora_continua_perguntando():
    r = CA.processar("adicione na agenda buscar a maria", agora=AGORA)
    assert r["acao"] == "pendente"


def test_adicionar_card_continua_no_canvas():
    assert CA.processar("adicione um card chamado Entrega")["tratado"] is False


def test_rota_cria_sem_cair_no_canvas(nia):
    obj, registros = nia
    assert obj._executar_frase_habilidade(
        "adicione na agenda buscar a maria as 21:06", "texto")
    assert "Abra um plano" not in " ".join(registros)
    assert len(agenda.listar()) == 1
    assert agenda.listar()[0]["titulo"] == "buscar a maria"
