# -*- coding: utf-8 -*-
"""Thread de métricas não pode usar COM sem inicialização (0x800401f0)."""
from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

import ui


def test_get_temp_windows_nao_chama_wmi_na_thread(monkeypatch):
    """Quebra: wmi.WMI() em thread worker aborta o processo com CO_E_NOTINITIALIZED."""
    chamadas = []

    class WmiFalsa:
        def __init__(self, *args, **kwargs):
            chamadas.append(1)

    monkeypatch.setattr(ui, '_OS', 'Windows')
    monkeypatch.setattr(importlib.util, 'find_spec',
                        lambda nome: object() if nome == 'wmi' else None)
    monkeypatch.setitem(__import__('sys').modules, 'wmi',
                        SimpleNamespace(WMI=WmiFalsa))
    monkeypatch.setattr(ui.psutil, 'sensors_temperatures', lambda: {}, raising=False)
    objeto = SimpleNamespace(_sem_temp=False)
    assert ui._SysMetrics._get_temp(objeto) == -1.0
    assert chamadas == []


def test_system_monitor_nao_chama_wmi_na_thread(monkeypatch):
    """Quebra: SystemMonitor também usava COM fora da thread principal."""
    import actions.system_monitor as SM

    chamadas = []

    class WmiFalsa:
        def __init__(self, *args, **kwargs):
            chamadas.append(1)

    monkeypatch.setattr(SM, '_OS', 'Windows')
    monkeypatch.setattr(importlib.util, 'find_spec',
                        lambda nome: object() if nome == 'wmi' else None)
    monkeypatch.setitem(__import__('sys').modules, 'wmi',
                        SimpleNamespace(WMI=WmiFalsa))
    monkeypatch.setattr(SM.psutil, 'sensors_temperatures', lambda: {}, raising=False)
    assert SM._get_cpu_temp() == -1.0
    assert chamadas == []
