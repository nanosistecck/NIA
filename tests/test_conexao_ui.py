# -*- coding: utf-8 -*-
"""Conexão entre cards existentes pela interface (revisão Prompt 02)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton

from core import planos as BP
from core.interface_mapa import ConexaoItem, EditorMapa
from core.planos import atualizar, criar, inicializar_mapa


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def plano(tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    p = inicializar_mapa(criar("Projeto dos lojistas", "Objetivo", "Geral").id)
    m = p.mapa
    m["cards"] += [
        {"id": "pub", "tipo": "ideia", "titulo": "Público-alvo", "resumo": "Lojistas",
         "descricao": "", "status": "", "x": 0.0, "y": 0.0, "modelo": "", "estado": "",
         "valor": None, "acumulado": None, "restrito": False, "financeiro": False},
        {"id": "div", "tipo": "ideia", "titulo": "Divulgação", "resumo": "Canais",
         "descricao": "", "status": "", "x": 260.0, "y": 0.0, "modelo": "", "estado": "",
         "valor": None, "acumulado": None, "restrito": False, "financeiro": False},
    ]
    return atualizar(p.id, {"mapa": m}, p.revisao)


@pytest.fixture
def editor(app, plano):
    ed = EditorMapa()
    ed.carregar(plano)
    yield ed
    ed._timer.stop()
    ed.cena.itens_cards.clear()
    ed.cena.itens_conexoes.clear()
    ed.cena.clear()
    ed.hide()
    ed.deleteLater()
    app.processEvents()


def test_iniciar_conexao_marca_origem_e_previa(editor):
    editor.iniciar_conexao("div")
    assert editor.modo_conexao is True
    assert editor.conexao_origem == "div"
    assert editor.cena.itens_cards["div"].isSelected()
    assert editor.cena.item_previa is not None
    assert editor.cena.item_previa.isVisible()


def test_escolher_destino_cria_conexao(editor):
    contador = editor.pilha.count()
    editor.iniciar_conexao("div")
    editor.concluir_conexao("pub")
    mapa = editor.plano_atual().mapa
    assert len(mapa["conexoes"]) == 1
    assert mapa["conexoes"][0]["origem"] == "div"
    assert mapa["conexoes"][0]["destino"] == "pub"
    assert editor.pilha.count() == contador + 1
    assert editor.modo_conexao is False
    assert editor.cena.item_previa is None


def test_esc_cancela_sem_alterar_mapa(editor):
    antes = editor.plano_atual().mapa
    editor.iniciar_conexao("div")
    editor.cancelar_conexao()
    QApplication.instance().processEvents()
    assert editor.modo_conexao is False
    assert editor.cena.item_previa is None
    assert editor.plano_atual().mapa == antes
    assert editor.pilha.count() == 0


def test_destino_invalido_nao_cria(editor):
    editor.iniciar_conexao("div")
    editor.concluir_conexao("div")
    editor.concluir_conexao("inexistente")
    assert editor.plano_atual().mapa["conexoes"] == []
    assert editor.modo_conexao is True


def test_conexao_pode_ser_selecionada_e_removida(editor):
    editor.conectar("div", "pub")
    lig = editor.cena.itens_conexoes[next(iter(editor.cena.itens_conexoes))]
    flags = lig.flags()
    assert flags & ConexaoItem.GraphicsItemFlag.ItemIsSelectable
    lig.setSelected(True)
    editor.excluir_selecionado()
    assert editor.plano_atual().mapa["conexoes"] == []
    assert len(editor.cena.itens_cards["pub"].dados) > 0  # cards preservados
    editor.desfazer()
    assert len(editor.plano_atual().mapa["conexoes"]) == 1


def test_botao_conectar_usa_modo(editor):
    editor.selecionar("div")
    botao = editor.findChild(QPushButton, "conectar")
    assert botao is not None
    botao.click()
    QApplication.instance().processEvents()
    assert editor.modo_conexao is True
    assert editor.conexao_origem == "div"


def test_linha_segue_movimento_com_zoom(editor):
    editor.conectar("div", "pub")
    lig = next(iter(editor.cena.itens_conexoes.values()))
    antes = lig.path().boundingRect()
    editor._view.scale(1.5, 1.5)
    editor.mover_card("pub", 400.0, 200.0)
    QApplication.instance().processEvents()
    assert lig.path().boundingRect() != antes
