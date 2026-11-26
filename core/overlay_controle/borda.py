# -*- coding: utf-8 -*-
"""Borda luminosa que envolve cada monitor.

Uma janela transparente por tela, sem foco e sem receber cliques. O traço
estático (cinco camadas) fica em cache por tamanho/DPR; só os reflexos em
movimento são repintados. Nada é criado fora de uma sessão de controle.
"""
from __future__ import annotations

import ctypes
import math
import sys

from PyQt6.QtCore import (
    QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QRegion
from PyQt6.QtWidgets import QWidget

from core.overlay_controle import tema

_WDA_EXCLUDEFROMCAPTURE = 0x11
_WDA_MONITOR = 0x01


def _pen(cor: str, largura: float, alpha: float) -> QPen:
    c = QColor(cor)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    p = QPen(c)
    p.setWidthF(max(0.1, float(largura)))
    p.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return p


def _aplicar_exclusao_captura(hwnd: int) -> bool:
    if sys.platform != 'win32':
        return False
    try:
        user32 = ctypes.windll.user32
        if user32.SetWindowDisplayAffinity(int(hwnd), _WDA_EXCLUDEFROMCAPTURE):
            return True
        return bool(user32.SetWindowDisplayAffinity(int(hwnd), _WDA_MONITOR))
    except Exception:
        return False


def _aplicar_estilo_nativo(hwnd: int, clique_atraves: bool) -> None:
    if sys.platform != 'win32':
        return
    try:
        user32 = ctypes.windll.user32
        gwl_exstyle = -20
        estilo = user32.GetWindowLongW(int(hwnd), gwl_exstyle)
        estilo |= 0x00000080   # WS_EX_TOOLWINDOW
        estilo |= 0x08000000   # WS_EX_NOACTIVATE
        estilo |= 0x00080000   # WS_EX_LAYERED
        if clique_atraves:
            estilo |= 0x00000020   # WS_EX_TRANSPARENT
        user32.SetWindowLongW(int(hwnd), gwl_exstyle, estilo)
    except Exception:
        pass


class JanelaBorda(QWidget):
    """Borda azul com halo, reflexos e pulsação leve."""

    def __init__(self, tela):
        super().__init__(None, self._flags())
        self._tela = tela
        self._fase = 0.0
        self._opacidade = 0.0
        self._ritmo = 'ativo'
        self._cache_base = None
        self._cache_glow = None
        self._cache_chave = None
        self._pontos: list[tuple[float, float, float, float]] = []
        self._regiao: QRegion | None = None
        self._captura_excluida = False
        self._anim_entrada = None
        self._anim_saida = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._timer.setInterval(42)
        self._timer.timeout.connect(self._animar)
        self._aplicar_geometria()
        self._captura_excluida = _aplicar_exclusao_captura(int(self.winId()))
        _aplicar_estilo_nativo(int(self.winId()), clique_atraves=True)

    @staticmethod
    def _flags():
        return (Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.Tool
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowTransparentForInput
                | Qt.WindowType.WindowDoesNotAcceptFocus)

    @property
    def captura_excluida(self) -> bool:
        return self._captura_excluida

    @property
    def tela(self):
        return self._tela

    def _aplicar_geometria(self) -> None:
        try:
            self.setGeometry(self._tela.geometry())
        except Exception:
            pass
        self._regiao = None

    def _regiao_bordas(self) -> QRegion:
        """Só as faixas da borda são repintadas; o centro fica intacto."""
        if self._regiao is None:
            largura, altura = self.width(), self.height()
            faixa = 76
            regiao = QRegion(0, 0, largura, min(faixa, altura))
            regiao |= QRegion(0, max(0, altura - faixa), largura, faixa)
            regiao |= QRegion(0, 0, min(faixa, largura), altura)
            regiao |= QRegion(max(0, largura - faixa), 0, faixa, altura)
            self._regiao = regiao
        return self._regiao

    def atualizar_tela(self, tela) -> None:
        self._tela = tela
        self._aplicar_geometria()
        self._cache_chave = None
        self.update()

    @pyqtProperty(float)
    def opacidade(self) -> float:
        return self._opacidade

    @opacidade.setter
    def opacidade(self, valor: float) -> None:
        self._opacidade = max(0.0, min(1.0, float(valor)))
        if self._opacidade <= 0.001:
            self.update()
        else:
            self.update(self._regiao_bordas())

    def mostrar(self) -> None:
        self._aplicar_geometria()
        self._opacidade = 0.0
        self.show()
        self.raise_()
        self._iniciar_entrada()

    def ocultar(self) -> None:
        if not self.isVisible():
            return
        if self._anim_saida is not None:
            self._anim_saida.stop()
        anim = QPropertyAnimation(self, b'opacidade', self)
        anim.setDuration(220)
        anim.setStartValue(self._opacidade)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        anim.finished.connect(self._fim_saida)
        self._anim_saida = anim
        anim.start()

    def _fim_saida(self) -> None:
        self._timer.stop()
        self.hide()

    def _iniciar_entrada(self) -> None:
        if self._anim_entrada is not None:
            self._anim_entrada.stop()
        anim = QPropertyAnimation(self, b'opacidade', self)
        anim.setDuration(280)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim_entrada = anim
        anim.start()
        self.definir_ritmo('ativo')

    def definir_ritmo(self, ritmo: str) -> None:
        """'ativo' (24 fps), 'economico' (12 fps) ou 'estatico' (sem timer)."""
        self._ritmo = ritmo
        if ritmo == 'estatico':
            self._timer.stop()
            return
        intervalo = 42 if ritmo == 'ativo' else 83
        if self._timer.interval() != intervalo:
            self._timer.setInterval(intervalo)
        if not self._timer.isActive():
            self._timer.start()

    def _animar(self) -> None:
        if not self.isVisible():
            self._timer.stop()
            return
        self._fase = (self._fase + (0.0055 if self._ritmo == 'ativo' else 0.0028)) % 1.0
        self.update(self._regiao_bordas())

    def apresentado(self) -> bool:
        if not self.isVisible() or self.width() <= 0 or self.height() <= 0:
            return False
        try:
            return self.geometry().intersects(self._tela.geometry())
        except Exception:
            return True

    def _reconstruir_cache(self) -> None:
        dpr = max(1.0, float(self.devicePixelRatioF()))
        largura, altura = self.width(), self.height()
        chave = (largura, altura, round(dpr, 2), self._tela.geometry().getRect())
        if chave == self._cache_chave and self._cache_base is not None:
            return
        self._cache_chave = chave

        base = QPixmap(int(largura * dpr), int(altura * dpr))
        base.setDevicePixelRatio(dpr)
        base.fill(Qt.GlobalColor.transparent)
        pb = QPainter(base)
        pb.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        glow = QPixmap(int(largura * dpr), int(altura * dpr))
        glow.setDevicePixelRatio(dpr)
        glow.fill(Qt.GlobalColor.transparent)
        pg = QPainter(glow)
        pg.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(8.0, 8.0, max(1.0, largura - 16.0), max(1.0, altura - 16.0))
        caminho = QPainterPath()
        caminho.addRoundedRect(rect, tema.RAIO_BORDA, tema.RAIO_BORDA)

        # Cinco traços do manual: halo 26/8%, halo 16/15%, brilho 8/30%,
        # linha 3/95% e reflexo 1/85%.
        pg.setPen(_pen(tema.AZUL, 26.0, 0.08))
        pg.drawPath(caminho)
        pg.setPen(_pen(tema.CIANO, 16.0, 0.15))
        pg.drawPath(caminho)
        pg.setPen(_pen(tema.AZUL, 8.0, 0.30))
        pg.drawPath(caminho)
        pg.end()

        pb.setPen(_pen(tema.CIANO, 3.0, 0.95))
        pb.drawPath(caminho)
        pb.setPen(_pen(tema.CRISTAL, 1.0, 0.85))
        pb.drawPath(caminho)
        pb.end()

        # Pré-calcula a geometria dos reflexos: `pointAtPercent`/`angleAtPercent`
        # custam caro e não precisam rodar 24 vezes por segundo.
        amostras = 128
        self._pontos = []
        for i in range(amostras):
            t = i / float(amostras)
            ponto = caminho.pointAtPercent(t)
            angulo = math.radians(-caminho.angleAtPercent(t))
            self._pontos.append((ponto.x(), ponto.y(), math.cos(angulo),
                                 math.sin(angulo)))

        self._cache_base = base
        self._cache_glow = glow

    def paintEvent(self, _evento) -> None:
        if self._opacidade <= 0.001:
            return
        self._reconstruir_cache()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setOpacity(self._opacidade)
        pulso = 0.72 + 0.28 * (0.5 + 0.5 * math.sin(
            2.0 * math.pi * (self._fase / 0.5333)))
        p.setOpacity(self._opacidade * pulso)
        p.drawPixmap(0, 0, self._cache_glow)
        p.setOpacity(self._opacidade)
        p.drawPixmap(0, 0, self._cache_base)
        self._pintar_reflexos(p)
        p.end()

    def _pintar_reflexos(self, p: QPainter) -> None:
        if not self._pontos:
            return
        total = len(self._pontos)
        for deslocamento in (0.0, 0.5):
            for i in range(8):
                t = (self._fase + deslocamento + i * 0.0064) % 1.0
                posicao = t * (total - 1)
                a = int(posicao)
                b = min(total - 1, a + 1)
                frac = posicao - a
                x0, y0, dx0, dy0 = self._pontos[a]
                x1, y1, dx1, dy1 = self._pontos[b]
                px = x0 + (x1 - x0) * frac
                py = y0 + (y1 - y0) * frac
                dx = dx0 + (dx1 - dx0) * frac
                dy = dy0 + (dy1 - dy0) * frac
                forca = 1.0 - (i / 8.0)
                comprimento = 10.0 * forca
                p.setPen(_pen(tema.CRISTAL, 2.6 * forca + 0.4, 0.55 * forca))
                p.drawLine(
                    QPointF(px - dx * comprimento, py - dy * comprimento),
                    QPointF(px + dx * comprimento, py + dy * comprimento),
                )
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(180, 241, 255, int(150 * forca)))
                raio = 2.2 * forca + 0.6
                p.drawEllipse(QPointF(px, py), raio, raio)
        p.setBrush(Qt.BrushStyle.NoBrush)
