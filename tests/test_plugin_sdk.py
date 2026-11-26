# -*- coding: utf-8 -*-
"""Fase 04 — SDK de plugins: contrato versionado, DTOs e transporte local."""
from __future__ import annotations

import json

import pytest

from core import plugin_sdk as PS

METODOS = ('initialize', 'get_capabilities', 'execute', 'open_ui',
           'health_check', 'get_status', 'cancel', 'shutdown')


def test_mock_cumpre_todos_os_metodos_do_contrato():
    """Quebra: não existe contrato verificável para plugins."""
    plugin = PS.MockPlugin()
    assert PS.validar_contrato(plugin) is True
    for metodo in METODOS:
        assert callable(getattr(plugin, metodo))


def test_manifesto_rejeita_versao_de_api_incompativel():
    """Quebra: versões incompatíveis eram aceitas sem checagem."""
    manifesto = PS.manifesto_padrao()
    manifesto['api'] = 2
    with pytest.raises(ValueError, match='API'):
        PS.validar_manifesto(manifesto)


def test_manifesto_rejeita_importacao_de_main_ou_ui():
    """Quebra: plugins podiam declarar dependência do runtime da NIA."""
    manifesto = PS.manifesto_padrao()
    manifesto['imports'] = ['main']
    with pytest.raises(PermissionError, match='main'):
        PS.validar_manifesto(manifesto)


def test_dtos_sao_serializaveis_sem_objetos_vivos():
    """Quebra: retorno do plugin não era convertido em DTO serializável."""
    plugin = PS.MockPlugin()
    plugin.initialize({'perfil': 'teste'})
    resposta = plugin.get_capabilities()
    texto = json.dumps(resposta.como_dict(), ensure_ascii=False)
    assert 'echo' in texto
    assert 'initialize' not in texto


def test_transporte_local_exige_token_autenticado():
    """Quebra: transporte local aceitava chamada sem autenticação."""
    transporte = PS.TransporteLocal(token='segredo-de-teste')
    with pytest.raises(PermissionError, match='token'):
        transporte.chamar('health_check', {}, token='errado')


def test_transporte_local_devolve_resposta_do_metodo():
    """Quebra: não havia ponte autenticada entre host e plugin."""
    plugin = PS.MockPlugin()
    transporte = PS.TransporteLocal(token='segredo-de-teste', plugin=plugin)
    resposta = transporte.chamar('health_check', {}, token='segredo-de-teste')
    assert resposta.ok is True
    assert resposta.dados['saudavel'] is True


def test_cancelamento_e_shutdown_sao_idempotentes():
    """Quebra: cancel/shutdown não tinham efeito verificável."""
    plugin = PS.MockPlugin()
    assert plugin.cancel('abc') is True
    assert plugin.shutdown() is True
    assert plugin.shutdown() is True
    assert plugin.get_status().estado == 'encerrado'


def test_falha_do_worker_nao_derruba_o_host():
    """Quebra: exceção do plugin vazava sem conversão em DTO."""
    plugin = PS.MockPlugin()
    plugin.falhar_proxima = True
    resposta = plugin.execute('eco', {'texto': 'oi'})
    assert resposta.ok is False
    assert resposta.erro == 'falha_do_plugin'
