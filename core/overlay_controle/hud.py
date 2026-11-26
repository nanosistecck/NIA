# -*- coding: utf-8 -*-
"""Painéis do overlay: banner central, status/controles e ações reais."""
from __future__ import annotations

import math
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap,
)
from PyQt6.QtWidgets import QPushButton, QWidget

from core.overlay_controle import tema

_RAIZ = Path(__file__).resolve().parents[2]
_LOGO = _RAIZ / 'assets' / 'nucleo' / 'energia.png'
_logo_cache: dict[int, QPixmap] = {}


def _logo(tamanho: int) -> QPixmap | None:
    if tamanho in _logo_cache:
        return _logo_cache[tamanho]
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: PLC0415
        bruto = QPixmap(str(_LOGO))
        if bruto.isNull():
            return None
        app = QApplication.instance()
        tela = app.primaryScreen() if app is not None else None
        escala = max(1.0, float(tela.devicePixelRatio()) if tela is not None else 1.0)
        pix = bruto.scaled(
            int(tamanho * escala), int(tamanho * escala),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        pix.setDevicePixelRatio(escala)
        _logo_cache[tamanho] = pix
        return pix
    except Exception:
        return None


def _vidro(p: QPainter, rect: QRectF, raio: float, *, halo: float = 16.0,
           inicio: str = tema.VIDRO_INICIO, fim: str = tema.VIDRO_FIM,
           contorno: str = tema.CIANO, alpha: float = 0.88) -> None:
    """Fundo de vidro azul com halo, gradiente e contorno fino."""
    p.setBrush(Qt.BrushStyle.NoBrush)
    for largura, forca in ((halo, 0.05), (halo * 0.62, 0.10), (halo * 0.3, 0.18)):
        p.setPen(_caneta(contorno, largura, forca))
        p.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), raio, raio)
    grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    c1 = QColor(inicio)
    c1.setAlphaF(alpha)
    c2 = QColor(fim)
    c2.setAlphaF(alpha)
    grad.setColorAt(0.0, c1)
    grad.setColorAt(1.0, c2)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(rect, raio, raio)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(_caneta(contorno, 1.5, 0.9))
    p.drawRoundedRect(rect, raio, raio)
    p.setPen(_caneta(tema.CRISTAL, 0.8, 0.35))
    p.drawLine(QPointF(rect.left() + raio * 0.7, rect.top() + 1.2),
               QPointF(rect.right() - raio * 0.7, rect.top() + 1.2))


def _caneta(cor: str, largura: float, alpha: float) -> QPen:
    c = QColor(cor)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    caneta = QPen(c)
    caneta.setWidthF(max(0.1, float(largura)))
    caneta.setCapStyle(Qt.PenCapStyle.RoundCap)
    caneta.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return caneta


def _icone_monitor(p: QPainter, rect: QRectF, cor: str) -> None:
    p.setPen(_caneta(cor, 2.4, 0.95))
    p.setBrush(Qt.BrushStyle.NoBrush)
    corpo = QRectF(rect.left() + 2, rect.top() + 3, rect.width() - 4, rect.height() * 0.64)
    p.drawRoundedRect(corpo, 3, 3)
    base_y = corpo.bottom() + 3
    p.drawLine(QPointF(rect.center().x(), corpo.bottom()),
               QPointF(rect.center().x(), base_y + 3))
    p.drawLine(QPointF(rect.center().x() - 7, base_y + 4),
               QPointF(rect.center().x() + 7, base_y + 4))


def _icone_engrenagem(p: QPainter, rect: QRectF, cor: str) -> None:
    centro = rect.center()
    raio = min(rect.width(), rect.height()) * 0.32
    p.setPen(_caneta(cor, 2.2, 0.95))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(centro, raio, raio)
    p.drawEllipse(centro, raio * 0.36, raio * 0.36)
    for i in range(8):
        ang = math.radians(i * 45)
        p.drawLine(
            QPointF(centro.x() + math.cos(ang) * raio * 1.02,
                    centro.y() + math.sin(ang) * raio * 1.02),
            QPointF(centro.x() + math.cos(ang) * raio * 1.42,
                    centro.y() + math.sin(ang) * raio * 1.42),
        )


