# -*- coding: utf-8 -*-
"""Importa todos os módulos do núcleo para detectar falhas/ciclos."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[3]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

modulos = []
for caminho in sorted((RAIZ / 'core').glob('*.py')):
    if caminho.name == '__init__.py':
        continue
    modulos.append('core.' + caminho.stem)

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
