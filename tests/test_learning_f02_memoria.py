# -*- coding: utf-8 -*-
"""RED F02: memória procedural SQLite persistente e versionada."""
from __future__ import annotations

import json
import sqlite3

import pytest

from core.aprendizado_adaptativo.memoria import MemoriaProcedural


def test_migracao_idempotente_cria_backup_de_esquema_antigo(tmp_path):
    db = tmp_path / 'mem.db'
    m = MemoriaProcedural(db)
    assert m.migrar()['user_version'] == 1
    assert m.migrar()['user_version'] == 1
    m.fechar()

    con = sqlite3.connect(db)
    con.execute('PRAGMA user_version=0')
    con.commit()
    con.close()

    m2 = MemoriaProcedural(db)
    assert m2.ultima_migracao['backup'] is True
    r = m2.migrar()
    assert r['user_version'] == 1
    assert list(tmp_path.glob('*.bak*'))
    m2.fechar()


def test_procedimento_persiste_entre_reinicios(tmp_path):
    db = tmp_path / 'mem.db'
    m = MemoriaProcedural(db)
    pid = m.registrar_procedimento('demo.fluxo', objetivo='Abrir demo',
                                   ferramentas=('demo.abrir',), origem='instrucao')
    m.adicionar_etapa(pid, 1, alvo='botão', acao='clicar',
                      parametros={'seletor': '#ok'})
    m.fechar()

    m2 = MemoriaProcedural(db)
    proc = m2.obter_procedimento(pid)
    assert proc['objetivo'] == 'Abrir demo'
    assert proc['etapas'][0]['acao'] == 'clicar'
    assert proc['etapas'][0]['parametros']['seletor'] == '#ok'
    m2.fechar()


def test_versao_anterior_preservada_e_correcao_cria_nova(tmp_path):
    m = MemoriaProcedural(tmp_path / 'mem.db')
    pid = m.registrar_procedimento('demo.fluxo', objetivo='v1', origem='instrucao')
    v1 = m.registrar_versao(pid, payload={'etapas': ['a']}, motivo='inicial')
    v2 = m.registrar_correcao(pid, 'usar alvo semântico', versao=2,
                              payload={'etapas': ['b']})
    assert v1 != v2
    versoes = m.obter_versoes(pid)
    assert [v['versao'] for v in versoes] == [1, 2]
    estados = {v['versao']: v['estado'] for v in versoes}
    assert estados[1] == 'OBSOLETO'
    assert estados[2] in ('VALIDADO', 'CONSOLIDADO', 'EM_REVISAO')
    assert m.obter_procedimento(pid)['versao'] == 2
    m.fechar()


def test_exclusao_remove_dados_dependentes(tmp_path):
    db = tmp_path / 'mem.db'
    m = MemoriaProcedural(db)
    pid = m.registrar_procedimento('demo.fluxo', objetivo='x', origem='instrucao')
    m.adicionar_etapa(pid, 1, acao='clicar')
    m.registrar_versao(pid, payload={'etapas': ['a']})
    assert m.excluir_procedimento(pid) is True
    assert m.obter_procedimento(pid) is None
    assert m.obter_versoes(pid) == ()
    con = sqlite3.connect(db)
    assert con.execute('SELECT COUNT(*) FROM steps').fetchone()[0] == 0
    con.close()
    m.fechar()


def test_segredos_sao_redigidos_antes_de_gravar(tmp_path):
    m = MemoriaProcedural(tmp_path / 'mem.db')
    kid = m.registrar_conhecimento(
        titulo='config',
        conteudo='senha: SuperSecreto123 api_key=ABCDEF token: XYZ',
        origem='instrucao')
    texto = json.dumps(m.obter('knowledge', kid), ensure_ascii=False)
    assert 'SuperSecreto123' not in texto
    assert 'ABCDEF' not in texto
    assert 'XYZ' not in texto
    assert '***' in texto
    m.fechar()


def test_eventos_e_checkpoints_sao_persistidos(tmp_path):
    m = MemoriaProcedural(tmp_path / 'mem.db')
    m.registrar_checkpoint('tarefa-1', {'estado': 'pausado', 'etapa': 2})
    cp = m.obter_checkpoint('tarefa-1')
    assert cp['payload']['etapa'] == 2
    m.salvar_checkpoint('tarefa-1', {'estado': 'concluido', 'etapa': 3})
    assert m.obter_checkpoint('tarefa-1')['payload']['etapa'] == 3
    m.fechar()
