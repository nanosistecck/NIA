# -*- coding: utf-8 -*-
"""Grade escura integrada ao fundo e chat maior com botão de histórico."""
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
    w.resize(1280, 820)
    w.show()
    app.processEvents()
    yield w
    for t in w.findChildren(__import__("PyQt6.QtCore", fromlist=["QTimer"]).QTimer):
        t.stop()
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_chat_maior(janela):
    assert janela._composer.width() == 620
    assert janela._composer.height() == 56


def test_botao_esconde_e_mostra_o_input(janela, app):
    botao = janela.findChild(QPushButton, "chat_inferior")
    assert botao is not None and botao.isVisible()
    assert botao.isChecked() is True
    assert janela._composer.isVisible()

    botao.click()
    app.processEvents()
    assert botao.isChecked() is False
    assert not janela._composer.isVisible()

    botao.click()
    app.processEvents()
    assert botao.isChecked() is True
    assert janela._composer.isVisible()


def test_grade_azul_escuro(janela):
    fundo = janela.centralWidget()
    assert isinstance(fundo, ui._FundoComGrade)
    assert fundo._PASSO_V == 80 and fundo._PASSO_H == 160
