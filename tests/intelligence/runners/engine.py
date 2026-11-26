# -*- coding: utf-8 -*-
"""Executor dos cenários pelos pontos reais de entrada da NIA."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import main
from core import catalogo_habilidades as CH
from core import comandos_aprendizado as CA
from core import comandos_agenda as AG
from core import comandos_agenda as CAG
from core import motor_conhecimento as MC
from core import permissoes_ferramentas as PF
from tests.intelligence.evaluators import avaliar
from tests.intelligence.fixtures.environment import LabEnvironment


def _executar_tool(lab, cenario):
    nome = cenario.allowed[0] if cenario.allowed else 'shell_inventado'
    motor = lab.motor()
    resposta = asyncio.run(motor._execute_tool(SimpleNamespace(
        id=cenario.id, name=nome, args=dict(cenario.arguments))))
    if resposta.response.get('result'):
        lab.respostas.append(str(resposta.response['result']))
    return resposta


def _executar_frase(lab, cenario):
    motor = lab.motor()
    motor._on_text_command(cenario.message)
    intencao_agenda = CAG.processar(cenario.message)
    if intencao_agenda.get('tratado') and intencao_agenda.get('acao') != 'saudacao':
        lab.observado.append(str(intencao_agenda.get('acao') or ''))
    habilidade, _termo = CH.reconhecer(cenario.message)
    if habilidade is not None:
        lab.observado.append(habilidade.id)
    if not lab.observado and lab.respostas:
        texto = ' '.join(lab.respostas).lower()
        for marcador, nome in (('são 10h', 'hora_agora'), ('status ok', 'system_status'),
                               ('previsao ok', 'weather_report'),
                               ('resultados', 'web_search')):
            if marcador in texto:
                lab.observado.append(nome)


def _executar_memoria(lab, cenario):
    antes = set(PF.ESCOPOS_LEGADOS)
    conhecimento = MC.MotorConhecimento(caminho=lab.raiz / 'conhecimento.json')
    identificador = conhecimento.registrar(
        'energia solar', ('fixture-local',), 'Energia solar gera eletricidade.')
    if 'ausente' in cenario.expected:
        lab.observado.append('ausente' if set(PF.ESCOPOS_LEGADOS) == antes else 'indevido')
    else:
        registro = conhecimento.obter(identificador)
        lab.observado.append('memoria' if registro and 'eletricidade' in registro['conclusao'] else 'ausente')
        lab.respostas.append(registro['conclusao'] if registro else '')


def executar(cenario):
    with LabEnvironment() as lab:
        with patch.object(main, 'types', SimpleNamespace(
                FunctionResponse=lambda **kw: SimpleNamespace(**kw))):
            if cenario.kind == 'phrase':
                _executar_frase(lab, cenario)
            elif cenario.kind == 'tool':
                _executar_tool(lab, cenario)
            elif cenario.kind == 'agenda':
                resultado = AG.processar(cenario.message)
                lab.observado.append(str(resultado.get('acao') or ''))
            elif cenario.kind == 'learning':
                from core import aprendizado as AP
                memoria = AP.Aprendizado(
                    caminho=lab.raiz / '.nia' / 'aprendizado.json',
                    capacidades=('planos', 'agenda', 'hab_resumo_dia'))
                memoria.aprender('escritório', 'planos')
                tipo, _dados = CA.reconhecer(cenario.message)
                lab.observado.append(tipo)
                if cenario.expected == 'planos':
                    alvo, _ = lab.motor()._habilidade_aprendida(cenario.message)
                    if alvo is not None:
                        lab.observado.append('planos')
            elif cenario.kind == 'memory':
                _executar_memoria(lab, cenario)
            else:
                lab.observado.append('nao_suportado')
    avaliacao = avaliar(cenario, lab.observado, lab.respostas, lab.argumentos)
    if cenario.blocked:
        from tests.intelligence.contracts import Evaluation
        avaliacao = Evaluation(
            scenario_id=cenario.id, ok=True, blocked=True,
            intent_ok=False, tool_ok=False, params_ok=False,
            effect_ok=False, response_ok=False, security_ok=avaliacao.security_ok,
            observed=avaliacao.observed,
            details='depende de decisão do modelo/contexto; não é verificação determinística')
    return avaliacao


def executar_todos(cenarios):
    return [executar(cenario) for cenario in cenarios]
