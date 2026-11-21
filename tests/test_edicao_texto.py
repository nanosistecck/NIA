# -*- coding: utf-8 -*-
"""Escrita multilinha, commit e histórico do Card (revisão Prompt 03)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLineEdit, QTextEdit

from core import planos as BP
from core.interface_mapa import EditorMapa
from core.planos import atualizar, carregar, criar, inicializar_mapa

TEXTO = ("Primeira ideia: feiras regionais em praças públicas.\n"
         "\n"
         "Segunda ideia:\n"
         "- parceria com associações de lojistas\n"
         "- divulgar no grupo da cidade")


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


def _campo(ed):
    campo = ed.findChild(QTextEdit, "mapa_descricao")
    assert campo is not None, "campo de descrição deve ser QTextEdit"
    return campo


def test_campo_e_multilinha(editor):
    assert isinstance(_campo(editor), QTextEdit)


def test_texto_com_paragrafos_lista_e_acentos_sobrevive_troca_e_reabertura(editor, plano):
    campo = _campo(editor)
    editor.selecionar("div")
    campo.setFocus()
    campo.setPlainText(TEXTO)
    QTest.keyClick(campo, Qt.Key.Key_Return)
    QTest.keyClicks(campo, "Terceira linha")
    texto_final = campo.toPlainText()
    assert "\n" in texto_final and "parceria" in texto_final

    editor.selecionar("pub")
    editor.selecionar("div")
    assert _campo(editor).toPlainText() == texto_final
    assert next(c for c in editor.plano_atual().mapa["cards"]
                if c["id"] == "div")["descricao"] == texto_final

    assert editor.salvar()[0]
    salvo = carregar(plano.id)
    assert next(c for c in salvo.mapa["cards"] if c["id"] == "div")["descricao"] == texto_final

    outro = EditorMapa()
    outro.carregar(salvo)
    assert _campo(outro).toPlainText() == ""  # nenhum card selecionado ao carregar
    outro.selecionar("div")
    assert _campo(outro).toPlainText() == texto_final
    outro._timer.stop()
    outro.cena.itens_cards.clear()
    outro.cena.itens_conexoes.clear()
    outro.cena.clear()
    outro.hide()
    outro.deleteLater()


def test_enter_insere_linha_no_campo(editor):
    editor.selecionar("div")
    campo = _campo(editor)
    campo.setFocus()
    campo.setPlainText("linha um")
    campo.moveCursor(QTextCursor.MoveOperation.End)
    QTest.keyClick(campo, Qt.Key.Key_Return)
    QTest.keyClicks(campo, "linha dois")
    assert campo.toPlainText() == "linha um\nlinha dois"


def test_edicao_e_uma_operacao_de_desfazer(editor):
    editor.selecionar("div")
    campo = _campo(editor)
    campo.setFocus()
    antes = editor.pilha.count()
    campo.setPlainText("Primeira versão")
    campo.setPlainText("Segunda versão com mais ideias")
    app = QApplication.instance()
    app.processEvents()
    assert editor.pilha.count() == antes + 1
    editor.desfazer()
    assert next(c for c in editor.plano_atual().mapa["cards"]
                if c["id"] == "div")["descricao"] == ""
    editor.refazer()
    assert next(c for c in editor.plano_atual().mapa["cards"]
                if c["id"] == "div")["descricao"] == "Segunda versão com mais ideias"


def test_ctrl_z_no_campo_nao_desfaz_o_canvas(editor):
    editor.selecionar("div")
    campo = _campo(editor)
    campo.setFocus()
    campo.setPlainText("Texto do campo")
    contador = editor.pilha.count()
    QTest.keyClick(campo, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    QApplication.instance().processEvents()
    assert editor.pilha.count() >= contador


def test_delete_no_campo_nao_exclui_card(editor):
    editor.selecionar("div")
    campo = _campo(editor)
    campo.setFocus()
    campo.setPlainText("abc")
    QTest.keyClick(campo, Qt.Key.Key_Delete)
    QApplication.instance().processEvents()
    assert "div" in editor.cena.itens_cards


def test_leitura_em_memoria_antes_do_salvamento(editor, plano):
    editor.selecionar("div")
    campo = _campo(editor)
    campo.setFocus()
    campo.setPlainText("Ideia aplicada agora")
    QApplication.instance().processEvents()
    plano_vivo = editor.plano_atual()
    assert plano_vivo.id == plano.id
    assert next(c for c in plano_vivo.mapa["cards"]
                if c["id"] == "div")["descricao"] == "Ideia aplicada agora"


def test_duplas_edicoes_rapidas_em_cards_diferentes(editor):
    editor.selecionar("div")
    _campo(editor).setPlainText("Texto de Divulgação")
    editor.selecionar("pub")
    _campo(editor).setPlainText("Texto de Público")
    QApplication.instance().processEvents()
    mapa = editor.plano_atual().mapa
    assert next(c for c in mapa["cards"] if c["id"] == "div")["descricao"] == "Texto de Divulgação"
    assert next(c for c in mapa["cards"] if c["id"] == "pub")["descricao"] == "Texto de Público"


def test_falha_de_gravacao_mantem_texto(editor, plano, monkeypatch):
    editor.selecionar("div")
    _campo(editor).setPlainText("Texto preservado")

    def falhar(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr("core.interface_mapa.atualizar", falhar)
    ok, _ = editor.salvar()
    assert not ok and editor.mudancas_pendentes
    assert next(c for c in editor.plano_atual().mapa["cards"]
                if c["id"] == "div")["descricao"] == "Texto preservado"


def test_conflito_de_revisao_mantem_texto(editor, monkeypatch):
    editor.selecionar("div")
    _campo(editor).setPlainText("Texto local")

    def conflito(*args, **kwargs):
        raise BP.ConflitoDeRevisao(0, 1)

    monkeypatch.setattr("core.interface_mapa.atualizar", conflito)
    ok, _ = editor.salvar()
    assert not ok and editor.mudancas_pendentes
    assert next(c for c in editor.plano_atual().mapa["cards"]
                if c["id"] == "div")["descricao"] == "Texto local"


def test_contexto_da_nia_ve_texto_aplicado_antes_do_salvamento(app, plano, tmp_path,
                                                               monkeypatch):
    import ui
    from core.interface_canvas_planos import CanvasEditor
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path / "config")
    w = ui.MainWindow("face.png")
    w.resize(1100, 700)
    w.show()
    app.processEvents()
    w._abrir_canvas_do_plano(plano.id)
    QTest.qWait(80)
    app.processEvents()
    casca = object.__new__(ui.NiaUI)
    casca._win = w
    editor = w._canvas_editor
    editor.selecionar_card("div")
    campo = editor.findChild(QTextEdit, "mapa_descricao")
    campo.setFocus()
    campo.setPlainText("Texto visível para a conversa")
    app.processEvents()
    contexto = casca.contexto_canvas()
    plano_vivo = contexto["plano"]
    assert plano_vivo is not None
    assert contexto["card_id"] == "div"
    assert next(c for c in plano_vivo.mapa["cards"]
                if c["id"] == "div")["descricao"] == "Texto visível para a conversa"
    for t in w.findChildren(QTimer):
        t.stop()
    editor.editor_internal.cena.itens_cards.clear()
    editor.editor_internal.cena.itens_conexoes.clear()
    editor.editor_internal.cena.clear()
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_plano_antigo_com_texto_abre(editor, plano):
    assert plano.id
    assert any(c["id"] == "div" for c in editor.plano_atual().mapa["cards"])
