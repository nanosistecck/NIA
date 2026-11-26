# -*- coding: utf-8 -*-
"""Atalho da página Geral para a Central de Aplicativos."""
import os
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtWidgets import QApplication, QPushButton

from core.config_dashboard import ConfigDashboardWindow
from core.config_preferencias import ConfigService
from core.personas import ESCOLHA_PADRAO


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_botao_geral_abre_central(app, tmp_path):
    host = SimpleNamespace(abrir_central=Mock(), abrir_manual=Mock())
    persona = tmp_path / 'persona.json'
    persona.write_text(__import__('json').dumps(dict(ESCOLHA_PADRAO)), encoding='utf-8')
    servico = ConfigService(host=host, persona_path=persona,
                            dashboard_path=tmp_path / 'dashboard.json',
                            interface_path=tmp_path / 'interface.json')
    janela = ConfigDashboardWindow(servico)
    janela.show()
    janela.activate_page('geral')
    app.processEvents()
    botoes = [b for b in janela.findChildren(QPushButton)
              if b.text() == 'Abrir Central de Aplicativos']
    assert len(botoes) == 1
    botoes[0].click()
    host.abrir_central.assert_called_once_with(True)
    manuais = [b for b in janela.findChildren(QPushButton)
               if b.text() == 'Abrir manual de uso']
    assert len(manuais) == 1
    manuais[0].click()
    host.abrir_manual.assert_called_once_with()
    janela.close(); janela.deleteLater(); app.processEvents()
