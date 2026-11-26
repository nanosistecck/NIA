# -*- coding: utf-8 -*-
"""Preflight rápido e determinístico da NIA (auditoria final).

Não faz rede, não lê credenciais, não inicializa interface nem agendador.
Separa falhas críticas (impedem inicialização segura) de degradações
(componentes opcionais indisponíveis).
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import re
import sqlite3
import sys

from core import permissoes_ferramentas as PF

RAIZ = Path(__file__).resolve().parents[1]
ESSENCIAIS = ('PyQt6', 'psutil', 'requests')
MODULOS_NUCLEO = ('catalogo_habilidades', 'registro_aplicativos', 'rotinas',
                  'permissoes_ferramentas', 'llm_router', 'contexto_ferramentas')


def verificar_python(version_info) -> bool:
    return tuple(version_info[:2]) >= (3, 10)


def _declaracoes() -> tuple:
    """Extrai TOOL_DECLARATIONS por regex: AST de `main.py` custa ~1 s."""
    try:
        texto = (RAIZ / 'main.py').read_text(encoding='utf-8')
    except OSError:
        return ()
    bloco = re.search(r'TOOL_DECLARATIONS\s*=\s*\[(.*?)^\s*\]', texto, re.S | re.M)
    if bloco is None:
        return ()
    return tuple(re.findall(
        r'''["']name["']\s*:\s*["']([A-Za-z0-9_]+)["']''', bloco.group(1)))


# Verificação essencial de inicialização: apenas arquivos cuja sintaxe
# quebraria a abertura. Uma varredura completa pertence à auditoria de
# manutenção, não ao boot (media 2+ s sob carga).
# `main.py`/`ui.py` são verificados pelo próprio interpreter ao iniciar;
# re-parseá-los no preflight custaria mais de 1 s.
CRITICOS = ('core/preflight.py', 'core/catalogo_habilidades.py',
            'core/permissoes_ferramentas.py', 'core/rotinas.py',
            'core/llm_router.py')


def _syntaxe_core() -> tuple:
    erros = []
    for relativo in CRITICOS:
        caminho = RAIZ / relativo
        try:
            ast.parse(caminho.read_text(encoding='utf-8'))
        except (OSError, SyntaxError) as exc:
            erros.append(f'{relativo}: {type(exc).__name__}')
    return tuple(erros)


def _banco(caminho: Path) -> str:
    if not caminho.is_file():
        return 'ausente'
    try:
        with sqlite3.connect(f'file:{caminho}?mode=ro', uri=True) as conexao:
            resultado = conexao.execute('PRAGMA quick_check').fetchone()
        return 'ok' if resultado and resultado[0] == 'ok' else 'corrompido'
    except sqlite3.Error:
        return 'corrompido'


def executar() -> dict:
    criticas = []
    degradacoes = []
    verificacoes = {}

    verificacoes['python'] = f'{sys.version_info.major}.{sys.version_info.minor}'
    if not verificar_python(sys.version_info):
        criticas.append('python: versão incompatível')

    for nome in ESSENCIAIS:
        disponivel = importlib.util.find_spec(nome) is not None
        verificacoes['dep_' + nome] = disponivel
        if not disponivel:
            criticas.append(f'dependência ausente: {nome}')

    for nome in MODULOS_NUCLEO:
        disponivel = importlib.util.find_spec('core.' + nome) is not None
        verificacoes['modulo_' + nome] = disponivel
        if not disponivel:
            criticas.append(f'módulo ausente: core.{nome}')

    declaracoes = _declaracoes()
    politicas = set(PF.ESCOPOS_LEGADOS)
    sem_politica = [n for n in declaracoes if n not in politicas]
    verificacoes['ferramentas'] = len(declaracoes)
    verificacoes['politicas'] = len(politicas)
    if declaracoes and sem_politica:
        criticas.append('politica ausente: ' + ', '.join(sem_politica[:5]))

    erros_sintaxe = _syntaxe_core()
    verificacoes['sintaxe_core'] = len(erros_sintaxe)
    if erros_sintaxe:
        criticas.append('sintaxe: ' + '; '.join(erros_sintaxe[:5]))

    base = Path.home() / '.nia'
    verificacoes['dados'] = str(base)
    for nome in ('rotinas.db', 'outbox.json', 'aprendizado.json'):
        if (base / nome).exists():
            estado = _banco(base / nome) if nome.endswith('.db') else 'presente'
            verificacoes['dado_' + nome] = estado
            if estado == 'corrompido':
                degradacoes.append(f'{nome} corrompido')
    for diretorio in ('logs', 'config'):
        verificacoes['dir_' + diretorio] = (RAIZ / diretorio).is_dir()
        if not (RAIZ / diretorio).is_dir():
            degradacoes.append(f'diretório ausente: {diretorio}')

    return {'ok': not criticas, 'falhas_criticas': tuple(criticas),
            'degradacoes': tuple(degradacoes), 'verificacoes': verificacoes}
