# -*- coding: utf-8 -*-
"""RED F08: fila priorizada, concorrência limitada e cancelamento efetivo."""
from __future__ import annotations

import pytest

from core.aprendizado_adaptativo.orquestrador import (
    OrquestradorTarefas, ResultadoTardio)


def test_prioridade_alta_antes_da_baixa():
    o = OrquestradorTarefas()
    o.agendar('baixa', prioridade=20)
    alta = o.agendar('alta', prioridade=90)
    prox = o.executar_proximo()
    assert prox['id'] == alta


def test_no_maximo_tres_pesquisas_concorrentes():
    o = OrquestradorTarefas(max_pesquisas=3)
    ids = [o.agendar(f'p{i}', tipo='pesquisa') for i in range(4)]
    assert ids[:3] and all(ids[:3])
    assert ids[3] is None


def test_cancelamento_impede_execucao_tardia():
    o = OrquestradorTarefas()
    tid = o.agendar('tarefa')
    o.cancelar(tid)
    with pytest.raises(RuntimeError):
        o.executar(tid)


def test_resultado_tardio_de_geracao_antiga_e_descartado():
    o = OrquestradorTarefas()
    tid = o.agendar('tarefa')
    geracao = o.obter(tid)['cancel_generation']
    resultado = o.registrar_resultado(tid, geracao, {'valor': 1})
    assert isinstance(resultado, ResultadoTardio)
    assert resultado.descartado is False
    o.cancelar(tid)
    tardio = o.registrar_resultado(tid, geracao, {'valor': 2})
    assert tardio.descartado is True


def test_encerrar_cancela_fila_inteira():
    o = OrquestradorTarefas()
    ids = [o.agendar(f't{i}') for i in range(3)]
    o.encerrar()
    assert o.executar_proximo() is None
    assert all(o.obter(i)['estado'] == 'CANCELADA' for i in ids)
