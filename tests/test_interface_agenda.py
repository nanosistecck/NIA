# -*- coding: utf-8 -*-
"""Janela Agenda: botao no dock, grade mensal e acompanhamento do dia."""
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
    monkeypatch.setenv("NIA_PERFIL", "teste-ui")
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    w = ui.MainWindow("face.png")
    w.resize(1280, 820)
    w.show()
    app.processEvents()
    yield w, app
    for timer in w.findChildren(QTimer):
        timer.stop()
    janela_agenda = getattr(w, "_agenda_window", None)
    if janela_agenda is not None:
        janela_agenda.hide()
        janela_agenda.deleteLater()
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_botao_agenda_abre_janela(janela):
    w, app = janela
    botao = w.findChild(QPushButton, "agenda")
    assert botao is not None
    QTest.mouseClick(botao, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert w._agenda_window is not None and w._agenda_window.isVisible()


def test_janela_mostra_compromisso_do_dia(janela):
    w, app = janela
    agenda.criar("Reunião com João", "2026-11-27T15:00:00-03:00", "reuniao")
    w._abrir_agenda()
    app.processEvents()
    jan = w._agenda_window
    assert jan is not None
    assert jan.mes_atual.year == 2026 and jan.mes_atual.month == 11
    assert jan.dia_selecionado.day == 27
    texto = jan.txt_compromissos.toPlainText()
    assert "Reunião com João" in texto and "15:00" in texto
    assert "14:45" in texto
