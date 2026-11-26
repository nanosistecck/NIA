# -*- coding: utf-8 -*-
"""Card 'Próximo compromisso' no Canvas principal da janela inicial."""
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton

import ui
from core import agenda


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app, tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "planos"))
    monkeypatch.setenv("NIA_AGENDA", str(tmp_path / "agenda.json"))
    monkeypatch.setenv("NIA_PERFIL", "teste-card")
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    agenda.criar("Reunião com João", "2026-11-27T15:00:00-03:00", "reuniao")
    w = ui.MainWindow("face.png")
    w.resize(1280, 820)
    w.show()
    app.processEvents()
    casca = object.__new__(ui.NiaUI)
    casca._win = w
    yield w, casca, app, tmp_path
    for timer in w.findChildren(QTimer):
        timer.stop()
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_card_nao_aparece_sem_compromisso(app, tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "planos"))
    monkeypatch.setenv("NIA_AGENDA", str(tmp_path / "agenda.json"))
    monkeypatch.setenv("NIA_PERFIL", "sem-compromisso")
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    w = ui.MainWindow("face.png")
    w.resize(1280, 820)
    w.show()
    app.processEvents()
    assert not w._stage.agenda_visivel()
    w.hide(); w.deleteLater(); app.processEvents()


def test_card_atualiza_apos_criacao_por_chat(janela):
    w, casca, app, _ = janela
    agenda.criar("Segunda reunião", "2026-11-28T10:00:00-03:00", "reuniao")
    w._atualizar_cartao_agenda()
    app.processEvents()
    assert "Reunião com João" in w._stage.agenda_texto.text()


def test_card_mostra_proximo_e_fecha(janela):
    w, casca, app, tmp = janela
    stage = w._stage
    assert stage.agenda_visivel()
    assert "Reunião com João" in stage.agenda_texto.text()
    botao = stage.findChild(QPushButton, "AgendaFechar")
    assert botao is not None
    QTest.mouseClick(botao, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert not stage.agenda_visivel()
    dados = json.loads((tmp / "interface.json").read_text(encoding="utf-8"))
    assert dados["cards"]["agenda"] is False
    casca.mostrar_agenda()
    app.processEvents()
    assert stage.agenda_visivel()
