# -*- coding: utf-8 -*-
"""Prontidão NIA para receber um .niateck real, sem código externo."""
from __future__ import annotations

import json

import pytest

from core import atualizador_local as AL
from core import fabrica_plugins as FP
from core import gestor_plugins as GP
from core import niateck as NT

MANIFESTO = {
    'api': 1, 'versao': '1.0.0', 'id': 'plugin_futuro', 'nome': 'Plugin futuro',
    'licenca': 'MIT', 'adaptador': 'adapter.py',
}
UPSTREAM = {'origem': 'fixture-local', 'repositorio': 'fixture', 'revisao': 'abc'}


def _fixture(tmp_path):
    origem = tmp_path / 'fixture'
    origem.mkdir()
    (origem / 'adapter.py').write_text('raise RuntimeError("nao executar")\n',
                                       encoding='utf-8')
    (origem / 'LICENSE').write_text('MIT\n', encoding='utf-8')
    return origem


def _pacote(tmp_path):
    destino = tmp_path / 'plugin.niateck'
    FP.construir(_fixture(tmp_path), destino, MANIFESTO, UPSTREAM)
    return destino


def test_ciclo_completo_de_recebimento(tmp_path):
    """Quebra: nao havia prova integrada build→inspeção→instalação→ativação."""
    pacote = _pacote(tmp_path)
    assert NT.inspecionar(pacote).ok is True
    gestor = GP.GerenciadorPlugins(raiz=tmp_path / 'plugins')
    registro = gestor.instalar(pacote)
    assert registro['id'] == 'plugin_futuro'
    assert gestor.ativar('plugin_futuro') is True
    assert gestor.inventario()[0]['ativo'] is True
    assert gestor.desativar('plugin_futuro') is True
    assert gestor.remover('plugin_futuro') is True


def test_atualizacao_do_pacote_com_rollback(tmp_path):
    """Quebra: recebimento nao cobria atualizacao do pacote instalado."""
    pacote = _pacote(tmp_path)
    raiz = tmp_path / 'updater'
    (raiz / 'atual').mkdir(parents=True)
    (raiz / 'atual' / 'versao.txt').write_text('0.9.0', encoding='utf-8')
    def aplicar(destino, _pkg):
        (destino / 'versao.txt').write_text('1.0.0', encoding='utf-8')
        return True

    atualizador = AL.Atualizador(raiz=raiz, aplicador=aplicar)
    assert atualizador.preparar(pacote)['ok'] is True
    assert atualizador.aplicar() is True
    assert atualizador.rollback() is True
    assert (raiz / 'atual' / 'versao.txt').read_text() == '0.9.0'


def test_pacote_malicioso_e_recusado_antes_de_qualquer_instalacao(tmp_path):
    """Quebra: gerenciador poderia aceitar pacote reprovado pelo inspetor."""
    ruim = tmp_path / 'ruim.niateck'
    ruim.write_bytes(b'nao e zip')
    gestor = GP.GerenciadorPlugins(raiz=tmp_path / 'plugins')
    with pytest.raises(ValueError, match='Pacote recusado'):
        gestor.instalar(ruim)
    assert gestor.inventario() == ()
