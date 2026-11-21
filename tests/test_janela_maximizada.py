# -*- coding: utf-8 -*-
"""Janela abre maximizada (com barra de tarefas), não em tela cheia F11."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

import ui


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_preferencia_padrao_e_maximizada_com_bordas():
    assert ui.janela_sem_bordas_padrao() is False


def test_aplicar_modo_janela_nunca_usa_fullscreen(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    w = ui.MainWindow("face.png")
    for sem_bordas in (True, False):
        w.aplicar_modo_janela(sem_bordas)
        w.show()
        app.processEvents()
        assert w.janela_tela_cheia is sem_bordas
        assert not w.isFullScreen(), "F11/fullscreen não deve ser o padrão"
        assert w.windowState() & Qt.WindowState.WindowMaximized
        if sem_bordas:
            assert w.windowFlags() & Qt.WindowType.FramelessWindowHint
        else:
            assert not (w.windowFlags() & Qt.WindowType.FramelessWindowHint)
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_niaui_abre_maximizada_sem_fullscreen(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    casca = ui.NiaUI("face.png")
    app.processEvents()
    assert casca._win.janela_tela_cheia is False
    assert not casca._win.isFullScreen()
    assert casca._win.windowState() & Qt.WindowState.WindowMaximized
    assert not (casca._win.windowFlags() & Qt.WindowType.FramelessWindowHint)
    for t in casca._win.findChildren(__import__("PyQt6.QtCore", fromlist=["QTimer"]).QTimer):
        t.stop()
    casca._win.hide()
    casca._win.deleteLater()
    app.processEvents()
