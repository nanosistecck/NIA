# -*- coding: utf-8 -*-
"""Inventário real do registro de aplicativos/ferramentas/habilidades."""
from __future__ import annotations

import json
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[3]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
os = __import__('os')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import main
from core import registro_aplicativos as RA

from core import registro_nativo as RN

RA.sincronizar_habilidades()
RA.sincronizar_ferramentas()
try:
    RN.registrar_nativos()
except Exception as exc:
    print('registro_nativo:', type(exc).__name__)
itens = RA.todos()
codigo_main = (RAIZ / 'main.py').read_text(encoding='utf-8')

tipos = {}
for item in itens:
    tipos[item.tipo] = tipos.get(item.tipo, 0) + 1

ferramentas = [i for i in itens if i.tipo == 'ferramenta']
sem_branch = [i.id for i in ferramentas
              if codigo_main.count(f'"{i.dominio_ferramenta}"') <= 1]
centrais = [i for i in itens if i.visivel_na_central]
dock = [i for i in itens if i.fixavel_no_dock]
sem_interface = [i.id for i in itens if i.tipo != 'ferramenta' and not i.possui_interface]

print(json.dumps({
    'total': len(itens),
    'por_tipo': tipos,
    'visiveis_na_central': len(centrais),
    'fixaveis_no_dock': len(dock),
    'ferramentas_declaradas': len(ferramentas),
    'ferramentas_sem_branch_em_main': sem_branch,
    'itens_sem_interface': len(sem_interface),
    'categorias': sorted({i.categoria for i in itens}),
    'amostras_central': [i.id for i in centrais[:20]],
}, ensure_ascii=False, indent=2))
