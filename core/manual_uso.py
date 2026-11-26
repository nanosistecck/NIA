# -*- coding: utf-8 -*-
"""Caminho do manual local da NIA (HTML estático, sem rede)."""
from __future__ import annotations

from pathlib import Path


def caminho_manual() -> Path:
    return Path(__file__).resolve().parents[1] / 'docs' / 'manual-nia' / 'index.html'


def disponivel() -> bool:
    return caminho_manual().is_file()
