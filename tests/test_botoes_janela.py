# -*- coding: utf-8 -*-
"""Botões próprios da janela sem bordas: minimizar, maximizar, fechar."""
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
    w.aplicar_modo_janela(True)
    w.show()
    app.processEvents()
    yield w
    for t in w.findChildren(__import__("PyQt6.QtCore", fromlist=["QTimer"]).QTimer):
        t.stop()
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_botoes_proprios_existem_no_cabecalho(janela):
    for nome in ("janela_minimizar", "janela_maximizar", "janela_fechar"):
        botao = janela.findChild(QPushButton, nome)
        assert botao is not None, nome
        assert botao.isVisible()
        assert botao.width() >= 28 and botao.height() >= 24


def test_sem_bordas_e_maximizada_com_barra_de_tarefas(janela):
    assert janela.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert not janela.isFullScreen()
    assert janela.windowState() & Qt.WindowState.WindowMaximized


def test_botao_maximizar_alterna_estado(janela, app, monkeypatch):
    chamados = []
    monkeypatch.setattr(janela, "showMaximized", lambda: chamados.append("max"))
    monkeypatch.setattr(janela, "showNormal", lambda: chamados.append("normal"))
    botao = janela.findChild(QPushButton, "janela_maximizar")
    botao.click()
    app.processEvents()
    botao.click()
    app.processEvents()
    assert chamados == ["normal", "max"]
