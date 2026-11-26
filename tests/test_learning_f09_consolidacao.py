# -*- coding: utf-8 -*-
"""RED F09: consolidação de experiências com versões e correções."""
from __future__ import annotations


def _mem(tmp_path):
    from core.aprendizado_adaptativo.memoria import MemoriaProcedural
    return MemoriaProcedural(tmp_path / 'm.db')


def test_experiencia_valida_gera_conhecimento_e_versao(tmp_path):
    from core.aprendizado_adaptativo.consolidacao import Consolidador
    mem = _mem(tmp_path)
    pid = mem.registrar_procedimento('fluxo', objetivo='x', origem='instrucao')
    c = Consolidador(mem)
    r = c.consolidar({'procedimento_id': pid, 'resultado': 'sucesso',
                      'evidencia': {'estado': 'ativo'}, 'origem': 'execucao'})
    assert r['consolidado'] is True
    assert mem.obter('knowledge', r['knowledge_id']) is not None
    versoes = mem.obter_versoes(pid)
    assert versoes and versoes[-1]['estado'] == 'CONSOLIDADO'
    mem.fechar()


def test_experiencia_falha_preserva_ultima_versao_valida(tmp_path):
    from core.aprendizado_adaptativo.consolidacao import Consolidador
    mem = _mem(tmp_path)
    pid = mem.registrar_procedimento('fluxo', objetivo='x', origem='instrucao')
    mem.registrar_versao(pid, versao=1, payload={'ok': True}, estado='VALIDADO')
    antes = mem.obter_procedimento(pid)['versao']
    c = Consolidador(mem)
    resultado = c.consolidar({'procedimento_id': pid, 'resultado': 'falha',
                              'evidencia': {}, 'origem': 'execucao'})
    assert resultado['consolidado'] is False
    assert mem.obter_procedimento(pid)['versao'] == antes
    mem.fechar()


def test_correcao_explicita_tem_precedencia(tmp_path):
    from core.aprendizado_adaptativo.consolidacao import Consolidador
    mem = _mem(tmp_path)
    pid = mem.registrar_procedimento('fluxo', objetivo='x', origem='instrucao')
    mem.registrar_versao(pid, versao=1, payload={'alvo': 'antigo'}, estado='VALIDADO')
    c = Consolidador(mem)
    c.aplicar_correcao(pid, 'usar alvo semântico', versao=2,
                       payload={'alvo': 'semantico'})
    versoes = {v['versao']: v for v in mem.obter_versoes(pid)}
    assert versoes[1]['estado'] == 'OBSOLETO'
    assert versoes[2]['estado'] in ('VALIDADO', 'CONSOLIDADO', 'EM_REVISAO')
    mem.fechar()


def test_exclusao_invalida_cache(tmp_path):
    from core.aprendizado_adaptativo.consolidacao import Consolidador
    db = tmp_path / 'm.db'
    mem = _mem(tmp_path)
    kid = mem.registrar_conhecimento('temporal', 'conteudo', origem='execucao')
    c = Consolidador(mem)
    assert c.obter(kid) is not None
    assert c.excluir(kid) is True
    assert c.obter(kid) is None
    mem.fechar()
