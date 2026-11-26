# -*- coding: utf-8 -*-
"""Fase 09 — retenção, deduplicação, contradições e exclusão com índices."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core import consolidacao_memoria as CM


def _item(id, texto, tipo='fato', dias=0, fonte='local'):
    criado = datetime(2026, 11, 25, tzinfo=timezone.utc).timestamp() - dias * 86400
    return CM.ItemMemoria(
        id=id, texto=texto, tipo=tipo,
        criado_em=datetime.fromtimestamp(criado, timezone.utc).isoformat(),
        fonte=fonte, referencias=())


def test_deduplicacao_mantem_o_registro_mais_recente():
    """Quebra: duplicatas eram mantidas todas sem critério."""
    itens = (_item('a', 'Gosta de café', dias=10),
             _item('b', 'gosta de cafe', dias=1))
    mantidos, removidos = CM.deduplicar(itens)
    assert [i.id for i in mantidos] == ['b']
    assert removidos == ('a',)


def test_retencao_preserva_preferencias_e_compromissos():
    """Quebra: retenção apagava preferências explícitas antigas."""
    itens = (_item('a', 'Fato antigo', dias=200),
             _item('b', 'Prefere chá', tipo='preferencia', dias=200),
             _item('c', 'Compromisso pago', tipo='compromisso', dias=200))
    assert [i.id for i in CM.retencao(itens, dias=90)] == ['b', 'c']


def test_contradicoes_sao_apontadas_sem_resolver_automaticamente():
    """Quebra: contradições eram silenciosamente sobrescritas."""
    itens = (_item('a', 'cidade: Recife'), _item('b', 'cidade: não é Recife'))
    pares = CM.contradicoes(itens)
    assert pares == (('a', 'b'),)


def test_resumo_traz_referencias_e_respeita_limite():
    """Quebra: resumo não ligava afirmações às suas fontes."""
    relatorio = CM.resumo((_item('a', 'Gosta de café'), _item('b', 'Prefere chá')),
                          limite=40)
    assert '[ref:' in relatorio
    assert len(relatorio) <= 40


def test_exclusao_remove_item_e_indice_derivado():
    """Quebra: exclusão deixava o índice derivado apontando para o item."""
    itens = (_item('a', 'Gosta de café'), _item('b', 'Prefere chá'))
    indice = CM.construir_indice(itens)
    novos, novo_indice = CM.excluir(itens, indice, 'a')
    assert [i.id for i in novos] == ['b']
    assert 'gosta de cafe' not in novo_indice
    assert 'gosta de cafe' in indice
