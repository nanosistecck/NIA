# -*- coding: utf-8 -*-
"""Topo compacto: logo menor, título N.I.A e status reduzido."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

import ui


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_topo_compacto(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    w = ui.MainWindow("face.png")
    app.processEvents()
    marca = next(x for x in w.findChildren(ui._MarcaNia))
    assert marca.width() == 36 and marca.height() == 36
    assert w._lbl_titulo_topo.text() == "N.I.A"
    assert w._lbl_titulo_topo.font().pointSize() <= 16
    header = w._lbl_titulo_topo.parentWidget()
    assert header.height() <= 44
    for t in w.findChildren(__import__("PyQt6.QtCore", fromlist=["QTimer"]).QTimer):
        t.stop()
    w.hide(); w.deleteLater(); app.processEvents()
