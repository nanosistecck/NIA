# -*- coding: utf-8 -*-
"""Botão Salvar do Canvas: alvo confortável e gravação pelo clique real."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton, QTextEdit

import ui
from core import planos as BP


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app, tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    w = ui.MainWindow("face.png")
    w.resize(1280, 820)
    w.show()
    app.processEvents()
    plano = BP.inicializar_mapa(BP.criar("Botão salvar", "Objetivo", "Geral").id)
    w._abrir_canvas_do_plano(plano.id)
    QTest.qWait(120)
    app.processEvents()
    yield w, plano, app
    editor = getattr(w, "_canvas_editor", None)
    if editor is not None:
        editor.editor_internal._timer.stop()
        editor.editor_internal.cena.itens_cards.clear()
        editor.editor_internal.cena.itens_conexoes.clear()
        editor.editor_internal.cena.clear()
    from PyQt6.QtCore import QTimer
    for t in w.findChildren(QTimer):
        t.stop()
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_botao_salvar_no_overlay_e_grava(janela):
    w, plano, app = janela
    overlay = w._canvas_editor
    botao = overlay.findChild(QPushButton, "salvar_canvas")
    assert botao is not None, "botão Salvar deve estar visível na barra do Canvas"
    assert botao.isVisible()
    assert botao.width() >= 64 and botao.height() >= 30

    raiz = plano.mapa["raiz_id"]
    overlay.editor_internal.selecionar(raiz)
    campo = overlay.editor_internal.findChild(QTextEdit, "mapa_descricao")
    campo.setPlainText("Ideia salva pelo botão")
    app.processEvents()
    antes = BP.carregar(plano.id).revisao

    QTest.mouseClick(botao, Qt.MouseButton.LeftButton)
    app.processEvents()

    salvo = BP.carregar(plano.id)
    assert salvo.revisao == antes + 1
    assert any(c.get("descricao") == "Ideia salva pelo botão"
               for c in salvo.mapa["cards"])


def test_botao_interno_tem_alvo_confortavel(janela):
    w, plano, app = janela
    botao = w._canvas_editor.editor_internal.findChild(QPushButton, "salvar")
    assert botao.width() >= 60 and botao.height() >= 28
