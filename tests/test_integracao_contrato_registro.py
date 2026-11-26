# -*- coding: utf-8 -*-
"""Integração Fase 02 → registro central: metadados de contrato propagados."""
from __future__ import annotations

import pytest

from core import catalogo_habilidades as CH
from core import registro_aplicativos as RA


@pytest.fixture(autouse=True)
def isolado(monkeypatch):
    monkeypatch.setattr(RA, '_DESCRITORS', {})
    monkeypatch.setattr(CH, '_MODULOS', {})
    yield


def test_sincronizacao_publica_versao_schemas_e_agendabilidade():
    """Quebra: sincronizar_habilidades descartava os campos do contrato."""
    habilidade = CH.Habilidade(
        id='relatorio', nome='Relatório', descricao='Relatório local',
        exemplo='NIA, gere o relatório.', acao='gerar',
        versao='2.1.0', api=1,
        esquema_entrada={'type': 'object', 'properties': {'mes': {'type': 'STRING'}}},
        esquema_saida={'type': 'object', 'properties': {}},
        agendavel=True, aliases=('relatorio mensal',),
    )
    CH.registrar_modulo(habilidade, lambda termo: CH.Resultado(True, 'ok'))
    RA.sincronizar_habilidades()
    descritor = RA.por_id('hab_relatorio')
    assert descritor.versao == '2.1.0'
    assert descritor.api == 1
    assert descritor.agendavel is True
    assert descritor.aliases == ('relatorio mensal',)
    assert 'mes' in descritor.esquema_entrada['properties']


def test_descritor_continua_valido_com_campos_novos():
    """Quebra: validação do registro rejeitava metadados do contrato."""
    RA.registrar(RA.DescritorApp(
        id='app_contrato', nome='App', descricao='App de teste',
        versao='1.2.3', agendavel=True, aliases=('aplicativo',),
    ))
    assert RA.por_id('app_contrato').versao == '1.2.3'
