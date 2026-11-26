# -*- coding: utf-8 -*-
"""Fase 03 (integração) — gateway na porta real de ferramentas do main."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import main
from core import catalogo_habilidades as CH
from core import permissoes_ferramentas as PF


@pytest.fixture(autouse=True)
def isolado(monkeypatch):
    monkeypatch.setattr(PF, '_CONCESSOES', {})
    monkeypatch.setattr(main, 'types', SimpleNamespace(
        FunctionResponse=lambda **kw: SimpleNamespace(**kw)))
    main._SEGUNDO_PLANO.clear()


def nia():
    obj = object.__new__(main.NiaLive)
    obj.ui = SimpleNamespace(muted=True, current_file='', write_log=Mock(),
                             set_state=Mock(), solicitar_permissao=Mock(),
                             fechar_permissao=Mock())
    obj._current_input_transcript = ''
    obj._ultima_fala_do_dono = ''
    obj._pending_manual_save_destination = ''
    obj._pending_manual_save_extension = ''
    obj._ferramenta_atual = None
    return obj


def chamar(obj, nome, args=None):
    return asyncio.run(obj._execute_tool(SimpleNamespace(
        id='t', name=nome, args=args or {})))


def test_origem_explicita_nao_autorizada_e_barrada(tmp_path, monkeypatch):
    """Quebra: a porta real nao verificava a origem da chamada."""
    efeito = Mock(return_value='status')
    monkeypatch.setattr(main, 'get_system_status', efeito)
    obj = nia()
    marcador = CH.definir_origem('email')
    try:
        resposta = chamar(obj, 'system_status')
    finally:
        CH.restaurar_origem(marcador)
    assert resposta.response['permitido'] is False
    assert not efeito.called


def test_quatro_origens_conhecidas_tem_paridade(monkeypatch):
    """Quebra: normalizar origens mudava o resultado da ferramenta."""
    monkeypatch.setattr(main, 'get_system_status', lambda: 'status comum')
    resultados = []
    for origem in ('chat', 'voz', 'canvas', 'remoto'):
        obj = nia()
        marcador = CH.definir_origem(origem)
        try:
            resultados.append(chamar(obj, 'system_status').response['result'])
        finally:
            CH.restaurar_origem(marcador)
    assert resultados == ['status comum'] * 4


def test_gateway_e_reaproveitado_entre_chamadas(monkeypatch):
    """Quebra: cada chamada recriava o gateway e perdia a correlacao."""
    monkeypatch.setattr(main, 'get_system_status', lambda: 'ok')
    obj = nia()
    chamar(obj, 'system_status')
    primeiro = obj._gateway
    chamar(obj, 'system_status')
    assert primeiro is obj._gateway
