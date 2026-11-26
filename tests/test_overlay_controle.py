# -*- coding: utf-8 -*-
"""Overlay de controle: comportamento, responsividade e evidência visual."""
from __future__ import annotations

import io
import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PIL import Image, ImageDraw
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QRect
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from core import controle_sessao as CS
from core.overlay_controle import tema
from core.overlay_controle.borda import JanelaBorda
from core.overlay_controle.gerenciador import (
    GerenciadorOverlay, encerrar_global, mascarar_captura,
)
from core.overlay_controle.hud import JanelaAtividades, JanelaBanner, JanelaControles


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


class TelaFalsa(QObject):
    def __init__(self, largura: int, altura: int):
        super().__init__()
        self._geo = QRect(0, 0, largura, altura)

    def geometry(self) -> QRect:
        return self._geo


def _pil_do_widget(widget) -> Image.Image:
    dados = QByteArray()
    buf = QBuffer(dados)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    widget.grab().save(buf, 'PNG')
    buf.close()
    return Image.open(io.BytesIO(bytes(dados.data()))).convert('RGBA')


def _fundo_sintetico(largura: int, altura: int) -> Image.Image:
    """Fundo abstrato azul gerado por código — nunca a tela do usuário."""
    img = Image.new('RGB', (largura, altura))
    d = ImageDraw.Draw(img)
    for y in range(altura):
        t = y / max(1, altura - 1)
        d.line([(0, y), (largura, y)],
               fill=(int(9 + 8 * t), int(20 + 26 * t), int(42 + 58 * t)))
    # Formas geométricas neutras: simulam um aplicativo qualquer sem copiar
    # a REFERência e sem capturar conteúdo real da área de trabalho.
    d.rounded_rectangle((int(largura * .18), int(altura * .22),
                         int(largura * .82), int(altura * .78)),
                        radius=28, outline=(38, 78, 120), width=3)
    d.rectangle((int(largura * .24), int(altura * .32),
                 int(largura * .55), int(altura * .36)), fill=(28, 58, 92))
    d.rectangle((int(largura * .24), int(altura * .40),
                 int(largura * .70), int(altura * .43)), fill=(24, 50, 80))
    d.rectangle((int(largura * .24), int(altura * .48),
                 int(largura * .62), int(altura * .51)), fill=(24, 50, 80))
    return img


def test_metricas_responsivas_e_folga_da_barra():
    for largura, altura in ((1280, 720), (1920, 1080), (3840, 2160), (720, 1280)):
        m = tema.metricas(largura, altura)
        assert 0 < m.banner_x and m.banner_y == 8
        assert m.banner_largura <= largura - 96
        assert m.status_x + m.status_largura <= largura
        assert m.atividades_y > 0
        assert altura - (m.atividades_y + m.atividades_altura) >= 54
        assert m.borda >= 2


@pytest.mark.parametrize('largura,altura', [(1280, 720), (1920, 1080)])
def test_evidencia_visual_sintetica(app, largura, altura):
    """Composite programático para inspeção; não usa a REFERência nem a tela."""
    m = tema.metricas(largura, altura)
    widgets = []
    tela = TelaFalsa(largura, altura)
    borda = JanelaBorda(tela)
    widgets.append((borda, 0, 0))
    banner = JanelaBanner(m)
    widgets.append((banner, m.banner_x - 24, m.banner_y - 24))
    controles = JanelaControles(m)
    widgets.append((controles, m.status_x - 10, m.status_y - 10))
    atividades = JanelaAtividades(m)
    widgets.append((atividades, m.atividades_x - 12, m.atividades_y - 12))
    atividades.definir_atividades([
        {'descricao': 'Abrindo Configurações', 'status': 'concluida'},
        {'descricao': 'Clique: Notificações', 'status': 'concluida'},
        {'descricao': 'Digitando', 'status': 'executando'},
    ])
    for widget, _, _ in widgets:
        widget.show()
        widget.raise_()
    borda.opacidade = 1.0
    QTest.qWait(180)
    app.processEvents()

    fundo = _fundo_sintetico(largura, altura).convert('RGBA')
    for widget, x, y in widgets:
        if not widget.isVisible():
            continue
        pedaco = _pil_do_widget(widget)
        fundo.alpha_composite(pedaco, (int(x), int(y)))

    destino = Path('logs') / 'overlay_controle' / f'visao-{largura}x{altura}.png'
    destino.parent.mkdir(parents=True, exist_ok=True)
    fundo.convert('RGB').save(destino)
    assert destino.exists() and destino.stat().st_size > 10000
    for widget, _, _ in widgets:
        widget.close()
        widget.deleteLater()


def test_botoes_de_controle_sao_compactos(app):
    """Quebra: botões de 46 px cobriam elementos da tela sendo controlada."""
    m = tema.metricas(1920, 1080)
    painel = JanelaControles(m)
    try:
        assert painel.btn_pausa.width() <= 32
        assert painel.btn_parar.height() <= 32
        assert m.status_altura <= 52
        assert m.status_largura <= 250
        assert painel.btn_pausa.x() > m.status_largura // 2
    finally:
        painel.close()
        painel.deleteLater()


