# -*- coding: utf-8 -*-
"""Integração real: agendador existente usando notificador do outbox."""
from __future__ import annotations

import pytest

from core import integracao_notificacoes as IN
from core import outbox_notificacoes as ON
from core import rotinas as R


def test_definir_notificador_e_usado_pelo_agendador():
    """Quebra: agendador nao permitia trocar notificador apos criacao."""
    agendador = R.Agendador(armazem=object())
    chamadas = []
    agendador.definir_notificador(lambda texto: chamadas.append(texto) or True)
    assert agendador._notificar('Rotina venceu') == (True, '')
    assert chamadas == ['Rotina venceu']


def test_ponte_outbox_preserva_a_entrega(tmp_path):
    """Quebra: ponte nao entregava aviso ao canal real injetado."""
    entregues = []
    outbox = ON.Outbox(caminho=tmp_path / 'o.json',
                       canais={'painel': lambda t: entregues.append(t) or 'ok'})
    agendador = R.Agendador(armazem=object())
    agendador.definir_notificador(
        IN.notificador_outbox(outbox, canal='painel', destino='agendador'))
    assert agendador._notificar('Aviso') == (True, '')
    assert entregues == ['Aviso']


def test_falha_do_canal_nao_derruba_o_agendador(tmp_path):
    """Quebra: exceção do canal interrompia o loop de rotinas."""
    outbox = ON.Outbox(caminho=tmp_path / 'o.json',
                       canais={'painel': lambda t: (_ for _ in ()).throw(OSError('off'))})
    agendador = R.Agendador(armazem=object())
    agendador.definir_notificador(
        IN.notificador_outbox(outbox, canal='painel', destino='agendador'))
    assert agendador._notificar('Aviso') == (False, '')


def test_main_injeta_notificador_outbox_no_agendador(tmp_path, monkeypatch):
    """Quebra: inicialização real nao ligava outbox ao agendador unico."""
    import main
    from core import config_preferencias as CP

    class AgendadorFalso:
        def __init__(self):
            self._notificador = None
            self.ao_resumo = None
            self.resumo_leitura_automatica = None

        def definir_notificador(self, notificador):
            self._notificador = notificador

    fake = AgendadorFalso()
    monkeypatch.setattr(R, 'agendador_global', lambda: fake)
    monkeypatch.setattr(CP.ConfigService, 'resumo_leitura_automatica', lambda self: False)
    monkeypatch.setattr(main.Path, 'home', classmethod(lambda cls: tmp_path))
    entregues = []
    monkeypatch.setattr('actions.reminder.notificar',
                        lambda texto: entregues.append(texto) or True)
    obj = object.__new__(main.NiaLive)
    obj._falar_resumo = lambda texto: None
    obj._configurar_agendador_resumo()
    assert callable(fake._notificador)
    assert fake._notificador('Aviso real') is True
    assert entregues == ['Aviso real']
