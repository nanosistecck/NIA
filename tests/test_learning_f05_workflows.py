# -*- coding: utf-8 -*-
"""RED F05: procedimentos declarativos seguros e idempotentes."""
from __future__ import annotations

import pytest

from core.aprendizado_adaptativo.contratos import Cancelado, ContextoCancelamento
from core.aprendizado_adaptativo.memoria import MemoriaProcedural
from core.aprendizado_adaptativo.workflows import ExecutorProcedimento


def _procedimento(mem, nome='demo.fluxo', ferramentas=('demo.abrir',)):
    pid = mem.registrar_procedimento(nome, objetivo='Abrir demo',
                                     ferramentas=ferramentas, origem='instrucao')
    mem.adicionar_etapa(pid, 1, alvo='botao', acao='demo.abrir', parametros={'x': 1},
                        poscondicao='demo.aberto')
    mem.registrar_versao(pid, versao=1, payload={'etapas': ['clicar']})
    return pid


def test_procedimento_executa_etapas_e_valida_poscondicao(tmp_path):
    mem = MemoriaProcedural(tmp_path / 'm.db')
    pid = _procedimento(mem)
    feitos = []
    ex = ExecutorProcedimento(
        memoria=mem,
        executar=lambda etapa: feitos.append(etapa['acao']) or True,
        validar=lambda etapa: True,
    )
    r = ex.executar(pid, {'alvo': 'demo'})
    assert r['estado'] == 'VALIDADO'
    assert feitos == ['demo.abrir']
    assert ex.memoria.obter_checkpoint(pid)['payload']['estado'] == 'VALIDADO'
    mem.fechar()


def test_reexecucao_idempotente_nao_repete_efeito(tmp_path):
    mem = MemoriaProcedural(tmp_path / 'm.db')
    pid = _procedimento(mem)
    feitos = []
    ex = ExecutorProcedimento(
        memoria=mem,
        executar=lambda etapa: feitos.append(etapa['acao']) or True,
        validar=lambda etapa: True,
    )
    ex.executar(pid, {'alvo': 'demo'})
    r2 = ex.executar(pid, {'alvo': 'demo'})
    assert r2['repetido'] is True
    assert feitos == ['demo.abrir']
    mem.fechar()


def test_ferramenta_fora_da_lista_e_bloqueada(tmp_path):
    mem = MemoriaProcedural(tmp_path / 'm.db')
    pid = _procedimento(mem, ferramentas=('demo.ler',))
    chamados = []
    ex = ExecutorProcedimento(
        memoria=mem, executar=lambda etapa: chamados.append(etapa) or True,
        validar=lambda etapa: True)
    r = ex.executar(pid, {})
    assert r['estado'] == 'BLOQUEADO'
    assert chamados == []
    mem.fechar()


def test_codigo_arbitrario_aprendido_nunca_e_executado(tmp_path):
    mem = MemoriaProcedural(tmp_path / 'm.db')
    pid = _procedimento(mem)
    chamados = []
    ex = ExecutorProcedimento(
        memoria=mem, executar=lambda etapa: chamados.append(etapa) or True,
        validar=lambda etapa: True)
    r = ex.executar(pid, {'acao': 'os.system("echo pwned")'})
    assert r['estado'] == 'REJEITADO'
    assert chamados == []
    mem.fechar()


def test_poscondicao_falha_nao_consolida(tmp_path):
    mem = MemoriaProcedural(tmp_path / 'm.db')
    pid = _procedimento(mem)
    ex = ExecutorProcedimento(
        memoria=mem, executar=lambda etapa: True, validar=lambda etapa: False)
    r = ex.executar(pid, {'alvo': 'outro'})
    assert r['estado'] == 'FALHOU'
    assert ex.memoria.obter_checkpoint(pid)['payload']['estado'] == 'FALHOU'
    mem.fechar()


def test_cancelamento_impede_acao_tardia(tmp_path):
    mem = MemoriaProcedural(tmp_path / 'm.db')
    pid = _procedimento(mem)
    ctx = ContextoCancelamento()
    chamados = []
    ex = ExecutorProcedimento(
        memoria=mem, executar=lambda etapa: chamados.append(etapa) or True,
        validar=lambda etapa: True, cancelamento=ctx)
    ctx.cancelar()
    with pytest.raises(Cancelado):
        ex.executar(pid, {})
    assert chamados == []
    mem.fechar()
