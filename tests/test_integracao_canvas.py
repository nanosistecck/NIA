# -*- coding: utf-8 -*-
"""Integração do editor Canvas com dock, núcleo e lista de planos."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox, QPushButton

import ui
from core import planos as BP
from core.planos import criar, inicializar_mapa


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    w = ui.MainWindow("face.png")
    w.resize(1280, 820)
    w.show()
    app.processEvents()
    plano = inicializar_mapa(criar("Plano integrado", "Objetivo", "Projeto").id)
    yield w, plano
    editor = getattr(w, "_canvas_editor", None)
    if editor is not None:
        interna = editor.editor_internal
        interna._timer.stop()
        interna.cena.itens_cards.clear()
        interna.cena.itens_conexoes.clear()
        interna.cena.clear()
    for timer in w.findChildren(QTimer):
        timer.stop()
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_abrir_editor_recolhe_dock_e_restaura_sem_persistir(window, app):
    w, plano = window
    dock = w._right_panel
    expanded_antes = dock.expanded
    preferencia_antes = dock.preferences.data.get("expanded")
    anchor_antes = w._stage.anchor

    w._abrir_planos()
    assert w._planos_window is not None
    assert w._abrir_canvas_do_plano(plano.id)

    assert dock.expanded is False
    assert dock.preferences.data.get("expanded") == preferencia_antes
    assert dock.expanded != expanded_antes or expanded_antes is False
    assert w._stage.anchor == "bottom-right"
    assert getattr(w._stage, "_canvas_editor_ativo", False) is True
    editor = w._canvas_editor
    assert editor.isVisible()
    assert plano.id in editor.contexto()["plano_id"]

    botao = editor.findChild(QPushButton, "voltar_planos")
    botao.click()
    app.processEvents()

    assert dock.expanded == expanded_antes
    assert dock.preferences.data.get("expanded") == preferencia_antes
    assert w._stage.anchor == anchor_antes
    assert getattr(w._stage, "_canvas_editor_ativo", False) is False
    assert w._planos_window.isVisible()
    assert w._planos_window.plano_selecionado_id == plano.id


def test_saida_com_falha_de_gravacao_nao_descarta(window, app, monkeypatch):
    w, plano = window
    w._abrir_planos()
    w._abrir_canvas_do_plano(plano.id)
    editor = w._canvas_editor
    editor.editor_internal.criar_card("Alteração pendente")
    assert editor.mudancas_pendentes

    def falhar(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr("core.interface_mapa.atualizar", falhar)
    monkeypatch.setattr(
        ui, "_perguntar_salvar_mapa",
        lambda *args, **kwargs: QMessageBox.StandardButton.Cancel)
    editor.findChild(QPushButton, "voltar_planos").click()
    app.processEvents()
    assert editor.isVisible()
    assert editor.mudancas_pendentes


def test_wrapper_nia_abrir_plano_e_contexto(window, app):
    w, plano = window
    casca = object.__new__(ui.NiaUI)
    casca._win = w
    casca.abrir_plano(plano.id)
    QTest.qWait(50)
    app.processEvents()
    assert w._canvas_editor.isVisible()
    contexto = casca.contexto_canvas()
    assert contexto["plano_id"] == plano.id
