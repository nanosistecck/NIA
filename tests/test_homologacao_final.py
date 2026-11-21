# -*- coding: utf-8 -*-
"""Homologação final: fluxo integrado e pontes reais da NIA."""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLineEdit, QPushButton

import main
import ui
from core import assistencia_planos as AP
from core import planos as BP


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def perfil(app, tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    w = ui.MainWindow("face.png")
    w.resize(1280, 820)
    w.show()
    app.processEvents()
    p = BP.inicializar_mapa(BP.criar("Projeto dos lojistas", "Objetivo", "Geral").id)
    m = p.mapa
    m["cards"] += [
        {"id": "pub", "tipo": "ideia", "titulo": "Público-alvo", "resumo": "Lojistas",
         "descricao": "", "status": "", "x": 0.0, "y": 0.0, "modelo": "", "estado": "",
         "valor": None, "acumulado": None, "restrito": False, "financeiro": False},
        {"id": "div", "tipo": "ideia", "titulo": "Divulgação", "resumo": "Canais",
         "descricao": "", "status": "", "x": 260.0, "y": 0.0, "modelo": "", "estado": "",
         "valor": None, "acumulado": None, "restrito": False, "financeiro": False},
    ]
    p = BP.atualizar(p.id, {"mapa": m}, p.revisao)
    yield w, p, app
    editor = getattr(w, "_canvas_editor", None)
    if editor is not None:
        editor.editor_internal._timer.stop()
        editor.editor_internal.cena.itens_cards.clear()
        editor.editor_internal.cena.itens_conexoes.clear()
        editor.editor_internal.cena.clear()
    for t in w.findChildren(QTimer):
        t.stop()
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_fluxo_integrado_escrita_conexao_consulta(perfil):
    w, plano, app = perfil
    w._abrir_canvas_do_plano(plano.id)
    QTest.qWait(80)
    app.processEvents()
    editor = w._canvas_editor
    editor.selecionar_card("div")
    campo = editor.findChild(QPushButton.__mro__[0], "definir_lembrete")  # presença do painel
    assert campo is not None

    from PyQt6.QtWidgets import QTextEdit
    descricao = editor.findChild(QTextEdit, "mapa_descricao")
    descricao.setFocus()
    descricao.setPlainText("Primeira ideia.\n\nSegunda ideia:\n- feiras")
    app.processEvents()
    vivo = w._ui.estado_canvas_vivo() if hasattr(w, "_ui") else editor.editor_internal.plano_atual()
    assert vivo is not None

    # Conectar pela interface: botão inicia modo, clique no destino conclui.
    editor.selecionar_card("div")
    editor.findChild(QPushButton, "conectar").click()
    assert editor.editor_internal.modo_conexao is True
    editor.editor_internal.concluir_conexao("pub")
    app.processEvents()
    assert any(c["origem"] == "div" and c["destino"] == "pub"
               for c in editor.editor_internal.plano_atual().mapa["conexoes"])

    # Consulta local pelo estado em memória (após a conexão).
    casca = object.__new__(ui.NiaUI)
    casca._win = w
    editor.selecionar_card("div")
    app.processEvents()
    contexto = casca.contexto_canvas()
    nia = object.__new__(main.NiaLive)
    nia.ui = SimpleNamespace(
        contexto_canvas=lambda: contexto,
        write_log=lambda *_: None,
        abrir_plano=lambda *_: None,
        abrir_planos=lambda: None,
        aplicar_lote_assistido=lambda *_: None,
        desfazer_lote_assistido=lambda: None,
        destacar_card=casca.destacar_card,
        estado_canvas_vivo=casca.estado_canvas_vivo,
    )
    nia._modo_local = True
    nia._provedor_assistido = None
    for nome in ("_contexto_planos", "_aplicar_resultado_planos",
                 "_processar_pedido_assistido", "_resolver_alvo_canvas",
                 "_resposta_assistida_local", "_processar_pedido_lembrete",
                 "_executar_frase_habilidade"):
        setattr(nia, nome, getattr(main.NiaLive, nome).__get__(nia, main.NiaLive))
    respostas = []
    nia.ui.write_log = lambda t: respostas.append(t)
    nia._executar_frase_habilidade("O que escrevi neste card?", "texto")
    assert any("Primeira ideia" in r for r in respostas)
    respostas.clear()
    nia._executar_frase_habilidade(
        "Com quais cards Divulgação está conectado?", "texto")
    assert any("Público-alvo" in r for r in respostas)

    assert editor.findChild(QPushButton, "perguntar_nia_card") is not None


def test_pontes_reais_estado_e_destaque(perfil):
    w, plano, app = perfil
    w._abrir_canvas_do_plano(plano.id)
    QTest.qWait(80)
    app.processEvents()
    casca = object.__new__(ui.NiaUI)
    casca._win = w
    vivo = casca.estado_canvas_vivo()
    assert vivo is not None and vivo.id == plano.id
    casca.destacar_card(plano.id, "pub")
    QTest.qWait(40)
    app.processEvents()
    assert w._canvas_editor.card_selecionado_id == "pub"
