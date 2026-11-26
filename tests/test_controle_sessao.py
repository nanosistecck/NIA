# -*- coding: utf-8 -*-
"""Testes do portão de sessão de controle (sem PyQt6, sem login real)."""
from __future__ import annotations

import threading

import pytest

from core import controle_sessao as CS
from actions import usar_computador as UC


class Relogio:
    def __init__(self):
        self.agora = 100.0

    def __call__(self):
        return self.agora


def test_gate_fechado_sem_apresentador():
    """Quebra: ação podia rodar mesmo sem o indicador confirmado."""
    s = CS.SessaoControle(relogio=Relogio(), id_factory=lambda: 'abc123')
    with pytest.raises(CS.ControleIndisponivel):
        s.iniciar('tarefa', simulado=False)
    assert s.estado is CS.EstadoControle.FAILED
    assert s.permitido() is False
    assert s.ativo() is False
    assert any(e.tipo == 'falha' for e in s.eventos)


def test_sessao_simulada_e_donos_aninhados():
    s = CS.SessaoControle(relogio=Relogio(), id_factory=lambda: 's1')
    token = s.iniciar('tarefa', simulado=True)
    assert s.estado is CS.EstadoControle.ACTIVE
    assert s.permitido() is True
    assert token.sessao_id == 's1'

    segundo = s.iniciar('subtarefa', simulado=True)
    assert segundo.aninhado is True
    s.encerrar(segundo)
    assert s.estado is CS.EstadoControle.ACTIVE
    s.encerrar(token)
    assert s.estado is CS.EstadoControle.IDLE
    assert s.permitido() is False


def test_pausa_bloqueia_acao_e_retomada():
    """Quebra: pausar o overlay não impedia novas ações de desktop."""
    s = CS.SessaoControle(relogio=Relogio())
    token = s.iniciar('tarefa', simulado=True)
    assert s.pausar('botão') is True
    assert s.estado in (CS.EstadoControle.PAUSING, CS.EstadoControle.PAUSED)
    assert s.permitido() is False
    s.confirmar_pausa()
    assert s.estado is CS.EstadoControle.PAUSED
    assert s.permitido() is False
    assert s.retomar() is True
    assert s.permitido() is True
    s.encerrar(token)


def test_suspensao_por_monitor_e_retomada_automatica():
    s = CS.SessaoControle(relogio=Relogio())
    token = s.iniciar('tarefa', simulado=True)
    assert s.suspender('monitor removido') is True
    assert s.permitido() is False
    assert any(e.tipo == 'suspenso' for e in s.eventos)
    s.retomar('monitores revalidados')
    assert s.permitido() is True
    s.encerrar(token)


def test_parada_imediata_chama_callback():
    s = CS.SessaoControle(relogio=Relogio())
    aviso = threading.Event()
    token = s.iniciar('tarefa', simulado=True, ao_parar=aviso.set)
    assert s.solicitar_parada('ESC') is True
    assert s.parada_solicitada() is True
    assert s.permitido() is False
    assert aviso.wait(1.0) is True
    s.encerrar(token)


def test_sanitizacao_nao_vaza_credenciais():
    texto = CS.sanitizar('Cliquei senha: SuperSecreto123 e apertai\nENTER\t<')
    assert 'SuperSecreto123' not in texto
    assert '***' in texto
    assert '\n' not in texto and '\t' not in texto


def test_atividades_e_eventos_sao_tipados_e_ordenados():
    s = CS.SessaoControle(relogio=Relogio(), id_factory=lambda: 's9')
    token = s.iniciar('tarefa', simulado=True)
    s.registrar_atividade('Clique: senha: abc123', 'executando')
    s.marcar_ultima('concluida')
    itens = s.atividades
    assert len(itens) == 1
    assert itens[0]['status'] == 'concluida'
    assert 'abc123' not in itens[0]['descricao']
    numeros = [e.sequencia for e in s.eventos]
    assert numeros == sorted(numeros)
    assert len(set(numeros)) == len(numeros)
    assert s.eventos[0].sessao_id == 's9'
    s.encerrar(token)


def test_resumo_da_acao_nao_revela_texto_digitado():
    assert UC._resumo_da_acao({'acao': 'digitar', 'texto': 'senha: 1234'}) == 'Digitando'
    assert 'Clique' in UC._resumo_da_acao({'acao': 'clicar', 'texto': 'Botão OK'})
    assert '1234' not in UC._resumo_da_acao({'acao': 'digitar', 'texto': '1234'})


def test_respeitar_pausa_bloqueia_ate_retomada(monkeypatch):
    """O movimento real só continua depois da retomada do overlay."""
    s = CS.SessaoControle(relogio=Relogio())
    monkeypatch.setattr(CS, 'sessao', s)
    token = s.iniciar('tarefa', simulado=True)
    s.pausar('teste')
    s.confirmar_pausa()

    liberou = threading.Event()

    def soltar():
        threading.Event().wait(0.25)
        s.retomar('teste')
        liberou.set()

    t = threading.Thread(target=soltar, daemon=True)
    t.start()
    assert UC._respeitar_pausa({}) is True
    assert liberou.wait(1.0) is True
    s.encerrar(token)


def test_respeitar_pausa_devolve_false_quando_parado(monkeypatch):
    s = CS.SessaoControle(relogio=Relogio())
    monkeypatch.setattr(CS, 'sessao', s)
    token = s.iniciar('tarefa', simulado=True)
    s.solicitar_parada('ESC')
    assert UC._respeitar_pausa({}) is False
    s.encerrar(token)
