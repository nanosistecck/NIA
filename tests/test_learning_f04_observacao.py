# -*- coding: utf-8 -*-
"""RED F04: observação somente em sessão autorizada, com filtro de privacidade."""
from __future__ import annotations

import pytest

from core import controle_sessao as CS
from core.aprendizado_adaptativo import contratos as CT
from core.aprendizado_adaptativo.observacao import (
    FiltroPrivacidade, ObservadorAutorizado)


class SessaoFalsa:
    def __init__(self):
        self.ativo = False

    def iniciar(self):
        self.ativo = True

    def parar(self):
        self.ativo = False


def test_sem_sessao_nao_observa_nada():
    s = SessaoFalsa()
    o = ObservadorAutorizado(sessao=s, filtro=FiltroPrivacidade())
    assert o.registrar('clique', alvo='botao', dados={'x': 1}) is False
    assert o.eventos == ()


def test_sessao_autorizada_registra_evento_tipado():
    s = SessaoFalsa()
    s.iniciar()
    o = ObservadorAutorizado(sessao=s, filtro=FiltroPrivacidade())
    assert o.registrar('clique', alvo='botao', dados={'x': 1}) is True
    ev = o.eventos[-1]
    assert ev.tipo == 'clique'
    assert ev.schema_version == 1
    assert ev.ator == 'usuario'


def test_campo_protegido_e_descartado():
    s = SessaoFalsa()
    s.iniciar()
    o = ObservadorAutorizado(sessao=s, filtro=FiltroPrivacidade())
    assert o.registrar('texto', alvo='campo',
                       dados={'valor': 'senha: SuperSecreto123'}) is False
    assert o.eventos == ()


def test_filtro_indisponivel_falha_fechado():
    s = SessaoFalsa()
    s.iniciar()
    o = ObservadorAutorizado(sessao=s, filtro=None)
    assert o.registrar('clique', alvo='botao', dados={}) is False


def test_parada_encerra_observacao_e_nao_reativa_sozinha():
    s = SessaoFalsa()
    s.iniciar()
    o = ObservadorAutorizado(sessao=s, filtro=FiltroPrivacidade())
    o.registrar('clique', alvo='a', dados={})
    s.parar()
    assert o.registrar('clique', alvo='b', dados={}) is False
    assert len(o.eventos) == 1
    novo = ObservadorAutorizado(sessao=s, filtro=FiltroPrivacidade())
    assert novo.registrar('clique', alvo='c', dados={}) is False
