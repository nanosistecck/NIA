# -*- coding: utf-8 -*-
"""RED F14: recuperação de checkpoints sem reativar controle/observação."""
from __future__ import annotations


def test_checkpoint_restaura_como_pausado(tmp_path):
    from core.aprendizado_adaptativo.memoria import MemoriaProcedural
    from core.aprendizado_adaptativo.recuperacao import salvar_estado, restaurar_estado

    mem = MemoriaProcedural(tmp_path / 'm.db')
    salvar_estado(mem, 'tarefa-1', {'estado': 'CONTROLE_ATIVO', 'etapa': 4})
    r = restaurar_estado(mem, 'tarefa-1')
    assert r['estado'] == 'PAUSADO'
    assert r['reativado'] is False
    assert r['payload']['etapa'] == 4
    mem.fechar()


def test_sem_checkpoint_devolve_estado_seguro(tmp_path):
    from core.aprendizado_adaptativo.memoria import MemoriaProcedural
    from core.aprendizado_adaptativo.recuperacao import restaurar_estado

    mem = MemoriaProcedural(tmp_path / 'm.db')
    r = restaurar_estado(mem, 'inexistente')
    assert r == {'estado': 'SEM_ESTADO', 'reativado': False, 'payload': {}}
    mem.fechar()
