# -*- coding: utf-8 -*-
"""Extensão do formato do plano com mapa (Etapa 2, camada de dados)."""
import json

import pytest

from core import planos as BP
from core.planos import FORMATO, carregar, criar, pasta_planos


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    destino = tmp_path / "dados"
    monkeypatch.setenv("NIA_PLANOS_DIR", str(destino))
    return destino


def _gravar_v1(plano):
    """Plano da Etapa 1: sem `mapa` e com formato 1."""
    dados = plano.para_json()
    dados.pop("mapa", None)
    dados["formato"] = 1
    (pasta_planos() / f"{plano.id}.json").write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def test_plano_v1_abre_e_inicializa_card_central_uma_vez(pasta):
    assert FORMATO == 2
    original = criar("Produto X", "Vender para lojistas", "Produto")
    _gravar_v1(original)

    antigo = carregar(original.id)
    assert antigo is not None and antigo.mapa == {}

    primeiro = BP.inicializar_mapa(original.id)
    assert len(primeiro.mapa["cards"]) == 1
    central = primeiro.mapa["cards"][0]
    assert central["titulo"] == primeiro.titulo
    assert central["descricao"] == primeiro.objetivo
    assert primeiro.mapa["raiz_id"] == central["id"]
    assert primeiro.mapa["inicializado"] is True

    segundo = BP.inicializar_mapa(primeiro.id)
    assert len(segundo.mapa["cards"]) == 1
    assert segundo.mapa["cards"][0]["id"] == central["id"]


def test_referencia_quebrada_de_conexao_e_descartada_com_aviso(pasta):
    mapa = BP.mapa_vazio()
    mapa["cards"] = [
        {"id": "a", "tipo": "ideia", "titulo": "A", "resumo": "",
         "descricao": "", "status": "", "x": 0.0, "y": 0.0},
    ]
    mapa["conexoes"] = [
        {"id": "c1", "origem": "a", "destino": "inexistente", "rotulo": ""},
        {"id": "c2", "origem": "a", "destino": "a", "rotulo": ""},
    ]
    limpo, avisos = BP.validar_mapa(mapa)
    assert limpo["conexoes"] == []
    assert len(avisos) == 2


def test_resumo_progresso_conta_so_tarefas(pasta):
    plano = criar("Projeto", "Objetivo", "Projeto")
    mapa = BP.mapa_vazio()
    mapa["cards"] = [
        {"id": "t1", "tipo": "tarefa", "titulo": "Feita", "resumo": "",
         "descricao": "", "status": "concluido", "x": 0.0, "y": 0.0},
        {"id": "t2", "tipo": "tarefa", "titulo": "Bloqueada", "resumo": "",
         "descricao": "", "status": "bloqueado", "x": 10.0, "y": 0.0},
        {"id": "i1", "tipo": "ideia", "titulo": "Ideia", "resumo": "",
         "descricao": "", "status": "", "x": 0.0, "y": 10.0},
    ]
    BP.atualizar(plano.id, {"mapa": mapa}, plano.revisao)
    plano = carregar(plano.id)
    r = BP.resumo_progresso(plano)
    assert r["total"] == 2
    assert r["concluido"] == 1 and r["bloqueado"] == 1
    assert r["pendente"] == 0 and r["em_andamento"] == 0
    assert r["sem_tarefas"] is False


def test_plano_sem_tarefas_e_sinalizado(pasta):
    plano = criar("Estudo", "Objetivo", "Estudos")
    r = BP.resumo_progresso(plano)
    assert r["sem_tarefas"] is True and r["total"] == 0
