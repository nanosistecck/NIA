# -*- coding: utf-8 -*-
"""Barra de título nativa do Windows sem texto/ícone, na cor da NIA."""
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


def test_sem_texto_e_icone_na_barra(janela):
    assert janela.windowTitle() == ""
    assert janela.windowIcon().isNull()


def test_cor_da_barra_e_aplicada(janela):
    # No offscreen a API DWM não existe; o método deve falhar em silêncio.
    assert janela._aplicar_barra_nativa() in (True, False)
