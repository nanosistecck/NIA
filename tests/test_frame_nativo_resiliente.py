# -*- coding: utf-8 -*-
"""Falha ao instalar moldura nativa não pode fechar a janela/NIA."""
from __future__ import annotations

import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtWidgets import QApplication

from core import windows_frame as WF


class JanelaSemHandle:
    def winId(self):
        raise RuntimeError('sem handle nativo')

    def centralWidget(self):
        return None

    def layout(self):
        return None


def test_sem_handle_retorna_false(monkeypatch):
    """Quebra: winId() fora do try propagava exceção ao clique do dock."""
    monkeypatch.setattr(QApplication, 'platformName', staticmethod(lambda: 'windows'))
    frame = WF.WindowsFrame(JanelaSemHandle())
    assert frame.install() is False
    assert frame.failed is True
