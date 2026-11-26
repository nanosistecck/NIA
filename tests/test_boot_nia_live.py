# -*- coding: utf-8 -*-
"""Boot completo de NiaLive em condições seguras e comparáveis."""
from __future__ import annotations

import os
import threading
import time
from unittest.mock import Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import psutil
import pytest

import main


@pytest.fixture
def isolado(tmp_path, monkeypatch):
    monkeypatch.setattr(main.Path, 'home', classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(main, '_aquecer_imports', lambda *args, **kwargs: None)
    monkeypatch.setattr(main.NiaLive, '_configurar_agendador_resumo', lambda self: None)
    return tmp_path


def test_nia_live_construi_com_pontes_e_sem_threads_extras(isolado):
    """Quebra: inicialização completa exigia dispositivo/rede para ser medida."""
    antes = {t.name for t in threading.enumerate()}
    ui = Mock()
    t0 = time.perf_counter()
    motor = main.NiaLive(ui)
    elapsed = time.perf_counter() - t0
    depois = {t.name for t in threading.enumerate()}
    assert elapsed < 5.0
    assert not (depois - antes)
    assert callable(ui.on_text_command)
    assert motor._contexto_ferramentas is not None


def test_boot_registra_memoria_e_tempo(isolado):
    """Quebra: nao havia evidencia numerica do boot do motor."""
    ui = Mock()
    processo = psutil.Process()
    rss0 = processo.memory_info().rss
    t0 = time.perf_counter()
    main.NiaLive(ui)
    elapsed = time.perf_counter() - t0
    rss1 = processo.memory_info().rss
    assert elapsed >= 0
    assert (rss1 - rss0) / 1048576 < 200
