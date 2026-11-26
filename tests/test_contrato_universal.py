# -*- coding: utf-8 -*-
"""Fase 02 — contrato universal: campos opcionais, aliases e schemas.

Cada teste falha antes da implementação por um motivo específico:
campos ausentes, módulo de contrato inexistente ou validação não implementada.
"""
from __future__ import annotations

import pytest

from core import catalogo_habilidades as CH
from core import contrato_universal as CU
from core import registro_aplicativos as RA


def _habilidade():
    return CH.Habilidade(
        id='relatorio_mensal', nome='Relatório mensal',
        descricao='Gera relatório local', exemplo='NIA, gere o relatório.',
        acao='gerar_relatorio',
        aliases=('relatorio', 'relatório mensal'),
    )


def test_habilidade_aceita_campos_opcionais_de_contrato():
    """Quebra: Habilidade não declara schemas, agendabilidade ou aliases."""
    habilidade = CH.Habilidade(
        id='relatorio_mensal', nome='Relatório mensal',
        descricao='Gera relatório local', exemplo='NIA, gere o relatório.',
        acao='gerar_relatorio',
        esquema_entrada={'type': 'object', 'properties': {'mes': {'type': 'STRING'}}},
        esquema_saida={'type': 'object', 'properties': {'ok': {'type': 'BOOLEAN'}}},
        agendavel=True, aliases=('relatorio', 'relatório mensal'),
    )
    assert habilidade.agendavel is True
    assert habilidade.aliases == ('relatorio', 'relatório mensal')


def test_descritor_publica_campos_de_contrato_no_dict():
    """Quebra: DescritorApp não Carrega versão, schemas nem agendabilidade."""
    descritor = RA.DescritorApp(
        id='relatorio', nome='Relatório', descricao='Relatório local',
        esquema_entrada={'type': 'object', 'properties': {}},
        esquema_saida={'type': 'object', 'properties': {}},
        agendavel=True, aliases=('relatorio_mensal',),
    )
    dados = descritor.como_dict()
    assert dados['agendavel'] is True
    assert dados['aliases'] == ['relatorio_mensal']
    assert dados['versao'] == '1.0.0'


def test_descrever_habilidade_gera_contrato_canonico():
    """Quebra: não existe conversão comum entre catálogo e registro."""
    contrato = CU.descrever(_habilidade())
    assert contrato.id == 'relatorio_mensal'
    assert contrato.origem == 'catalogo'
    assert contrato.versao == '1.0.0'
    assert contrato.api == 1


def test_descrever_descritor_respeita_origem_e_permissoes():
    """Quebra: descritores não viram contrato com escopo declarado."""
    descritor = RA.DescritorApp(
        id='hab_relatorio', nome='Relatório', descricao='Relatório local',
        permissoes=('dados:gravar',), origem='catalogo',
    )
    contrato = CU.descrever(descritor)
    assert contrato.origem == 'catalogo'
    assert contrato.permissoes == ('dados:gravar',)


def test_indice_rejeita_alias_que_colia_com_id_existente():
    """Quebra: não há verificação de colisão entre IDs e aliases."""
    primeiro = CU.descrever(_habilidade())
    segundo = CH.Habilidade(
        id='outro', nome='Outro', descricao='Outro', exemplo='NIA, outro.',
        acao='outro', aliases=('relatorio_mensal',),
    )
    with pytest.raises(ValueError, match='Colis'):
        CU.indice((primeiro, CU.descrever(segundo)))


def test_resolver_localiza_contrato_por_alias_sem_ambiguidade():
    """Quebra: aliases não são resolvidos pelo contrato universal."""
    contrato = CU.descrever(_habilidade())
    indice = CU.indice((contrato,))
    assert CU.resolver(indice, 'relatorio mensal').id == 'relatorio_mensal'
    assert CU.resolver(indice, 'inexistente') is None


def test_validar_esquema_rejeita_required_fora_de_properties():
    """Quebra: schemas inválidos ainda são aceitos silenciosamente."""
    esquema = {'type': 'object', 'properties': {'mes': {'type': 'STRING'}},
               'required': ['ano']}
    with pytest.raises(ValueError, match='required'):
        CU.validar_esquema(esquema)


def test_validar_esquema_rejeita_tipo_que_nao_e_objeto():
    """Quebra: schema de raiz não objeto é aceito."""
    with pytest.raises(ValueError, match='object'):
        CU.validar_esquema({'type': 'string'})


def test_descoberta_nao_importa_modulo_do_carregador():
    """Quebra: descrever/carregar índice importa módulo declarado."""
    descritor = RA.DescritorApp(
        id='plugin_ausente', nome='Plugin', descricao='Plugin de teste',
        carregador='modulo_que_nao_existe_123:abrir',
    )
    contrato = CU.descrever(descritor)
    indice = CU.indice((contrato,))
    assert CU.resolver(indice, 'plugin_ausente').id == 'plugin_ausente'
