# -*- coding: utf-8 -*-
"""Comandos de Agenda por chat/voz: puros, sem Qt e sem arquivos."""
import pytest

from core import comandos_agenda as CA


def test_criar_sem_data_pergunta():
    r = CA.processar("agende uma reunião com o João",
                     agora="2026-11-23T10:00:00-03:00")
    assert r["tratado"] is True
    assert r["acao"] in ("pendente", "sem_data")


def test_criar_com_data_e_hora():
    r = CA.processar("agende uma reunião com o João amanhã às 15h",
                     agora="2026-11-23T10:00:00-03:00")
    assert r["acao"] == "criar"
    assert "2026-11-24T15:00" in r["inicio"]
    assert r["titulo"] == "reunião com o João"
    assert r["tipo"] == "reuniao"


def test_alvo_ambigu_pede_escolha():
    itens = [{"id": "1", "titulo": "Reunião"}, {"id": "2", "titulo": "Reunião"}]
    assert CA.resolver_alvo("mude a reunião", itens, None) is None


def test_sem_referencia_usa_proximo():
    itens = [{"id": "1", "titulo": "Reunião"}, {"id": "2", "titulo": "Consulta"}]
    assert CA.resolver_alvo("conclua", itens, itens[1])["id"] == "2"


def test_alvo_por_titulo():
    itens = [{"id": "1", "titulo": "Reunião com João"},
             {"id": "2", "titulo": "Consulta"}]
    assert CA.resolver_alvo("mude a reunião com joão", itens, itens[1])["id"] == "1"


def test_alvo_por_data():
    itens = [{"id": "1", "titulo": "Reunião", "inicio": "2026-11-24T15:00:00-03:00"},
             {"id": "2", "titulo": "Consulta", "inicio": "2026-11-25T09:00:00-03:00"}]
    assert CA.resolver_alvo("conclua a de amanhã", itens, None,
                            agora="2026-11-23T10:00:00-03:00")["id"] == "1"


@pytest.mark.parametrize('frase,acao', [
    ('bom dia', 'saudacao'),
    ('bom dia NIA', 'saudacao'),
    ('qual o próximo compromisso?', 'proximo'),
    ('o que tenho hoje?', 'listar'),
    ('mostre os compromissos', 'listar'),
    ('mostrar card da agenda', 'mostrar_card'),
    ('conclua o compromisso', 'concluir'),
    ('cancele a reunião', 'cancelar'),
])
def test_acoes_reconhecidas(frase, acao):
    assert CA.processar(frase)["acao"] == acao, frase


def test_frase_fora_da_agenda_nao_e_tratada():
    assert CA.processar("que horas são?")["tratado"] is False


def test_mover_e_editar():
    r = CA.processar("mude a reunião para amanhã às 16h",
                     agora="2026-11-23T10:00:00-03:00")
    assert r["acao"] == "mover" and "2026-11-24T16:00" in r["inicio"]
    r2 = CA.processar("mude o preparo da reunião para 45 minutos")
    assert r2["acao"] == "editar" and r2["campos"]["preparo_minutos"] == 45
