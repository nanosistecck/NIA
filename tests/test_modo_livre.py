# -*- coding: utf-8 -*-
"""Modo de autonomia total: nenhuma confirmação interativa."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import main
from core import autonomia_total as AT
from core import permissoes_ferramentas as PF


@pytest.fixture(autouse=True)
def modo_live(monkeypatch):
    monkeypatch.setenv('NIA_MODO_LIVRE', '1')
    monkeypatch.setattr(PF, '_CONCESSOES', {})
    monkeypatch.setattr(main, 'types', SimpleNamespace(
        FunctionResponse=lambda **kw: SimpleNamespace(**kw)))
    main._SEGUNDO_PLANO.clear()


def _nia():
    obj = object.__new__(main.NiaLive)
    obj.ui = SimpleNamespace(
        muted=True, current_file='', write_log=Mock(), set_state=Mock(),
        solicitar_permissao=Mock(side_effect=AssertionError('não deve perguntar')),
        fechar_permissao=Mock())
    obj._current_input_transcript = ''
    obj._ultima_fala_do_dono = ''
    obj._pending_manual_save_destination = ''
    obj._pending_manual_save_extension = ''
    obj._ferramenta_atual = None
    return obj


def chamar(obj, nome, args):
    return asyncio.run(obj._execute_tool(SimpleNamespace(id='t', name=nome, args=args)))


def test_modo_livre_esta_ligado_por_padrao():
    """Quebra: não havia forma de desativar confirmações."""
    assert AT.ativado() is True


def test_open_app_executa_sem_prompt(monkeypatch):
    """Quebra: open_app pedia confirmação mesmo em pesquisa/ação simples."""
    efeito = Mock(return_value='abriu')
    monkeypatch.setattr(main, 'open_app', efeito)
    obj = _nia()
    resposta = chamar(obj, 'open_app', {'app_name': 'Calculadora'})
    assert resposta.response['result'] == 'abriu'
    assert efeito.called
    obj.ui.solicitar_permissao.assert_not_called()


def test_pesquisa_executa_sem_prompt(monkeypatch):
    """Quebra: web_search exigia confirmação por ser escopo rede:consultar."""
    efeito = Mock(return_value='resultados')
    monkeypatch.setattr(main, 'web_search_action', efeito)
    obj = _nia()
    obj.ui.show_content = Mock()
    resposta = chamar(obj, 'web_search', {'query': 'teste'})
    assert resposta.response['result'] == 'resultados'
    obj.ui.solicitar_permissao.assert_not_called()


def test_modulo_registrado_executa_sem_prompt(monkeypatch):
    """Quebra: módulos nativos também pediam confirmação."""
    from core import catalogo_habilidades as CH

    chamadas = []
    habilidade = CH.Habilidade(
        id='modulo_livre_teste', nome='Módulo livre', descricao='Teste',
        exemplo='NIA, use o módulo livre.', acao='usar_modulo_livre',
        permissoes=('arquivos:acessar',))
    monkeypatch.setattr(CH, '_MODULOS', {})
    CH.registrar_modulo(
        habilidade,
        lambda termo: chamadas.append(termo) or CH.Resultado(True, 'feito'))
    obj = _nia()
    asyncio.run(obj._executar_modulo_com_confirmacao(habilidade, 'ok', 'chat'))
    assert chamadas == ['ok']
    obj.ui.solicitar_permissao.assert_not_called()


def test_modo_pode_ser_desativado(monkeypatch):
    """Quebra: não havia opt-out para volta ao modo seguro."""
    monkeypatch.setenv('NIA_MODO_LIVRE', '0')
    assert AT.ativado() is False
