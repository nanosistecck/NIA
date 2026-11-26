# -*- coding: utf-8 -*-
"""Integração do aprendizado explícito ao roteamento local da NIA."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import main
from core import aprendizado as AP
from core import catalogo_habilidades as CH


@pytest.fixture
def perfil(tmp_path, monkeypatch):
    monkeypatch.setattr(main.Path, 'home', classmethod(lambda cls: tmp_path))
    capacidades = tuple(h.id for h in CH.todas())
    AP.Aprendizado(caminho=tmp_path / '.nia' / 'aprendizado.json',
                   capacidades=capacidades).aprender('relatorio do mes', 'resumo_dia')
    return tmp_path


def test_habilidade_aprendida_resolve_frase_explicita(perfil):
    """Quebra: roteamento nao consultava associacoes aprendidas."""
    obj = object.__new__(main.NiaLive)
    habilidade, termo = obj._habilidade_aprendida('Relatório do mês')
    assert habilidade.id == 'resumo_dia'
    assert termo == ''


def test_habilidade_aprendida_nao_inventa_comando(perfil):
    """Quebra: frase nao aprendida podia virar habilidade."""
    obj = object.__new__(main.NiaLive)
    assert obj._habilidade_aprendida('faz isso de novo') == (None, '')


def test_habilidade_aprendida_reevalida_capacidade(perfil, monkeypatch):
    """Quebra: habilidade removida continuava resolvida."""
    monkeypatch.setattr(CH, 'todas', lambda: ())
    obj = object.__new__(main.NiaLive)
    assert obj._habilidade_aprendida('relatorio do mes') == (None, '')


def test_ensino_por_frase_persiste_e_resolve_apos_recriar(perfil, monkeypatch):
    """Quebra: ensino por linguagem natural não chegava ao armazenamento."""
    from core import comandos_aprendizado as CA
    obj = object.__new__(main.NiaLive)
    obj.ui = SimpleNamespace(write_log=Mock(),
                             falar=Mock(), focar_busca=Mock())
    frase = 'NIA, quando eu falar escritório, abra meu projeto'
    tipo, dados = CA.reconhecer(frase)
    assert obj._executar_frase_habilidade(frase, 'chat') is True
    novo = object.__new__(main.NiaLive)
    habilidade, _ = novo._habilidade_aprendida('escritório')
    assert habilidade is not None
    assert habilidade.id == dados['capacidade']


def test_preferencia_aprendida_persiste(perfil):
    """Quebra: preferência dita pelo usuário não era guardada."""
    obj = object.__new__(main.NiaLive)
    obj.ui = SimpleNamespace(write_log=Mock())
    assert obj._executar_frase_habilidade('NIA, prefiro respostas curtas', 'chat') is True
    assert obj._aprendizado().preferencias()['respostas'] == 'curtas'


def test_executar_frase_habilidade_usa_associacao(perfil, monkeypatch):
    """Quebra: a rota real ignorava o aprendizado mesmo apos reconhecer None."""
    obj = object.__new__(main.NiaLive)
    obj.ui = SimpleNamespace(write_log=Mock())
    habilidade = CH.por_id('resumo_dia')
    monkeypatch.setattr(CH, 'reconhecer', lambda texto: (None, ''))
    executadas = []
    monkeypatch.setattr(CH, 'executar', lambda ident, termo: executadas.append(ident) or (True, 'ok'))
    monkeypatch.setattr(CH, 'definir_origem', lambda origem: 'token')
    monkeypatch.setattr(CH, 'restaurar_origem', lambda token: None)
    assert obj._executar_frase_habilidade('relatorio do mes', 'chat') is True
    assert executadas == ['resumo_dia']
