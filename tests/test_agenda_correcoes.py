# -*- coding: utf-8 -*-
"""Correcoes apontadas pelos testes reais do dono na Agenda."""
import os
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import main
from core import agenda, comandos_agenda as CA, comandos_planos as CP


@pytest.fixture
def nia(tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_AGENDA", str(tmp_path / "agenda.json"))
    monkeypatch.setenv("NIA_PERFIL", "correcoes")
    # Relógio congelado: os testes usam datas relativas a 23/11/2026 10:00 (-03).
    # Sem isto, "próximo" e saudações mudam de resultado após a meia-noite.
    agora_original = agenda._agora
    agora_fixo = datetime(2026, 11, 23, 13, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(agenda, "_agora",
        lambda agora=None: agora_fixo if agora is None else agora_original(agora))
    registros = []
    obj = object.__new__(main.NiaLive)
    obj.ui = SimpleNamespace(
        contexto_canvas=lambda: {"plano_id": None, "card_id": None, "plano": None},
        write_log=registros.append,
        abrir_plano=lambda _: None, abrir_planos=lambda: None,
    )
    for nome in ("_contexto_planos", "_aplicar_resultado_planos",
                 "_processar_pedido_assistido", "_processar_pedido_lembrete",
                 "_responder_conversa_plano", "_falar_resposta_comando",
                 "_processar_pedido_agenda", "_executar_frase_habilidade"):
        setattr(obj, nome, getattr(main.NiaLive, nome).__get__(obj, main.NiaLive))
    obj._modo_local = True
    obj._sessao_planos = CP.SessaoComandosPlanos()
    return obj, registros


def test_adicionar_tarefa_vai_para_agenda_nao_para_canvas(nia):
    obj, registros = nia
    assert obj._executar_frase_habilidade(
        "adicione uma tarefa de relatório para amanhã às 10h", "texto")
    assert "Abra um plano" not in " ".join(registros)
    assert any("relatório" in item.lower() for item in agenda.listar()[0].values()
               if isinstance(item, str))


def test_mude_preparo_vai_para_agenda(nia):
    obj, registros = nia
    agenda.criar("Reunião", "2026-11-24T15:00:00-03:00", "reuniao")
    assert obj._executar_frase_habilidade(
        "mude o preparo da reunião para 45 minutos", "texto")
    assert "Abra um plano" not in " ".join(registros)
    assert agenda.listar()[0]["preparo_minutos"] == 45


def test_excluir_acao_e_executada(nia):
    obj, registros = nia
    item = agenda.criar("Tarefa antiga", "2026-11-24T10:00:00-03:00", "tarefa")
    assert CA.processar("exclua a tarefa antiga")["acao"] == "excluir"
    assert obj._executar_frase_habilidade("exclua a tarefa antiga", "texto")
    assert all(i["id"] != item["id"] for i in agenda.listar())
    assert "excluído" in " ".join(registros).lower()


def test_referencia_inexistente_nao_cai_para_proximo(nia):
    obj, registros = nia
    agenda.criar("Reunião", "2026-11-24T15:00:00-03:00", "reuniao")
    assert obj._executar_frase_habilidade("conclua a tarefa de relatório", "texto")
    texto = " ".join(registros).lower()
    assert "não encontrei" in texto
    assert "mais de um" not in texto
    assert agenda.listar()[0]["estado"] == "pendente"


def test_mensagem_de_concluir_e_corretta(nia):
    obj, registros = nia
    agenda.criar("Consulta", "2026-11-24T09:00:00-03:00", "chamada")
    obj._executar_frase_habilidade("conclua a consulta", "texto")
    texto = " ".join(registros).lower()
    assert "concluído" in texto and "concluir:" not in texto


def test_listagem_proximo_mes_filtra_e_cita_proximo(nia):
    obj, registros = nia
    agenda.criar("Consulta amanhã", "2026-11-24T09:00:00-03:00", "chamada")
    agenda.criar("Revisão dezembro", "2026-12-10T14:00:00-03:00", "reuniao")
    resultado = CA.processar("quais compromissos tem para o próximo mês?",
                             agora="2026-11-23T10:00:00-03:00")
    assert resultado["acao"] == "listar"
    filtrados = agenda.filtrar_por_periodo(
        agenda.listar(), resultado.get("periodo"),
        agora="2026-11-23T10:00:00-03:00")
    assert [i["titulo"] for i in filtrados] == ["Revisão dezembro"]
    obj._executar_frase_habilidade(
        "quais compromissos tem para o próximo mês?", "texto")
    resposta = " ".join(registros)
    assert "Revisão dezembro" in resposta
    # A lista e filtrada, mas o proximo compromisso e citado a parte (pedido do dono).
    assert "Próximo compromisso: Consulta amanhã" in resposta


def test_titulo_sem_preposicao_orfã():
    r = CA.processar(
        "adicione uma tarefa de relatório para depois de amanhã às 10h",
        agora="2026-11-23T10:00:00-03:00")
    assert r["titulo"] == "tarefa de relatório"


def test_mudar_para_dia_do_mes():
    r = CA.processar("mude a reunião para o dia 11 às 15h",
                     agora="2026-11-23T10:00:00-03:00")
    assert r["acao"] == "mover" and "2026-12-11T15:00" in r["inicio"]


def test_alvo_por_token_do_titulo(nia):
    item = agenda.criar("Consulta médica", "2026-11-24T09:00:00-03:00", "chamada")
    assert CA.resolver_alvo("mude o preparo da consulta para 45 minutos",
                            agenda.listar(), None)["id"] == item["id"]


def test_alvo_ignora_preposicao_no_titulo(nia):
    item = agenda.criar("Revisão dezembro", "2026-12-10T14:00:00-03:00", "reuniao")
    assert CA.resolver_alvo("exclua a revisão de dezembro",
                            agenda.listar(), None)["id"] == item["id"]


def test_proxima_semana_e_a_seguinte():
    agora = "2026-11-23T10:00:00-03:00"   # segunda
    itens = [
        {"titulo": "Amanhã", "inicio": "2026-11-24T09:00:00-03:00"},
        {"titulo": "Semana que vem", "inicio": "2026-11-30T09:00:00-03:00"},
    ]
    filtrados = agenda.filtrar_por_periodo(itens, "proxima_semana", agora=agora)
    assert [i["titulo"] for i in filtrados] == ["Semana que vem"]


def test_excluir_todos_nao_apaga_tudo(nia):
    obj, registros = nia
    agenda.criar("Um", "2026-11-24T09:00:00-03:00")
    agenda.criar("Dois", "2026-11-25T09:00:00-03:00")
    assert obj._executar_frase_habilidade("exclua todos os compromissos", "texto")
    assert len(agenda.listar()) == 2
    assert "qual" in " ".join(registros).lower()


def test_reuniao_ambigu_pergunta_qual(nia):
    obj, registros = nia
    agenda.criar("Reunião A", "2026-11-24T09:00:00-03:00", "reuniao")
    agenda.criar("Reunião B", "2026-11-25T10:00:00-03:00", "reuniao")
    assert obj._executar_frase_habilidade("exclua a reunião", "texto")
    assert "mais de um" in " ".join(registros).lower()
    assert len(agenda.listar()) == 2


def test_titulo_remove_dia_e_hora():
    r = CA.processar("adicione um aniversário da mãe dia 27 às 18h",
                     agora="2026-11-23T10:00:00-03:00")
    assert r["titulo"] == "aniversário da mãe"


@pytest.mark.parametrize('frase,saudacao', [
    ('bom dia', 'bom dia'), ('boa tarde', 'boa tarde'), ('boa noite', 'boa noite')])
def test_saudacoes_dao_o_resumo(nia, frase, saudacao):
    obj, registros = nia
    agenda.criar("Consulta", "2026-11-24T09:00:00-03:00", "chamada")
    assert obj._executar_frase_habilidade(frase, "texto")
    resposta = " ".join(registros).lower()
    assert saudacao in resposta
    assert "próximo compromisso" in resposta


def test_bom_dia_tem_saudacao(nia):
    obj, registros = nia
    agenda.criar("Consulta", "2026-11-24T09:00:00-03:00", "chamada")
    obj._executar_frase_habilidade("bom dia", "texto")
    assert "bom dia" in " ".join(registros).lower()
