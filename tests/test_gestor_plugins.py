# -*- coding: utf-8 -*-
"""Fase 06 — gerenciador de plugins: staging, ativação, remoção e reparo."""
from __future__ import annotations

import hashlib
import json
import zipfile

import pytest

from core import gestor_plugins as GP
from core import niateck as NT

MANIFESTO = {
    'api': 1, 'versao': '1.0.0', 'id': 'plugin_mock', 'nome': 'Plugin mock',
    'licenca': 'MIT', 'adaptador': 'adapter.py', 'hashes': {},
    'upstream': {'origem': 'local'},
}


def _pacote(tmp_path, nome='plugin_mock.niateck'):
    caminho = tmp_path / nome
    conteudo = b'raise RuntimeError("nao deve executar")\n'
    with zipfile.ZipFile(caminho, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('adapter.py', conteudo)
        zf.writestr('manifest.json', json.dumps(MANIFESTO))
        zf.writestr('upstream.json', json.dumps(
            {'origem': 'local', 'repositorio': 'fixture', 'revisao': 'abc'}))
    return caminho


def test_instalacao_simulada_nao_importa_nem_extrai_adapter(tmp_path):
    """Quebra: não existe gerenciador com staging separado do código."""
    pacote = _pacote(tmp_path)
    gestor = GP.GerenciadorPlugins(raiz=tmp_path / 'dados')
    registro = gestor.instalar(pacote)
    assert registro['id'] == 'plugin_mock'
    assert registro['ativo'] is False
    instalado = tmp_path / 'dados' / 'instalados' / 'plugin_mock' / 'pacote.niateck'
    assert instalado.is_file()
    with zipfile.ZipFile(instalado) as zf:
        assert 'adapter.py' in zf.namelist()
    assert not (tmp_path / 'dados' / 'instalados' / 'plugin_mock' / 'adapter.py').exists()


def test_ativar_e_desativar_apenas_muda_estado(tmp_path):
    """Quebra: não havia controle de ativação sem execução."""
    gestor = GP.GerenciadorPlugins(raiz=tmp_path / 'dados')
    gestor.instalar(_pacote(tmp_path))
    assert gestor.ativar('plugin_mock') is True
    assert gestor.inventario()[0]['ativo'] is True
    assert gestor.desativar('plugin_mock') is True
    assert gestor.inventario()[0]['ativo'] is False


def test_remocao_vai_para_quarentena_sem_apagar(tmp_path):
    """Quebra: remoção apagava o pacote sem possibilidade de recuperação."""
    gestor = GP.GerenciadorPlugins(raiz=tmp_path / 'dados')
    gestor.instalar(_pacote(tmp_path))
    assert gestor.remover('plugin_mock') is True
    assert gestor.inventario() == ()
    quarentena = tmp_path / 'dados' / 'removidos'
    assert any(p.is_dir() for p in quarentena.iterdir())


def test_recuperacao_reconcilia_staging_interrompido(tmp_path):
    """Quebra: staging interrompido não era retomado."""
    pacote = _pacote(tmp_path)
    gestor = GP.GerenciadorPlugins(raiz=tmp_path / 'dados')
    gestor.preparar(pacote)
    assert gestor.inventario() == ()
    assert gestor.recuperar() >= 1
    assert gestor.inventario()[0]['estado'] == 'instalado'


def test_reparo_marca_pacote_corrompido(tmp_path):
    """Quebra: reparo não revalidava o conteúdo do pacote."""
    gestor = GP.GerenciadorPlugins(raiz=tmp_path / 'dados')
    gestor.instalar(_pacote(tmp_path))
    destino = tmp_path / 'dados' / 'instalados' / 'plugin_mock' / 'pacote.niateck'
    destino.write_bytes(b'ZIP invalido')
    assert gestor.reparar('plugin_mock') is False
    assert gestor.inventario()[0]['estado'] == 'corrompido'


def test_inventario_nao_importa_o_adapter(tmp_path):
    """Quebra: inventário poderia carregar o módulo do plugin."""
    gestor = GP.GerenciadorPlugins(raiz=tmp_path / 'dados')
    gestor.instalar(_pacote(tmp_path))
    itens = gestor.inventario()
    assert itens[0]['carregador'] == ''
    assert 'adapter' not in str(itens[0])
