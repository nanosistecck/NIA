# -*- coding: utf-8 -*-
"""Modelos de planejamento locais e progresso por ramo (Prompt 05)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QTextEdit

from core import assistencia_planos as AP
from core import modelos_planos as MP
from core import planos as BP
from core.interface_mapa import EditorMapa
from core.planos import atualizar, carregar, criar, inicializar_mapa


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def plano(tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    return inicializar_mapa(criar("Plano base", "Objetivo", "Geral").id)


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


def _aplicar(editor, ops, rotulo):
    ctx = AP.montar_contexto(editor.plano_atual(), editor.card_selecionado_id)
    validas, erros = AP.validar_lote(ops, editor.plano_atual(), ctx)
    assert not erros, erros
    AP.aplicar_lote(editor, validas, rotulo)


def test_cinco_modelos_tem_estrutura_local():
    for tipo in MP.TIPOS_MODELO:
        ops = MP.estrutura_modelo(tipo, "Título", "Objetivo")
        cards = [o for o in ops if o["tipo"] == "criar_card"]
        ligs = [o for o in ops if o["tipo"] == "conectar"]
        assert cards and ligs, tipo
        assert all(o["titulo"].strip() for o in cards)


def test_reconhecer_tipo_pelas_frases_do_prompt():
    assert MP.reconhecer_tipo("quero vender alguma coisa para pequenos lojistas") == "Produto"
    assert MP.reconhecer_tipo("vamos planejar um SaaS de agendamento") == "Projeto"
    assert MP.reconhecer_tipo("quero estudar fotografia do zero") == "Estudos"
    assert MP.reconhecer_tipo("criar um post sobre lanÃ§amento") == "Conteúdo"
    assert MP.reconhecer_tipo("minhas finanças do mês") == "Finanças"


def test_ramo_conecta_ao_card_e_preserva_arranjo(editor, plano):
    raiz = plano.mapa["raiz_id"]
    antes = {c["id"]: (c["x"], c["y"]) for c in plano.mapa["cards"]}
    ops = MP.ramo_modelo("Estudos", raiz)
    _aplicar(editor, ops, "Ramo de estudos")
    mapa = editor.plano_atual().mapa
    criados = [c for c in mapa["cards"] if c["id"] not in antes]
    assert criados
    assert all(c["modelo"] == "estudos" for c in criados)
    assert any(l["origem"] == raiz for l in mapa["conexoes"])
    for ident, (x, y) in antes.items():
        atual = next(c for c in mapa["cards"] if c["id"] == ident)
        assert (atual["x"], atual["y"]) == (x, y)


def test_combinar_modelos_mantem_tipo_principal(editor, plano):
    raiz = plano.mapa["raiz_id"]
    _aplicar(editor, MP.ramo_modelo("Produto", raiz), "Produto")
    _aplicar(editor, MP.ramo_modelo("Estudos", raiz), "Estudos")
    assert editor.plano_atual().tipo == "Geral"
    assert {c["modelo"] for c in editor.plano_atual().mapa["cards"] if c.get("modelo")} >= {
        "produto", "estudos"}


def test_progresso_por_ramo(editor, plano):
    raiz = plano.mapa["raiz_id"]
    _aplicar(editor, MP.ramo_modelo("Projeto", raiz), "Projeto")
    mapa = editor.plano_atual().mapa
    tarefa = next(c for c in mapa["cards"] if c["modelo"] == "projeto"
                  and c["tipo"] == "tarefa")
    editor.definir_progresso(tarefa["id"], "bloqueado")
    ramos = MP.progresso_por_ramo(editor.plano_atual())
    assert ramos["projeto"]["bloqueado"] == 1
    assert ramos["projeto"]["total"] >= 1


def test_publicacao_de_conteudo_aparece_no_progresso(editor, plano):
    raiz = plano.mapa["raiz_id"]
    _aplicar(editor, MP.ramo_modelo("Conteúdo", raiz), "Conteúdo")
    card = next(c for c in editor.plano_atual().mapa["cards"]
                if c["modelo"] == "conteudo" and "Rascunho" in c["titulo"])
    editor.editar_card(card["id"], {"estado": "publicado"})
    ramos = MP.progresso_por_ramo(editor.plano_atual())
    assert ramos["conteudo"]["publicado"] == 1


def test_calculo_financeiro_exato_e_branco_diferente_de_zero(editor, plano):
    raiz = plano.mapa["raiz_id"]
    meta = MP.cards_financeiros("Meta viagem", "100000", "25000")[0]
    zero = MP.cards_financeiros("Meta zero", "0", "")[0]
    ops = [{"tipo": "criar_card", "titulo": meta["titulo"], "tipo_card": "ideia",
            "origem": raiz, "modelo": "financas", "valor": meta["valor"],
            "acumulado": meta["acumulado"]},
           {"tipo": "criar_card", "titulo": zero["titulo"], "tipo_card": "ideia",
            "origem": raiz, "modelo": "financas", "valor": zero["valor"],
            "acumulado": zero["acumulado"]}]
    _aplicar(editor, ops, "Finanças")
    calculo = MP.calculo_financeiro(editor.plano_atual())
    viagem = calculo["metas"][0]
    assert viagem["acumulado"] == 25000 and viagem["restante"] == 75000
    assert any(m["acumulado"] is None for m in calculo["metas"])


def test_geracao_e_uma_unica_operacao_de_desfazer(editor, plano):
    raiz = plano.mapa["raiz_id"]
    contador = editor.pilha.count()
    _aplicar(editor, MP.ramo_modelo("Produto", raiz), "Produto")
    assert editor.pilha.count() == contador + 1
    editor.desfazer()
    assert all(c.get("modelo") != "produto" for c in editor.plano_atual().mapa["cards"])
    editor.refazer()
    assert any(c.get("modelo") == "produto" for c in editor.plano_atual().mapa["cards"])


def test_criar_plano_com_modelo_pelo_gerenciador(tmp_path, monkeypatch, app):
    import ui
    from PyQt6.QtWidgets import QComboBox, QLineEdit, QPushButton
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    from core.interface_planos import PlanosWindow
    janela = PlanosWindow()
    janela.findChild(QPushButton, "novo_plano").click()
    janela.findChild(QLineEdit, "campo_titulo").setText("Trilha de fotografia")
    janela.findChild(QTextEdit, "campo_objetivo").setPlainText("Aprender do zero")
    janela.findChild(QComboBox, "campo_tipo").setCurrentText("Estudos")
    janela.findChild(QPushButton, "salvar_plano").click()
    planos, _ = BP.listar()
    assert len(planos) == 1 and planos[0].tipo == "Estudos"
    assert any(c.get("modelo") == "estudos" for c in planos[0].mapa["cards"])
    janela.hide()
    janela.deleteLater()
    app.processEvents()


def test_adicionar_modelo_como_ramo_pelo_canvas(app, plano, tmp_path):
    from PyQt6.QtWidgets import QWidget
    from core.interface_canvas_planos import CanvasEditor
    from pathlib import Path as _Path
    from core.interface_canvas import DockPreferences as _DP
    host = QWidget()
    host._prefs = _DP(_Path(tmp_path) / "interface.json")
    host.resize(900, 600)
    editor = CanvasEditor(host)
    editor.abrir(plano)
    from PyQt6.QtWidgets import QPushButton
    assert editor.findChild(QPushButton, "adicionar_modelo") is not None
    raiz = plano.mapa["raiz_id"]
    editor.selecionar_card(raiz)
    assert editor.adicionar_modelo("Estudos") is True
    assert any(c.get("modelo") == "estudos"
               for c in editor.editor_internal.plano_atual().mapa["cards"])
    editor.editor_internal._timer.stop()
    editor.editor_internal.cena.itens_cards.clear()
    editor.editor_internal.cena.itens_conexoes.clear()
    editor.editor_internal.cena.clear()
    editor.hide()
    editor.deleteLater()
    host.deleteLater()
    app.processEvents()


def test_plano_antigo_sem_campos_novos_abre(plano):
    dados = carregar(plano.id)
    assert dados is not None
    assert all("modelo" in c and "estado" in c for c in dados.mapa["cards"])
