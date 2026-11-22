# -*- coding: utf-8 -*-
"""Dock estilo prancha: ícone central, sem textos, botões 46 px e vidro."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

import ui
from core.interface_canvas import VerticalDock


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    w = ui.MainWindow("face.png")
    w.resize(1280, 820)
    w.show()
    app.processEvents()
    yield w
    for t in w.findChildren(__import__("PyQt6.QtCore", fromlist=["QTimer"]).QTimer):
        t.stop()
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_botoes_46px(janela):
    botao = janela._right_panel.buttons["globo"]
    assert botao.width() == 46 and botao.height() == 46


def test_dock_vidro_com_borda_ciano(janela):
    dock = janela._right_panel
    assert isinstance(dock, VerticalDock)
    estilo = dock.styleSheet()
    assert "rgba(25,211,243,55)" in estilo
    assert "border-radius:22px" in estilo


def test_rotulos_continuam_nos_botoes(janela):
    # A informação não se perde: texto e tooltip continuam no widget.
    botao = janela._right_panel.buttons["globo"]
    assert "GLOBO" in botao.text() or button_tooltip(botao)


def button_tooltip(botao):
    return botao.toolTip() or ""
