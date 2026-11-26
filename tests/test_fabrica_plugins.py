# -*- coding: utf-8 -*-
"""Fase 18 — factory local de .niateck com build determinístico e proveniência."""
from __future__ import annotations

import json
import zipfile

import pytest

from core import fabrica_plugins as FP
from core import niateck as NT

MANIFESTO = {
    'api': 1, 'versao': '1.0.0', 'id': 'plugin_fixture', 'nome': 'Fixture local',
    'licenca': 'MIT', 'adaptador': 'adapter.py',
}
UPSTREAM = {'origem': 'fixture-local', 'repositorio': 'fixture', 'revisao': 'abc123'}


def _fixture(tmp_path, com_licenca=True):
    origem = tmp_path / 'fixture'
    origem.mkdir()
    (origem / 'adapter.py').write_text(
        'raise RuntimeError("nao deve executar")\n', encoding='utf-8')
    if com_licenca:
        (origem / 'LICENSE').write_text('MIT\n', encoding='utf-8')
    return origem


def test_build_e_deterministico(tmp_path):
    """Quebra: ZIP variava por timestamp/ordem e nao era reproduzivel."""
    origem = _fixture(tmp_path)
    a = FP.construir(origem, tmp_path / 'a.niateck', MANIFESTO, UPSTREAM)
    b = FP.construir(origem, tmp_path / 'b.niateck', MANIFESTO, UPSTREAM)
    assert a['ok'] and b['ok']
    assert (tmp_path / 'a.niateck').read_bytes() == (tmp_path / 'b.niateck').read_bytes()


def test_pacote_construido_e_aceito_pelo_inspetor(tmp_path):
    """Quebra: pacote gerado nao passava na validacao de .niateck."""
    origem = _fixture(tmp_path)
    FP.construir(origem, tmp_path / 'p.niateck', MANIFESTO, UPSTREAM)
    relatorio = NT.inspecionar(tmp_path / 'p.niateck')
    assert relatorio.ok is True
    with zipfile.ZipFile(tmp_path / 'p.niateck') as zf:
        assert sorted(zf.namelist()) == [
            'LICENSE', 'adapter.py', 'manifest.json', 'upstream.json']


def test_fixture_sem_licenca_e_recusada(tmp_path):
    """Quebra: factory aceitava pacote sem licença declarada no arquivo."""
    origem = _fixture(tmp_path, com_licenca=False)
    resultado = FP.construir(origem, tmp_path / 'p.niateck', MANIFESTO, UPSTREAM)
    assert resultado['ok'] is False
    assert any('licen' in m.lower() for m in resultado['motivos'])


def test_relatorio_de_proveniencia_tem_hashes_e_caminhos(tmp_path):
    """Quebra: nao havia registro de origem/hashes do que foi empacotado."""
    origem = _fixture(tmp_path)
    resultado = FP.construir(origem, tmp_path / 'p.niateck', MANIFESTO, UPSTREAM)
    assert resultado['proveniencia']['origem'] == 'fixture-local'
    assert 'adapter.py' in resultado['proveniencia']['arquivos']


def test_build_nao_executa_nem_acessa_rede(tmp_path, monkeypatch):
    """Quebra: factory podia importar adapter ou abrir conexão."""
    def bloqueia(*_args, **_kw):
        raise AssertionError('rede nao deveria ser usada')

    monkeypatch.setattr('socket.socket', bloqueia)
    origem = _fixture(tmp_path)
    resultado = FP.construir(origem, tmp_path / 'p.niateck', MANIFESTO, UPSTREAM)
    assert resultado['ok'] is True
