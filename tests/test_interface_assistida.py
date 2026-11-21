# -*- coding: utf-8 -*-
"""Modo 'Editar com a NIA': alternância, lotes na GUI e roteamento compartilhado."""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton

import main
import ui
from core import assistencia_planos as AP
from core import planos as BP
from core.planos import criar, inicializar_mapa


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    w = ui.MainWindow("face.png")
    w.resize(1280, 820)
    w.show()
    app.processEvents()
    plano = inicializar_mapa(criar("Assistido", "Objetivo", "Produto").id)
    yield w, plano
    editor = getattr(w, "_canvas_editor", None)
    if editor is not None:
        editor.editor_internal._timer.stop()
        editor.editor_internal.cena.itens_cards.clear()
        editor.editor_internal.cena.itens_conexoes.clear()
        editor.editor_internal.cena.clear()
    for timer in w.findChildren(QTimer):
        timer.stop()
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_botao_do_gerenciador_abre_canvas_em_modo_assistido(window, app):
    w, plano = window
    w._abrir_planos()
    w._planos_window.selecionar(plano.id)
    botao = w._planos_window.findChild(QPushButton, "abrir_canvas_ia")
    assert botao is not None
    botao.click()
    app.processEvents()
    assert w._canvas_editor.isVisible()
    assert w._canvas_editor.modo_assistido is True


def test_alternar_modo_preserva_mapa_selecao_e_camera(window, app):
    w, plano = window
    w._abrir_canvas_do_plano(plano.id, assistido=True)
    editor = w._canvas_editor
    raiz = plano.mapa["raiz_id"]
    editor.selecionar_card(raiz)
    editor.editor_internal.definir_camera(33.0, 44.0, 1.25)
    editor.editor_internal.criar_card("Pendente local")
    antes = editor.editor_internal.plano_atual().mapa

    botao = editor.findChild(QPushButton, "alternar_modo")
    botao.click()
    app.processEvents()

    assert editor.modo_assistido is False
    assert editor.card_selecionado_id == raiz
    assert editor.editor_internal._camera == {"cx": 33.0, "cy": 44.0, "zoom": 1.25}
    assert editor.editor_internal.plano_atual().mapa == antes
    assert editor.mudancas_pendentes


def test_lote_assistido_pela_casca_usa_thread_da_interface(window, app):
    w, plano = window
    w._abrir_canvas_do_plano(plano.id, assistido=True)
    contexto = AP.montar_contexto(plano, plano.mapa["raiz_id"])
    ops, erros = AP.pedido_local("Adicione três soluções a este card.", contexto)
    assert not erros
    casca = object.__new__(ui.NiaUI)
    casca._win = w
    casca.aplicar_lote_assistido(ops, "Adicionar soluções")
    QTest.qWait(50)
    app.processEvents()
    assert len(w._canvas_editor.editor_internal.plano_atual().mapa["cards"]) == 4


def test_pedido_assistido_por_texto_e_voz_usam_mesmo_caminho(window, app):
    w, plano = window
    contexto = AP.montar_contexto(plano, plano.mapa["raiz_id"])
    registros = []
    nia = object.__new__(main.NiaLive)
    nia._modo_local = True
    nia._provedor_assistido = None
    nia.ui = SimpleNamespace(
        contexto_canvas=lambda: {**contexto, "plano": plano},
        write_log=lambda texto: registros.append(texto),
        aplicar_lote_assistido=lambda ops, rotulo: registros.append((ops, rotulo)),
    )
    frase = "Crie três cards de divulgação gratuita ligados a este."
    r1 = main.NiaLive._processar_pedido_assistido(nia, frase, "texto")
    r2 = main.NiaLive._processar_pedido_assistido(nia, frase, "voz")
    assert r1 is True and r2 is True
    assert sum(isinstance(r, tuple) for r in registros) == 2


def test_provedor_recebe_apenas_contexto_permitido_mesmo_em_fallback(window):
    _, plano = window
    plano = BP.atualizar(plano.id, {"mapa": {
        **plano.mapa,
        "cards": [{**c, "restrito": True} if c["id"] == plano.mapa["raiz_id"]
                  else c for c in plano.mapa["cards"]],
    }}, plano.revisao)
    contexto = AP.montar_contexto(plano, plano.mapa["raiz_id"])
    recebido = []
    nia = object.__new__(main.NiaLive)
    nia._modo_local = True  # modo local, mas o fallback externo nao pode vazar
    nia.ui = SimpleNamespace(
        contexto_canvas=lambda: {**contexto, "plano": plano},
        write_log=lambda *_: None,
        aplicar_lote_assistido=lambda *_: None,
    )
    nia._provedor_assistido = lambda pedido, ctx: (
        recebido.append(ctx) or '{"operacoes":[]}')
    assert main.NiaLive._processar_pedido_assistido(
        nia, "Crie uma variação nova para este card.", "texto") is True
    assert recebido and recebido[0]["card"] is None
    assert recebido[0]["destino_local"] is False


def test_pedido_assistido_sem_card_selecionado_nao_altera_mapa(window):
    nia = object.__new__(main.NiaLive)
    nia._modo_local = True
    nia._provedor_assistido = None
    nia.ui = SimpleNamespace(
        contexto_canvas=lambda: {"plano_id": None, "card_id": None, "plano": None},
        write_log=lambda *_: None,
        aplicar_lote_assistido=lambda *_: pytest.fail("nao deveria aplicar lote"),
    )
    assert main.NiaLive._processar_pedido_assistido(
        nia, "Adicione três soluções a este card.", "texto") is True
