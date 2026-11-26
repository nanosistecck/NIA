# -*- coding: utf-8 -*-
"""Fluxo ponta a ponta local: lacuna → aprendizado → execução → reuso (F14)."""
from __future__ import annotations

import time
from pathlib import Path

from core import aprendizado as AP
from core.aprendizado_adaptativo import contratos as CT


def _gravar(etapa) -> bool:
    destino = Path(etapa['parametros']['destino'])
    destino.write_text('conteudo real', encoding='utf-8')
    return destino.exists()


def test_fluxo_inédito_aprende_executa_verifica_e_reutiliza(tmp_path):
    from core.aprendizado_adaptativo.adaptadores import construir_avaliador
    from core.aprendizado_adaptativo.consolidacao import Consolidador
    from core.aprendizado_adaptativo.memoria import MemoriaProcedural
    from core.aprendizado_adaptativo.workflows import ExecutorProcedimento

    ap = AP.Aprendizado(caminho=tmp_path / 'aprendizado.json',
                        capacidades=('demo.escrever',))
    assert ap.aprender('crie o arquivo de demonstração', 'demo.escrever') is True

    avaliador = construir_avaliador(
        aprendizado=ap,
        evidencias={'demo.escrever': {'confirmado_em': time.time()}})
    avaliacao = avaliador.avaliar('crie o arquivo de demonstração')
    assert avaliacao.estado is CT.EstadoAvaliacao.CONHECIDO
    assert avaliacao.partes_seguras == ('demo.escrever',)

    db = tmp_path / 'mem.db'
    destino = tmp_path / 'saida.txt'
    mem = MemoriaProcedural(db)
    pid = mem.registrar_procedimento('demo.escrever', objetivo='Criar arquivo',
                                     ferramentas=('demo.escrever',),
                                     origem='instrucao')
    mem.adicionar_etapa(pid, 1, alvo='arquivo', acao='demo.escrever',
                        parametros={'destino': str(destino)},
                        poscondicao='arquivo.existe')
    mem.registrar_versao(pid, versao=1, payload={'ok': True})
    executor = ExecutorProcedimento(
        memoria=mem, executar=_gravar,
        validar=lambda etapa: Path(etapa['parametros']['destino']).exists())
    r = executor.executar(pid, {})
    assert r['estado'] == 'VALIDADO'
    assert destino.read_text(encoding='utf-8') == 'conteudo real'

    c = Consolidador(mem)
    consolidado = c.consolidar({'procedimento_id': pid, 'resultado': 'sucesso',
                                'evidencia': {'arquivo': str(destino)},
                                'origem': 'execucao'})
    assert consolidado['consolidado'] is True
    mem.fechar()

    # Reinício: o conhecimento e o procedimento permanecem e não repetem efeito.
    mem2 = MemoriaProcedural(db)
    executor2 = ExecutorProcedimento(
        memoria=mem2, executar=_gravar,
        validar=lambda etapa: Path(etapa['parametros']['destino']).exists())
    r2 = executor2.executar(pid, {})
    assert r2['repetido'] is True
    assert destino.read_text(encoding='utf-8') == 'conteudo real'
    assert mem2.obter('knowledge', consolidado['knowledge_id']) is not None
    mem2.fechar()
