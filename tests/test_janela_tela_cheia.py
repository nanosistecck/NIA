# -*- coding: utf-8 -*-
"""Controles da janela maximizada: bordas opcionais, sem F11 por padrão."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMenu

import ui
from core.interface_canvas import DockPreferences


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_preferencia_tela_cheia_padrao(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    assert ui.janela_sem_bordas_padrao() is False
    ui.salvar_preferencia_janela(tmp_path / "interface.json", False)
    assert ui.janela_sem_bordas(tmp_path / "interface.json") is False
    ui.salvar_preferencia_janela(tmp_path / "interface.json", True)
    assert ui.janela_sem_bordas(tmp_path / "interface.json") is True


def test_janela_abre_em_tela_cheia(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui, "_TESTE_JANELA", True)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    w = ui.MainWindow("face.png")
    w.aplicar_modo_janela(True)
    w.show()
    app.processEvents()
    assert w.janela_tela_cheia is True
    assert w.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert not w.isFullScreen()
    assert w.windowState() & Qt.WindowState.WindowMaximized
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_preferencia_com_bordas_nao_entra_tela_cheia(app, tmp_path, monkeypatch):
    arquivo = tmp_path / "interface.json"
    ui.salvar_preferencia_janela(arquivo, False)
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui, "_TESTE_JANELA", True)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    w = ui.MainWindow("face.png")
    w.aplicar_modo_janela(False)
    w.show()
    app.processEvents()
    assert w.janela_tela_cheia is False
    assert not (w.windowFlags() & Qt.WindowType.FramelessWindowHint)
    assert not w.isFullScreen()
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_menu_contexto_tem_acoes(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui, "_TESTE_JANELA", True)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    w = ui.MainWindow("face.png")
    w.show()
    app.processEvents()
    menu = w._construir_menu_janela()
    assert isinstance(menu, QMenu)
    rotulos = [a.text() for a in menu.actions()]
    assert any("Minimizar" in r for r in rotulos)
    assert any("Maximizar" in r or "Tela cheia" in r for r in rotulos)
    assert any("Restaurar" in r or "Reduzir" in r for r in rotulos)
    w.hide()
    w.deleteLater()
    app.processEvents()
