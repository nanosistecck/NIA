# -*- coding: utf-8 -*-
"""Comandos naturais de aprendizado (Fase 07 operacional).

Reconhece ensino, esquecimento, consulta e preferências sem inferência e sem
conceder permissões. A associação efetiva continua em ``core.aprendizado``.
"""
from __future__ import annotations

import re

from core import catalogo_habilidades as CH
from core import registro_aplicativos as RA

_BLOQUEADOS = re.compile(
    r'(?i)\b(senha|permiss|autoriz|token|credencial|libere\s+tudo|api[_-]?key)\b')
_PADROES = (
    ('aprender', re.compile(
        r'(?is)^\s*(?:nia[,:]?\s+)?quando eu (?:falar|dizer)\s+'
        r'(?P<frase>.+?)\s*,\s*(?:abra|abre|abrir|execute|executar|faça|faca|fale)\s+'
        r'(?P<alvo>.+?)\s*\??\s*$')),
    ('esquecer', re.compile(
        r'(?is)^\s*(?:nia[,:]?\s+)?(?:esqueça|esquece|remova|apague)\s+'
        r'o (?:significado|comando|aprendizado) de\s+(?P<frase>.+?)\s*\??\s*$')),
    ('listar', re.compile(
        r'(?is)^\s*(?:nia[,:]?\s+)?(?:o que você aprendeu comigo|'
        r'quais comandos você aprendeu|mostre o que aprendeu)\s*\??\s*$')),
    ('aprender', re.compile(
        r'(?is)^\s*(?:nia[,:]?\s+)?agora\s+(?P<frase>.+?)\s+'
        r'significa\s+outra\s+coisa\s*[.!?]?\s*$')),
    ('preferencia', re.compile(
        r'(?is)^\s*(?:nia[,:]?\s+)?prefiro respostas\s+'
        r'(?P<valor>curtas|breves|longas|detalhadas)\s*\??\s*$')),
    ('procedimento', re.compile(
        r'(?is)^\s*(?:nia[,:]?\s+)?faça como fizemos da última vez'
        r'(?P<detalhe>.*?)\s*\??\s*$')),
)


def _capacidade(texto: str) -> str:
    alvo = str(texto or '').strip(' .!?')
    if not alvo:
        return ''
    habilidade, _ = CH.reconhecer('NIA, abra ' + alvo)
    if habilidade is not None:
        return habilidade.id
    encontrados = RA.buscar(alvo)
    if encontrados:
        return encontrados[0].id
    normal = RA.normalizar(alvo)
    # Alvos comuns de linguagem natural mapeados para descritores reais.
    if any(chave in normal for chave in ('projeto', 'plano', 'canvas')):
        return 'planos'
    if 'secretaria' in normal:
        return 'hab_secretaria'
    if 'agenda' in normal or 'compromisso' in normal:
        return 'agenda'
    if 'globo' in normal or 'mapa' in normal:
        return 'globo'
    return 'app_' + re.sub(r'\W+', '_', normal).strip('_')[:64]


def reconhecer(texto: str) -> tuple:
    """Devolve (tipo, dados). Nunca devolve ação para texto de permissão."""
    if not isinstance(texto, str) or not texto.strip():
        return '', {}
    if _BLOQUEADOS.search(texto):
        return '', {}
    for tipo, padrao in _PADROES:
        encontrado = padrao.match(texto)
        if encontrado is None:
            continue
        dados = encontrado.groupdict()
        if tipo == 'aprender':
            frase = str(dados.get('frase') or '').strip(' .!?')
            capacidade = _capacidade(dados.get('alvo', ''))
            if not capacidade and frase:
                capacidade = 'planos'  # correção genérica sem alvo explícito
            if not frase or not capacidade:
                return '', {}
            return tipo, {'frase': frase, 'capacidade': capacidade}
        if tipo == 'esquecer':
            return tipo, {'frase': str(dados.get('frase') or '').strip(' .!?')}
        return tipo, {k: str(v or '').strip() for k, v in dados.items()}
    return '', {}
