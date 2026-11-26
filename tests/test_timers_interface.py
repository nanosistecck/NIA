# -*- coding: utf-8 -*-
"""Timer de lembretes pertence à janela e nunca cria disparos órfãos."""
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

import ui
from core import lembretes as _lembretes


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_timer_e_filho_da_janela_e_rearmado(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(ui.MainWindow, '_check_config', lambda self: True)
    for chave in ('NIA_PLANOS_DIR', 'NIA_AGENDA', 'NIA_PERFIL'):
        monkeypatch.setenv(chave, str(tmp_path / chave))
    monkeypatch.setattr(_lembretes, 'vencidos', lambda: [])
    futuro = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    monkeypatch.setattr(_lembretes, 'proximo', lambda: {'horario': futuro})

    w = ui.MainWindow('face.png')
    w.show(); app.processEvents()
    try:
        timer = w._lembrete_timer
        assert timer.parent() is w
        assert timer.isActive()
        antes = len(w.findChildren(QTimer))
        w._reagendar_lembretes()
        app.processEvents()
        assert len(w.findChildren(QTimer)) == antes
        assert timer.isActive()
    finally:
        for t in w.findChildren(QTimer):
            t.stop()
        w.hide(); w.deleteLater(); app.processEvents()
