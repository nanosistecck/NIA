# -*- coding: utf-8 -*-
"""Inicialização controlada da aplicação, sem rede, áudio ou janelas reais."""
from __future__ import annotations

import asyncio
import os
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

import main
from core import rotinas


def test_main_inicializa_e_encerra_sem_dispositivos(monkeypatch, tmp_path, capsys):
    """Quebra: não havia prova de inicialização/encerramento controlado."""
    ui = Mock()
    ui.root.mainloop = lambda: None
    ui.wait_for_api_key = lambda: None
    monkeypatch.setattr(main, 'NiaUI', lambda *a, **k: ui)
    monkeypatch.setattr(main, '_rastrear_cameras', lambda: None)
    monkeypatch.setattr(main, '_encerrar_tudo', lambda *a, **k: None)
    async def _run_vazio(self):
        return None

    monkeypatch.setattr(main.NiaLive, 'run', _run_vazio)
    monkeypatch.setattr(rotinas, 'agendador_global',
                        lambda: SimpleNamespace(iniciar=lambda: None))
    monkeypatch.setattr(main.Path, 'home', classmethod(lambda cls: tmp_path))

    antes = {t.name for t in threading.enumerate()}
    t0 = time.perf_counter()
    main.main()
    decorrido = time.perf_counter() - t0
    limite = time.monotonic() + 3.0
    while time.monotonic() < limite:
        novas = {t.name for t in threading.enumerate()} - antes - {'MainThread'}
        if not novas:
            break
        time.sleep(0.02)
    depois = {t.name for t in threading.enumerate()}
    saida = capsys.readouterr().out

    assert decorrido < 10.0
    assert 'Preflight' in saida
    assert not (depois - antes - {'MainThread'})
    assert callable(ui.on_text_command)
