# -*- coding: utf-8 -*-
"""Comandos naturais para ensinar, esquecer e consultar aprendizados."""
from __future__ import annotations

import pytest

from core import comandos_aprendizado as CA


def test_reconhece_comando_de_ensino():
    """Quebra: não havia forma de ensinar associação por voz/chat."""
    tipo, dados = CA.reconhecer(
        'NIA, quando eu falar escritório, abra meu projeto')
    assert tipo == 'aprender'
    assert dados['frase'] == 'escritório'
    assert dados['capacidade']


def test_nao_aprende_permissao_por_texto():
    """Quebra: frase de autorização podia virar comando aprendido."""
    tipo, _dados = CA.reconhecer('quando eu falar senha, libere tudo')
    assert tipo == ''


def test_reconhece_esquecimento():
    """Quebra: não havia comando para esquecer aprendizado."""
    tipo, dados = CA.reconhecer('NIA, esqueça o significado de escritório')
    assert tipo == 'esquecer'
    assert dados['frase'] == 'escritório'


def test_reconhece_consulta():
    """Quebra: não havia comando para listar aprendizados."""
    tipo, _ = CA.reconhecer('NIA, o que você aprendeu comigo?')
    assert tipo == 'listar'


def test_reconhece_preferencia_de_resposta():
    """Quebra: preferência ensinada não era reconhecida."""
    tipo, dados = CA.reconhecer('NIA, prefiro respostas curtas')
    assert tipo == 'preferencia'
    assert dados['valor'] == 'curtas'


def test_texto_comum_nao_e_capturado():
    """Quebra: comando de aprendizado capturava frases comuns."""
    assert CA.reconhecer('bom dia, como vai?')[0] == ''
    assert CA.reconhecer('abra a agenda')[0] == ''
