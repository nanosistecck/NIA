# -*- coding: utf-8 -*-
"""Canvas reserva o rodapé e enquadra os cards sem sobrepor controles."""
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


def _assentar(app, ms=700):
    QTest.qWait(ms)
    app.processEvents()


def _posicoes(w):
    stage = w._stage
    nucleo = stage.hud_stack.geometry()
    editor = w._canvas_editor.geometry()
    return stage, nucleo, editor


@pytest.mark.parametrize("largura", [960, 1280, 1600])
def test_rodape_sem_sobreposicoes(window, app, largura):
    w, plano = window
    w.resize(largura, 820)
    limites = (w._composer.minimumSize(), w._composer.maximumSize())
    assert w._abrir_canvas_do_plano(plano.id)
    _assentar(app, 80)
    editor = w._canvas_editor
    assert not w._composer.isVisible()
    assert not w._btn_chat_abajo.isVisible()
    controles = [editor.editor_internal, editor.editor_internal.zoom_bar,
                 editor.navegar, editor.estado_nia, editor.chat_toggle,
                 w._stage.hud_stack, w._composer]
    geometrias = [widget.geometry() for widget in controles]
    editor.chat_toggle.click()
    app.processEvents()
    assert w._composer.isVisible()
    assert editor.chat_toggle.y() - (w._composer.y() + w._composer.height()) == 10
    widgets = [w._stage.hud_stack, w._composer, editor.estado_nia,
               editor.navegar, editor.editor_internal.zoom_bar]
    if editor.chat_toggle.isVisible():
        widgets.append(editor.chat_toggle)
    for i, widget in enumerate(widgets):
        assert editor.rect().contains(widget.geometry())
        assert not editor.editor_internal.geometry().intersects(widget.geometry())
        for outro in widgets[i+1:]:
            assert not widget.geometry().intersects(outro.geometry())
    assert w._composer.width() == min(620, max(240, editor.width()-2*max(200, editor.editor_internal.zoom_bar.width()+30)))
    assert w._composer.height() == 56
    antes = w._stage.hud_stack.geometry()
    w._stage.arrange(False)
    assert w._stage.hud_stack.geometry() == antes
    assert [widget.geometry() for widget in controles] == geometrias
    editor.chat_toggle.click()
    app.processEvents()
    assert not w._composer.isVisible()
    assert [widget.geometry() for widget in controles] == geometrias
    w._canvas_editor.voltar.emit()
    app.processEvents()
    assert (w._composer.minimumSize(), w._composer.maximumSize()) == limites


def test_cards_abrem_enquadrados_no_viewport(window, app):
    w, plano = window
    assert w._abrir_canvas_do_plano(plano.id)
    _assentar(app, 80)
    view = w._canvas_editor.editor_internal._view
    cena = view.scene().itemsBoundingRect()
    centro = view.mapToScene(view.viewport().rect().center())
    assert abs(centro.x() - cena.center().x()) < 8
    assert abs(centro.y() - cena.center().y()) < 8
    visivel = view.mapToScene(view.viewport().rect()).boundingRect()
    assert visivel.contains(cena)


def test_reabrir_mantem_layout(window, app):
    w, plano = window
    for _ in range(3):
        assert w._abrir_canvas_do_plano(plano.id)
        _assentar(app, 80)
        editor = w._canvas_editor
        assert not editor.editor_internal.geometry().intersects(w._stage.hud_stack.geometry())
        assert w._composer.width() == 620
        assert not w._composer.isVisible()
        editor.chat_toggle.click()
        app.processEvents()
        assert w._composer.isVisible()
        editor.chat_toggle.click()
        assert not w._composer.isVisible()
        editor.voltar.emit()
        app.processEvents()
