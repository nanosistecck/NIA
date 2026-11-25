# -*- coding: utf-8 -*-
"""Ícones próprios dos apps fixáveis na bandeja."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtWidgets import QApplication

import core.registro_aplicativos as RA


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_nativos_usam_icone_da_propria_ferramenta(monkeypatch):
    monkeypatch.setattr(RA, '_DESCRITORS', {})
    from core.registro_nativo import registrar_nativos
    registrar_nativos()
    assert RA.por_id('canvas').icone == 'canvas'
    assert RA.por_id('agenda').icone == 'agenda'


def test_icones_canvas_e_agenda_sao_vetoriais_e_distintos(app):
    from core.interface_canvas import _ICONS, vector_icon
    assert 'canvas' in _ICONS and 'agenda' in _ICONS
    assert _ICONS['canvas'] != _ICONS['agenda']
    assert vector_icon('canvas').isValid()
    assert vector_icon('agenda').isValid()


def test_icone_desconhecido_cai_no_fallback(app):
    from core.interface_canvas import icon
    assert not icon('inexistente').isNull()
