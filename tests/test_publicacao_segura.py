# -*- coding: utf-8 -*-
"""Proteção de saída para publicação de conteúdo do Canvas."""
import os

import pytest

from core import publicacao_segura as PS
from core.planos import criar


@pytest.fixture
def plano(tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    plano = criar("Post", "Lançamento", "Conteúdo")
    from core import planos as BP
    mapa = BP.mapa_vazio()
    mapa["cards"] = [
        {"id": "livre", "tipo": "ideia", "titulo": "Público", "resumo": "Liberado",
         "descricao": "", "status": "", "x": 0, "y": 0, "modelo": "conteudo",
         "estado": "pronto", "valor": None, "acumulado": None,
         "restrito": False, "financeiro": False},
        {"id": "secreto", "tipo": "ideia", "titulo": "Interno", "resumo": "Sigilo",
         "descricao": "", "status": "", "x": 0, "y": 0, "modelo": "conteudo",
         "estado": "", "valor": None, "acumulado": None,
         "restrito": True, "financeiro": False},
    ]
    return BP.atualizar(plano.id, {"mapa": mapa}, plano.revisao)


def test_bloqueia_card_restrito_e_resumo_derivado(plano):
    payload = PS.preparar_conteudo(plano, ["livre", "secreto"])
    motivos = PS.validar(payload, destino="github")
    assert any("restrito" in m for m in motivos)
    derivado = PS.preparar_conteudo(plano, ["livre"], resumo_de="secreto")
    assert any("derivado" in m for m in PS.validar(derivado, destino="github"))


def test_bloqueia_anexo_interno_e_segredo(plano):
    payload = PS.preparar_conteudo(
        plano, ["livre"], anexos=[".git/config"], mensagem="chave sk-abcdefghijklmnop")
    motivos = PS.validar(payload, destino="github")
    assert any("anexo" in m for m in motivos)
    assert any("segredo" in m for m in motivos)


def test_publicacao_permitida_com_confirmacao_da_previa(plano):
    payload = PS.preparar_conteudo(plano, ["livre"], mensagem="Texto permitido")
    assert PS.validar(payload, destino="github") == []
    token = PS.confirmar(payload["previa"])
    enviados = []
    resultado = PS.publicar(payload, token, "github", lambda dados: enviados.append(dados))
    assert resultado["ok"] and len(enviados) == 1


def test_previa_alterada_exige_nova_confirmacao(plano):
    payload = PS.preparar_conteudo(plano, ["livre"], mensagem="Original")
    token = PS.confirmar(payload["previa"])
    payload["mensagem"] = "Alterada depois da confirmação"
    with pytest.raises(PS.BloqueioPublicacao):
        PS.publicar(payload, token, "github", lambda dados: None)


def test_reenvio_revalida_conteudo(plano):
    payload = PS.preparar_conteudo(plano, ["livre"])
    token = PS.confirmar(payload["previa"])
    PS.publicar(payload, token, "github", lambda dados: None)
    payload["cards"].append({"id": "secreto", "titulo": "Interno",
                             "restrito": True})
    with pytest.raises(PS.BloqueioPublicacao):
        PS.publicar(payload, token, "github", lambda dados: None)


def test_sem_publicacao_real_do_canvas(plano):
    payload = PS.preparar_conteudo(plano, ["livre"])
    with pytest.raises(PS.BloqueioPublicacao):
        PS.publicar(payload, PS.confirmar(payload["previa"]), "github-real",
                    lambda dados: pytest.fail("nao deve enviar"))
