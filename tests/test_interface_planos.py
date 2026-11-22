# -*- coding: utf-8 -*-
"""Gerenciador de Planos: fluxo por clique, filtros e estados (Etapa 1)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton, QTextEdit

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
    janela.findChild(QTextEdit, "campo_objetivo").setPlainText("Estudar luz")
    _combo(janela, "campo_tipo").setCurrentText("Estudos")
    _botao(janela, "salvar_plano").click()

    planos, _ = listar()
    assert len(planos) == 1
    plano_id = planos[0].id
    assert janela.plano_selecionado_id == plano_id

    _texto(janela, "campo_busca").setText("fotogra")  # sem acento
    janela.aplicar_filtros()
    assert [janela.lista.item(i).data(0x0100) for i in range(janela.lista.count())] == [plano_id]

    janela.selecionar(plano_id)
    _botao(janela, "visualizar").click()
    assert _texto(janela, "campo_titulo").isReadOnly()
    from PyQt6.QtWidgets import QDialog
    janela.findChild(QDialog, "visualizacao_plano").close()
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
    assert "Nenhum" in janela.status.text()

    from core.planos import criar as criar_plano
    plano = criar_plano("Original", "Objetivo original")
    janela.recarregar()
    janela.selecionar(plano.id)
    _botao(janela, "editar").click()
    _texto(janela, "campo_titulo").setText("Titulo digitado")
    janela.findChild(QTextEdit, "campo_objetivo").setPlainText("Objetivo digitado")

    def falhar(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr(IP, "atualizar", falhar)
    _botao(janela, "salvar_plano").click()
    assert "Falha ao salvar" in janela.status.text()
    assert _texto(janela, "campo_titulo").text() == "Titulo digitado"
    assert janela.findChild(QTextEdit, "campo_objetivo").toPlainText() == "Objetivo digitado"


def test_conflito_de_revisao_e_sinalizado_no_gerenciador(janela, monkeypatch):
    from core.planos import ConflitoDeRevisao, criar as criar_plano
    plano = criar_plano("Original", "Objetivo", "Projeto")
    janela.recarregar()
    janela.selecionar(plano.id)
    _botao(janela, "editar").click()
    _texto(janela, "campo_titulo").setText("Titulo local")

    def conflito(*args, **kwargs):
        raise ConflitoDeRevisao(0, 1)

    monkeypatch.setattr(IP, "atualizar", conflito)
    _botao(janela, "salvar_plano").click()
    assert "conflito" in janela.status.text().lower()
    assert _texto(janela, "campo_titulo").text() == "Titulo local"


def test_visualizar_abre_detalhes_somente_leitura(janela):
    from PyQt6.QtWidgets import QDialog
    from core.planos import criar
    plano = criar("Detalhes", "Objetivo completo", "Projeto")
    janela.recarregar()
    janela.selecionar(plano.id)
    _botao(janela, "visualizar").click()
    dialogo = janela.findChild(QDialog, "visualizacao_plano")
    assert dialogo is not None and dialogo.isVisible()
    objetivo = dialogo.findChild(QTextEdit)
    assert objetivo.isReadOnly()
    assert objetivo.toPlainText() == plano.objetivo
    dialogo.close()


def test_filtrar_limpa_selecao_e_detalhes(janela):
    from core.planos import criar
    plano = criar("Selecionado", "Objetivo")
    janela.recarregar()
    janela.selecionar(plano.id)
    janela.campo_busca.setText("sem resultados")
    janela.aplicar_filtros()
    assert janela.plano_selecionado_id is None
    assert not _botao(janela, "visualizar").isEnabled()
    assert not _botao(janela, "excluir_permanentemente").isEnabled()
    assert janela.campo_titulo.text() == ""


def test_primeiro_selecionado_e_acoes_em_lote(janela):
    from core.planos import criar
    planos = [criar(f"Plano {i}", "Objetivo") for i in range(3)]
    janela.recarregar()
    assert janela.lista.currentRow() == 0
    assert len(janela.lista.selectedItems()) == 1
    for i in range(janela.lista.count()):
        janela.lista.item(i).setSelected(True)
    _botao(janela, "arquivar").click()
    assert all(carregar(p.id).status == "arquivado" for p in planos)
    janela.filtro_status.setCurrentText("Arquivados")
    for i in range(janela.lista.count()):
        janela.lista.item(i).setSelected(True)
    _botao(janela, "restaurar").click()
    assert all(carregar(p.id).status == "ativo" for p in planos)


def test_delete_exclui_lote_e_seleciona_proximo(janela, monkeypatch, app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from core.planos import criar
    for i in range(3):
        criar(f"Plano {i}", "Objetivo")
    janela.recarregar()
    janela.lista.item(1).setSelected(True)
    ids = [i.data(Qt.ItemDataRole.UserRole) for i in janela.lista.selectedItems()]
    monkeypatch.setattr(janela, "_confirmar_exclusao", lambda ids: True)
    janela.activateWindow()
    janela.lista.setFocus()
    app.processEvents()
    QTest.keyClick(janela.lista, Qt.Key.Key_Delete)
    assert all(carregar(ident) is None for ident in ids)
    assert janela.lista.count() == 1
    assert janela.lista.currentRow() == 0
    assert len(janela.lista.selectedItems()) == 1


def test_delete_no_formulario_nao_exclui_plano(janela, monkeypatch, app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from core.planos import criar
    plano = criar("Plano", "Objetivo")
    janela.recarregar()
    chamadas = []
    monkeypatch.setattr(janela, "_confirmar_exclusao", lambda ids: chamadas.append(ids))
    janela.editar()
    janela.campo_titulo.setFocus()
    app.processEvents()
    QTest.keyClick(janela.campo_titulo, Qt.Key.Key_Delete)
    assert not chamadas
    assert carregar(plano.id) is not None
