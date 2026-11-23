# -*- coding: utf-8 -*-
"""Ação no PC não pode ser confundida com abertura de plano."""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import main
from core import comandos_planos as CP


@pytest.mark.parametrize('frase', [
    'abra o youtube e toque uma musica',
    'abra o youtube',
    'abra a secretaria',
    'abra o bloco de notas',
    'abra o chrome',
    'abre o spotify',
])
def test_acao_de_pc_nao_e_abrir_plano(frase):
    assert CP.reconhecer(frase).tipo != 'ABRIR', frase


@pytest.mark.parametrize('frase', [
    'abra o plano Campanha de novembro',
    'Abre o projeto do aplicativo de estoque',
    'abra o produto Produto seguinte',
])
def test_abrir_plano_por_nome_preservado(frase):
    assert CP.reconhecer(frase).tipo == 'ABRIR', frase


def test_retomar_e_gerenciador_preservados():
    assert CP.reconhecer('continua meu estudo').tipo == 'RETOMAR'
    assert CP.reconhecer('abra o gerenciador de planos').tipo == 'GERENCIADOR'


@pytest.fixture
def nia():
    obj = object.__new__(main.NiaLive)
    registros = []
    obj.ui = SimpleNamespace(
        contexto_canvas=lambda: {"plano_id": None, "card_id": None, "plano": None},
        write_log=registros.append,
        abrir_plano=lambda plano_id: None,
        abrir_planos=lambda: None,
    )
    for nome in ("_contexto_planos", "_aplicar_resultado_planos",
                 "_processar_pedido_assistido", "_processar_pedido_lembrete",
                 "_responder_conversa_plano", "_executar_frase_habilidade"):
        setattr(obj, nome, getattr(main.NiaLive, nome).__get__(obj, main.NiaLive))
    obj._modo_local = True
    obj._sessao_planos = CP.SessaoComandosPlanos()
    return obj, registros


def test_frase_de_pc_chega_na_habilidade_e_nao_lista_planos(nia, monkeypatch):
    obj, registros = nia
    chamados = []

    def reconhecer(texto):
        chamados.append(texto)
        return SimpleNamespace(id='youtube_video', acao='tocar'), 'youtube'

    monkeypatch.setattr(main.CH, 'reconhecer', reconhecer)
    monkeypatch.setattr(main.CH, 'executar', lambda ident, termo: (True, 'Tocando'))
    assert obj._executar_frase_habilidade('abra o youtube e toque uma musica', 'texto')
    assert chamados
    assert not any('Encontrei vários planos' in item for item in registros)
