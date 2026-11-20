# -*- coding: utf-8 -*-
"""Gerenciador de Planos: fluxo por clique, filtros e estados (Etapa 1)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton

import core.interface_planos as IP
from core.planos import carregar, listar


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


def _botao(janela, nome):
    return janela.findChild(QPushButton, nome)


def _texto(janela, nome):
    return janela.findChild(QLineEdit, nome)


def _combo(janela, nome):
    return janela.findChild(QComboBox, nome)


def test_criar_buscar_visualizar_editar_arquivar_restaurar(janela):
    _botao(janela, "novo_plano").click()
    _texto(janela, "campo_titulo").setText("Fotografia")
    _texto(janela, "campo_objetivo").setText("Estudar luz")
    _combo(janela, "campo_tipo").setCurrentText("Estudos")
    _botao(janela, "salvar_plano").click()

    planos, _ = listar()
    assert len(planos) == 1
    plano_id = planos[0].id
    assert janela.plano_selecionado_id == plano_id

    _texto(janela, "campo_busca").setText("fotogra")  # sem acento
    janela.aplicar_filtros()
    assert [janela.lista.item(i).data(0x0100) for i in range(janela.lista.count())] == [plano_id]

    _botao(janela, "visualizar").click()
    assert _texto(janela, "campo_titulo").isReadOnly()
    _botao(janela, "editar").click()
    assert not _texto(janela, "campo_titulo").isReadOnly()
    _texto(janela, "campo_titulo").setText("Fotografia II")
    _botao(janela, "salvar_plano").click()
    assert carregar(plano_id).id == plano_id
    assert carregar(plano_id).titulo == "Fotografia II"

    _botao(janela, "arquivar").click()
    assert carregar(plano_id).status == "arquivado"
    _combo(janela, "filtro_status").setCurrentText("Arquivados")
    janela.aplicar_filtros()
    assert [janela.lista.item(i).data(0x0100) for i in range(janela.lista.count())] == [plano_id]
    _botao(janela, "restaurar").click()
    assert carregar(plano_id).status == "ativo"


def test_estados_vazios_e_erro_preserva_digitado(janela, monkeypatch):
    assert "Nenhum plano" in janela.status.text()
    _texto(janela, "campo_busca").setText("inexistente")
    janela.aplicar_filtros()
    assert "Nenhum resultado" in janela.status.text()

    from core.planos import criar as criar_plano
    plano = criar_plano("Original", "Objetivo original")
    janela.recarregar()
    janela.selecionar(plano.id)
    _botao(janela, "editar").click()
    _texto(janela, "campo_titulo").setText("Titulo digitado")
    _texto(janela, "campo_objetivo").setText("Objetivo digitado")

    def falhar(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr(IP, "atualizar", falhar)
    _botao(janela, "salvar_plano").click()
    assert "Falha ao salvar" in janela.status.text()
    assert _texto(janela, "campo_titulo").text() == "Titulo digitado"
    assert _texto(janela, "campo_objetivo").text() == "Objetivo digitado"
