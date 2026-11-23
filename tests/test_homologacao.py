# -*- coding: utf-8 -*-
"""Homologação do Canvas Infinito: cenário principal e recuperação (Prompt 07)."""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

import main
import ui
from core import assistencia_planos as AP
from core import comandos_planos as CP
from core import lembretes as LEM
from core import modelos_planos as MP
from core import planos as BP
from core.planos import carregar, criar


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
    yield w
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


def test_cenario_principal_criar_editar_consultar_lembrar_e_retomar(perfil, app):
    w = perfil
    sessao = CP.SessaoComandosPlanos()
    criado = sessao.processar("Vamos planejar um estudo de fotografia do zero.", "texto")
    assert criado.tratado and criado.acoes[0]["tipo"] == "abrir_canvas"
    plano = BP.carregar(criado.acoes[0]["plano_id"])
    assert plano.tipo == "Estudos"
    assert any(c.get("modelo") == "estudos" for c in plano.mapa["cards"])

    assert w._abrir_canvas_do_plano(plano.id)
    editor = w._canvas_editor
    exercicio = next(c for c in plano.mapa["cards"]
                     if c.get("modelo") == "estudos" and "Exercício" in c["titulo"])
    editor.selecionar_card(exercicio["id"])
    editor.editor_internal.definir_progresso(exercicio["id"], "concluido")
    editor.editor_internal.definir_camera(120.0, 80.0, 1.4)
    assert editor.editor_internal.salvar()[0]

    casca = object.__new__(ui.NiaUI)
    casca._win = w
    contexto = casca.contexto_canvas()
    resposta = sessao.processar("O que falta agora?", "texto", contexto)
    assert "concluid" not in resposta.resposta.lower()
    assert "pendente" in resposta.resposta.lower()

    nia = object.__new__(main.NiaLive)
    nia._modo_local = True
    nia.ui = SimpleNamespace(contexto_canvas=lambda: casca.contexto_canvas(),
                             write_log=lambda *_: None)
    main.NiaLive._processar_pedido_lembrete(
        nia, "Amanhã às 19h me lembra de revisar este exercício", "texto")
    lembretes = LEM.listar(plano.id)
    assert len(lembretes) == 1 and lembretes[0]["card_id"] == exercicio["id"]

    # "Reinício": recarrega do disco e abre pelo lembrete.
    salvo = carregar(plano.id)
    alvo = LEM.alvo(lembretes[0])
    casca.abrir_lembrete(alvo["plano_id"], alvo["card_id"])
    QTest.qWait(80)
    app.processEvents()
    assert editor.card_selecionado_id == exercicio["id"]
    card = BP.card_por_id(salvo, exercicio["id"])
    assert card["status"] == "concluido"
    assert salvo.mapa["camera"]["zoom"] == 1.4


def test_troca_de_plano_com_pendencia_nao_perde_trabalho(perfil, app, monkeypatch):
    w = perfil
    primeiro = BP.inicializar_mapa(criar("Um", "Um", "Geral").id)
    segundo = BP.inicializar_mapa(criar("Dois", "Dois", "Geral").id)
    w._abrir_canvas_do_plano(primeiro.id)
    editor = w._canvas_editor
    editor.editor_internal.criar_card("Edição pendente")
    assert editor.mudancas_pendentes

    def falhar(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr("core.interface_mapa.atualizar", falhar)
    monkeypatch.setattr(ui, "_perguntar_salvar_mapa",
                        lambda *a: 4194304)  # Cancelar
    assert w._abrir_canvas_do_plano(segundo.id) is False
    assert editor.isVisible()
    assert editor.editor_internal.plano_atual().id == primeiro.id
    assert editor.mudancas_pendentes


def test_fechamento_do_canvas_nao_deixa_timer_de_autosave_ativo(perfil, app):
    w = perfil
    plano = BP.inicializar_mapa(criar("Timer", "Obj", "Geral").id)
    w._abrir_canvas_do_plano(plano.id)
    editor = w._canvas_editor
    assert editor.editor_internal._timer.isActive() is False
    editor.editor_internal.criar_card("Mudança")
    assert editor.editor_internal._timer.isActive() is True
    editor.voltar.emit()
    app.processEvents()
    assert editor.isVisible() is False or editor.editor_internal._timer.isActive() is False


def test_modelos_e_privacidade_sem_rede(perfil, monkeypatch):
    assert len(MP.TIPOS_MODELO) == 5
    import requests
    def sem_rede(*args, **kwargs):
        pytest.fail("homologação não deve usar rede")
    monkeypatch.setattr(requests, "get", sem_rede)
    monkeypatch.setattr(requests, "post", sem_rede)
    plano = BP.inicializar_mapa(criar("Local", "Obj", "Geral").id)
    ops = MP.estrutura_modelo("Produto", "Local", "Obj")
    mapa = MP.aplicar_estrutura_no_mapa(plano.mapa, ops, plano.mapa["raiz_id"])
    assert any("divulgar" in c["titulo"] for c in mapa["cards"])
    assert any("vender" in c["titulo"] for c in mapa["cards"])
