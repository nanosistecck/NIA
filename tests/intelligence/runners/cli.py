# -*- coding: utf-8 -*-
"""CLI do NIA Intelligence Test Lab.

Uso:
  python -m tests.intelligence.runners.cli --mode quick
  python -m tests.intelligence.runners.cli --mode full
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from datetime import datetime

RAIZ = Path(__file__).resolve().parents[3]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from tests.intelligence.datasets.scenarios import selecionar
from tests.intelligence.runners.engine import executar

DOCS = RAIZ / 'docs' / 'nia-intelligence-lab'
MODOS = ('quick', 'full', 'intelligence', 'learning', 'automation',
         'plugins', 'regression', 'providers', 'stress', 'release')


def _metricas(avaliacoes):
    total = len(avaliacoes)
    bloqueados = sum(1 for a in avaliacoes if a.blocked)
    avaliaveis = total - bloqueados
    def conta(attr):
        return sum(1 for a in avaliacoes if getattr(a, attr))
    return {
        'total': total,
        'bloqueados': bloqueados,
        'avaliaveis': avaliaveis,
        'aprovados': conta('ok') - bloqueados,
        'reprovados': avaliaveis - (conta('ok') - bloqueados),
        'intencao': (conta('intent_ok'), total),
        'ferramenta': (conta('tool_ok'), total),
        'parametros': (conta('params_ok'), total),
        'efeito': (conta('effect_ok'), total),
        'resposta': (conta('response_ok'), total),
        'seguranca': (conta('security_ok'), total),
    }


def _gravar(modo, cenarios, avaliacoes):
    DOCS.mkdir(parents=True, exist_ok=True)
    metricas = _metricas(avaliacoes)
    linhas = ['# Métricas reais do laboratório', '',
              f'Modo: `{modo}` — {datetime.now().astimezone().isoformat(timespec="seconds")}', '',
              'Dimensão | Aprovados | Total', '---|---:|---:']
    rotulos = {'intencao': 'Intenção', 'ferramenta': 'Ferramenta',
               'parametros': 'Parâmetros', 'efeito': 'Efeito',
               'resposta': 'Resposta', 'seguranca': 'Segurança'}
    for chave, rotulo in rotulos.items():
        num, den = metricas[chave]
        linhas.append(f'{rotulo} | {num} | {den}')
    linhas += ['', f'Cenários aprovados: {metricas["aprovados"]}/{metricas["avaliaveis"]}',
               f'Cenários reprovados: {metricas["reprovados"]}/{metricas["avaliaveis"]}',
               f'Cenários bloqueados (decisão do modelo/contexto): '
               f'{metricas["bloqueados"]}/{metricas["total"]}', '']
    (DOCS / 'METRICS.md').write_text('\n'.join(linhas), encoding='utf-8')

    matriz = ['# Matriz de capacidades e cobertura', '',
              'Categoria | Cenários | Aprovados | IDs', '---|---:|---:|---']
    por_categoria = {}
    for c, a in zip(cenarios, avaliacoes):
        item = por_categoria.setdefault(c.category, [0, 0, []])
        item[0] += 1
        item[1] += int(a.ok)
        item[2].append(f'{c.id}:{"ok" if a.ok else "FALHA"}')
    for cat, (tot, ok, ids) in sorted(por_categoria.items()):
        matriz.append(f'{cat} | {tot} | {ok} | {", ".join(ids[:6])}')
    (DOCS / 'CAPABILITY_MATRIX.md').write_text('\n'.join(matriz) + '\n', encoding='utf-8')

    checkpoint = {
        'schema_version': 1, 'stage': 'executed',
        'mode': modo, 'suite_version': '1.0.0',
        'scenarios': [c.id for c in cenarios],
        'failures': [a.scenario_id for a in avaliacoes if not a.ok],
        'metrics': metricas,
        'next_action': 'Analisar falhas e corrigir mecanismos',
        'updated_at': datetime.now().astimezone().isoformat(timespec='seconds'),
    }
    caminho = DOCS / 'CHECKPOINT.json'
    temporario = caminho.with_suffix('.tmp')
    temporario.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporario.replace(caminho)
    return metricas


def main(argv=None):
    parser = argparse.ArgumentParser(description='Laboratório de inteligência da NIA')
    parser.add_argument('--mode', choices=MODOS, default='quick')
    parser.add_argument('--json', action='store_true', help='imprime só JSON')
    args = parser.parse_args(argv)

    cenarios = selecionar(args.mode)
    avaliacoes = [executar(c) for c in cenarios]
    metricas = _gravar(args.mode, cenarios, avaliacoes)
    if args.json:
        print(json.dumps(metricas, ensure_ascii=False, indent=2))
    else:
        print(f'[{args.mode}] aprovados {metricas["aprovados"]}/{metricas["avaliaveis"]} '
              f'(bloqueados {metricas["bloqueados"]}/{metricas["total"]})')
        for c, a in zip(cenarios, avaliacoes):
            if not a.ok:
                print(f'  FALHA {c.id}: {a.details} observado={a.observed}')
    return 0 if not metricas['reprovados'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
