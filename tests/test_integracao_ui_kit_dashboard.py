# -*- coding: utf-8 -*-
"""Fase 17 integrada ao dashboard real, com captura da janela."""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QWidget

from core.config_dashboard import ConfigDashboardWindow
from core.config_preferencias import ConfigService
from core.personas import ESCOLHA_PADRAO


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def _janela(app, tmp_path):
    persona = tmp_path / 'persona.json'
    persona.write_text(json.dumps(dict(ESCOLHA_PADRAO, personagem='sulafat')),
                       encoding='utf-8')
    servico = ConfigService(
        host=None, persona_path=persona,
        dashboard_path=tmp_path / 'dashboard_config.json',
        interface_path=tmp_path / 'interface.json')
    janela = ConfigDashboardWindow(servico, refresh_on_open=False)
    janela.activate_page('geral')
    app.processEvents()
    return janela


def test_pagina_geral_tem_indicador_do_ui_kit(app, tmp_path):
    """Quebra: UI Kit nao aparecia em nenhuma tela real."""
    janela = _janela(app, tmp_path)
    try:
        indicadores = [w for w in janela.findChildren(QWidget)
                       if w.objectName() == 'nia_ui_kit_indicador']
        assert len(indicadores) == 1
        assert indicadores[0].text() == 'NIA pronta'
    finally:
        janela.close()


def test_captura_do_dashboard_com_ui_kit(app, tmp_path):
    """Quebra: nao havia evidencia visual da integracao."""
    janela = _janela(app, tmp_path)
    try:
        janela.resize(1000, 700)
        app.processEvents()
        destino = Path('logs') / 'captura_dashboard_ui_kit.png'
        destino.parent.mkdir(parents=True, exist_ok=True)
        assert janela.grab().save(str(destino)) is True
        assert destino.stat().st_size > 5000
    finally:
        janela.close()


def test_tab_percorre_controles_da_pagina_geral(app, tmp_path):
    """Quebra: navegação por teclado não foi validada na janela real."""
    janela = _janela(app, tmp_path)
    try:
        janela.show()
        janela.setFocus()
        app.processEvents()
        vistos = set()
        for _ in range(10):
            QTest.keyClick(janela, Qt.Key.Key_Tab)
            app.processEvents()
            foco = QApplication.focusWidget()
            if foco is not None:
                vistos.add(foco.objectName() or foco.metaObject().className())
                assert janela.isAncestorOf(foco)
        assert len(vistos) >= 2
    finally:
        janela.close()


def test_viewport_compacto_sem_overflow_e_captura(app, tmp_path):
    """Quebra: telas pequenas não tinham evidência de layout."""
    janela = _janela(app, tmp_path)
    try:
        janela.resize(640, 480)
        app.processEvents()
        assert janela.minimumSizeHint().width() <= 640
        destino = Path('logs') / 'captura_dashboard_compacto.png'
        destino.parent.mkdir(parents=True, exist_ok=True)
        assert janela.grab().save(str(destino)) is True
        assert destino.stat().st_size > 3000
    finally:
        janela.close()
