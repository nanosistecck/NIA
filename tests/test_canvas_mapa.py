# -*- coding: utf-8 -*-
"""Editor visual do mapa: undo/redo, conexões, câmera e falha de gravação."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from core import planos as BP
from core.interface_mapa import EditorMapa
from core.planos import carregar, criar, inicializar_mapa


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def plano(tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    p = criar("Mapa", "Objetivo do mapa", "Projeto")
    return inicializar_mapa(p.id)


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


def test_excluir_card_com_conexoes_e_desfeito_e_refeito(app, editor):
    raiz = editor.plano_atual().mapa["raiz_id"]
    a = editor.criar_card("A")
    b = editor.criar_card("B")
    editor.conectar(raiz, a)
    editor.conectar(a, b)
    assert len(editor.plano_atual().mapa["conexoes"]) == 2

    editor.selecionar(a)
    editor.excluir_selecionado()
    cards = [c["id"] for c in editor.plano_atual().mapa["cards"]]
    assert a not in cards and b in cards
    assert editor.plano_atual().mapa["conexoes"] == []

    editor.desfazer()
    cards = [c["id"] for c in editor.plano_atual().mapa["cards"]]
    assert a in cards
    assert len(editor.plano_atual().mapa["conexoes"]) == 2

    editor.refazer()
    cards = [c["id"] for c in editor.plano_atual().mapa["cards"]]
    assert a not in cards
    assert editor.plano_atual().mapa["conexoes"] == []


def test_conexoes_acompanham_movimento_em_uma_operacao(app, editor):
    raiz = editor.plano_atual().mapa["raiz_id"]
    a = editor.criar_card("A", x=0.0, y=0.0)
    lig_id = editor.conectar(raiz, a)
    lig = editor.cena.itens_conexoes[lig_id]
    antes = lig.path().boundingRect()
    contador = editor.pilha.count()
    editor.mover_card(a, 240.0, 130.0)
    assert lig.path().boundingRect() != antes
    assert editor.pilha.count() == contador + 1
    editor.desfazer()
    pos = next(c for c in editor.plano_atual().mapa["cards"] if c["id"] == a)
    assert (pos["x"], pos["y"]) == (0.0, 0.0)


def test_camera_e_posicoes_restauradas(app, editor, plano):
    a = editor.criar_card("A", x=120.0, y=80.0)
    editor.mover_card(a, 300.0, -40.0)
    editor.definir_camera(50.0, 25.0, 1.5)
    ok, _ = editor.salvar()
    assert ok

    outro = EditorMapa()
    outro.carregar(carregar(plano.id))
    mapa = outro.plano_atual().mapa
    pos = next(c for c in mapa["cards"] if c["id"] == a)
    assert (pos["x"], pos["y"]) == (300.0, -40.0)
    assert mapa["camera"] == {"cx": 50.0, "cy": 25.0, "zoom": 1.5}
    outro._timer.stop()
    outro.cena.itens_cards.clear()
    outro.cena.itens_conexoes.clear()
    outro.cena.clear()
    outro.hide()
    outro.deleteLater()
    app.processEvents()


def test_card_central_nao_pode_ser_excluido(app, editor):
    raiz = editor.plano_atual().mapa["raiz_id"]
    editor.selecionar(raiz)
    editor.excluir_selecionado()
    assert raiz in [c["id"] for c in editor.plano_atual().mapa["cards"]]


def test_falha_de_gravacao_mantem_trabalho(app, editor, monkeypatch):
    editor.criar_card("Novo")
    antes = editor.plano_atual().mapa

    def falhar(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr("core.interface_mapa.atualizar", falhar)
    ok, _ = editor.salvar()
    assert not ok
    assert editor.mudancas_pendentes
    assert editor.plano_atual().mapa == antes
