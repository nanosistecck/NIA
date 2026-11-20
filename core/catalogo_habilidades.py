# -*- coding: utf-8 -*-
"""Catálogo único das habilidades nativas da NIA.

Uma única definição por habilidade (identificador estável, nome, descrição,
frase de exemplo e ação) alimenta o dashboard, os atalhos do Canvas, o chat e
a voz. A seleção é local: nenhuma rede, inferência, indexagem ou sondagem
acontece ao carregar o catálogo.

A forma de descrever e descobrir habilidades foi inspirada em
``src/openjarvis/skills/`` (OpenJarvis, revisão 427c2dd, Apache 2.0): um
manifesto por habilidade com nome, descrição e etapas reutilizáveis. Nenhum
código foi copiado; a NIA usa uma estrutura Python simples e executores já
existentes, sem carregar manifestos remotos.
"""
from __future__ import annotations

import contextvars
import re
import unicodedata
from dataclasses import dataclass
from typing import Callable

# Executor registrado uma única vez pelo ponto de entrada real (main.py).
# Assim dashboard, Canvas, chat e voz chamam exatamente a mesma operação.
_EXECUTOR: Callable[[str, str], tuple[bool, str]] | None = None
_ORIGEM = contextvars.ContextVar('nia_habilidade_origem', default='catalogo')


def definir_origem(origem: str):
    """Marca quem acionou a habilidade (chat, voz, canvas) neste contexto."""
    return _ORIGEM.set(str(origem or 'catalogo'))


def restaurar_origem(token) -> None:
    _ORIGEM.reset(token)


def origem() -> str:
    return _ORIGEM.get()


@dataclass(frozen=True)
class Habilidade:
    id: str
    nome: str
    descricao: str
    exemplo: str
    acao: str
    config: str = ''


@dataclass(frozen=True)
class Disponibilidade:
    pronta: bool
    motivo: str


CATALOGO: tuple[Habilidade, ...] = (
    Habilidade(
        id='secretaria',
        nome='Consultar a Secretaria',
        descricao='Abre a janela da Secretaria ou a área para ativá-la.',
        exemplo='NIA, abra a Secretaria.',
        acao='abrir_secretaria',
        config='secretaria',
    ),
    Habilidade(
        id='buscar_arquivos',
        nome='Buscar nos arquivos',
        descricao='Busca com fontes verificáveis da Skill 03, sem inferência.',
        exemplo='NIA, procure nos meus arquivos por garantia.',
        acao='abrir_busca',
        config='documentos',
    ),
    Habilidade(
        id='resumo_dia',
        nome='Preparar resumo do dia',
        descricao='Gera o resumo local do Hoje sem alterar a rotina agendada.',
        exemplo='NIA, prepare o resumo do dia.',
        acao='gerar_resumo',
        config='geral',
    ),
)


def todas() -> tuple[Habilidade, ...]:
    return CATALOGO


def por_id(identificador: str) -> Habilidade | None:
    return next((h for h in CATALOGO if h.id == identificador), None)


def registrar_executor(funcao: Callable[[str, str], tuple[bool, str]]) -> None:
    """Registra o ponto de entrada único; chamadas repetidas substituem a ponte."""
    global _EXECUTOR
    _EXECUTOR = funcao


def executar(identificador: str, termo: str = '') -> tuple[bool, str]:
    """Executa uma habilidade pelo mesmo caminho usado por chat e voz."""
    if por_id(identificador) is None:
        return False, 'Habilidade desconhecida.'
    if _EXECUTOR is None:
        return False, 'A ponte da NIA ainda não foi inicializada.'
    return _EXECUTOR(identificador, termo or '')


def disponibilidade(identificador: str) -> Disponibilidade:
    """Estado local da habilidade, sem rede, modelo ou varredura."""
    habilidade = por_id(identificador)
    if habilidade is None:
        return Disponibilidade(False, 'Habilidade desconhecida.')
    if habilidade.id == 'secretaria':
        try:
            from core import secretaria  # noqa: PLC0415
            if not secretaria.carregar().get('ligada'):
                return Disponibilidade(
                    False, 'Secretária desligada: ative-a em Configurações → '
                           'Integrações → Secretária.')
        except Exception:
            return Disponibilidade(False, 'Módulo da Secretária indisponível.')
        return Disponibilidade(True, 'Secretária ativa e pronta para abrir.')
    if habilidade.id == 'buscar_arquivos':
        try:
            from core import indice_local  # noqa: PLC0415
            if not indice_local.fts5_disponivel():
                return Disponibilidade(
                    False, 'Este Python não tem FTS5; configure o índice local '
                           'em Configurações → Documentos.')
            from core.config_preferencias import ConfigService  # noqa: PLC0415
            if not ConfigService().carregar_fontes_indice():
                return Disponibilidade(
                    False, 'Nenhuma pasta configurada: adicione fontes em '
                           'Configurações → Documentos.')
        except Exception as exc:
            return Disponibilidade(False, f'Índice local indisponível: {type(exc).__name__}.')
        return Disponibilidade(True, 'Busca local disponível, mesmo sem rede.')
    return Disponibilidade(True, 'Resumo local sempre disponível.')


def _normalizar(texto: str) -> str:
    bruto = unicodedata.normalize('NFKD', str(texto or '')).lower()
    return ''.join(c for c in bruto if not unicodedata.combining(c)).strip()


_PADROES: dict[str, str] = {
    'secretaria': r'^(?:nia[,:]?\s+)?(?:abra|abrir) a secretaria\.?$',
    'buscar_arquivos': (r'^(?:nia[,:]?\s+)?(?:procure|busque|pesquise) '
                        r'(?:nos|nas|em|no|na) (?:meus|minhas|meu|minha)?\s*'
                        r'(?:arquivos|documentos)'
                        r'(?:\s+por\s+(?P<termo>.+?))?\.?$'),
    'resumo_dia': (r'^(?:nia[,:]?\s+)?(?:prepare|gere|faca) o resumo '
                   r'do dia\.?$'),
}


def reconhecer(texto: str) -> tuple[Habilidade | None, str]:
    """Reconhece apenas as frases de exemplo documentadas, sem IA."""
    limpo = _normalizar(texto)
    for habilidade in CATALOGO:
        padrao = _PADROES.get(habilidade.id)
        if not padrao:
            continue
        encontrado = re.match(padrao, limpo)
        if encontrado:
            return habilidade, (encontrado.groupdict().get('termo') or '').strip(' .!?;:')
    return None, ''
