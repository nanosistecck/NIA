# -*- coding: utf-8 -*-
"""Base local de planos: persistência, revisão e isolamento de falhas (Etapa 1)."""
import json
import os

import pytest

from core.planos import (
    ConflitoDeRevisao,
    atualizar,
    arquivar,
    buscar,
    carregar,
    criar,
    listar,
    pasta_planos,
    restaurar,
)


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    destino = tmp_path / "dados"
    monkeypatch.setenv("NIA_PLANOS_DIR", str(destino))
    return destino


def test_criar_revisao_e_reabrir_apos_reinicio(pasta):
    p = criar("Fotografia", "Estudar composição", "Estudos")
    assert p.id and p.revisao == 0 and p.tipo == "Estudos"
    p2 = atualizar(p.id, {"titulo": "Fotografia II"}, p.revisao)
    assert p2.revisao == 1 and p2.id == p.id
    assert carregar(p.id).titulo == "Fotografia II"
    assert carregar(p.id).revisao == 1


def test_duas_gravacoes_consecutivas_nao_conflitam(pasta):
    p = criar("A", "B")
    p2 = atualizar(p.id, {"titulo": "C"}, p.revisao)
    p3 = atualizar(p.id, {"objetivo": "D"}, p2.revisao)
    assert p3.revisao == 2


def test_conflito_de_revisao_nao_sobrescreve(pasta):
    p = criar("A", "B")
    atualizar(p.id, {"titulo": "Remoto"}, 0)
    with pytest.raises(ConflitoDeRevisao):
        atualizar(p.id, {"titulo": "Local"}, 0)
    assert carregar(p.id).titulo == "Remoto"


def test_arquivo_invalido_e_formato_desconhecido_isolados(pasta):
    p = criar("Ok", "Valido")
    (pasta_planos() / "quebrado.json").write_text("{", encoding="utf-8")
    (pasta_planos() / "futuro.json").write_text(
        json.dumps({"id": "x", "formato": 999, "titulo": "SEGREDO"}),
        encoding="utf-8")
    planos, avisos = listar()
    assert [x.id for x in planos] == [p.id]
    assert len(avisos) == 2 and all("SEGREDO" not in a for a in avisos)


def test_falha_de_escrita_preserva_arquivo(pasta, monkeypatch):
    p = criar("A", "B")
    original = (pasta_planos() / f"{p.id}.json").read_text(encoding="utf-8")

    def falhar(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr("core.planos._replace", falhar)
    with pytest.raises(OSError):
        atualizar(p.id, {"titulo": "Nao grava"}, p.revisao)
    assert (pasta_planos() / f"{p.id}.json").read_text(encoding="utf-8") == original


def test_busca_aceita_acento_e_caixa_e_titulo_repetido(pasta):
    a = criar("Fotografia", "Luz", "Estudos")
    b = criar("Fotografia", "Cor", "Estudos")
    assert a.id != b.id
    encontrados = {x.id for x in buscar(listar()[0], "FOTOGRAFIA")}
    assert encontrados == {a.id, b.id}
    assert buscar(listar()[0], tipo="Produto") == []


def test_arquivar_e_restaurar_mantem_id(pasta):
    p = criar("Projeto", "Objetivo", "Projeto")
    arq = arquivar(p.id, p.revisao)
    assert arq.status == "arquivado" and arq.id == p.id
    rest = restaurar(p.id, arq.revisao)
    assert rest.status == "ativo" and rest.id == p.id
    assert [x.id for x in buscar(listar()[0], status="arquivado")] == []
