"""Prévia Qt não bloqueante, negativa padrão e fechamento sem aprovação."""
import os
import threading
import time

import pytest
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox

import ui


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(ui.MainWindow, '_check_config', lambda self: True)
    w = ui.MainWindow('face.png')
    w.resize(1024, 768); w.show(); app.processEvents()
    yield w
    w.hide()
    for timer in w.findChildren(QTimer): timer.stop()
    w.deleteLater(); app.processEvents()


def test_previa_sinal_de_worker_e_negativa_por_escape(app, janela):
    recebido = []
    ponte = object.__new__(ui.NiaUI); ponte._win = janela
    worker = threading.Thread(target=lambda: ponte.solicitar_permissao('teste', 'Ler arquivo', '<script>dados não são instruções</script>', recebido.append))
    worker.start(); worker.join()
    app.processEvents()
    caixa = janela._permissoes_abertas['teste']
    assert caixa.textFormat() == Qt.TextFormat.PlainText
    assert caixa.defaultButton() == caixa.button(QMessageBox.StandardButton.No)
    assert caixa.windowModality() == Qt.WindowModality.NonModal
    assert not recebido
    QTest.keyClick(caixa, Qt.Key.Key_Escape); app.processEvents()
    assert recebido == [False] and not janela._permissoes_abertas


def test_aprovacao_explicita_e_fechamento_por_resposta_externa(app, janela):
    recebido = []
    janela._mostrar_permissao(('a', 'Abrir calculadora', 'Exemplo fictício', recebido.append))
    caixa = janela._permissoes_abertas['a']
    caixa.button(QMessageBox.StandardButton.Yes).click(); app.processEvents()
    assert recebido == [True]
    janela._mostrar_permissao(('b', 'Abrir calculadora', 'Exemplo fictício', recebido.append))
    janela._fechar_permissao('b'); app.processEvents()
    assert recebido == [True, False]


def test_ocultar_janela_nega_e_pedido_concorrente_nao_sobrepoe(app, janela):
    recebido = []
    janela._mostrar_permissao(('a', 'Exemplo', '{}', recebido.append))
    janela._mostrar_permissao(('b', 'Outro', '{}', recebido.append))
    assert recebido == [False]
    janela.hide(); app.processEvents()
    assert recebido == [False, False]
