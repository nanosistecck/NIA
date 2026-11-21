# -*- coding: utf-8 -*-
"""Núcleo deve ir para o canto inferior direito em toda abertura do Canvas."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

import ui
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
    plano = inicializar_mapa(criar("Núcleo", "Objetivo", "Geral").id)
    yield w, plano
    editor = getattr(w, "_canvas_editor", None)
    if editor is not None:
        editor.editor_internal._timer.stop()
        editor.editor_internal.cena.itens_cards.clear()
        editor.editor_internal.cena.itens_conexoes.clear()
        editor.editor_internal.cena.clear()
    for timer in w.findChildren(QTimer):
        timer.stop()
    w.hide()
    w.deleteLater()
    app.processEvents()


def _assentar(app, ms=350):
    QTest.qWait(ms)
    app.processEvents()


def _posicoes(w):
    stage = w._stage
    nucleo = stage.hud_stack.geometry()
    editor = w._canvas_editor.geometry()
    return stage, nucleo, editor


def test_nucleo_no_canto_inferior_direito_ao_abrir(window, app):
    w, plano = window
    assert w._abrir_canvas_do_plano(plano.id)
    _assentar(app)
    stage, nucleo, _editor = _posicoes(w)
    assert stage.anchor == "bottom-right"
    assert nucleo.x() == stage.width() - nucleo.width()
    assert nucleo.y() == stage.height() - nucleo.height()


def test_nucleo_no_canto_mesmo_com_brief_visivel(window, app):
    w, plano = window
    w._brief_sig.emit({"tipo": "hora", "token": 901})
    _assentar(app, 80)
    assert w._stage.brief_host.isVisible()
    assert w._abrir_canvas_do_plano(plano.id)
    _assentar(app)
    stage, nucleo, _editor = _posicoes(w)
    assert nucleo.x() == stage.width() - nucleo.width()
    assert nucleo.y() == stage.height() - nucleo.height()


def test_overlay_reserva_espaco_para_o_nucleo(window, app):
    w, plano = window
    assert w._abrir_canvas_do_plano(plano.id)
    _assentar(app)
    _stage, nucleo, editor = _posicoes(w)
    assert editor.right() <= nucleo.left() + 4, (
        f"editor termina em {editor.right()}, núcleo começa em {nucleo.left()}")


def test_reabrir_posiciona_novamente(window, app):
    w, plano = window
    for _ in range(3):
        assert w._abrir_canvas_do_plano(plano.id)
        _assentar(app, 300)
        stage, nucleo, editor = _posicoes(w)
        assert nucleo.x() == stage.width() - nucleo.width()
        assert nucleo.y() == stage.height() - nucleo.height()
        assert editor.right() <= nucleo.left() + 4
        w._canvas_editor.voltar.emit()
        app.processEvents()
        _assentar(app, 300)
