# -*- coding: utf-8 -*-
"""Catálogo das ferramentas do dock expostas na bandeja."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtWidgets import QApplication

import core.registro_aplicativos as RA

ESPERADOS = {
    'mute', 'so_nome', 'interrupt', 'whatsapp', 'remote', 'webcam',
    'cowork', 'computer_use', 'segundo_plano', 'globo', 'planos', 'agenda',
    'central', 'config', 'system', 'skill_secretaria',
    'skill_buscar_arquivos', 'skill_resumo_dia',
}


@pytest.fixture(autouse=True)
def registro_isolado(monkeypatch):
    monkeypatch.setattr(RA, '_DESCRITORS', {})
    monkeypatch.setattr(RA, '_PROVEDOR_FERRAMENTAS', None)
    monkeypatch.setattr(RA, '_PROVEDOR_DISPONIBILIDADE', None)


def test_bandeja_tem_as_18_entradas_do_dock_sem_duplicatas():
    from core.registro_nativo import registrar_nativos
    registrar_nativos()
    ids = [i.id for i in RA.buscar()]
    assert set(ids) == ESPERADOS
    assert len(ids) == 18
    assert 'canvas' not in ids


def test_icones_novos_das_habilidades():
    from core.interface_canvas import _ICONS, icon, vector_icon
    app = QApplication.instance() or QApplication([])
    for nome in ('secretaria', 'buscar_arquivos', 'resumo'):
        assert nome in _ICONS
        assert vector_icon(nome).isValid()
    assert not icon('inexistente-para-teste').isNull()
