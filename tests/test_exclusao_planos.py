# -*- coding: utf-8 -*-
"""Exclusão permanente de planos arquivados (revisão Prompt 07)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QListWidget, QMessageBox

from core import planos as BP
from core.interface_planos import PlanosWindow
from core.planos import arquivar, carregar, criar, listar, restaurar


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app, tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    w = PlanosWindow()
    w.show()
    app.processEvents()
    yield w
    w.hide()
    w.deleteLater()
    app.processEvents()


def _plano(titulo, arquivar_plano=True):
    p = criar(titulo, "Objetivo", "Geral")
    if arquivar_plano:
        atual = carregar(p.id)
        arquivar(p.id, atual.revisao)
    return p


def test_existe_api_excluir_e_so_arquivados():
    assert hasattr(BP, "excluir_permanentemente")
    ativo = _plano("Ativo", arquivar_plano=False)
    with pytest.raises(BP.ErroPlano):
        BP.excluir_permanentemente(ativo.id, carregar(ativo.id).revisao)
    assert carregar(ativo.id) is not None


def test_excluir_arquivado_remove_arquivo_e_lembretes(tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    p = _plano("Excluir")
    from core import lembretes as LEM
    LEM.criar(p.id, "Aviso", "2026-12-01T22:00:00+00:00", "UTC")
    assert LEM.listar(p.id)
    BP.excluir_permanentemente(p.id, carregar(p.id).revisao)
    assert carregar(p.id) is None
    assert all(x.get("plano_id") != p.id for x in LEM.listar_todos())
    assert p.id not in [x.id for x in listar()[0]]


def test_conflito_de_revisao_preserva(tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    p = _plano("Conflito")
    with pytest.raises(BP.ConflitoDeRevisao):
        BP.excluir_permanentemente(p.id, 0)
    assert carregar(p.id) is not None


def test_restaurado_entre_selecao_e_exclusao(tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    p = _plano("Restaurado")
    atual = carregar(p.id)
    restaurar(p.id, atual.revisao)
    with pytest.raises(BP.PlanoInvalido):
        BP.excluir_permanentemente(p.id, atual.revisao)
    assert carregar(p.id) is not None


def test_lote_parcial_e_retry(tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    um = _plano("Igual")
    dois = _plano("Igual")
    tres = _plano("Tres")
    revisoes = {p.id: carregar(p.id).revisao for p in (um, dois, tres)}
    falhas = {dois.id}

    resultado = BP.excluir_lote([(p.id, revisoes[p.id]) for p in (um, dois, tres)],
                                falhas=falhas)
    assert resultado["excluidos"] == [um.id, tres.id]
    assert resultado["falhas"] == [dois.id]
    assert carregar(um.id) is None and carregar(tres.id) is None
    assert carregar(dois.id) is not None
    retry = BP.excluir_lote([(dois.id, carregar(dois.id).revisao)])
    assert retry["excluidos"] == [dois.id] and carregar(dois.id) is None


def test_interface_botao_e_selecao_multipla(janela, app, monkeypatch):
    p1 = _plano("Mesmo")
    p2 = _plano("Mesmo")
    janela.recarregar()
    janela.filtro_status.setCurrentText("Arquivados")
    janela.aplicar_filtros()
    assert janela.lista.selectionMode() == QListWidget.SelectionMode.ExtendedSelection
    assert janela.botoes["excluir_permanentemente"].isVisible()

    janela.botoes["excluir_permanentemente"].setEnabled(True)
    # simula confirmação aceita sem abrir diálogo modal
    monkeypatch.setattr(janela, "_confirmar_exclusao", lambda ids: True)
    for i in range(janela.lista.count()):
        janela.lista.item(i).setSelected(True)
    janela._excluir_permanentemente()
    app.processEvents()
    assert carregar(p1.id) is None and carregar(p2.id) is None


def test_cancelar_preserva(janela, app, monkeypatch):
    p = _plano("Cancelar")
    janela.filtro_status.setCurrentText("Arquivados")
    janela.aplicar_filtros()
    monkeypatch.setattr(janela, "_confirmar_exclusao", lambda ids: False)
    janela.selecionar(p.id)
    janela._excluir_permanentemente()
    app.processEvents()
    assert carregar(p.id) is not None


@pytest.mark.parametrize("confirmar", [True, False])
def test_confirmacao_real_e_exclusao_de_ativo(janela, app, confirmar):
    from PyQt6.QtCore import QTimer
    p = _plano("Plano ativo", arquivar_plano=False)
    janela.recarregar()
    janela.selecionar(p.id)

    def responder():
        caixa = janela.findChild(QMessageBox)
        assert caixa is not None
        if confirmar:
            botao = next(b for b in caixa.buttons()
                         if caixa.buttonRole(b) == QMessageBox.ButtonRole.DestructiveRole)
        else:
            botao = caixa.button(QMessageBox.StandardButton.Cancel)
        botao.click()

    QTimer.singleShot(0, responder)
    janela.botoes["excluir_permanentemente"].click()
    if confirmar:
        assert carregar(p.id) is None
        assert janela.plano_selecionado_id is None
        assert janela.campo_titulo.text() == ""
    else:
        assert carregar(p.id).status == "ativo"
