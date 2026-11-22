# -*- coding: utf-8 -*-
"""Criação por voz deve falar a pergunta/confirmação e abrir o Canvas."""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import main
from core import comandos_planos as CP
from core import planos as BP


@pytest.fixture
def nia(tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    falas = []
    aberturas = []
    mensagens = []
    nia = object.__new__(main.NiaLive)
    nia._modo_local = True
    nia._sessao_planos = CP.SessaoComandosPlanos()
    nia._provedor_assistido = None
    nia.ui = SimpleNamespace(
        contexto_canvas=lambda: {"plano_id": None, "card_id": None, "plano": None},
        write_log=lambda texto: mensagens.append(texto),
        abrir_plano=lambda plano_id: aberturas.append(plano_id),
        abrir_planos=lambda: None,
    )
    monkeypatch.setattr(main.NiaLive, "_falar_local",
                        lambda self, texto, **kw: falas.append(texto))
    for nome in ("_contexto_planos", "_aplicar_resultado_planos",
                 "_processar_pedido_assistido", "_processar_pedido_lembrete",
                 "_resposta_assistida_local", "_executar_frase_habilidade"):
        setattr(nia, nome, getattr(main.NiaLive, nome).__get__(nia, main.NiaLive))
    return nia, falas, aberturas, mensagens


def test_pergunta_por_voz_e_falada_e_depois_abre_canvas(nia):
    obj, falas, aberturas, mensagens = nia
    assert obj._executar_frase_habilidade("NIA, quero criar um projeto.", "voz")
    assert falas and "projeto" in falas[0].lower()
    assert not aberturas
    assert any("Qual" in m for m in mensagens)

    assert obj._executar_frase_habilidade("Meu aplicativo de estoque", "voz")
    assert len(aberturas) == 1
    plano = BP.carregar(aberturas[0])
    assert plano.titulo == "Meu aplicativo de estoque"
    assert any("Abrindo" in f or "criado" in f.lower() for f in falas)


def test_criacao_direta_por_voz_fala_e_abre(nia):
    obj, falas, aberturas, _mensagens = nia
    frase = "Vamos planejar um produto para pequenos lojistas."
    assert obj._executar_frase_habilidade(frase, "voz")
    assert len(aberturas) == 1
    assert falas
    plano = BP.carregar(aberturas[0])
    assert plano.tipo == "Produto"


def test_abrir_plano_por_comando_traz_janela_para_frente(tmp_path, monkeypatch):
    import ui
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtTest import QTest
    app = QApplication.instance() or QApplication([])
    w = ui.MainWindow("face.png")
    w.resize(1100, 700)
    w.show()
    app.processEvents()
    plano = BP.inicializar_mapa(BP.criar("Voz", "Objetivo", "Geral").id)
    casca = object.__new__(ui.NiaUI)
    casca._win = w
    chamadas = []
    original = w._abrir_canvas_do_plano

    def registrar(pid, *args, **kwargs):
        chamadas.append(pid)
        return original(pid, *args, **kwargs)

    monkeypatch.setattr(w, "_abrir_canvas_do_plano", registrar)
    casca.abrir_plano(plano.id)
    QTest.qWait(80)
    app.processEvents()
    assert chamadas == [plano.id]
    editor = getattr(w, "_canvas_editor", None)
    assert editor is not None and editor.isVisible()
    from PyQt6.QtCore import QTimer
    for t in w.findChildren(QTimer):
        t.stop()
    editor.editor_internal.cena.itens_cards.clear()
    editor.editor_internal.cena.itens_conexoes.clear()
    editor.editor_internal.cena.clear()
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_texto_tambem_responde_com_fala_uma_vez(nia):
    import time
    obj, falas, _aberturas, _mensagens = nia
    obj._executar_frase_habilidade("NIA, quero criar um projeto.", "texto")
    for _ in range(100):
        if falas:
            break
        time.sleep(.01)
    assert len(falas) == 1 and 'Qual' in falas[0]
