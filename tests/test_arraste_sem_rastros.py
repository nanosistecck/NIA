# -*- coding: utf-8 -*-
"""Arraste de cards sem rastros gráficos (regiões pintadas dentro do boundingRect)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QRectF
from PyQt6.QtWidgets import QApplication, QGraphicsView

from core import planos as BP
from core.interface_mapa import CardItem, EditorMapa, _CARD_H, _CARD_W


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_boundingrect_contem_sombra_e_contorno():
    item = CardItem({"id": "a", "titulo": "A"})
    br = item.boundingRect()
    corpo = QRectF(0, 0, _CARD_W, _CARD_H)
    sombra = corpo.translated(0, 4)
    contorno = corpo.adjusted(-5, -5, 5, 5)
    assert br.contains(sombra), (br, sombra)
    assert br.contains(contorno), (br, contorno)


def test_view_repinta_completo_durante_arraste(app):
    editor = EditorMapa()
    plano = BP.inicializar_mapa(BP.criar("Arraste", "Obj", "Geral").id)
    editor.carregar(plano)
    assert editor._view.viewportUpdateMode() == QGraphicsView.ViewportUpdateMode.FullViewportUpdate
    editor._timer.stop()
    editor.cena.itens_cards.clear()
    editor.cena.itens_conexoes.clear()
    editor.cena.clear()
    editor.hide()
    editor.deleteLater()
    app.processEvents()
