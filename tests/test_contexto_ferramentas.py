# -*- coding: utf-8 -*-
"""Contexto da ferramenta ativa: ações tipadas, concorrência e ambiguidade."""
import threading
from types import SimpleNamespace

import pytest

import main
from core.contexto_ferramentas import (AcaoTipada, ContextoFerramentas,
                                       ResultadoTipado)


def test_acao_e_resultado_correlacionados():
    ctx = ContextoFerramentas()
    acao = ctx.iniciar('open_app', {'app_name': 'Calculadora'})
    assert isinstance(acao, AcaoTipada) and acao.ferramenta == 'open_app'
    assert ctx.ativo is acao and ctx.sequencia == 1
    resultado = ctx.concluir(True, 'abriu')
    assert isinstance(resultado, ResultadoTipado)
    assert resultado.sequencia == 1 and resultado.ok and resultado.resumo == 'abriu'
    assert ctx.ativo is None and ctx.ultimo_resultado is resultado
    assert ctx.concluir(True, 'atrasado') is None


def test_concorrencia_segunda_acao_substitui_a_anterior():
    ctx = ContextoFerramentas()
    primeira = ctx.iniciar('web_search', {'query': 'a'})
    segunda = ctx.iniciar('weather_report', {'cidade': 'b'})
    assert ctx.sequencia == 2 and ctx.ativo is segunda
    assert ctx.concluir(True, 'segunda') is not None
    assert ctx.ativo is None
    assert ctx.ultimo_resultado.ferramenta == 'weather_report'
    assert primeira.ferramenta == 'web_search'  # registro antigo intacto


def test_ambiguidade_nunca_vira_shell():
    ctx = ContextoFerramentas()
    ctx.iniciar('open_app', {'app_name': 'Calculadora'})
    for frase in ('faz isso', 'aquilo', 'roda aí', 'executa', 'vai', 'coloca'):
        assert ctx.resolver(frase) is None
    for nome in ('executar_comando', 'shell', 'powershell', 'cmd', 'bash'):
        with pytest.raises(PermissionError):
            ctx.iniciar(nome, {'comando': 'qualquer'})
    assert ctx.ativo is not None


def test_seguimento_explicito_reusa_apenas_a_acao_tipada():
    ctx = ContextoFerramentas()
    acao = ctx.iniciar('file_controller', {'action': 'read', 'path': '/tmp/x'})
    repetida = ctx.resolver('  Repita, por favor!  ')
    assert repetida is not None
    assert repetida.ferramenta == acao.ferramenta
    assert repetida.argumentos == acao.argumentos
    assert 'comando' not in repetida.argumentos
    # "pare" revoga a prévia sem inventar nova ação.
    assert ctx.resolver('não, pare') is None
    assert ctx.ativo is None


def test_falha_e_descarte_por_troca_de_assunto():
    ctx = ContextoFerramentas()
    ctx.iniciar('youtube_video', {'query': 'x'})
    falha = ctx.falhar('sem rede (fictício)')
    assert falha is not None and falha.ok is False and 'sem rede' in falha.resumo
    ctx.iniciar('globo', {'cidade': 'Tóquio'})
    ctx.cancelar()
    assert ctx.ativo is None
    assert ctx.concluir(True, 'resultado em voo') is None
    assert ctx.ultimo_resultado is falha


def test_expiracao_do_contexto_com_relogio_ficticio():
    agora = [0.0]
    ctx = ContextoFerramentas(ttl=10, relogio=lambda: agora[0])
    ctx.iniciar('system_status', {})
    agora[0] = 9.0
    assert ctx.ativo is not None
    agora[0] = 11.0
    assert ctx.ativo is None and ctx.resolver('repita') is None


def test_argumentos_invalidos_sao_recusados():
    ctx = ContextoFerramentas()
    with pytest.raises(ValueError):
        ctx.iniciar('', {})
    with pytest.raises(ValueError):
        ctx.iniciar('open_app', ['invalido'])
    with pytest.raises(ValueError):
        ctx.iniciar('open_app', {'valor': float('nan')})


def test_preserva_hora_clima_e_canvas_sem_reescrever():
    ctx = ContextoFerramentas()
    for nome, args in (('hora_agora', {}), ('weather_report', {'cidade': 'São Paulo'}),
                       ('system_status', {})):
        acao = ctx.iniciar(nome, args)
        assert acao.argumentos == args  # sem "comando" injetado
        assert ctx.concluir(True, 'ok') is not None
        assert ctx.ultimo_resultado.ferramenta == nome


def test_integracao_nialive_ctx_e_interrompcao():
    obj = object.__new__(main.NiaLive)
    obj._contexto_ferramentas = ContextoFerramentas()
    obj.ui = SimpleNamespace(write_log=lambda texto: None, muted=True,
                             set_state=lambda estado: None)
    obj._speaking_lock = threading.Lock()
    obj._is_speaking = False
    obj._tool_busy = False
    obj._interrupted = False
    obj._interruptivel = True
    obj._turno_seq = 0
    obj._fala_seq = 0
    obj._boca_bypass = False
    obj._ferramenta_futuro = None
    obj.audio_in_queue = None
    obj._loop = None
    obj._turn_done_event = None
    obj._mic_fechado_ate = 0.0
    obj._consentimentos = None
    obj._contexto_ferramentas.iniciar('open_app', {'app_name': 'Calculadora'})
    obj.interrupt(silencioso=True)
    assert obj._contexto_ferramentas.ativo is None
    assert obj._contexto_ferramentas.resolver('repita') is None
    obj._contexto_ferramentas.iniciar('system_status', {})
    obj._ctx_concluir(True, 'ok')
    assert obj._contexto_ferramentas.ultimo_resultado.ok is True