def _icone_teclado(p: QPainter, rect: QRectF, cor: str) -> None:
    p.setPen(_caneta(cor, 1.8, 0.95))
    p.setBrush(Qt.BrushStyle.NoBrush)
    corpo = rect.adjusted(2, 7, -2, -6)
    p.drawRoundedRect(corpo, 3, 3)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(cor))
    for linha in range(2):
        for col in range(4):
            x = corpo.left() + 5 + col * 5.2
            y = corpo.top() + 5 + linha * 5.2
            p.drawEllipse(QPointF(x, y), 1.1, 1.1)


def _icone_check(p: QPainter, centro: QPointF, cor: str) -> None:
    p.setPen(_caneta(cor, 2.4, 1.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPolyline([
        QPointF(centro.x() - 5, centro.y()),
        QPointF(centro.x() - 1, centro.y() + 4),
        QPointF(centro.x() + 6, centro.y() - 5),
    ])


def _icone_erro(p: QPainter, centro: QPointF, cor: str) -> None:
    p.setPen(_caneta(cor, 2.4, 1.0))
    p.drawLine(QPointF(centro.x() - 4, centro.y() - 4),
               QPointF(centro.x() + 4, centro.y() + 4))
    p.drawLine(QPointF(centro.x() + 4, centro.y() - 4),
               QPointF(centro.x() - 4, centro.y() + 4))


def _icone_curso(p: QPainter, centro: QPointF, cor: str, fase: float) -> None:
    p.setPen(_caneta(cor, 2.2, 0.95))
    p.setBrush(Qt.BrushStyle.NoBrush)
    rect = QRectF(centro.x() - 6, centro.y() - 6, 12, 12)
    p.drawArc(rect, int((fase * 360) % 360 * 16), int(250 * 16))


class JanelaBanner(QWidget):
    """Identidade central: núcleo, NIA, monitor e o texto obrigatório."""

    def __init__(self, metrica):
        super().__init__(None, self._flags())
        self._m = metrica
        self._margem = 24
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._aplicar_tamanho()

    @staticmethod
    def _flags():
        return (Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.Tool
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowTransparentForInput
                | Qt.WindowType.WindowDoesNotAcceptFocus)

    def _aplicar_tamanho(self) -> None:
        self.setFixedSize(self._m.banner_largura + self._margem * 2,
                          self._m.banner_altura + self._margem * 2)

    def atualizar_metrica(self, metrica) -> None:
        self._m = metrica
        self._aplicar_tamanho()
        self.update()

    def paintEvent(self, _evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        m = self._m
        rect = QRectF(self._margem, self._margem,
                      m.banner_largura, m.banner_altura)
        raio = min(42.0, rect.height() / 2.0)
        _vidro(p, rect, raio, halo=16.0, inicio=tema.BANNER_INICIO,
               fim=tema.BANNER_FIM, contorno=tema.CIANO, alpha=0.88)

        compacto = rect.width() < 700 or m.compacto
        margem = 20 if compacto else 24
        logo_lado = 44 if compacto else 64
        nia_tam = 28 if compacto else 44
        texto_tam = 18 if compacto else 30
        monitor_lado = 28 if compacto else 42
        espaco = 10 if compacto else 20

        x = rect.left() + margem
        centro_y = rect.center().y()
        logo = _logo(logo_lado)
        if logo is not None:
            modo = p.compositionMode()
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
            p.drawPixmap(QPointF(x, centro_y - logo_lado / 2), logo)
            p.setCompositionMode(modo)
        else:
            p.setPen(_caneta(tema.CIANO, 2.0, 0.9))
            p.setBrush(QColor(tema.AZUL))
            p.drawEllipse(QRectF(x, centro_y - logo_lado / 2, logo_lado, logo_lado))
        x += logo_lado + espaco

        fonte_nia = tema.fonte(nia_tam, QFont.Weight.DemiBold)
        p.setFont(fonte_nia)
        p.setPen(QColor(tema.TEXTO))
        largura_nia = QFontMetrics(fonte_nia).horizontalAdvance('NIA')
        p.drawText(QPointF(x, centro_y + nia_tam * 0.34), 'NIA')
        x += largura_nia + espaco

        p.setPen(_caneta(tema.CRISTAL, 1.0, 0.45))
        p.drawLine(QPointF(x, centro_y - 24), QPointF(x, centro_y + 24))
        x += espaco

        _icone_monitor(p, QRectF(x, centro_y - monitor_lado / 2,
                                 monitor_lado, monitor_lado), tema.CRISTAL)
        x += monitor_lado + espaco

        disponivel = rect.right() - margem - x
        texto = 'NIA Controlando o Computador'
        tam = texto_tam
        fonte_texto = tema.fonte(tam, QFont.Weight.Medium)
        while tam > 13 and QFontMetrics(fonte_texto).horizontalAdvance(texto) > disponivel:
            tam -= 1
            fonte_texto = tema.fonte(tam, QFont.Weight.Medium)
        p.setFont(fonte_texto)
        p.setPen(QColor(tema.TEXTO))
        if QFontMetrics(fonte_texto).horizontalAdvance(texto) <= disponivel:
            p.drawText(QPointF(x, centro_y + tam * 0.34), texto)
        else:
            # Retrato/compacto: duas linhas, sem cortar o texto.
            fonte_texto = tema.fonte(15, QFont.Weight.Medium)
            p.setFont(fonte_texto)
            p.drawText(QPointF(x, centro_y - 2), 'NIA Controlando')
            p.drawText(QPointF(x, centro_y + 16), 'o Computador')

        # Adornos ciano discretos nas pontas, se houver espaço.
        if rect.width() >= 760:
            self._adorno(p, rect.left() + 14, centro_y, False)
            self._adorno(p, rect.right() - 14, centro_y, True)
        p.end()

    @staticmethod
    def _adorno(p: QPainter, x: float, y: float, inverter: bool) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(3):
            cor = QColor(tema.CIANO)
            cor.setAlphaF(0.55 - i * 0.12)
            p.setBrush(cor)
            dx = (-1 if inverter else 1) * i * 7
            p.drawRoundedRect(QRectF(x + dx - 2, y - 11, 4, 22), 2, 2)


class BotaoIcone(QPushButton):
    """Botão compacto desenhado à mão; não rouba foco e mantém alvo de 24 px."""

    _BASE = 46.0

    def __init__(self, icone: str, dica: str, pai=None, lado: int = 32):
        super().__init__(pai)
        self._icone = icone
        self._hover = False
        self._lado = max(24, int(lado))
        self.setFixedSize(self._lado, self._lado)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(dica)
        self.setAccessibleName(dica)
        self.setStyleSheet('background: transparent; border: none;')

    def definir_icone(self, icone: str) -> None:
        if icone != self._icone:
            self._icone = icone
            self.update()

    def enterEvent(self, evento) -> None:
        self._hover = True
        self.update()
        super().enterEvent(evento)

    def leaveEvent(self, evento) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(evento)

    def paintEvent(self, _evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Desenha sempre na BASE de 46 px e escala: o ícone mantém a forma e
        # a área de clique acompanha o tamanho compacto.
        p.scale(self.width() / self._BASE, self.height() / self._BASE)
        rect = QRectF(1, 1, self._BASE - 2, self._BASE - 2)
        if self._hover:
            p.setPen(_caneta(tema.CIANO, 1.2, 0.65))
            p.setBrush(QColor(0, 140, 255, 45))
            p.drawEllipse(rect)
        centro = rect.center()
        p.setPen(_caneta(tema.TEXTO, 2.4, 0.95))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if self._icone == 'pausa':
            p.drawLine(QPointF(centro.x() - 4, centro.y() - 6),
                       QPointF(centro.x() - 4, centro.y() + 6))
            p.drawLine(QPointF(centro.x() + 4, centro.y() - 6),
                       QPointF(centro.x() + 4, centro.y() + 6))
        elif self._icone == 'play':
            caminho = QPainterPath()
            caminho.moveTo(centro.x() - 4, centro.y() - 7)
            caminho.lineTo(centro.x() + 7, centro.y())
            caminho.lineTo(centro.x() - 4, centro.y() + 7)
            caminho.closeSubpath()
            p.setBrush(QColor(tema.TEXTO))
            p.drawPath(caminho)
        else:
            p.setBrush(QColor(tema.TEXTO))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(centro.x() - 5, centro.y() - 5, 10, 10), 1.5, 1.5)
        p.end()


class JanelaControles(QWidget):
    """Status superior direito com pausa/retomada e encerramento."""

    pausar_clicado = pyqtSignal()
    parar_clicado = pyqtSignal()

    def __init__(self, metrica):
        super().__init__(None, self._flags())
        self._m = metrica
        self._margem = 10
        self._estado = 'ACTIVE'
        self._motivo = ''
        self._ponto = tema.VERDE
        self._lado = max(24, min(32, int(32 * metrica.escala)))
        self._espaco = 4
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_pausa = BotaoIcone('pausa', 'Pausar controle', self, self._lado)
        self.btn_parar = BotaoIcone('parar', 'Encerrar controle (ESC)', self, self._lado)
        self.btn_pausa.clicked.connect(self.pausar_clicado)
        self.btn_parar.clicked.connect(self.parar_clicado)
        self._aplicar_tamanho()
        self._posicionar_botoes()

    @staticmethod
    def _flags():
        return (Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.Tool
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowDoesNotAcceptFocus)

    def _aplicar_tamanho(self) -> None:
        self.setFixedSize(self._m.status_largura + self._margem * 2,
                          self._m.status_altura + self._margem * 2)

    def atualizar_metrica(self, metrica) -> None:
        self._m = metrica
        self._lado = max(24, min(32, int(32 * metrica.escala)))
        for botao in (self.btn_pausa, self.btn_parar):
            botao.setFixedSize(self._lado, self._lado)
        self._aplicar_tamanho()
        self._posicionar_botoes()

    def resizeEvent(self, evento) -> None:
        self._posicionar_botoes()
        super().resizeEvent(evento)

    def _posicionar_botoes(self) -> None:
        y = (self.height() - self._lado) // 2
        borda = self._margem + 2
        x_parar = self.width() - borda - self._lado
        self.btn_parar.move(x_parar, y)
        self.btn_pausa.move(x_parar - self._lado - self._espaco, y)

    def definir_estado(self, estado: str, motivo: str = '') -> None:
        self._estado = estado
        self._motivo = motivo
        if estado in ('PAUSED', 'PAUSING', 'WAITING'):
            self._ponto = tema.AMBAR
            self.btn_pausa.definir_icone('play')
            self.btn_pausa.setToolTip('Retomar controle')
            self.btn_pausa.setAccessibleName('Retomar controle')
        elif estado in ('FAILED', 'STOPPING'):
            self._ponto = tema.VERMELHO if estado == 'FAILED' else tema.AMBAR
            self.btn_pausa.definir_icone('play')
        else:
            self._ponto = tema.VERDE
            self.btn_pausa.definir_icone('pausa')
            self.btn_pausa.setToolTip('Pausar controle')
            self.btn_pausa.setAccessibleName('Pausar controle')
        self.update()

    def paintEvent(self, _evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        m = self._m
        rect = QRectF(self._margem, self._margem, m.status_largura, m.status_altura)
        raio = rect.height() / 2.0
        _vidro(p, rect, raio, halo=10.0, inicio='#0C2C50', fim='#061525',
               contorno=tema.CIANO, alpha=0.82)
        centro_y = rect.center().y()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._ponto))
        p.drawEllipse(QPointF(rect.left() + 16, centro_y), 6, 6)
        p.setBrush(QColor(0, 230, 118, 38))
        p.drawEllipse(QPointF(rect.left() + 16, centro_y), 10, 10)

        texto = {
            'ACTIVE': 'Controle Ativo',
            'PAUSING': 'Pausando…',
            'PAUSED': 'Controle Pausado',
            'WAITING': 'Aguardando',
            'STOPPING': 'Encerrando…',
            'FAILED': 'Falha no indicador',
        }.get(self._estado, 'Controle Ativo')
        tam = max(12, int(16 * min(1.0, m.escala + 0.05)))
        fonte = tema.fonte(tam, QFont.Weight.Medium)
        p.setFont(fonte)
        p.setPen(QColor(tema.TEXTO))
        texto_x = rect.left() + 30
        # O texto não pode passar por baixo dos botões compactos.
        livre = max(40, int(rect.right() - texto_x - 2 * self._lado
                            - self._espaco - 10))
        texto = QFontMetrics(fonte).elidedText(
            texto, Qt.TextElideMode.ElideRight, livre)
        p.drawText(QPointF(texto_x, centro_y + tam * 0.34), texto)
        p.end()


class JanelaAtividades(QWidget):
    """Canto inferior esquerdo: até três ações reais, sem texto digitado."""

    def __init__(self, metrica):
        super().__init__(None, self._flags())
        self._m = metrica
        self._margem = 12
        self._itens: list[dict] = []
        self._fase = 0.0
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._timer = None
        self._aplicar_tamanho()

    @staticmethod
    def _flags():
        return (Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.Tool
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowTransparentForInput
                | Qt.WindowType.WindowDoesNotAcceptFocus)

    def _aplicar_tamanho(self) -> None:
        self.setFixedSize(self._m.atividades_largura + self._margem * 2,
                          self._m.atividades_altura + self._margem * 2)

    def atualizar_metrica(self, metrica) -> None:
        self._m = metrica
        self._aplicar_tamanho()
        self.update()

    def definir_atividades(self, itens) -> None:
        self._itens = [dict(item) for item in (itens or [])][-3:]
        self.update()

    def definir_animacao(self, ligada: bool) -> None:
        if ligada:
            if self._timer is None:
                from PyQt6.QtCore import QTimer  # noqa: PLC0415
                self._timer = QTimer(self)
                self._timer.setInterval(83)
                self._timer.timeout.connect(self._animar)
            if not self._timer.isActive():
                self._timer.start()
        elif self._timer is not None:
            self._timer.stop()

    def _animar(self) -> None:
        self._fase = (self._fase + 0.04) % 1.0
        if any(item.get('status') == 'executando' for item in self._itens):
            self.update()

    def paintEvent(self, _evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        m = self._m
        rect = QRectF(self._margem, self._margem,
                      m.atividades_largura, m.atividades_altura)
        _vidro(p, rect, 22.0, halo=12.0, inicio='#0A2A4C', fim='#04101F',
               contorno=tema.CIANO, alpha=0.86)
        x = rect.left() + 20
        y = rect.top() + 22
        logo = _logo(24)
        if logo is not None:
            modo = p.compositionMode()
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
            p.drawPixmap(QPointF(x, y - 10), logo)
            p.setCompositionMode(modo)
        x += 32
        fonte_titulo = tema.fonte(max(15, int(22 * min(1.0, m.escala + 0.04))),
                                  QFont.Weight.DemiBold)
        p.setFont(fonte_titulo)
        p.setPen(QColor(tema.TEXTO))
        p.drawText(QPointF(x, y + 8), 'Ações da NIA')

        p.setPen(_caneta(tema.CRISTAL, 1.0, 0.22))
        p.drawLine(QPointF(rect.left() + 20, y + 26),
                   QPointF(rect.right() - 20, y + 26))

        if not self._itens:
            p.setFont(tema.fonte(max(12, int(16 * m.escala)), QFont.Weight.Normal))
            p.setPen(QColor(tema.TEXTO_SUAVE))
            p.drawText(QPointF(rect.left() + 20, y + 58),
                       'Aguardando a primeira ação')
            p.end()
            return

        linha_y = y + 52
        fonte_item = tema.fonte(max(12, int(17 * min(1.0, m.escala + 0.04))),
                                QFont.Weight.Normal)
        p.setFont(fonte_item)
        largura_texto = rect.width() - 40 - 34 - 30
        for item in self._itens:
            descricao = str(item.get('descricao') or '')
            status = str(item.get('status') or 'executando')
            if status == 'concluida':
                _icone_check(p, QPointF(rect.left() + 30, linha_y - 6), tema.CIANO)
            elif status == 'erro':
                _icone_erro(p, QPointF(rect.left() + 30, linha_y - 6), tema.VERMELHO)
            elif status == 'teclado':
                _icone_teclado(p, QRectF(rect.left() + 19, linha_y - 17, 22, 22),
                               tema.CRISTAL)
            else:
                _icone_curso(p, QPointF(rect.left() + 30, linha_y - 6),
                             tema.CIANO, self._fase)
            p.setPen(QColor(tema.TEXTO if status != 'erro' else '#FFB3BC'))
            texto = QFontMetrics(fonte_item).elidedText(
                descricao, Qt.TextElideMode.ElideRight, max(40, int(largura_texto)))
            p.drawText(QPointF(rect.left() + 52, linha_y), texto)
            linha_y += 32
        p.end()
