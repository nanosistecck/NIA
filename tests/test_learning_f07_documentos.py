# -*- coding: utf-8 -*-
"""RED F07: documentos inteligentes com revisão otimista e undo/redo."""
from __future__ import annotations

import pytest

from core.aprendizado_adaptativo.documentos import (
    DocumentoInteligente, ConflitoRevisao)


def test_blocos_tipados_e_exportacao_markdown():
    d = DocumentoInteligente(titulo='Plano de estudo')
    d.adicionar_bloco('titulo', {'texto': 'Semana 1'})
    d.adicionar_bloco('checklist', {'itens': ['Ler', 'Praticar']})
    md = d.exportar_markdown()
    assert '# Plano de estudo' in md
    assert '- [ ] Ler' in md and '- [ ] Praticar' in md


def test_revisao_otimista_bloqueia_edicao_antiga():
    d = DocumentoInteligente(titulo='Doc')
    bid = d.adicionar_bloco('texto', {'texto': 'v1'})
    d.editar_bloco(bid, {'texto': 'v2'}, revisao=d.revisao)
    with pytest.raises(ConflitoRevisao):
        d.editar_bloco(bid, {'texto': 'v3'}, revisao=0)


def test_desfazer_e_refazer():
    d = DocumentoInteligente(titulo='Doc')
    bid = d.adicionar_bloco('texto', {'texto': 'original'})
    d.editar_bloco(bid, {'texto': 'novo'}, revisao=d.revisao)
    d.desfazer()
    assert d.blocos[0]['dados']['texto'] == 'original'
    d.refazer()
    assert d.blocos[0]['dados']['texto'] == 'novo'


def test_persistencia_no_memoria_e_recuperacao(tmp_path):
    from core.aprendizado_adaptativo.memoria import MemoriaProcedural
    mem = MemoriaProcedural(tmp_path / 'm.db')
    d = DocumentoInteligente(titulo='Doc persistido', memoria=mem)
    d.adicionar_bloco('lista', {'itens': ['a', 'b']})
    did = d.salvar()

    d2 = DocumentoInteligente.carregar(did, memoria=mem)
    assert d2.titulo == 'Doc persistido'
    assert d2.blocos[0]['dados']['itens'] == ['a', 'b']
    mem.fechar()
