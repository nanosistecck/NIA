# -*- coding: utf-8 -*-
"""Módulo uinput deve ser importável fora do Linux e degradar com segurança."""
from __future__ import annotations

import importlib
import sys

import pytest


def test_modulo_importa_fora_do_linux():
    """Quebra: import top-level de fcntl quebra no Windows."""
    modulo = importlib.import_module('core.entrada_uinput')
    assert modulo is not None


def test_disponivel_e_falso_onde_nao_ha_uinput():
    """Quebra: disponibilidade precisava de fcntl para ser consultada."""
    modulo = importlib.import_module('core.entrada_uinput')
    if sys.platform.startswith('linux'):
        assert isinstance(modulo.disponivel(), bool)
    else:
        assert modulo.disponivel() is False
        assert modulo.instalar_no_pyautogui() is False
