# -*- coding: utf-8 -*-
"""Fase 19 — atualização local com candidato separado e rollback."""
from __future__ import annotations

import json

import pytest

from core import atualizador_local as AL
from core import fabrica_plugins as FP

MANIFESTO = {
    'api': 1, 'versao': '2.0.0', 'id': 'plugin_fixture', 'nome': 'Fixture',
    'licenca': 'MIT', 'adaptador': 'adapter.py',
}
UPSTREAM = {'origem': 'fixture-local', 'repositorio': 'fixture', 'revisao': 'abc'}


def _pacote(tmp_path):
    origem = tmp_path / 'fixture'
    origem.mkdir(exist_ok=True)
    (origem / 'adapter.py').write_text('VALOR = 2\n', encoding='utf-8')
    (origem / 'LICENSE').write_text('MIT\n', encoding='utf-8')
    destino = tmp_path / 'candidato.niateck'
    FP.construir(origem, destino, MANIFESTO, UPSTREAM)
    return destino


def _atualizador(tmp_path, aplicador=None):
    raiz = tmp_path / 'atualizador'
    (raiz / 'atual').mkdir(parents=True, exist_ok=True)
    (raiz / 'atual' / 'versao.txt').write_text('1.0.0', encoding='utf-8')
    return AL.Atualizador(raiz=raiz, aplicador=aplicador)


def _aplicador(destino, pacote):
    (destino / 'versao.txt').write_text('2.0.0', encoding='utf-8')
    return True


def test_candidato_valido_e_preparado_sem_extrair(tmp_path):
    """Quebra: não havia staging separado do código atual."""
    atualizador = _atualizador(tmp_path)
    relatorio = atualizador.preparar(_pacote(tmp_path))
    assert relatorio['ok'] is True
    assert (tmp_path / 'atualizador' / 'candidatos' / 'plugin_fixture.niateck').is_file()
    assert (tmp_path / 'atualizador' / 'atual' / 'versao.txt').read_text() == '1.0.0'


def test_pacote_incompativel_e_recusado(tmp_path):
    """Quebra: pacote inválido podia virar candidato."""
    ruim = tmp_path / 'ruim.niateck'
    ruim.write_bytes(b'nao e zip')
    relatorio = _atualizador(tmp_path).preparar(ruim)
    assert relatorio['ok'] is False


def test_aplicacao_cria_backup_e_usa_staging(tmp_path):
    """Quebra: aplicar sobrescrevia o código sem backup."""
    atualizador = _atualizador(tmp_path, aplicador=_aplicador)
    atualizador.preparar(_pacote(tmp_path))
    assert atualizador.aplicar() is True
    assert (tmp_path / 'atualizador' / 'atual' / 'versao.txt').read_text() == '2.0.0'
    backups = list((tmp_path / 'atualizador' / 'backups').iterdir())
    assert any((b / 'versao.txt').read_text() == '1.0.0' for b in backups if b.is_dir())


def test_rollback_restaura_versao_anterior(tmp_path):
    """Quebra: não havia volta para o código anterior."""
    atualizador = _atualizador(tmp_path, aplicador=_aplicador)
    atualizador.preparar(_pacote(tmp_path))
    atualizador.aplicar()
    assert atualizador.rollback() is True
    assert (tmp_path / 'atualizador' / 'atual' / 'versao.txt').read_text() == '1.0.0'


def test_migracao_irreversivel_bloqueia_aplicacao(tmp_path):
    """Quebra: atualização com migração irreversível podia prosseguir."""
    atualizador = _atualizador(tmp_path, aplicador=_aplicador)
    atualizador.preparar(_pacote(tmp_path))
    assert atualizador.aplicar(migracao_irreversivel=True) is False
    assert (tmp_path / 'atualizador' / 'atual' / 'versao.txt').read_text() == '1.0.0'


def test_interrupcao_e_recuperada_pelo_estado(tmp_path):
    """Quebra: estado 'aplicando' ficava preso após interrupção."""
    atualizador = _atualizador(tmp_path, aplicador=_aplicador)
    atualizador.preparar(_pacote(tmp_path))
    atualizador._estado['estado'] = 'aplicando'
    atualizador._salvar()
    assert atualizador.recuperar() is True
    assert atualizador.estado()['estado'] == 'aplicado'
