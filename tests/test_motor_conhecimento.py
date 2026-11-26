# -*- coding: utf-8 -*-
"""Fase 10 — motor de conhecimento com fontes, lacunas e revisões."""
from __future__ import annotations

import json

import pytest

from core import motor_conhecimento as MC


class IndiceFalso:
    def __init__(self, trechos):
        self.trechos = trechos
        self.termos = []

    def buscar(self, termo, limite=10):
        self.termos.append(termo)
        return [t for t in self.trechos if termo.casefold() in t['texto'].casefold()][:limite]


def _trecho(fonte, texto):
    return {'fonte': fonte, 'texto': texto, 'posicao': 0}


def test_busca_local_funciona_sem_fts5_e_sem_rede(tmp_path):
    """Quebra: sem FTS5 a busca local não tinha fallback."""
    indice = IndiceFalso([_trecho('manual', 'garantia do produto')])
    motor = MC.MotorConhecimento(caminho=tmp_path / 'conhecimento.json',
                                 indice=indice, fts5=False,
                                 autorizadas=('manual',))
    resultados = motor.buscar('garantia')
    assert resultados[0]['fonte'] == 'manual'
    assert indice.termos == ['garantia']


def test_fonte_nao_autorizada_e_ignorada(tmp_path):
    """Quebra: qualquer fonte era indexada e devolvida."""
    indice = IndiceFalso([_trecho('internet', 'garantia externa')])
    motor = MC.MotorConhecimento(caminho=tmp_path / 'c.json', indice=indice,
                                 fts5=False, autorizadas=())
    assert motor.buscar('garantia') == ()
    assert indice.termos == []


def test_pesquisa_registra_fontes_data_conclusao_e_lacunas(tmp_path):
    """Quebra: pesquisas não eram registradas com proveniência."""
    caminho = tmp_path / 'c.json'
    identificador = MC.MotorConhecimento(caminho=caminho).registrar(
        'garantia', ('manual',), 'Cobertura de 12 meses.', ('prazo',))
    outro = MC.MotorConhecimento(caminho=caminho)
    registro = outro.obter(identificador)
    assert registro['fontes'] == ['manual']
    assert registro['conclusao'] == 'Cobertura de 12 meses.'
    assert registro['lacunas'] == ['prazo']
    assert registro['criado_em']


def test_revisao_incrementa_versao_da_conclusao(tmp_path):
    """Quebra: revisões sobrescreviam sem histórico."""
    motor = MC.MotorConhecimento(caminho=tmp_path / 'c.json')
    identificador = motor.registrar('garantia', ('manual',), '12 meses')
    assert motor.revisar(identificador, '24 meses') is True
    assert motor.obter(identificador)['revisoes'] == 1
    assert motor.obter(identificador)['conclusao'] == '24 meses'


def test_exclusao_remove_pesquisa_e_referencia_de_canvas(tmp_path):
    """Quebra: exclusão deixava referências derivadas no Canvas."""
    motor = MC.MotorConhecimento(caminho=tmp_path / 'c.json')
    identificador = motor.registrar('garantia', ('manual',), '12 meses')
    cartao = motor.integrar_canvas(identificador)
    assert cartao['pesquisa_id'] == identificador
    assert motor.excluir(identificador) is True
    assert motor.obter(identificador) is None
    assert motor.referencias_canvas() == ()


def test_estado_persistido_e_json_valido(tmp_path):
    """Quebra: registro não era gravado em disco."""
    caminho = tmp_path / 'c.json'
    MC.MotorConhecimento(caminho=caminho).registrar('x', ('manual',), 'y')
    dados = json.loads(caminho.read_text(encoding='utf-8'))
    assert len(dados['pesquisas']) == 1
