# -*- coding: utf-8 -*-
"""Auditoria estática somente leitura da NIA."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import sys

RAIZ = Path(__file__).resolve().parents[3]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
EXCLUIR = {'NIA_PLUGIN_FACTORY', '.venv-apis', '__pycache__', '.git', '.pytest_cache'}


def fontes():
    for caminho in RAIZ.rglob('*.py'):
        if any(p in EXCLUIR for p in caminho.parts):
            continue
        yield caminho


def principal():
    arquivos = list(fontes())
    sintaxe = []
    nao_usados = []
    esqueletos = []
    nomes = {}
    todos = []
    for caminho in arquivos:
        rel = caminho.relative_to(RAIZ).as_posix()
        texto = caminho.read_text(encoding='utf-8', errors='replace')
        todos.append((rel, texto))
        try:
            arvore = ast.parse(texto, filename=rel)
        except SyntaxError as exc:
            sintaxe.append({'arquivo': rel, 'erro': str(exc)})
            continue
        importados = {}
        usados = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                for alias in no.names:
                    nome = alias.asname or alias.name.split('.')[0]
                    if alias.name != '__future__':
                        importados[nome] = alias.name
            elif isinstance(no, ast.ImportFrom):
                for alias in no.names:
                    if alias.name == '*':
                        continue
                    nome = alias.asname or alias.name
                    if no.module != '__future__':
                        importados[nome] = f'{no.module}.{alias.name}'
            elif isinstance(no, ast.Name):
                usados.add(no.id)
            elif isinstance(no, ast.Attribute):
                pass
        for nome, origem in importados.items():
            if nome not in usados and nome not in ('annotations',):
                nao_usados.append({'arquivo': rel, 'nome': nome, 'origem': origem})
        for no in arvore.body:
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                nomes.setdefault(no.name, []).append(rel)
                if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    corpo = [n for n in no.body
                             if not (isinstance(n, ast.Expr)
                                     and isinstance(n.value, ast.Constant)
                                     and isinstance(n.value.value, str))]
                    if len(corpo) == 1 and isinstance(corpo[0], (ast.Pass, ast.Raise)):
                        esqueletos.append({'arquivo': rel, 'nome': no.name,
                                           'linha': no.lineno})

    duplicados = {n: v for n, v in nomes.items() if len(set(v)) > 3}

    padroes = {
        'eval': r'(?<![\w.])eval\s*\(',
        'exec': r'(?<![\w.])exec\s*\(',
        'pickle_load': r'pickle\.load\s*\(',
        'yaml_load': r'yaml\.load\s*\(',
        'shell_true': r'shell\s*=\s*True',
        'os_system': r'os\.system\s*\(',
        'todo': r'(?i)\b(TODO|FIXME|XXX)\b',
        'credencial_literal': r'(?i)(api[_-]?key|password|token)\s*=\s*[\"\'][^\"\']{8,}',
    }
    seguranca = {}
    for chave, padrao in padroes.items():
        encontrados = []
        rx = re.compile(padrao)
        for rel, texto in todos:
            for i, linha in enumerate(texto.splitlines(), 1):
                if rx.search(linha):
                    encontrados.append({'arquivo': rel, 'linha': i,
                                        'trecho': linha.strip()[:140]})
        seguranca[chave] = {'total': len(encontrados), 'amostras': encontrados[:12]}

    declaracoes = []
    politicas = []
    try:
        import main
        from core import permissoes_ferramentas as PF
        declaracoes = [d['name'] for d in main.TOOL_DECLARATIONS]
        politicas = sorted(PF.ESCOPOS_LEGADOS)
    except Exception as exc:
        declaracoes = ['ERRO_IMPORT:' + type(exc).__name__]
    codigo_main = next((t for r, t in todos if r == 'main.py'), '')
    sem_branch = [n for n in declaracoes
                  if n and codigo_main.count(f'"{n}"') <= 1]

    print(json.dumps({
        'arquivos_python': len(arquivos),
        'erros_sintaxe': sintaxe,
        'imports_nao_usados_total': len(nao_usados),
        'imports_nao_usados_amostras': nao_usados[:40],
        'esqueletos_total': len(esqueletos),
        'esqueletos_amostras': esqueletos[:30],
        'nomes_duplicados': duplicados,
        'ferramentas_declaradas': len(declaracoes),
        'ferramentas_sem_literal_no_main': sem_branch,
        'politicas_registradas': len(politicas),
        'seguranca': seguranca,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    principal()
