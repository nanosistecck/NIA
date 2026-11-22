# -*- coding: utf-8 -*-
"""Lembretes locais do Canvas: datas, fusos, vencimentos e vínculos."""
import os
from datetime import datetime, timezone

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import lembretes as L
from core.planos import arquivar, criar, atualizar, inicializar_mapa, restaurar


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def plano(tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    p = inicializar_mapa(criar("Estudos", "Revisar fotografia", "Estudos").id)
    mapa = p.mapa
    mapa["cards"].append({"id": "topico2", "tipo": "tarefa",
                          "titulo": "Tópico 2", "resumo": "Exercício",
                          "descricao": "", "status": "pendente",
                          "x": 200.0, "y": 0.0, "modelo": "estudos",
                          "estado": "", "valor": None, "acumulado": None,
                          "restrito": False, "financeiro": False})
    return atualizar(p.id, {"mapa": mapa}, p.revisao)


AGORA = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)


def test_interpretar_amanha_as_19h_no_fuso():
    horario, confirmacao = L.interpretar(
        "Amanhã às 19h me lembra de revisar este exercício",
        fuso="America/Sao_Paulo", agora=AGORA)
    assert horario.startswith("2026-11-21")
    assert "19:00" in confirmacao or "19h" in confirmacao


def test_pede_data_quando_falta(plano):
    horario, confirmacao = L.interpretar(
        "Me lembra de revisar este tópico",
        fuso="America/Sao_Paulo", agora=AGORA)
    assert horario is None
    assert "data" in confirmacao.lower() or "hora" in confirmacao.lower()


def test_criar_persistir_e_listar(plano):
    lembrete = L.criar(plano.id, "Revisar exercício",
                       "2026-11-21T22:00:00+00:00",
                       "America/Sao_Paulo", card_id="topico2")
    assert lembrete["id"] and lembrete["estado"] == "pendente"
    assert L.listar(plano.id)[0]["id"] == lembrete["id"]
    assert L.carregar(lembrete["id"])["card_id"] == "topico2"


def test_vencidos_e_aviso_unico(plano):
    lembrete = L.criar(plano.id, "Revisar", "2026-11-20T17:00:00+00:00",
                       "America/Sao_Paulo", card_id="topico2")
    agora = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
    assert [x["id"] for x in L.vencidos(agora)] == [lembrete["id"]]
    L.registrar_aviso(lembrete["id"], "2026-11-20T17:00:00+00:00")
    assert L.vencidos(agora) == []


def test_suspender_por_card_e_restaurar(plano):
    lembrete = L.criar(plano.id, "Revisar", "2026-11-21T22:00:00+00:00",
                       "America/Sao_Paulo", card_id="topico2")
    L.suspender_por_card(plano.id, "topico2")
    assert L.carregar(lembrete["id"])["estado"] == "suspenso"
    L.restaurar_por_card(plano.id, "topico2")
    assert L.carregar(lembrete["id"])["estado"] == "pendente"


def test_arquivar_e_restaurar_plano_suspende(plano):
    lembrete = L.criar(plano.id, "Revisar", "2026-11-21T22:00:00+00:00",
                       "America/Sao_Paulo")
    atual = __import__("core.planos", fromlist=["carregar"]).carregar(plano.id)
    arquivar(plano.id, atual.revisao)
    assert L.carregar(lembrete["id"])["estado"] == "suspenso"
    atual = __import__("core.planos", fromlist=["carregar"]).carregar(plano.id)
    restaurar(plano.id, atual.revisao)
    assert L.carregar(lembrete["id"])["estado"] == "pendente"


def test_adiar_concluir_cancelar(plano):
    lembrete = L.criar(plano.id, "Revisar", "2026-11-21T22:00:00+00:00",
                       "America/Sao_Paulo")
    adiado = L.adiar(lembrete["id"], "2026-11-22T22:00:00+00:00")
    assert adiado["horario"] == "2026-11-22T22:00:00+00:00"
    assert L.concluir(lembrete["id"])["estado"] == "concluido"
    assert L.cancelar(lembrete["id"])["estado"] == "cancelado"


def test_comando_por_voz_cria_no_card(plano):
    from core.comandos_lembretes import processar
    r = processar("Amanhã às 19h me lembra de revisar este exercício", "voz",
                  {"plano_id": plano.id, "card_id": "topico2",
                   "card": {"titulo": "Tópico 2"}}, agora=AGORA)
    assert r["tratado"] and r["acao"] == "criar"
    assert r["horario"].startswith("2026-11-21")
    assert r["card_id"] == "topico2"


def test_comando_pede_data_e_alvo(plano):
    from core.comandos_lembretes import processar
    r = processar("Me lembra de revisar este tópico", "texto",
                  {"plano_id": plano.id, "card_id": "topico2",
                   "card": {"titulo": "Tópico 2"}}, agora=AGORA)
    assert r["acao"] == "pendente" and "data" in r["resposta"].lower()
    sem_card = processar("Me lembra de revisar este tópico", "texto",
                         {"plano_id": plano.id, "card_id": None}, agora=AGORA)
    assert sem_card["acao"] == "sem_card"


def test_excluir_card_suspende_e_desfazer_restaura(app, plano):
    from core.interface_mapa import EditorMapa
    lembrete = L.criar(plano.id, "Revisar", "2026-11-21T22:00:00+00:00",
                       "America/Sao_Paulo", card_id="topico2")
    ed = EditorMapa()
    ed.carregar(plano)
    ed.selecionar("topico2")
    ed.excluir_selecionado()
    assert L.carregar(lembrete["id"])["estado"] == "suspenso"
    ed.desfazer()
    assert L.carregar(lembrete["id"])["estado"] == "pendente"
    ed._timer.stop()
    ed.cena.itens_cards.clear()
    ed.cena.itens_conexoes.clear()
    ed.cena.clear()
    ed.hide()
    ed.deleteLater()


def test_alvo_do_lembrete(plano):
    lembrete = L.criar(plano.id, "Revisar", "2026-11-21T22:00:00+00:00",
                       "America/Sao_Paulo", card_id="topico2")
    assert L.alvo(lembrete) == {"plano_id": plano.id, "card_id": "topico2"}
