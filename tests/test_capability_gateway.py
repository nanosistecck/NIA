# -*- coding: utf-8 -*-
"""Fase 03 — Capability Gateway sobre o executor único existente."""
from __future__ import annotations

import threading

import pytest

from core import capability_gateway as CG

DECLARACOES = [{
    'name': 'hora_agora',
    'description': 'Hora local',
    'parameters': {'type': 'OBJECT', 'properties': {}},
}]


def test_gateway_recusa_origem_fora_das_quatro_conhecidas():
    """Quebra: qualquer origem era aceita sem validação."""
    gateway = CG.CapabilityGateway(declaracoes=DECLARACOES)
    with pytest.raises(PermissionError, match='Origem'):
        gateway.validar(CG.Solicitacao(ferramenta='hora_agora', origem='email'))


def test_gateway_valida_argumentos_com_as_declaracoes_reais():
    """Quebra: argumentos não declarados chegavam ao executor."""
    gateway = CG.CapabilityGateway(declaracoes=DECLARACOES)
    with pytest.raises(ValueError, match='Argumento'):
        gateway.validar(CG.Solicitacao(
            ferramenta='hora_agora', argumentos={'cidade': 'Recife'}, origem='chat'))


def test_gateway_normaliza_resultado_do_executor_unico():
    """Quebra: não existe forma comum de devolver resultado por origem."""
    gateway = CG.CapabilityGateway(declaracoes=DECLARACOES)
    resultado = gateway.executar(
        CG.Solicitacao(ferramenta='hora_agora', origem='voz'),
        executador=lambda nome, args: {'result': 'São 10h.'},
    )
    assert resultado.ok is True
    assert resultado.mensagem == 'São 10h.'
    assert resultado.origem == 'voz'
    assert resultado.ferramenta == 'hora_agora'


def test_gateway_respeita_cancelamento_antes_da_execucao():
    """Quebra: cancelamento não era verificado."""
    cancelamento = threading.Event()
    cancelamento.set()
    gateway = CG.CapabilityGateway(declaracoes=DECLARACOES)
    with pytest.raises(CG.Cancelamento):
        gateway.executar(
            CG.Solicitacao(ferramenta='hora_agora', origem='canvas',
                           cancelamento=cancelamento),
            executador=lambda nome, args: 'não deve rodar',
        )


def test_gateway_recusa_chamada_duplicada_em_voo():
    """Quebra: duas origens podiam disparar a mesma ferramenta ao mesmo tempo."""
    iniciou = threading.Event()
    liberar = threading.Event()
    chamadas = []

    def executor(nome, args):
        chamadas.append(nome)
        iniciou.set()
        liberar.wait(3)
        return 'ok'

    gateway = CG.CapabilityGateway(declaracoes=DECLARACOES)
    solicitacao = CG.Solicitacao(ferramenta='hora_agora', origem='chat')
    thread = threading.Thread(target=gateway.executar, args=(solicitacao, executor))
    thread.start()
    assert iniciou.wait(3)
    with pytest.raises(RuntimeError, match='duplicada'):
        gateway.executar(solicitacao, executor)
    liberar.set()
    thread.join(3)
    assert chamadas == ['hora_agora']


def test_gateway_devolve_resumo_sem_catalogo_integral():
    """Quebra: o resultado incluía a lista completa de capacidades."""
    gateway = CG.CapabilityGateway(declaracoes=DECLARACOES)
    resumo = gateway.resumo()
    assert resumo == ()
