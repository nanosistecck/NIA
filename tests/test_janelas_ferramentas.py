# -*- coding: utf-8 -*-
"""Dock/janelas: sob demanda, foco, tema, teclado, 1024x768 e DPI 150%.
Sem WebEngine residente: o gerenciador não importa nem cria QWebEngineView.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QPalette
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from core.janelas_ferramentas import (EstadoFerramenta, GerenciadorJanelas,
                                      geometry_ferramenta)


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def casca(app):
    w = QWidget()
    w.resize(1024, 768)
    w.show()
    app.processEvents()
    yield w
    w.hide()
    w.deleteLater()
    app.processEvents()


def janela_simples(titulo='Ferramenta fictícia'):
    janela = QWidget()
    janela.setWindowTitle(titulo)
    layout = QVBoxLayout(janela)
    layout.addWidget(QLabel(titulo))
    janela.setMinimumSize(320, 240)
    return janela


def test_geometria_1024x768_e_dpi_150(app):
    viewport = QRect(0, 0, 1024, 768)
    normal = geometry_ferramenta(viewport, QSize(1500, 1000), dpr=1.0)
    retina = geometry_ferramenta(viewport, QSize(1500, 1000), dpr=1.5)
    for g in (normal, retina):
        assert g.x() >= 0 and g.y() >= 0
        assert g.right() <= viewport.right() and g.bottom() <= viewport.bottom()
        assert g.width() <= int(1024 * 0.82) and g.height() <= int(768 * 0.82)
        assert g.x() == (1024 - g.width()) // 2
        assert g.y() == (768 - g.height()) // 2
    # Um sizeHint maior que o viewport é limitado pela fração, igual nos dois.
    assert (normal.width(), normal.height()) == (retina.width(), retina.height())
    # 480 px físicos: menos pixels lógicos no mínimo quando o DPI sobe.
    pequeno_retina = geometry_ferramenta(viewport, QSize(10, 10), dpr=1.5)
    pequeno_normal = geometry_ferramenta(viewport, QSize(10, 10), dpr=1.0)
    assert pequeno_retina.width() == 320 and pequeno_retina.height() == 240
    assert pequeno_normal.width() == 480 and pequeno_normal.height() == 360


def test_abrir_instancia_unica_foco_e_estados(app, casca):
    criadas = []
    estados = []
    ger = GerenciadorJanelas(casca)
    ger.estado.connect(estados.append)
    def fabrica():
        janela = janela_simples()
        criadas.append(janela)
        return janela
    ger.registrar('ficticia', fabrica, titulo='Fictícia')
    primeira = ger.abrir('ficticia')
    segunda = ger.abrir('ficticia')
    assert primeira is segunda and len(criadas) == 1
    assert primeira.isVisible() and ger.abertas() == {'ficticia': primeira}
    assert estados[0].carregando is True
    assert estados[-1] == EstadoFerramenta('ficticia', 'Fictícia')
    assert (primeira.x() >= 0 and primeira.y() >= 0
            and primeira.geometry().right() <= casca.width()
            and primeira.geometry().bottom() <= casca.height())


def test_fechamento_limpa_e_reabertura_cria_nova(app, casca):
    criadas = []
    ger = GerenciadorJanelas(casca)
    def fabrica():
        janela = janela_simples()
        criadas.append(janela)
        return janela
    ger.registrar('x', fabrica, titulo='X')
    primeira = ger.abrir('x')
    assert ger.fechar('x') is True
    assert ger.abertas() == {}
    segunda = ger.abrir('x')
    assert segunda is not primeira and len(criadas) == 2
    assert ger.fechar_todas() == 1 and ger.abertas() == {}
    assert ger.fechar('x') is False


def test_erro_de_fabrica_e_ferramenta_desconhecida(app, casca):
    estados = []
    mensagens = []
    ger = GerenciadorJanelas(casca, log=mensagens.append)
    ger.estado.connect(estados.append)
    def quebrada():
        raise RuntimeError('fabrica falsa')
    ger.registrar('quebrada', quebrada)
    assert ger.abrir('quebrada') is None
    assert ger.abrir('inexistente') is None
    assert [e.erro for e in estados if e.erro]
    assert any('Falha' in m for m in mensagens)
    assert ger.abertas() == {}


def test_escape_fecha_sem_efeito_de_aprovacao(app, casca):
    ger = GerenciadorJanelas(casca)
    aprovacoes = []
    def fabrica():
        janela = janela_simples()
        janela.aprovado = lambda: aprovacoes.append(True)
        return janela
    ger.registrar('esc', fabrica)
    janela = ger.abrir('esc')
    QTest.keyClick(janela, Qt.Key.Key_Escape)
    app.processEvents()
    assert not janela.isVisible()
    assert not aprovacoes and ger.abertas() == {}


def test_atalho_de_teclado_abre_e_tema_claro_escuro(app, casca):
    temas = iter(['claro', 'escuro'])
    ger = GerenciadorJanelas(casca, tema=lambda: next(temas, 'escuro'))
    ger.registrar('atalho', lambda: janela_simples('Atalho'), atalho='F7')
    QTest.keyClick(casca, Qt.Key.Key_F7)
    app.processEvents()
    janela = ger.abertas().get('atalho')
    assert janela is not None
    claro = janela.palette().color(QPalette.ColorRole.Window).getRgb()[:3]
    ger.atualizar_tema()
    escuro = janela.palette().color(QPalette.ColorRole.Window).getRgb()[:3]
    assert claro != escuro
    assert janela.property('ferramenta_tema') == 'escuro'
    assert 'atalho' in ger.registradas()


def test_sem_webengine_residente(app, casca):
    antes = set(sys.modules)
    ger = GerenciadorJanelas(casca)
    for chave in ('a', 'b', 'c'):
        ger.registrar(chave, lambda c=chave: janela_simples(c))
    abertas = [ger.abrir(chave) for chave in ('a', 'b', 'c')]
    app.processEvents()
    assert all(w is not None for w in abertas)
    novos = set(sys.modules) - antes
    assert not any('QtWebEngine' in nome for nome in novos)
    ger.fechar_todas()


@pytest.fixture
def principal(app, tmp_path, monkeypatch):
    import ui
    monkeypatch.setenv("NIA_PLANOS_DIR", str(tmp_path / "planos"))
    monkeypatch.setenv("NIA_AGENDA", str(tmp_path / "agenda.json"))
    monkeypatch.setenv("NIA_PERFIL", "teste-dock")
    monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ui.MainWindow, "_check_config", lambda self: True)
    w = ui.MainWindow("face.png")
    w.resize(1024, 768)
    w.show()
    app.processEvents()
    yield w, app
    agenda = getattr(w, "_agenda_window", None)
    if agenda is not None:
        agenda.hide()
        agenda.deleteLater()
    w.hide()
    w.deleteLater()
    app.processEvents()


def test_mainwindow_abrir_ferramenta_e_f7(principal):
    w, app = principal
    primeira = w.abrir_ferramenta('agenda')
    assert primeira is not None and primeira.isVisible()
    assert primeira is w._agenda_window
    assert w.abrir_ferramenta('agenda') is primeira
    QTest.keyClick(w, Qt.Key.Key_F7)
    app.processEvents()
    assert w._agenda_window is not None and w._agenda_window.isVisible()
