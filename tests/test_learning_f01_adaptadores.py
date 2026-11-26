# -*- coding: utf-8 -*-
"""RED F01: o avaliador padrão usa aprendizado e permissões reais."""
from __future__ import annotations

import time

from core import aprendizado as AP
from core.aprendizado_adaptativo import contratos as CT


def test_avaliador_padrao_resolve_aprendizado_real(tmp_path):
    from core.aprendizado_adaptativo.adaptadores import construir_avaliador

    mem = AP.Aprendizado(caminho=tmp_path / 'aprendizado.json',
                         capacidades=('demo.abrir',))
    assert mem.aprender('abra a demonstração', 'demo.abrir') is True
    avaliador = construir_avaliador(
        aprendizado=mem,
        evidencias={'demo.abrir': {'confirmado_em': time.time()}},
    )
    r = avaliador.avaliar('abra a demonstração')
    assert r.estado is CT.EstadoAvaliacao.CONHECIDO
    assert r.partes_seguras == ('demo.abrir',)
    assert r.eventos[-1].schema_version == 1


def test_avaliador_padrao_nao_confia_em_frase_desconhecida(tmp_path):
    from core.aprendizado_adaptativo.adaptadores import construir_avaliador

    mem = AP.Aprendizado(caminho=tmp_path / 'aprendizado.json',
                         capacidades=('demo.abrir',))
    avaliador = construir_avaliador(aprendizado=mem, evidencias={})
    r = avaliador.avaliar('faça algo totalmente novo')
    assert r.estado is CT.EstadoAvaliacao.DESCONHECIDO
