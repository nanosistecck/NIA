# -*- coding: utf-8 -*-
"""Interface dos lembretes: gerenciador e retomada do card correto."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton

import ui
from core import lembretes as L
from core.planos import atualizar, criar, inicializar_mapa


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    w = ui.MainWindow("face.png")
    w.resize(1280, 820)
    w.show()
    app.processEvents()
    plano = inicializar_mapa(criar("Estudos", "Revisar", "Estudos").id)
    mapa = plano.mapa
    mapa["cards"].append({"id": "alvo", "tipo": "tarefa", "titulo": "Tópico 2",
                          "resumo": "", "descricao": "", "status": "pendente",
                          "x": 200.0, "y": 0.0, "modelo": "estudos",
                          "estado": "", "valor": None, "acumulado": None,
                          "restrito": False, "financeiro": False})
    atualizar(plano.id, {"mapa": mapa}, plano.revisao)
    yield w, plano
    editor = getattr(w, "_canvas_editor", None)
    if editor is not None:
        editor.editor_internal._timer.stop()
        editor.editor_internal.cena.itens_cards.clear()
        editor.editor_internal.cena.itens_conexoes.clear()
        editor.editor_internal.cena.clear()
    for timer in w.findChildren(QTimer):
        timer.stop()
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_botao_lembretes_e_definir_no_canvas(window):
    w, plano = window
    w._abrir_planos()
    assert w._planos_window.findChild(QPushButton, "lembretes") is not None
    w._abrir_canvas_do_plano(plano.id)
    assert w._canvas_editor.findChild(QPushButton, "definir_lembrete") is not None


def test_abrir_lembrete_seleciona_plano_e_card(window, app):
    w, plano = window
    lembrete = L.criar(plano.id, "Revisar tópico",
                       "2026-11-21T22:00:00+00:00", "America/Sao_Paulo",
                       card_id="alvo")
    casca = object.__new__(ui.NiaUI)
    casca._win = w
    alvo = L.alvo(lembrete)
    casca.abrir_lembrete(alvo["plano_id"], alvo["card_id"])
    QTest.qWait(80)
    app.processEvents()
    assert w._canvas_editor.isVisible()
    assert w._canvas_editor.card_selecionado_id == "alvo"
