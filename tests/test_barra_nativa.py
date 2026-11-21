# -*- coding: utf-8 -*-
"""Quadro DWM com controles nativos e identidade preservada."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

import ui


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    w = ui.MainWindow("face.png")
    w.aplicar_modo_janela(False)
    w.show()
    app.processEvents()
    yield w
    for t in w.findChildren(__import__("PyQt6.QtCore", fromlist=["QTimer"]).QTimer):
        t.stop()
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_controles_nativos_e_maximizado(janela):
    assert not (janela.windowFlags() & Qt.WindowType.FramelessWindowHint)
    assert janela.isMaximized()
    assert not janela.isFullScreen()


def test_preserva_identidade_da_janela(janela):
    assert janela.windowTitle() == "NIA"
    from PyQt6.QtGui import QIcon
    janela.setWindowIcon(QIcon(str(ui._app_icon_path())))
    antes = janela.windowIcon().cacheKey()
    janela._aplicar_barra_nativa()
    assert janela.windowIcon().cacheKey() == antes


def test_offscreen_mantem_moldura_padrao(janela):
    assert janela._aplicar_barra_nativa() is False
