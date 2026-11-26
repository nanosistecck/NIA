# -*- coding: utf-8 -*-
"""Fase 15 — segundo plano autorizado, silencioso e sem processos órfãos."""
from __future__ import annotations

import threading

import pytest

from core import autonomia_segundo_plano as AS


class ProcessoFalso:
    def __init__(self):
        self.terminado = False

    def terminate(self):
        self.terminado = True

    def wait(self, timeout=None):
        return 0


def _gerenciador(**kw):
    return AS.GerenciadorSegundoPlano(evento=threading.Event(), **kw)


def test_segundo_plano_exige_autorizacao_explicita():
    """Quebra: qualquer chamada podia esconder a janela."""
    g = _gerenciador()
    with pytest.raises(PermissionError, match='autoriza'):
        g.ativar()
    assert g.estado()['modo'] == 'ativo'


def test_tecla_f9_alterna_estado_sem_ativar_microfone():
    """Quebra: F9 podia ligar o microfone junto com o modo silencioso."""
    g = _gerenciador()
    g.processar_tecla()
    assert g.estado()['modo'] == 'segundo_plano'
    assert g.estado()['microfone'] is False
    g.processar_tecla()
    assert g.estado()['modo'] == 'ativo'


def test_notificacoes_sao_silenciadas_sem_autorizacao():
    """Quebra: segundo plano notificava como em primeiro plano."""
    entregues = []
    g = _gerenciador(notificador=entregues.append)
    g.ativar(autorizado=True)
    assert g.notificar('novo evento') is False
    assert entregues == []


def test_notificacao_autorizada_e_entregue():
    """Quebra: não havia autorização específica para notificar."""
    entregues = []
    g = _gerenciador(notificador=entregues.append)
    g.ativar(autorizado=True, notificacoes_autorizadas=True)
    assert g.notificar('novo evento') is True
    assert entregues == ['novo evento']


def test_revogacao_volta_ao_primeiro_plano_e_limpa_autorizacao():
    """Quebra: revogar não desfazia o modo silencioso."""
    entregues = []
    g = _gerenciador(notificador=entregues.append)
    g.ativar(autorizado=True, notificacoes_autorizadas=True)
    assert g.revogar() is True
    assert g.estado()['modo'] == 'ativo'
    assert g.notificar('oi') is False


def test_encerrar_termina_processos_registrados():
    """Quebra: processos ficavam órfãos ao encerrar."""
    g = _gerenciador()
    p1, p2 = ProcessoFalso(), ProcessoFalso()
    g.registrar_processo(p1)
    g.registrar_processo(p2)
    assert g.encerrar() == 2
    assert p1.terminado and p2.terminado
    assert g.estado()['processos'] == 0
