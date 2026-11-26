# -*- coding: utf-8 -*-
"""Preflight rápido e determinístico antes da inicialização da NIA."""
from __future__ import annotations

import time

import pytest

from core import preflight as PF_TEST


def test_preflight_approva_ambiente_atual():
    """Quebra: não havia verificação de inicialização."""
    relatorio = PF_TEST.executar()
    assert relatorio['ok'] is True
    assert relatorio['falhas_criticas'] == ()
    assert relatorio['verificacoes']


def test_preflight_detecta_ferramenta_sem_politica(monkeypatch):
    """Quebra: ferramenta sem política podia chegar ao executor."""
    from core import permissoes_ferramentas as PF
    original = dict(PF.ESCOPOS_LEGADOS)
    monkeypatch.setattr(PF, 'ESCOPOS_LEGADOS', {})
    relatorio = PF_TEST.executar()
    assert relatorio['ok'] is False
    assert any('politica' in f for f in relatorio['falhas_criticas'])
    monkeypatch.setattr(PF, 'ESCOPOS_LEGADOS', original)


def test_verificacao_de_python_rejeita_versao_antiga():
    """Quebra: versões incompatíveis não eram sinalizadas."""
    assert PF_TEST.verificar_python((3, 10, 0)) is True
    assert PF_TEST.verificar_python((3, 8, 0)) is False


def test_preflight_nao_usa_rede(monkeypatch):
    """Quebra: preflight poderia consultar serviços externos."""
    def bloqueia(*_a, **_k):
        raise AssertionError('rede não deveria ser usada')

    monkeypatch.setattr('socket.socket', bloqueia)
    assert PF_TEST.executar()['ok'] is True


def test_preflight_encontra_todas_as_ferramentas():
    """Quebra: regex poderia perder declarações do catálogo."""
    assert len(PF_TEST._declaracoes()) == 40


def test_preflight_e_rapido():
    """Quebra: auditoria completa na inicialização atrasaria a abertura."""
    t0 = time.perf_counter()
    PF_TEST.executar()
    assert time.perf_counter() - t0 < 2.0


def test_main_executa_preflight_antes_de_abrir(monkeypatch):
    """Quebra: preflight existia mas nao era chamado na inicialização."""
    import main
    chamadas = []
    monkeypatch.setattr(PF_TEST, 'executar',
                        lambda: chamadas.append(1) or {'ok': True, 'falhas_criticas': ()})
    monkeypatch.setattr(main, '_ja_existe_um_nia', lambda: True)
    main.main()
    assert chamadas == [1]
