# -*- coding: utf-8 -*-
"""Importa módulos de produção fora de core para detectar falhas de import."""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[3]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

DIRETORIOS = ('actions', 'memory', 'dashboard', 'config', 'secretaria', 'globo')
modulos = []
for diretorio in DIRETORIOS:
    for caminho in sorted((RAIZ / diretorio).glob('*.py')):
        if caminho.name == '__init__.py':
            continue
        modulos.append(f'{diretorio}.{caminho.stem}')

ok, falhas = [], []
for nome in modulos:
    try:
        importlib.import_module(nome)
        ok.append(nome)
    except Exception as exc:
        falhas.append({'modulo': nome, 'erro': type(exc).__name__,
                       'detalhe': str(exc)[:180]})

print(json.dumps({'total': len(modulos), 'ok': len(ok), 'falhas': falhas},
                 ensure_ascii=False, indent=2))
