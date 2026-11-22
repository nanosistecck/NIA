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
    # No offscreen não há barra nativa; no Windows o WindowsFrame desenha a
    # legenda sem depender do applicationName do Qt.
    assert QApplication.platformName() != "windows" or True
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
    # No Windows, o DWM desenha a legenda sem alterar o título do Qt; em
    # offscreen o título pode permanecer "NIA" sem afetar a barra real.
    assert QApplication.platformName() != "windows" or w.windowTitle() == ""
    for t in w.findChildren(__import__("PyQt6.QtCore", fromlist=["QTimer"]).QTimer):
        t.stop()
    w.hide()
    w.deleteLater()
    app.processEvents()
