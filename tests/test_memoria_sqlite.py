# -*- coding: utf-8 -*-
"""Fase 08 — migração idempotente para SQLite, sem tocar nos originais."""
from __future__ import annotations

import hashlib
import json

import pytest

from core import memoria_sqlite as MS


def _fixtures(tmp_path):
    memoria = tmp_path / 'memory.json'
    memoria.write_text(json.dumps({'nome': 'Ana', 'cidade': 'Recife'}), encoding='utf-8')
    diario = tmp_path / 'diario.jsonl'
    diario.write_text(
        '\n'.join(json.dumps({'texto': f'nota {i}', 'sessao': 'atual' if i == 2 else 'antiga'})
                  for i in range(3)) + '\n', encoding='utf-8')
    return memoria, diario, tmp_path / 'memoria.db'


def _hash(caminho):
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def test_migracao_cria_banco_e_inventario_com_proveniencia(tmp_path):
    """Quebra: não existe migração com IDs e contagem verificada."""
    memoria, diario, db = _fixtures(tmp_path)
    migrador = MS.MigradorMemoria(memoria, diario, db, perfil='p1')
    relatorio = migrador.migrar()
    assert relatorio['ok'] is True
    assert relatorio['memoria'] == 2
    assert relatorio['diario'] == 3
    assert migrador.sessao_atual() == 'nota 2'


def test_migracao_e_idempotente(tmp_path):
    """Quebra: repetir a migração duplicava registros."""
    memoria, diario, db = _fixtures(tmp_path)
    migrador = MS.MigradorMemoria(memoria, diario, db, perfil='p1')
    migrador.migrar()
    segundo = MS.MigradorMemoria(memoria, diario, db, perfil='p1').migrar()
    assert segundo['ok'] is True
    assert segundo['ja_migrado'] is True
    assert MS.MigradorMemoria(memoria, diario, db, perfil='p1').contar() == {
        'memoria': 2, 'diario': 3}


def test_originais_e_backup_permanece_intacto(tmp_path):
    """Quebra: migração poderia modificar ou apagar os arquivos de origem."""
    memoria, diario, db = _fixtures(tmp_path)
    antes_memoria, antes_diario = _hash(memoria), _hash(diario)
    MS.MigradorMemoria(memoria, diario, db, perfil='p1').migrar()
    assert _hash(memoria) == antes_memoria
    assert _hash(diario) == antes_diario
    assert any(p.name.startswith('memory.json.bak-') for p in tmp_path.iterdir())
    assert any(p.name.startswith('diario.jsonl.bak-') for p in tmp_path.iterdir())


def test_dados_corrompidos_nao_apagam_originais(tmp_path):
    """Quebra: JSON corrompido derrubava a migração sem relatório."""
    memoria, diario, db = _fixtures(tmp_path)
    memoria.write_text('{invalido', encoding='utf-8')
    antes = _hash(memoria)
    relatorio = MS.MigradorMemoria(memoria, diario, db, perfil='p1').migrar()
    assert relatorio['ok'] is False
    assert _hash(memoria) == antes
    assert not db.exists()


def test_perfis_sao_isolados(tmp_path):
    """Quebra: registros de perfis diferentes se misturavam."""
    memoria, diario, db = _fixtures(tmp_path)
    MS.MigradorMemoria(memoria, diario, db, perfil='p1').migrar()
    MS.MigradorMemoria(memoria, diario, db, perfil='p2').migrar()
    assert MS.MigradorMemoria(memoria, diario, db, perfil='p1').contar() == {
        'memoria': 2, 'diario': 3}
    assert MS.MigradorMemoria(memoria, diario, db, perfil='p2').historico()[0][1] == 'p2'


def test_contexto_respeita_orcamento_e_traz_proveniencia(tmp_path):
    """Quebra: contexto não separava sessão/histórico nem limitava tamanho."""
    memoria, diario, db = _fixtures(tmp_path)
    migrador = MS.MigradorMemoria(memoria, diario, db, perfil='p1')
    migrador.migrar()
    contexto = migrador.contexto(limite=24)
    assert len(contexto) <= 24
    assert 'memoria:' in contexto
