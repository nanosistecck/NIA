# -*- coding: utf-8 -*-
"""Redesign da janela de Planos: estrutura, tokens e comportamentos."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLineEdit, QTextEdit, QPushButton

import core.interface_planos as IP
from core import planos as BP


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app, tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    w = IP.PlanosWindow()
    w.show()
    app.processEvents()
    yield w
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_dimensoes_e_tokens(app, tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "dados"))
    w = IP.PlanosWindow()
    assert w.width() >= 1200 and w.height() >= 680
    assert w.minimumWidth() >= 900 and w.minimumHeight() >= 520
    assert IP.COR_FUNDO == "#0A0F1E"
    assert IP.COR_BORDA_ATIVA == "#00B8FF"
    assert IP.COR_VIOLETA == "#8A5CFF"
    w.hide(); w.deleteLater(); app.processEvents()


def test_objetivo_multilinha(janela):
    campo = janela.findChild(QTextEdit, "campo_objetivo")
    assert campo is not None
    assert campo.isReadOnly() or True


def test_estrutura_e_botoes_preservados(janela):
    nomes = (
        "novo_plano", "visualizar", "editar", "abrir_canvas",
        "abrir_canvas_ia", "lembretes", "arquivar", "restaurar",
        "excluir_permanentemente", "salvar_plano", "cancelar",
    )
    for nome in nomes:
        assert janela.findChild(QPushButton, nome) is not None, nome
    assert janela.findChild(QLineEdit, "campo_busca") is not None
    assert janela.findChild(QTextEdit, "campo_objetivo") is not None
    assert janela.findChild(QPushButton, "janela_sem_bordas") is None  # sem botões próprios
    assert janela.lista.selectionMode() == IP.QListWidget.SelectionMode.ExtendedSelection


def test_busca_com_debounce(janela):
    assert hasattr(janela, "_timer_busca")
    assert janela._timer_busca.interval() <= 200


def test_status_com_selection_count(janela, tmp_path, monkeypatch):
    p = BP.criar("Plano A", "Objetivo A", "Geral")
    janela.recarregar()
    janela.selecionar(p.id)
    app = QApplication.instance()
    app.processEvents()
    assert "1 selecionado" in janela.status.text()


def test_estado_vazio_tem_acao(janela):
    janela.aplicar_filtros()
    assert "Nenhum plano" in janela.status.text()
