# -*- coding: utf-8 -*-
"""Janela maximizada com controles nativos do Windows, sem botões próprios."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QPushButton

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


def test_sem_botoes_proprios(janela):
    for nome in ("janela_minimizar", "janela_maximizar", "janela_fechar"):
        assert janela.findChild(QPushButton, nome) is None


def test_maximizada_com_controles_nativos(janela):
    assert janela.isMaximized()
    assert not janela.isFullScreen()
    assert not (janela.windowFlags() & Qt.WindowType.FramelessWindowHint)


def test_preferencia_padrao_usa_controles_nativos():
    assert ui.janela_sem_bordas_padrao() is False