def test_botoes_compactos_mantem_alvo_minimo_em_720p(app):
    m = tema.metricas(1280, 720)
    painel = JanelaControles(m)
    try:
        assert 24 <= painel.btn_pausa.width() <= 32
        assert 24 <= painel.btn_parar.height() <= 32
        assert m.status_altura >= 36
    finally:
        painel.close()
        painel.deleteLater()


def test_evidencia_painel_pausado(app):
    """Estado pausado: texto e ícone de retomada cabem no painel compacto."""
    painel = JanelaControles(tema.metricas(1920, 1080))
    try:
        painel.definir_estado('PAUSED', 'pedido do usuário')
        painel.show()
        QTest.qWait(60)
        app.processEvents()
        destino = Path('logs') / 'overlay_controle' / 'painel-pausado.png'
        destino.parent.mkdir(parents=True, exist_ok=True)
        assert painel.grab().save(str(destino))
        assert destino.exists()
    finally:
        painel.close()
        painel.deleteLater()


def test_overlay_aparece_antes_da_acao_e_sai_no_fim(app):
    """Quebra: overlay poderia faltar ou sumir antes do fim da sessão."""
    sessao = CS.SessaoControle(id_factory=lambda: 'ov1')
    gerenciador = GerenciadorOverlay(sessao)
    try:
        token = sessao.iniciar('tarefa', simulado=False)
        assert gerenciador.visivel is True
        assert sessao.estado is CS.EstadoControle.ACTIVE
        assert sessao.permitido() is True
        assert all(w.isVisible() for w in gerenciador._bordas)
        assert all(w.isVisible() for w in gerenciador._banners)
        assert gerenciador._controles.isVisible()
        assert gerenciador._atividades.isVisible()

        sessao.encerrar(token)
        QTest.qWait(500)
        app.processEvents()
        assert sessao.estado is CS.EstadoControle.IDLE
        assert gerenciador.visivel is False
        for timer in (gerenciador._watchdog, gerenciador._ritmo_ativo,
                      gerenciador._ritmo_estatico, gerenciador._fade):
            assert timer.isActive() is False
    finally:
        gerenciador.encerrar()
        encerrar_global()


def test_pausa_e_retomada_pelos_botoes(app):
    """Quebra: botões de pausa/retomada não alteravam o gate."""
    sessao = CS.SessaoControle(id_factory=lambda: 'ov2')
    gerenciador = GerenciadorOverlay(sessao)
    try:
        token = sessao.iniciar('tarefa', simulado=False)
        gerenciador._alternar_pausa()
        QTest.qWait(150)
        app.processEvents()
        assert sessao.estado is CS.EstadoControle.PAUSED
        assert sessao.permitido() is False
        assert gerenciador._controles.btn_pausa._icone == 'play'
        gerenciador._alternar_pausa()
        app.processEvents()
        assert sessao.estado is CS.EstadoControle.ACTIVE
        assert sessao.permitido() is True
        sessao.encerrar(token)
        QTest.qWait(500)
        app.processEvents()
    finally:
        gerenciador.encerrar()
        encerrar_global()


def test_parada_pelo_botao_fecha_o_gate(app):
    sessao = CS.SessaoControle(id_factory=lambda: 'ov3')
    gerenciador = GerenciadorOverlay(sessao)
    try:
        token = sessao.iniciar('tarefa', simulado=False)
        gerenciador._parar()
        app.processEvents()
        assert sessao.parada_solicitada() is True
        assert sessao.permitido() is False
        sessao.encerrar(token)
        QTest.qWait(500)
        app.processEvents()
    finally:
        gerenciador.encerrar()
        encerrar_global()


def test_mascara_de_captura_quando_exclusao_nativa_falha(app):
    """Fallback: se o Windows não exclui o overlay, a captura é limpa."""
    sessao = CS.SessaoControle(id_factory=lambda: 'ov4')
    gerenciador = GerenciadorOverlay(sessao)
    try:
        token = sessao.iniciar('tarefa', simulado=False)
        app.processEvents()
        print('captura_excluida=', gerenciador.captura_excluida)
        imagem = Image.new('RGB', (2400, 1400), (200, 30, 30))
        saida = mascarar_captura(imagem)
        if not gerenciador.captura_excluida:
            alvo = next((w for w in (*gerenciador._banners,
                                     gerenciador._controles,
                                     gerenciador._atividades)
                         if w is not None and w.isVisible()), None)
            assert alvo is not None
            geo = alvo.geometry()
            dpr = max(1.0, float(alvo.devicePixelRatioF()))
            # As janelas incluem uma margem de brilho; amostra dentro do painel.
            x = min(2399, max(0, int(geo.x() * dpr) + 30))
            y = min(1399, max(0, int(geo.y() * dpr) + 30))
            assert saida.getpixel((x, y)) != (200, 30, 30)
        sessao.encerrar(token)
        QTest.qWait(500)
        app.processEvents()
    finally:
        gerenciador.encerrar()
        encerrar_global()
