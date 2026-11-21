# -*- coding: utf-8 -*-
"""Barra sem texto nem ícone: o Windows não deve mostrar 'python'."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

import ui


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_nome_da_aplicacao_nao_e_python(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    w = ui.MainWindow("face.png")
    w.aplicar_modo_janela(False)
    app.processEvents()
    assert QApplication.applicationName() != "python"
    for t in w.findChildren(__import__("PyQt6.QtCore", fromlist=["QTimer"]).QTimer):
        t.stop()
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_janela_sem_titulo_e_icone(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    w = ui.MainWindow("face.png")
    w.aplicar_modo_janela(False)
    w.show()
    app.processEvents()
    assert w.windowTitle() == ""
    assert w.windowIcon().isNull()
    for t in w.findChildren(__import__("PyQt6.QtCore", fromlist=["QTimer"]).QTimer):
        t.stop()
    w.hide()
    w.deleteLater()
    app.processEvents()
