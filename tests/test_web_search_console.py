# -*- coding: utf-8 -*-
"""Pesquisa online não pode quebrar por emoji em console cp1252."""
from __future__ import annotations

import io
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from actions import web_search as WS


class StreamCp1252(io.StringIO):
    """Simula console Windows que só aceita cp1252."""

    def write(self, texto):
        str(texto).encode('cp1252')
        return super().write(str(texto))


def test_web_search_sobrevive_a_console_cp1252(monkeypatch):
    """Quebra: print com 🔍 gerava UnicodeEncodeError e 'Search failed'."""
    monkeypatch.setattr(WS, '_search', lambda query: 'resultado real')
    saida = StreamCp1252()
    monkeypatch.setattr(sys, 'stdout', saida)
    assert WS.web_search({'query': 'teste', 'mode': 'search'}) == 'resultado real'


def test_web_search_nao_imprime_emoji(monkeypatch):
    """Quebra: mensagens de log com emoji não são portáveis no Windows."""
    monkeypatch.setattr(WS, '_search', lambda query: 'ok')
    saida = io.StringIO()
    monkeypatch.setattr(sys, 'stdout', saida)
    WS.web_search({'query': 'teste'})
    texto = saida.getvalue()
    assert '🔍' not in texto and '⚠️' not in texto and '❌' not in texto
