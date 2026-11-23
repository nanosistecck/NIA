# -*- coding: utf-8 -*-
"""Janela Agenda: selecionar, editar, concluir, reabrir e excluir."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QApplication, QListWidget, QPushButton

from core import agenda, interface_agenda as IA


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app, tmp_path, monkeypatch):
    monkeypatch.setenv("NIA_AGENDA", str(tmp_path / "agenda.json"))
    monkeypatch.setenv("NIA_PERFIL", "crud-ui")
    w = IA.AgendaWindow()
    w.resize(1000, 700)
    w.show()
    app.processEvents()
    yield w
    for timer in w.findChildren(QTimer):
        timer.stop()
    w.hide(); w.deleteLater(); app.processEvents()


def test_clicar_lista_carrega_formulario(janela):
    w = janela
    item = agenda.criar("Consulta", "2026-11-24T09:00:00-03:00", "chamada",
                        notas="levar exames")
    w.recarregar()
    w.selecionar_item(item["id"])
    assert w.campo_titulo.text() == "Consulta"
    assert w.campo_notas.toPlainText() == "levar exames"
    assert w.campo_tipo.currentText() == "chamada"
    assert w.btn_salvar.text() == "Salvar alterações"


def test_salvar_edicao_de_todos_os_campos(janela):
    w = janela
    item = agenda.criar("Consulta", "2026-11-24T09:00:00-03:00", "chamada")
    w.recarregar(); w.selecionar_item(item["id"])
    w.campo_titulo.setText("Consulta particular")
    w.campo_tipo.setCurrentText("tarefa")
    w.campo_preparo.setValue(45)
    w.campo_notas.setPlainText("levar exames e exames antigos")
    w.campo_estado.setCurrentText("concluido")
    w.btn_salvar.click()
    salvo = next(i for i in agenda.listar() if i["id"] == item["id"])
    assert salvo["titulo"] == "Consulta particular"
    assert salvo["tipo"] == "tarefa"
    assert salvo["preparo_minutos"] == 45
    assert salvo["notas"] == "levar exames e exames antigos"
    assert salvo["estado"] == "concluido"


def test_concluir_reabrir_e_excluir(janela, monkeypatch):
    w = janela
    item = agenda.criar("Consulta", "2026-11-24T09:00:00-03:00", "chamada")
    w.recarregar(); w.selecionar_item(item["id"])
    w.btn_concluir.click()
    assert next(i for i in agenda.listar() if i["id"] == item["id"])["estado"] == "concluido"
    w.btn_reabrir.click()
    assert next(i for i in agenda.listar() if i["id"] == item["id"])["estado"] == "pendente"
    monkeypatch.setattr(w, "_confirmar_exclusao", lambda: True)
    w.btn_excluir.click()
    assert all(i["id"] != item["id"] for i in agenda.listar())


def test_excluir_cancelado_nao_apaga(janela, monkeypatch):
    w = janela
    item = agenda.criar("Consulta", "2026-11-24T09:00:00-03:00", "chamada")
    w.recarregar(); w.selecionar_item(item["id"])
    monkeypatch.setattr(w, "_confirmar_exclusao", lambda: False)
    w.btn_excluir.click()
    assert any(i["id"] == item["id"] for i in agenda.listar())


def test_novo_apos_edicao_limpa_formulario(janela):
    w = janela
    item = agenda.criar("Consulta", "2026-11-24T09:00:00-03:00", "chamada")
    w.recarregar(); w.selecionar_item(item["id"])
    w.btn_cancelar.click()
    assert w.item_selecionado_id is None
    assert w.btn_salvar.text() == "+ Compromisso"
    assert w.campo_titulo.text() == ""
