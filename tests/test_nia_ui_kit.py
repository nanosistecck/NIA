# -*- coding: utf-8 -*-
"""Fase 17 — UI Kit reutilizando tema e componentes PyQt6 da NIA."""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtWidgets import QApplication

from core import nia_ui_kit as UK
from core import tema


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_indicador_aceita_estados_sem_recriar_widget(app):
    """Quebra: não existia componente de estado padronizado."""
    widget = UK.IndicadorEstado('Pronto')
    for estado in ('normal', 'carregando', 'erro', 'desativado'):
        widget.definir_estado(estado)
        assert widget.estado == estado


def test_estilo_usa_tokens_do_tema_da_nia(app):
    """Quebra: componentes usavam cores arbitrárias fora da identidade NIA."""
    widget = UK.IndicadorEstado('Erro')
    widget.definir_estado('erro')
    assert tema.cor(tema.ORIGINAL['vermelho']) in widget.styleSheet()


def test_botao_desativado_nao_emite_acao(app):
    """Quebra: estado desativado ainda permitia acionamento."""
    botao = UK.BotaoAcao('Executar')
    chamadas = []
    botao.acionado.connect(lambda: chamadas.append(1))
    botao.setEnabled(False)
    botao.click()
    assert chamadas == []


def test_painel_compacto_nao_tem_overflow(app):
    """Quebra: painel não respeitava viewport compacta."""
    painel = UK.PainelEstado('Rotina', 'Próxima às 09:00')
    painel.resize(320, 240)
    assert painel.minimumSizeHint().width() <= 320
    assert painel.minimumSizeHint().height() <= 240


def test_captura_offscreen_da_janela_de_teste(app):
    """Quebra: nenhuma evidência visual do componente foi produzida."""
    painel = UK.PainelEstado('Rotina', 'Próxima às 09:00')
    painel.resize(720, 360)
    painel.definir_estado('carregando')
    app.processEvents()
    destino = Path('logs') / 'captura_ui_kit.png'
    destino.parent.mkdir(parents=True, exist_ok=True)
    assert painel.grab().save(str(destino)) is True
    assert destino.stat().st_size > 1000
