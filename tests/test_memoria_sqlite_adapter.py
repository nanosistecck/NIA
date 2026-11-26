# -*- coding: utf-8 -*-
"""Migração SQLite pronta: adaptador compatível com memory_manager/diario."""
from __future__ import annotations

import json

import pytest

from core import memoria_sqlite_adapter as MSA


@pytest.fixture
def fontes(tmp_path):
    memoria = tmp_path / 'memory.json'
    memoria.write_text(json.dumps({'nome': 'Ana', 'cidade': 'Recife'}), encoding='utf-8')
    diario = tmp_path / 'diario.jsonl'
    diario.write_text(
        '\n'.join(json.dumps({'texto': t, 'sessao': 'atual'}) for t in
                  ('Gosta de café', 'Reunião amanhã')) + '\n', encoding='utf-8')
    return memoria, diario, tmp_path / 'm.db'


def _adapter(fontes):
    memoria, diario, db = fontes
    return MSA.MemoriaSQLite(db_path=db, perfil='p1',
                             memoria_json=memoria, diario_jsonl=diario)


def test_load_memory_preserve_valores_migrados(fontes):
    """Quebra: nao havia adaptador SQLite com a API de memory_manager."""
    assert _adapter(fontes).load_memory() == {'nome': 'Ana', 'cidade': 'Recife'}


def test_update_memory_e_remember_persistem(fontes):
    """Quebra: atualizações nao eram gravadas no banco."""
    adapter = _adapter(fontes)
    adapter.update_memory({'nome': 'Ana Maria'})
    adapter.remember('cor', 'verde')
    assert MSA.MemoriaSQLite(db_path=fontes[2], perfil='p1').load_memory() == {
        'nome': 'Ana Maria', 'cidade': 'Recife', 'cor': 'verde'}


def test_diario_ler_e_procurar(fontes):
    """Quebra: diario migrado nao era consultável pela API antiga."""
    adapter = _adapter(fontes)
    assert 'Gosta de café' in adapter.ler()
    assert adapter.procurar('reunião') == ['Reunião amanhã']


def test_anotar_e_gravado_no_banco(fontes):
    """Quebra: novas anotações continuavam indo só para JSONL."""
    adapter = _adapter(fontes)
    adapter.anotar('Nova nota')
    assert 'Nova nota' in MSA.MemoriaSQLite(db_path=fontes[2], perfil='p1').ler()


def test_excluir_remove_memoria_diario_e_indice(fontes):
    """Quebra: exclusão deixava índice derivado e diario com o dado."""
    adapter = _adapter(fontes)
    assert adapter.excluir('cidade') is True
    assert 'cidade' not in adapter.load_memory()
    assert 'Recife' not in adapter.format_memory_for_prompt()
    assert adapter.procurar('Recife') == []


def test_migracao_segunda_instancia_e_idempotente(fontes):
    """Quebra: reabrir o adaptador duplicava registros."""
    _adapter(fontes).anotar('Extra')
    segundo = _adapter(fontes)
    assert segundo.ler().count('Extra') == 1
    assert segundo.load_memory()['nome'] == 'Ana'


def test_originais_nao_sao_alterados(fontes):
    """Quebra: adaptador poderia apagar JSON/JSONL de origem."""
    memoria, diario, _ = fontes
    antes = (memoria.read_bytes(), diario.read_bytes())
    _adapter(fontes)
    assert (memoria.read_bytes(), diario.read_bytes()) == antes
