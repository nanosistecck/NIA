# -*- coding: utf-8 -*-
"""Dashboard experimental de Configurações da NIA (PyQt6, sem WebEngine).

Etapa 4: este é o painel padrão de Configurações da NIA. A engrenagem do dock,
F2, a reconfiguração e os atalhos de credencial abrem esta janela. A persistência
e a aplicação ao motor ficam em ``core/config_preferencias.py``; aqui só há
apresentação, navegação, busca e o encaminhamento de trabalho bloqueante.
"""
from __future__ import annotations

import json
import queue
import threading
import time
from datetime import date
from pathlib import Path

from PyQt6.QtCore import (QEasingCurve, QEvent, QPoint, QPointF,
                          QPropertyAnimation, QRect, QSize, Qt, QTimer,
                          pyqtSignal)
from PyQt6.QtGui import (QColor, QFont, QFontDatabase, QKeySequence,
                         QLinearGradient, QPainter, QPen, QRadialGradient,
                         QShortcut)
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup,
                             QCheckBox, QColorDialog, QComboBox, QFileDialog,
                             QFrame, QGridLayout, QHBoxLayout, QLabel,
                             QLineEdit, QListWidget, QListWidgetItem,
                             QMessageBox, QPushButton, QScrollArea, QSizePolicy,
                             QSlider, QSpinBox, QStackedWidget, QVBoxLayout,
                             QWidget)

from core import catalogo_habilidades as CH
from core.config_preferencias import (ConfigService, TEMAS, TEMA_PADRAO,
                                      normalizar_dispositivo)
from core.interface_canvas import icon
from core.personas import (PERSONAGENS, PERSONALIDADES, nome_da_ia,
                           nome_original)

# ── paleta semântica do dashboard ─────────────────────────────────────────
# O tema do dashboard é independente do sistema de cores do núcleo
# (config/cores.json). As folhas levam o marcador /*sem-tema*/ para não
# passarem pelo gancho de recoloração global do ui.py.
PALETAS = {
    "escuro": {
        "bg": "#0B1422",
        "bg2": "#07101B",
        "glow1": "rgba(24,120,150,72)",
        "glow2": "rgba(42,72,138,58)",
        "glass": "rgba(19,34,54,196)",
        "glass_strong": "rgba(13,25,42,242)",
        "field": "rgba(8,20,34,238)",
        "field_hover": "rgba(13,31,50,248)",
        "text": "#EAF4FC",
        "muted": "#A3BCCF",
        "dim": "#7892A8",
        "border": "rgba(139,200,224,50)",
        "border_strong": "rgba(99,218,240,150)",
        "accent": "#63DAF0",
        "accent_hover": "#8BEAF8",
        "accent_text": "#04222A",
        "accent_soft": "rgba(99,218,240,38)",
        "selection": "rgba(99,218,240,64)",
        "focus": "#9BF3FF",
        "success": "#5BE3A5",
        "warning": "#FFCE6B",
        "error": "#FF7A90",
        "nav_hover": "rgba(255,255,255,14)",
    },
    "claro": {
        "bg": "#EDF4FA",
        "bg2": "#DDEBF5",
        "glow1": "rgba(0,150,180,42)",
        "glow2": "rgba(74,124,200,34)",
        "glass": "rgba(255,255,255,180)",
        "glass_strong": "rgba(255,255,255,238)",
        "field": "rgba(255,255,255,244)",
        "field_hover": "#FFFFFF",
        "text": "#14263A",
        "muted": "#4F687D",
        "dim": "#70879A",
        "border": "rgba(20,70,100,38)",
        "border_strong": "rgba(0,107,131,140)",
        "accent": "#006B83",
        "accent_hover": "#0087A4",
        "accent_text": "#F2FBFD",
        "accent_soft": "rgba(0,107,131,30)",
        "selection": "rgba(0,107,131,46)",
        "focus": "#007E9A",
        "success": "#087A4E",
        "warning": "#8A5A00",
        "error": "#B4233C",
        "nav_hover": "rgba(0,60,90,12)",
    },
}

_FAMILIA_FONTE: str | None = None


def _qcolor(valor) -> QColor:
    """QColor não entende ``rgba(...)`` de folha de estilo; converte aqui."""
    texto = str(valor or "").strip()
    baixo = texto.lower()
    if baixo.startswith(("rgba(", "rgb(")):
        corpo = texto[texto.index("(") + 1:texto.rindex(")")]
        partes = [p.strip() for p in corpo.split(",")]
        try:
            r, g, b = (max(0, min(255, int(float(p)))) for p in partes[:3])
            a = 255
            if len(partes) > 3:
                bruto = partes[3]
                a = (max(0.0, min(1.0, float(bruto))) * 255
                     if "." in bruto or float(bruto) <= 1.0 else float(bruto))
                a = int(max(0, min(255, a)))
            return QColor(r, g, b, a)
        except (ValueError, TypeError):
            return QColor()
    cor = QColor(texto)
    if not cor.isValid() and texto.startswith("#") and len(texto) == 9:
        # #RRGGBBAA não é aceito por todas as versões; separa o alfa.
        cor = QColor(texto[:7])
        cor.setAlpha(int(texto[7:9], 16))
    return cor


def familia_da_fonte() -> str:
    """Inter quando existir; depois Segoe UI; por fim a fonte do sistema."""
    global _FAMILIA_FONTE
    if _FAMILIA_FONTE is None:
        try:
            familias = set(QFontDatabase.families())
        except Exception:
            familias = set()
        for candidata in ("Inter", "Segoe UI", "Noto Sans", "DejaVu Sans"):
            if candidata in familias:
                _FAMILIA_FONTE = candidata
                break
        else:
            _FAMILIA_FONTE = QApplication.font().family() or "Sans Serif"
    return _FAMILIA_FONTE


def _qss(paleta: dict) -> str:
    p = paleta
    familia = familia_da_fonte().replace('"', "'")
    return f"""/*sem-tema*/
* {{ font-family: "{familia}"; }}
QWidget#DashboardRoot {{ background: transparent; color: {p['text']}; }}
QWidget#PageContent {{ background: transparent; }}
QLabel {{ color: {p['text']}; background: transparent; }}
QLabel#Brand {{ font-size: 19px; font-weight: 600; }}
QLabel#BrandSub {{ color: {p['muted']}; font-size: 11px; }}
QLabel#Eyebrow {{ color: {p['dim']}; font-size: 10px; font-weight: 600; letter-spacing: 2px; }}
QLabel#PageTitle {{ font-size: 20px; font-weight: 600; }}
QLabel#PageSubtitle {{ color: {p['muted']}; font-size: 12px; }}
QLabel#CardTitle {{ font-size: 15px; font-weight: 600; }}
QLabel#CardSubtitle {{ color: {p['muted']}; font-size: 11px; }}
QLabel#FieldLabel {{ color: {p['muted']}; font-size: 11px; font-weight: 600; }}
QLabel#Hint {{ color: {p['dim']}; font-size: 11px; }}
QLabel#Pill {{ color: {p['accent']}; background: {p['accent_soft']};
    border: 1px solid {p['border']}; border-radius: 10px; padding: 4px 10px;
    font-size: 10px; font-weight: 600; }}
QLabel#Status {{ color: {p['dim']}; font-size: 11px; }}
QLabel#Status[estado="info"] {{ color: {p['muted']}; }}
QLabel#Status[estado="success"] {{ color: {p['success']}; }}
QLabel#Status[estado="warning"] {{ color: {p['warning']}; }}
QLabel#Status[estado="error"] {{ color: {p['error']}; }}
QFrame#Sidebar {{ background: {p['glass']}; border: 1px solid {p['border']};
    border-radius: 20px; }}
QFrame#GlassCard {{ background: {p['glass']}; border: 1px solid {p['border']};
    border-radius: 18px; }}
QFrame#Rule {{ background: {p['border']}; border: none; max-height: 1px; }}
QPushButton {{ color: {p['text']}; background: transparent; border: none; }}
QPushButton#Nav {{ background: transparent; border: 1px solid transparent;
    color: {p['muted']}; text-align: left; padding: 10px 14px;
    border-radius: 12px; font-weight: 500; min-height: 22px; }}
QPushButton#Nav:hover {{ color: {p['text']}; background: {p['nav_hover']}; }}
QPushButton#Nav:checked {{ color: {p['accent']}; font-weight: 600; }}
QPushButton#Nav:focus {{ border: 2px solid {p['focus']}; padding: 9px 13px; }}
QPushButton#Primary {{ background: {p['accent']}; color: {p['accent_text']};
    border: 1px solid {p['accent']}; border-radius: 10px;
    padding: 8px 15px; font-weight: 600; min-height: 20px; }}
QPushButton#Primary:hover {{ background: {p['accent_hover']};
    border-color: {p['accent_hover']}; }}
QPushButton#Primary:pressed {{ background: {p['accent']}; }}
QPushButton#Primary:focus {{ border: 2px solid {p['focus']}; padding: 7px 14px; }}
QPushButton#Secondary {{ background: transparent; color: {p['text']};
    border: 1px solid {p['border']}; border-radius: 10px;
    padding: 8px 14px; min-height: 20px; }}
QPushButton#Secondary:hover {{ border-color: {p['border_strong']};
    background: {p['accent_soft']}; }}
QPushButton#Secondary:pressed {{ background: {p['selection']}; }}
QPushButton#Secondary:focus {{ border: 2px solid {p['focus']}; padding: 7px 13px; }}
QPushButton#Segment {{ background: transparent; color: {p['muted']};
    border: 1px solid {p['border']}; border-radius: 9px;
    padding: 6px 12px; font-size: 11px; font-weight: 600; }}
QPushButton#Segment:hover {{ color: {p['text']}; background: {p['nav_hover']}; }}
QPushButton#Segment:checked {{ color: {p['accent']}; background: {p['accent_soft']};
    border-color: {p['border_strong']}; }}
QPushButton#Segment:focus {{ border: 2px solid {p['focus']}; padding: 5px 11px; }}
QPushButton#CardAction {{ background: transparent; color: {p['muted']};
    border: 1px solid {p['border']}; border-radius: 8px;
    padding: 5px 9px; font-size: 10px; }}
QPushButton#CardAction:hover {{ color: {p['text']}; border-color: {p['border_strong']};
    background: {p['accent_soft']}; }}
QPushButton#CardAction:focus {{ border: 2px solid {p['focus']}; padding: 4px 8px; }}
QPushButton#Toggle {{ background: {p['nav_hover']}; color: {p['muted']};
    border: 1px solid {p['border']}; border-radius: 10px; padding: 8px 14px;
    font-weight: 600; }}
QPushButton#Toggle[ligado="true"] {{ background: {p['accent_soft']};
    color: {p['accent']}; border-color: {p['border_strong']}; }}
QPushButton#Toggle:hover {{ border-color: {p['border_strong']}; }}
QPushButton#Toggle:focus {{ border: 2px solid {p['focus']}; }}
QFrame#PanelSection {{ background: {p['glass']}; border: 1px solid {p['border']};
    border-radius: 16px; }}
QFrame#ApiCard {{ background: {p['field']}; border: 1px solid {p['border']};
    border-radius: 12px; }}
QLabel#SectionTitle {{ font-size: 13px; font-weight: 600; }}
QLabel#SectionHint {{ color: {p['muted']}; font-size: 11px; }}
QLabel#EffectiveState, QLabel#PreferenceState {{ color: {p['muted']};
    background: {p['accent_soft']}; border: 1px solid {p['border']};
    border-radius: 10px; padding: 8px 10px; font-size: 11px; }}
QLabel#EffectiveState[estado="success"], QLabel#PreferenceState[estado="success"],
QLabel#PanelStatus[estado="success"] {{ color: {p['success']}; }}
QLabel#EffectiveState[estado="warning"], QLabel#PreferenceState[estado="warning"],
QLabel#PanelStatus[estado="warning"] {{ color: {p['warning']}; }}
QLabel#EffectiveState[estado="error"], QLabel#PreferenceState[estado="error"],
QLabel#PanelStatus[estado="error"] {{ color: {p['error']}; }}
QLabel#PanelStatus {{ color: {p['muted']}; font-size: 11px; }}
QLabel#ApiBadge {{ color: {p['muted']}; background: {p['nav_hover']};
    border: 1px solid {p['border']}; border-radius: 9px;
    padding: 3px 8px; font-size: 10px; font-weight: 600; }}
QLabel#ApiBadge[estado="validado"] {{ color: {p['success']};
    border-color: {p['success']}; }}
QLabel#ApiBadge[estado="invalido"], QLabel#ApiBadge[estado="esgotado"] {{ color: {p['error']};
    border-color: {p['error']}; }}
QLabel#ApiBadge[estado="limitado"], QLabel#ApiBadge[estado="inconclusivo"],
QLabel#ApiBadge[estado="pausada"] {{ color: {p['warning']};
    border-color: {p['warning']}; }}
QProgressBar#PanelProgress {{ background: {p['field']}; border: 1px solid {p['border']};
    border-radius: 5px; max-height: 8px; min-height: 8px; }}
QProgressBar#PanelProgress::chunk {{ background: {p['accent']}; border-radius: 4px; }}
QPushButton#ThemeCard {{ background: {p['glass']}; color: {p['text']};
    border: 1px solid {p['border']}; border-radius: 16px;
    padding: 10px; text-align: left; }}
QPushButton#ThemeCard:hover {{ border-color: {p['border_strong']};
    background: {p['field_hover']}; }}
QPushButton#ThemeCard:checked {{ border: 2px solid {p['accent']};
    background: {p['accent_soft']}; padding: 9px; }}
QPushButton#ThemeCard:focus {{ border: 2px solid {p['focus']}; padding: 9px; }}
QPushButton:disabled {{ color: {p['dim']}; }}
QComboBox, QLineEdit, QSpinBox {{ background: {p['field']}; color: {p['text']};
    border: 1px solid {p['border']}; border-radius: 10px;
    padding: 8px 10px; min-height: 20px;
    selection-background-color: {p['selection']}; selection-color: {p['text']}; }}
QSpinBox::up-button, QSpinBox::down-button {{ background: transparent;
    border: none; width: 16px; }}
QCheckBox {{ color: {p['text']}; background: transparent; spacing: 8px;
    min-height: 22px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid {p['border_strong']}; background: {p['field']}; }}
QCheckBox::indicator:checked {{ background: {p['accent']};
    border-color: {p['accent']}; }}
QCheckBox:focus {{ border: 1px solid {p['focus']}; border-radius: 6px; }}
QSlider::groove:horizontal {{ height: 6px; border-radius: 3px;
    background: {p['field']}; border: 1px solid {p['border']}; }}
QSlider::sub-page:horizontal {{ background: {p['accent']}; border-radius: 3px; }}
QSlider::handle:horizontal {{ width: 16px; height: 16px; margin: -6px 0;
    border-radius: 8px; background: {p['accent']};
    border: 2px solid {p['glass_strong']}; }}
QSlider:focus {{ border: 1px solid {p['focus']}; border-radius: 6px; }}
QListWidget {{ background: {p['field']}; color: {p['text']};
    border: 1px solid {p['border']}; border-radius: 10px; padding: 4px; }}
QListWidget::item {{ padding: 6px; border-radius: 6px; min-height: 22px; }}
QListWidget::item:selected {{ background: {p['selection']}; }}
QListWidget::item:hover {{ background: {p['accent_soft']}; }}
QFrame#Preview {{ background: {p['field']}; border: 1px solid {p['border']};
    border-radius: 14px; }}
QComboBox:hover, QLineEdit:hover {{ background: {p['field_hover']};
    border-color: {p['border_strong']}; }}
QComboBox:focus, QLineEdit:focus {{ border: 2px solid {p['focus']};
    padding: 7px 9px; }}
QComboBox:disabled, QLineEdit:disabled {{ color: {p['dim']}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox QAbstractItemView {{ background: {p['glass_strong']};
    color: {p['text']}; border: 1px solid {p['border_strong']};
    border-radius: 10px; padding: 4px; outline: 0;
    selection-background-color: {p['selection']}; selection-color: {p['text']}; }}
QComboBox QAbstractItemView::item {{ min-height: 26px; padding: 4px 8px;
    border-radius: 6px; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent;
    border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: {p['border_strong']};
    min-height: 28px; border-radius: 4px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent; }}
QToolTip {{ background: {p['glass_strong']}; color: {p['text']};
    border: 1px solid {p['border_strong']}; padding: 6px; }}
"""


class _Backdrop(QWidget):
    """Gradiente estático; nenhum desfoque em tempo real."""

    def __init__(self, paleta: dict, parent=None):
        super().__init__(parent)
        self.paleta = paleta
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_paleta(self, paleta: dict) -> None:
        self.paleta = paleta
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = max(1, self.width()), max(1, self.height())
        fundo = QLinearGradient(0, 0, w, h)
        fundo.setColorAt(0.0, _qcolor(self.paleta["bg"]))
        fundo.setColorAt(1.0, _qcolor(self.paleta["bg2"]))
        p.fillRect(self.rect(), fundo)
        for x, y, raio, cor in ((0.12, 0.10, 0.52, self.paleta["glow1"]),
                                (0.92, 0.88, 0.58, self.paleta["glow2"])):
            brilho = QRadialGradient(QPointF(w * x, h * y), max(w, h) * raio)
            centro = _qcolor(cor)
            brilho.setColorAt(0.0, centro)
            borda = _qcolor(cor)
            borda.setAlpha(0)
            brilho.setColorAt(1.0, borda)
            p.fillRect(self.rect(), brilho)
        p.end()


class _TaskBridge(QWidget):
    """Recebe resultados de threads de trabalho na thread Qt (AutoConnection)."""

    terminou = pyqtSignal(int, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hide()


class TaskRunner:
    """Fila de uma thread daemon para áudio, voz e chamadas do motor.

    A fila preserva a ordem das escolhas. Resultados atrasados são ignorados
    pelos tokens da janela, então trocar de dispositivo durante um teste não
    deixa a resposta velha sobrescrever a nova seleção.
    """

    def __init__(self, parent: QWidget | None = None):
        self.bridge = _TaskBridge(parent)
        self._fila: queue.Queue = queue.Queue()
        self._token = 0
        self._ativo = threading.Event()
        self._ativo.set()
        self._thread = threading.Thread(target=self._laco, daemon=True,
                                        name="nia-config-dashboard")
        self._thread.start()

    def executar(self, funcao) -> int:
        self._token += 1
        token = self._token
        if self._ativo.is_set():
            self._fila.put((token, funcao))
        return token

    def _laco(self) -> None:
        while True:
            item = self._fila.get()
            if item is None:
                return
            token, funcao = item
            if not self._ativo.is_set():
                continue
            try:
                resultado = funcao()
            except Exception as exc:
                resultado = {"__excecao__": f"{type(exc).__name__}: {str(exc)[:180]}"}
            if not self._ativo.is_set():
                continue
            try:
                self.bridge.terminou.emit(token, resultado)
            except RuntimeError:
                return

    def encerrar(self) -> None:
        self._ativo.clear()
        try:
            self._fila.put(None)
        except Exception:
            pass


class StatusLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Status")
        self.setProperty("estado", "info")
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.hide()

    def mostrar(self, texto: str, estado: str = "info") -> None:
        self.setProperty("estado", estado)
        self.style().unpolish(self)
        self.style().polish(self)
        self.setText(texto)
        self.show()

    def limpar(self) -> None:
        self.setText("")
        self.hide()


class NavButton(QPushButton):
    def __init__(self, texto: str, icone: str, mover, parent=None):
        super().__init__(texto, parent)
        self.setObjectName("Nav")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QSize(20, 20))
        self.setIcon(icon(icone))
        self.setAccessibleName(texto)
        self.setMinimumHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._mover = mover

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self._mover(-1 if event.key() == Qt.Key.Key_Up else 1)
            event.accept()
            return
        super().keyPressEvent(event)


class _NavIndicator(QWidget):
    def __init__(self, paleta: dict, parent=None):
        super().__init__(parent)
        self.paleta = paleta
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_paleta(self, paleta: dict) -> None:
        self.paleta = paleta
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.rect().adjusted(1, 1, -1, -1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_qcolor(self.paleta["accent_soft"]))
        p.drawRoundedRect(r, 12, 12)
        p.setBrush(_qcolor(self.paleta["accent"]))
        p.drawRoundedRect(QRect(r.left(), r.top() + 9, 3, max(1, r.height() - 18)),
                          2, 2)
        p.end()


class ThemePreview(QWidget):
    """Miniatura estática do dashboard, específica do tema que ela representa."""

    def __init__(self, tema: str, parent=None):
        super().__init__(parent)
        self.paleta = PALETAS[tema]
        self.setFixedHeight(86)
        self.setMinimumWidth(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(_qcolor(self.paleta["border"]), 1))
        p.setBrush(_qcolor(self.paleta["bg"]))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 10, 10)
        # barra lateral
        lateral = QRect(6, 6, max(34, int(self.width() * 0.28)), self.height() - 12)
        p.setBrush(_qcolor(self.paleta["glass_strong"]))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(lateral, 7, 7)
        p.setBrush(_qcolor(self.paleta["accent"]))
        p.drawRoundedRect(QRect(lateral.left() + 5, lateral.top() + 8,
                                max(10, lateral.width() - 18), 4), 2, 2)
        for i in range(2):
            p.setBrush(_qcolor(self.paleta["muted"]))
            p.drawRoundedRect(QRect(lateral.left() + 5, lateral.top() + 20 + i * 10,
                                    max(8, lateral.width() - 16), 3), 1.5, 1.5)
        # conteúdo
        x = lateral.right() + 8
        largura = max(20, self.width() - x - 12)
        p.setBrush(_qcolor(self.paleta["glass"]))
        p.setPen(QPen(_qcolor(self.paleta["border"]), 1))
        p.drawRoundedRect(QRect(x, 10, largura, 22), 5, 5)
        p.setBrush(_qcolor(self.paleta["field"]))
        p.setPen(QPen(_qcolor(self.paleta["border"]), 1))
        p.drawRoundedRect(QRect(x, 38, largura, 20), 5, 5)
        p.setBrush(_qcolor(self.paleta["accent"]))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRect(x, 64, min(48, largura), 8), 4, 4)
        p.end()


class ThemeCard(QPushButton):
    def __init__(self, tema: str, titulo: str, descricao: str, parent=None):
        super().__init__(parent)
        self.tema = tema
        self.setObjectName("ThemeCard")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(f"Tema {titulo}")
        self.setAccessibleDescription(descricao)
        self.setMinimumHeight(148)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)
        layout.addWidget(ThemePreview(tema, self))
        titulo_lbl = QLabel(titulo, self)
        titulo_lbl.setObjectName("CardTitle")
        layout.addWidget(titulo_lbl)
        desc_lbl = QLabel(descricao, self)
        desc_lbl.setObjectName("Hint")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)
        self._vizinho = None

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right) and self._vizinho:
            self._vizinho(event.key() == Qt.Key.Key_Right)
            event.accept()
            return
        super().keyPressEvent(event)


class _NucleoPreview(QWidget):
    """Prévia vetorial leve: simula fases sem tocar áudio, voz ou modelo."""

    FASES = ("repouso", "ouvindo", "pensando", "falando")

    def __init__(self, paleta: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("Preview")
        self.setMinimumSize(190, 190)
        self.paleta = paleta
        self.fase = "repouso"
        self.nome = "Núcleo"
        self._angulo = 0.0

    def avancar(self, dt: float) -> None:
        velocidade = {"repouso": 18.0, "ouvindo": 70.0,
                      "pensando": 120.0, "falando": 95.0}.get(self.fase, 18.0)
        self._angulo = (self._angulo + velocidade * dt) % 360.0
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        cor = {
            "repouso": self.paleta["muted"],
            "ouvindo": self.paleta["accent"],
            "pensando": self.paleta["warning"],
            "falando": self.paleta["success"],
        }.get(self.fase, self.paleta["accent"])
        w, h = self.width(), self.height()
        raio = min(w, h) * 0.34
        cx, cy = w / 2.0, h / 2.0 - 8
        p.setPen(QPen(_qcolor(cor), 2))
        p.drawEllipse(QRect(int(cx - raio), int(cy - raio),
                            int(raio * 2), int(raio * 2)))
        p.setPen(QPen(_qcolor(cor), 1))
        p.drawArc(QRect(int(cx - raio * 0.72), int(cy - raio * 0.72),
                        int(raio * 1.44), int(raio * 1.44)),
                  int(self._angulo * 16), 250 * 16)
        p.drawArc(QRect(int(cx - raio * 0.44), int(cy - raio * 0.44),
                        int(raio * 0.88), int(raio * 0.88)),
                  int(-self._angulo * 22) % (360 * 16), 190 * 16)
        pulso = 4.0 if self.fase in ("ouvindo", "falando") else 2.0
        p.setBrush(_qcolor(cor))
        p.drawEllipse(QRect(int(cx - pulso), int(cy - pulso),
                            int(pulso * 2), int(pulso * 2)))
        p.setPen(QPen(_qcolor(self.paleta["text"])))
        p.setFont(QFont(familia_da_fonte(), 10))
        p.drawText(QRect(0, h - 30, w, 22),
                   Qt.AlignmentFlag.AlignCenter,
                   f"{self.nome} · {self.fase.title()}")
        p.end()


class GlassCard(QFrame):
    def __init__(self, titulo: str, subtitulo: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("GlassCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 18, 20, 20)
        v.setSpacing(10)
        titulo_lbl = QLabel(titulo, self)
        titulo_lbl.setObjectName("CardTitle")
        v.addWidget(titulo_lbl)
        if subtitulo:
            sub = QLabel(subtitulo, self)
            sub.setObjectName("CardSubtitle")
            sub.setWordWrap(True)
            v.addWidget(sub)
        self.body = QVBoxLayout()
        self.body.setSpacing(14)
        v.addLayout(self.body)


def _regra(parent: QWidget | None = None) -> QFrame:
    linha = QFrame(parent)
    linha.setObjectName("Rule")
    linha.setFixedHeight(1)
    linha.setFrameShape(QFrame.Shape.NoFrame)
    return linha


def _campo(rotulo: str, controle: QWidget, status: StatusLabel,
           dica: str = "", parent: QWidget | None = None) -> QVBoxLayout:
    caixa = QVBoxLayout()
    caixa.setSpacing(6)
    lab = QLabel(rotulo, parent)
    lab.setObjectName("FieldLabel")
    lab.setWordWrap(True)
    try:
        lab.setBuddy(controle)
    except (AttributeError, TypeError):
        pass
    caixa.addWidget(lab)
    if dica:
        hint = QLabel(dica, parent)
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        caixa.addWidget(hint)
    caixa.addWidget(controle)
    caixa.addWidget(status)
    return caixa


def _rotulo_secao(texto: str, parent=None) -> QLabel:
    lab = QLabel(texto, parent)
    lab.setObjectName("SectionTitle")
    return lab


def _botoes(*botoes: tuple[str, str]) -> QHBoxLayout:
    linha = QHBoxLayout()
    linha.setSpacing(8)
    for texto, papel in botoes:
        b = QPushButton(texto)
        b.setObjectName(papel)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setAccessibleName(texto)
        b.setMinimumHeight(36)
        linha.addWidget(b)
    linha.addStretch()
    return linha


class ConfigDashboardWindow(QWidget):
    """Janela independente e reutilizável enquanto estiver aberta."""

    fechada = pyqtSignal()
    credencial_pronta = pyqtSignal()

    def __init__(self, service: ConfigService | None = None, parent=None,
                 refresh_on_open: bool = True):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setObjectName("DashboardRoot")
        self.setWindowTitle("NIA · Configurações")
        self.setMinimumSize(700, 460)
        largura, altura = 1120, 720
        tela = QApplication.primaryScreen()
        if tela is not None:
            area = tela.availableGeometry()
            largura = min(largura, max(700, area.width() - 60))
            altura = min(altura, max(460, area.height() - 80))
        self.resize(largura, altura)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFont(QFont(familia_da_fonte(), 10))

        self._service = service or ConfigService()
        self._tema_atual = self._service.carregar_tema()
        if self._tema_atual not in TEMAS:
            self._tema_atual = TEMA_PADRAO
        self._paleta = PALETAS[self._tema_atual]
        self._microfones: list[dict] = []
        self._saidas: list[dict] = []
        self._pendentes: dict[int, object] = {}
        self._fechado = False
        self._primeira_exibicao = True
        self._pagina = 0
        self._modo_compacto = None
        self._modo_cabecalho = None
        self._temas_empilhados = None
        self._mic_teste_seq = 0
        self._saida_teste_seq = 0
        self._alias_pendente = None
        self._tema_restauracao = None
        self._placeholders: dict[str, tuple] = {}
        self._paginas_lazy: dict[str, QWidget] = {}
        self._indice = None
        self._indice_ativo = False
        self._indice_cancelar = None
        self._indice_busca_seq = 0

        self._runner = TaskRunner(self)
        self._runner.bridge.terminou.connect(self._receber_resultado)

        self._construir()
        self._aplicar_valores()
        self._sincronizar_tema()
        self._aplicar_estilo()

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        atalho_busca = QShortcut(QKeySequence("Ctrl+F"), self)
        atalho_busca.activated.connect(self._focar_busca)
        if refresh_on_open:
            QTimer.singleShot(0, self.atualizar_dispositivos)

    # ── construção ─────────────────────────────────────────────────────────
    def _construir(self) -> None:
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(16, 16, 16, 16)
        raiz.setSpacing(0)

        self._backdrop = _Backdrop(self._paleta, self)
        self._backdrop.lower()

        casca = QHBoxLayout()
        casca.setContentsMargins(0, 0, 0, 0)
        casca.setSpacing(16)
        raiz.addLayout(casca)

        self._sidebar = self._construir_sidebar()
        casca.addWidget(self._sidebar)

        direita = QVBoxLayout()
        direita.setContentsMargins(0, 0, 0, 0)
        direita.setSpacing(12)
        casca.addLayout(direita, 1)
        direita.addWidget(self._construir_cabecalho())

        self._stack = QStackedWidget()
        self._stack.setObjectName("PageStack")
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding,
                                  QSizePolicy.Policy.Expanding)
        direita.addWidget(self._stack, 1)

        self._pagina_voz = self._construir_pagina_voz()
        self._pagina_aparencia = self._construir_pagina_aparencia()
        self._painel_provedores = None
        self._pagina_provedores = self._criar_placeholder_provedores()
        self._pagina_geral = self._criar_placeholder(
            "geral", "Geral",
            "Saudação ao abrir e inicialização com o sistema.",
            "Abra esta página para consultar o estado real da inicialização.")
        self._pagina_perfil = self._criar_placeholder(
            "perfil", "Meu perfil",
            "Os dados que a NIA usa para te conhecer nas próximas conversas.",
            "Abra esta página para carregar seus dados.")
        self._pagina_integracoes = self._criar_placeholder(
            "integracoes", "Integrações",
            "WhatsApp, Secretária e acesso pelo celular.",
            "Abra esta página para consultar conexões e atalhos.")
        self._pagina_documentos = self._criar_placeholder(
            "documentos", "Documentos",
            "Índice textual local de arquivos .txt, com fontes verificáveis.",
            "Abra esta página para configurar pastas e testar a busca local.")
        self._pagina_habilidades = self._criar_placeholder(
            "habilidades", "Habilidades",
            "O que a NIA faz nativamente, com exemplos e ações reais.",
            "Abra esta página para ver as habilidades disponíveis.")
        self._stack.addWidget(self._pagina_voz)
        self._stack.addWidget(self._pagina_aparencia)
        self._stack.addWidget(self._pagina_provedores)
        self._stack.addWidget(self._pagina_geral)
        self._stack.addWidget(self._pagina_perfil)
        self._stack.addWidget(self._pagina_integracoes)
        self._stack.addWidget(self._pagina_documentos)
        self._stack.addWidget(self._pagina_habilidades)
        self._scrolls = [self._pagina_voz, self._pagina_aparencia,
                         self._pagina_provedores, self._pagina_geral,
                         self._pagina_perfil, self._pagina_integracoes,
                         self._pagina_documentos, self._pagina_habilidades]
        self._stack.setCurrentIndex(0)
        self._ir_para_pagina(0, animar=False, focar=False)
        self._atualizar_cabecalho()

    def _construir_sidebar(self) -> QFrame:
        barra = QFrame(self)
        barra.setObjectName("Sidebar")
        barra.setFixedWidth(236)
        v = QVBoxLayout(barra)
        v.setContentsMargins(14, 18, 14, 16)
        v.setSpacing(8)

        marca = QHBoxLayout()
        marca.setSpacing(9)
        self._marca_icone = QLabel(barra)
        self._marca_icone.setFixedSize(30, 30)
        marca.addWidget(self._marca_icone)
        textos = QVBoxLayout()
        textos.setSpacing(0)
        titulo = QLabel("NIA", barra)
        titulo.setObjectName("Brand")
        subtitulo = QLabel("Configurações", barra)
        subtitulo.setObjectName("BrandSub")
        textos.addWidget(titulo)
        textos.addWidget(subtitulo)
        marca.addLayout(textos, 1)
        v.addLayout(marca)
        v.addSpacing(12)

        seccao = QLabel("AJUSTES", barra)
        seccao.setObjectName("Eyebrow")
        v.addWidget(seccao)
        v.addSpacing(4)

        self._nav_host = QWidget(barra)
        nav = QVBoxLayout(self._nav_host)
        nav.setContentsMargins(0, 0, 0, 0)
        nav.setSpacing(4)
        self._indicador = _NavIndicator(self._paleta, self._nav_host)
        self._indicador.lower()
        self._indicador.hide()
        self._anim_indicador = QPropertyAnimation(self._indicador, b"geometry", self)
        self._anim_indicador.setDuration(155)
        self._anim_indicador.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._grupo_nav = QButtonGroup(self)
        self._grupo_nav.setExclusive(True)
        self._nav_buttons: list[NavButton] = []
        for indice, (texto, icone) in enumerate((
                ("Voz e áudio", "mic"),
                ("Aparência", "palette"),
                ("Provedores e modelos", "system"),
                ("Geral", "config"),
                ("Meu perfil", "so_nome"),
                ("Integrações", "remote"),
                ("Documentos", "attach"),
                ("Habilidades", "system"))):
            botao = NavButton(texto, icone, self._mover_nav, self._nav_host)
            botao._icone_nome = icone
            botao.clicked.connect(lambda _=False, i=indice: self._ir_para_pagina(i))
            self._grupo_nav.addButton(botao, indice)
            self._nav_buttons.append(botao)
            nav.addWidget(botao)
        v.addWidget(self._nav_host)
        v.addStretch(1)
        rodape = QLabel("Configurações padrão\nOito páginas, uma única janela.", barra)
        rodape.setObjectName("Hint")
        rodape.setWordWrap(True)
        v.addWidget(rodape)
        return barra

    def _construir_cabecalho(self) -> QWidget:
        caixa = QWidget(self)
        h = QHBoxLayout(caixa)
        h.setContentsMargins(4, 2, 4, 2)
        h.setSpacing(6)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        titulo = QLabel("Configurações", caixa)
        titulo.setObjectName("PageTitle")
        subtitulo = QLabel("Ajuste a NIA inteira em um só lugar.", caixa)
        subtitulo.setObjectName("PageSubtitle")
        subtitulo.setWordWrap(True)
        self._cabecalho_subtitulo = subtitulo
        textos.addWidget(titulo)
        textos.addWidget(subtitulo)
        h.addLayout(textos, 1)

        self.busca_edit = QLineEdit(caixa)
        self.busca_edit.setObjectName("Search")
        self.busca_edit.setPlaceholderText("Buscar configuração…  (Ctrl+F)")
        self.busca_edit.setAccessibleName("Buscar configurações")
        self.busca_edit.setClearButtonEnabled(True)
        self.busca_edit.setFixedWidth(240)
        self.busca_edit.returnPressed.connect(self._buscar_config)
        h.addWidget(self.busca_edit)
        self.busca_status = StatusLabel(caixa)
        self.busca_status.setVisible(False)
        textos.addWidget(self.busca_status)

        pilula = QLabel("CONFIGURAÇÕES", caixa)
        pilula.setObjectName("Pill")
        pilula.setAccessibleName("Painel padrão de configurações")
        self._pilula = pilula
        h.addWidget(pilula)
        fechar = QPushButton("Fechar", caixa)
        fechar.setObjectName("Secondary")
        fechar.setCursor(Qt.CursorShape.PointingHandCursor)
        fechar.setAccessibleName("Fechar configurações")
        fechar.setMinimumHeight(34)
        fechar.clicked.connect(self.close)
        h.addWidget(fechar)
        return caixa

    def _pagina_base(self, titulo: str, subtitulo: str) -> tuple[QScrollArea, QVBoxLayout]:
        rolagem = QScrollArea(self)
        rolagem.setFrameShape(QFrame.Shape.NoFrame)
        rolagem.setWidgetResizable(True)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        rolagem.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        conteudo = QWidget()
        conteudo.setObjectName("PageContent")
        v = QVBoxLayout(conteudo)
        v.setContentsMargins(4, 4, 10, 28)
        v.setSpacing(14)
        cab = QLabel(titulo, conteudo)
        cab.setObjectName("PageTitle")
        v.addWidget(cab)
        sub = QLabel(subtitulo, conteudo)
        sub.setObjectName("PageSubtitle")
        sub.setWordWrap(True)
        v.addWidget(sub)
        rolagem.setWidget(conteudo)
        return rolagem, v

    def _criar_placeholder(self, chave: str, titulo: str, subtitulo: str,
                           aviso: str) -> QScrollArea:
        """Casca leve: o conteúdo só nasce na primeira visita da página."""
        rolagem, layout = self._pagina_base(titulo, subtitulo)
        # Painéis largos não podem impor o próprio sizeHint ao QScrollArea,
        # senão aparece rolagem horizontal em janelas estreitas.
        conteudo = rolagem.widget()
        politica = conteudo.sizePolicy()
        politica.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        conteudo.setSizePolicy(politica)
        aviso_lbl = QLabel(aviso, rolagem)
        aviso_lbl.setObjectName("Hint")
        layout.addWidget(aviso_lbl)
        layout.addStretch(1)
        self._placeholders[chave] = (rolagem, layout, aviso_lbl)
        return rolagem

    def _criar_placeholder_provedores(self) -> QScrollArea:
        pagina = self._criar_placeholder(
            "provedores", "Provedores e modelos",
            "Cadastre APIs externas e escolha o modelo local do Ollama. "
            "Os dados continuam no banco local e na configuração já existentes.",
            "Abra esta página para carregar as APIs e o Ollama.")
        rolagem, layout, aviso = self._placeholders["provedores"]
        self._provedores_layout = layout
        self._provedores_placeholder = aviso
        return pagina

    def _garantir_conteudo(self, chave: str, construtor) -> QWidget:
        """Monta uma página sob demanda e substitui o aviso pelo conteúdo real."""
        if chave in self._paginas_lazy:
            return self._paginas_lazy[chave]
        if chave not in self._placeholders:
            raise KeyError(chave)
        rolagem, layout, aviso = self._placeholders.pop(chave)
        conteudo = construtor(rolagem)
        indice = layout.indexOf(aviso)
        layout.insertWidget(max(0, indice), conteudo)
        aviso.deleteLater()
        self._paginas_lazy[chave] = conteudo
        return conteudo

    def _garantir_pagina_provedores(self) -> None:
        if self._painel_provedores is not None:
            return
        self._provedores_layout = self._placeholders["provedores"][1]
        self._provedores_placeholder = self._placeholders["provedores"][2]
        from core.config_apis_ui import ConfigAPIsPanel
        self._painel_provedores = self._garantir_conteudo(
            "provedores", lambda pai: ConfigAPIsPanel(pai))
        self._painel_provedores.credencial_pronta.connect(
            self.credencial_pronta.emit)
        self._provedores_placeholder = None

    # ── Geral ────────────────────────────────────────────────────────────────
    def _construir_pagina_geral(self, pai) -> QWidget:
        pagina = QWidget(pai)
        raiz = QVBoxLayout(pagina)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(14)

        cartao = GlassCard("Iniciar com o sistema",
                           "Consultamos o estado real do sistema operacional; "
                           "a consulta roda fora da thread da interface.", pagina)
        self.inicio_botao = QPushButton(cartao)
        self.inicio_botao.setObjectName("Toggle")
        self.inicio_botao.setCursor(Qt.CursorShape.PointingHandCursor)
        self.inicio_botao.setMinimumHeight(38)
        self.inicio_botao.setAccessibleName("Iniciar com o sistema")
        self.inicio_botao.clicked.connect(self._inicio_mudou)
        self.inicio_status = StatusLabel(cartao)
        cartao.body.addWidget(self.inicio_botao)
        cartao.body.addWidget(self.inicio_status)
        raiz.addWidget(cartao)

        cartao2 = GlassCard("Saudação ao abrir",
                            "A NIA cumprimenta você quando o programa abre.", pagina)
        self.saudacao_botao = QPushButton(cartao2)
        self.saudacao_botao.setObjectName("Toggle")
        self.saudacao_botao.setCursor(Qt.CursorShape.PointingHandCursor)
        self.saudacao_botao.setMinimumHeight(38)
        self.saudacao_botao.setAccessibleName("Saudação ao abrir")
        self.saudacao_botao.clicked.connect(self._saudacao_mudou)
        self.saudacao_status = StatusLabel(cartao2)
        cartao2.body.addWidget(self.saudacao_botao)
        cartao2.body.addWidget(self.saudacao_status)
        raiz.addWidget(cartao2)
        raiz.addWidget(self._construir_cartao_rotinas(pagina))
        raiz.addStretch(1)

        self._inicio_seq = 0
        self._inicio_disponivel = False
        self._pintar_saudacao()
        self._consultar_inicio()
        return pagina

    # ── Rotinas locais (Skill 04) ──────────────────────────────────────────
    def _construir_cartao_rotinas(self, pai) -> GlassCard:
        from core import rotinas as R
        cartao = GlassCard(
            "Rotinas",
            "Lembretes locais com recorrência. A NIA precisa estar aberta para "
            "agendar novas execuções; em segundo plano as notificações locais "
            "continuam. Atrasos enquanto esteve fechada geram um único registro.", pai)
        self._rotinas = R.ArmazemRotinas()
        self._rotina_seq = 0
        self._rotina_editando = None
        self.rotinas_lista = QListWidget(cartao)
        self.rotinas_lista.setAccessibleName('Rotinas cadastradas')
        self.rotinas_lista.currentRowChanged.connect(self._rotina_selecionou)
        cartao.body.addWidget(self.rotinas_lista)

        grade = QGridLayout()
        grade.setHorizontalSpacing(10)
        grade.setVerticalSpacing(8)
        self.rotina_titulo = QLineEdit(cartao)
        self.rotina_titulo.setPlaceholderText('Título da rotina')
        self.rotina_titulo.setAccessibleName('Título da rotina')
        self.rotina_mensagem = QLineEdit(cartao)
        self.rotina_mensagem.setPlaceholderText('Mensagem do lembrete')
        self.rotina_mensagem.setAccessibleName('Mensagem do lembrete')
        self.rotina_repeticao = QComboBox(cartao)
        self.rotina_repeticao.addItem('Uma vez', 'unica')
        self.rotina_repeticao.addItem('Diária', 'diaria')
        self.rotina_repeticao.addItem('Dias úteis', 'dias_uteis')
        self.rotina_repeticao.setAccessibleName('Repetição da rotina')
        self.rotina_acao = QComboBox(cartao)
        self.rotina_acao.addItem('Lembrete', 'lembrete')
        self.rotina_acao.addItem('Resumo do dia', 'resumo')
        self.rotina_acao.setAccessibleName('Ação da rotina')
        self.rotina_data = QLineEdit(date.today().isoformat(), cartao)
        self.rotina_data.setPlaceholderText('AAAA-MM-DD')
        self.rotina_data.setAccessibleName('Data da rotina única')
        self.rotina_hora = QLineEdit('09:00', cartao)
        self.rotina_hora.setPlaceholderText('HH:MM')
        self.rotina_hora.setAccessibleName('Hora da rotina')
        self.rotina_fuso = QLineEdit(R.fuso_padrao(), cartao)
        self.rotina_fuso.setAccessibleName('Fuso da rotina')
        for linha, (rotulo, campo) in enumerate((
                ('Título', self.rotina_titulo),
                ('Mensagem', self.rotina_mensagem),
                ('Repetição', self.rotina_repeticao),
                ('Ação', self.rotina_acao),
                ('Data', self.rotina_data),
                ('Hora', self.rotina_hora),
                ('Fuso', self.rotina_fuso))):
            grade.addWidget(_rotulo_secao(rotulo, cartao), linha, 0)
            grade.addWidget(campo, linha, 1)
        cartao.body.addLayout(grade)

        botoes = QHBoxLayout()
        botoes.setSpacing(8)
        self.rotina_salvar = QPushButton('Salvar rotina', cartao)
        self.rotina_salvar.setObjectName('Primary')
        self.rotina_salvar.clicked.connect(self._salvar_rotina)
        self.rotina_nova = QPushButton('Nova', cartao)
        self.rotina_nova.setObjectName('Secondary')
        self.rotina_nova.clicked.connect(self._nova_rotina)
        self.rotina_pausar = QPushButton('Pausar', cartao)
        self.rotina_pausar.setObjectName('Secondary')
        self.rotina_pausar.clicked.connect(self._pausar_rotina)
        self.rotina_agora = QPushButton('Executar agora', cartao)
        self.rotina_agora.setObjectName('Secondary')
        self.rotina_agora.clicked.connect(self._executar_rotina_agora)
        self.rotina_historico = QPushButton('Ver histórico', cartao)
        self.rotina_historico.setObjectName('Secondary')
        self.rotina_historico.clicked.connect(self._ver_historico_rotina)
        for botao in (self.rotina_salvar, self.rotina_nova,
                      self.rotina_pausar, self.rotina_agora,
                      self.rotina_historico):
            botoes.addWidget(botao)
        botoes.addStretch()
        cartao.body.addLayout(botoes)
        self.rotinas_status = StatusLabel(cartao)
        cartao.body.addWidget(self.rotinas_status)
        self.rotinas_historico = QListWidget(cartao)
        self.rotinas_historico.setAccessibleName('Histórico da rotina')
        cartao.body.addWidget(self.rotinas_historico)
        self._atualizar_lista_rotinas()
        return cartao

    def _formatar_proxima_rotina(self, rotina: dict) -> str:
        from core import rotinas as R
        instante = R._de_iso(rotina.get('proxima_execucao') or '')
        if instante is None:
            return 'sem próxima execução'
        local = instante.astimezone(R._fuso(rotina.get('fuso') or R.fuso_padrao()))
        return local.strftime('%d/%m %H:%M')

    def _atualizar_lista_rotinas(self) -> None:
        if self._rotinas is None:
            return
        anterior = self._rotina_selecionada()
        anterior_id = anterior['id'] if anterior else None
        self.rotinas_lista.clear()
        for rotina in self._rotinas.listar():
            rotulo = (f"{rotina['titulo']} · {rotina['estado']} · "
                      f"próxima {self._formatar_proxima_rotina(rotina)}")
            item = QListWidgetItem(rotulo, self.rotinas_lista)
            item.setData(Qt.ItemDataRole.UserRole, rotina['id'])
            item.setToolTip(rotina['mensagem'][:120])
            if rotina['id'] == anterior_id:
                self.rotinas_lista.setCurrentItem(item)
        selecionada = self._rotina_selecionada()
        self.rotina_pausar.setText(
            'Retomar' if selecionada and selecionada['estado'] == 'pausado'
            else 'Pausar')

    def _rotina_selecionada(self) -> dict | None:
        if self._rotinas is None:
            return None
        item = self.rotinas_lista.currentItem()
        if item is None:
            return None
        return self._rotinas.obter(
            str(item.data(Qt.ItemDataRole.UserRole) or ''))

    def _rotina_selecionou(self, *_):
        rotina = self._rotina_selecionada()
        if rotina is None:
            return
        self._rotina_editando = rotina['id']
        self.rotina_titulo.setText(rotina['titulo'])
        self.rotina_mensagem.setText(rotina['mensagem'])
        self.rotina_repeticao.setCurrentIndex(
            self.rotina_repeticao.findData(rotina['repeticao']))
        self.rotina_acao.setCurrentIndex(
            self.rotina_acao.findData(rotina.get('acao') or 'lembrete'))
        self.rotina_data.setText(rotina.get('data') or date.today().isoformat())
        self.rotina_hora.setText(rotina['hora'])
        self.rotina_fuso.setText(rotina['fuso'])
        self.rotina_pausar.setText(
            'Retomar' if rotina['estado'] == 'pausado' else 'Pausar')

    def _nova_rotina(self):
        from core import rotinas as R
        self.rotinas_lista.clearSelection()
        self._rotina_editando = None
        self.rotina_titulo.clear()
        self.rotina_mensagem.clear()
        self.rotina_repeticao.setCurrentIndex(0)
        self.rotina_acao.setCurrentIndex(0)
        self.rotina_data.setText(date.today().isoformat())
        self.rotina_hora.setText('09:00')
        self.rotina_fuso.setText(R.fuso_padrao())
        self.rotinas_status.mostrar('Formulário limpo.', 'info')

    def _salvar_rotina(self) -> None:
        from core import rotinas as R
        titulo = self.rotina_titulo.text().strip()
        mensagem = self.rotina_mensagem.text().strip()
        acao = self.rotina_acao.currentData()
        if not titulo or (acao != 'resumo' and not mensagem):
            self.rotinas_status.mostrar('Informe título e mensagem.', 'warning')
            return
        dados = {
            'titulo': titulo, 'mensagem': mensagem, 'acao': acao,
            'repeticao': self.rotina_repeticao.currentData(),
            'data': self.rotina_data.text().strip(),
            'hora': self.rotina_hora.text().strip(),
            'fuso': self.rotina_fuso.text().strip() or R.fuso_padrao(),
        }
        try:
            if self._rotina_editando:
                self._rotinas.atualizar(self._rotina_editando, dados)
            else:
                self._rotinas.criar(dados)
            R.agendador_global().recalcular()
        except Exception as exc:
            self.rotinas_status.mostrar(
                f'Não foi possível salvar: {type(exc).__name__}: {str(exc)[:100]}.',
                'error')
            return
        self.rotinas_status.mostrar('Salvo', 'success')
        self._atualizar_lista_rotinas()
        atualizar = getattr(self._service.host, 'atualizar_hoje', None)
        if atualizar is not None:
            atualizar()

    def _pausar_rotina(self) -> None:
        from core import rotinas as R
        rotina = self._rotina_selecionada()
        if rotina is None:
            return
        if rotina['estado'] == 'pausado':
            self._rotinas.reativar(rotina['id'])
            mensagem = 'Salvo · rotina reativada.'
        else:
            self._rotinas.pausar(rotina['id'])
            mensagem = 'Salvo · rotina pausada.'
        R.agendador_global().recalcular()
        self.rotinas_status.mostrar(mensagem, 'success')
        self._atualizar_lista_rotinas()

    def _executar_rotina_agora(self) -> None:
        from core import rotinas as R
        rotina = self._rotina_selecionada()
        if rotina is None:
            return
        self._rotina_seq += 1
        seq = self._rotina_seq
        self.rotinas_status.mostrar('Executando rotina…', 'info')

        def terminou(resultado):
            if self._fechado or seq != self._rotina_seq:
                return
            if isinstance(resultado, dict) and resultado.get('ok'):
                self.rotinas_status.mostrar('Salvo · rotina executada.', 'success')
            else:
                self.rotinas_status.mostrar(
                    'Não foi possível notificar nesta execução.', 'error')
            self._atualizar_lista_rotinas()
            self._ver_historico_rotina()
            if isinstance(resultado, dict) and resultado.get('atualizar_hoje'):
                atualizar = getattr(self._service.host, 'atualizar_hoje', None)
                if atualizar is not None:
                    atualizar()

        def executar():
            armazem = R.ArmazemRotinas(db_path=self._rotinas.db_path)
            bloqueio = armazem.bloqueio(rotina['id'])
            if not bloqueio.acquire(blocking=False):
                return {'ok': False}
            try:
                log = armazem.reservar(
                    rotina['id'], f"manual-{time.time_ns()}", 'manual')
                if log is None:
                    return {'ok': False}
                if rotina.get('acao') == 'resumo':
                    from core import resumo_dia as RD  # noqa: PLC0415
                    resultado = RD.gerar_e_salvar()
                    ok = bool(resultado.get('ok'))
                    armazem.finalizar(
                        log, ok, '' if ok else str(resultado.get('erro') or 'falha'))
                    return {'ok': ok, 'atualizar_hoje': ok}
                ok, erro = R.Agendador(armazem=armazem)._notificar(
                    rotina['mensagem'])
                armazem.finalizar(log, ok, '' if ok else 'Notificação falhou')
                return {'ok': ok}
            finally:
                bloqueio.release()

        self._executar(executar, terminou)

    def _ver_historico_rotina(self) -> None:
        rotina = self._rotina_selecionada()
        self.rotinas_historico.clear()
        if rotina is None:
            return
        for execucao in self._rotinas.historico(rotina['id'], 10):
            self.rotinas_historico.addItem(
                f"{execucao['origem']} · {execucao['resultado']} · "
                f"{execucao['iniciada_em'][:19]}")

    def _pintar_botao_estado(self, botao: QPushButton, ligado: bool,
                             ligado_txt: str, desligado_txt: str) -> None:
        botao.setText(ligado_txt if ligado else desligado_txt)
        botao.setProperty("ligado", "true" if ligado else "false")
        botao.style().unpolish(botao)
        botao.style().polish(botao)

    def _pintar_saudacao(self) -> None:
        ligado = bool(self._service.carregar_persona().get("saudacao", True))
        self._pintar_botao_estado(
            self.saudacao_botao, ligado,
            "LIGADA · clique para desligar", "DESLIGADA · clique para ligar")

    def _saudacao_mudou(self) -> None:
        ligado = bool(self._service.carregar_persona().get("saudacao", True))
        alvo = not ligado
        self._alterar("saudacao", alvo, self.saudacao_status,
                      ao_terminar=lambda _: self._pintar_saudacao())

    def _consultar_inicio(self) -> None:
        self._inicio_seq += 1
        seq = self._inicio_seq
        self.inicio_status.mostrar("Consultando o estado do sistema…", "info")

        def pronto(estado):
            if self._fechado or seq != self._inicio_seq:
                return
            if not isinstance(estado, dict):
                estado = {"disponivel": False, "ligado": False, "motivo": ""}
            self._inicio_disponivel = bool(estado.get("disponivel"))
            self.inicio_botao.setEnabled(self._inicio_disponivel)
            self._pintar_botao_estado(
                self.inicio_botao, bool(estado.get("ligado")),
                "LIGADO · clique para desligar", "DESLIGADO · clique para ligar")
            motivo = str(estado.get("motivo") or "").strip()
            if not self._inicio_disponivel:
                self.inicio_status.mostrar(
                    motivo or "Este sistema não permite consultar a inicialização.",
                    "warning")
            else:
                self.inicio_status.limpar()

        def consultar():
            try:
                from core import iniciar_com_sistema as ini  # noqa: PLC0415
                disponivel = bool(ini.disponivel())
                return {"disponivel": disponivel,
                        "ligado": bool(ini.esta_ligado()) if disponivel else False,
                        "motivo": ""}
            except Exception as exc:
                return {"disponivel": False, "ligado": False,
                        "motivo": f"{type(exc).__name__}: {str(exc)[:120]}"}

        self._executar(consultar, pronto)

    def _inicio_mudou(self) -> None:
        if not self._inicio_disponivel:
            return
        ligado = self.inicio_botao.property("ligado") == "true"
        alvo = not ligado
        self._inicio_seq += 1
        seq = self._inicio_seq
        self.inicio_status.mostrar("Aplicando…", "info")

        def alterar():
            try:
                from core import iniciar_com_sistema as ini  # noqa: PLC0415
                ok, motivo = ini.ligar(alvo)
                return {"ok": bool(ok), "motivo": str(motivo or ""),
                        "ligado": bool(ini.esta_ligado())}
            except Exception as exc:
                return {"ok": False, "ligado": ligado,
                        "motivo": f"{type(exc).__name__}: {str(exc)[:120]}"}

        def pronto(resultado):
            if self._fechado or seq != self._inicio_seq:
                return
            self._pintar_botao_estado(
                self.inicio_botao, bool(resultado.get("ligado")),
                "LIGADO · clique para desligar", "DESLIGADO · clique para ligar")
            if resultado.get("ok"):
                self.inicio_status.mostrar("Salvo", "success")
            else:
                self.inicio_status.mostrar(
                    f"Não foi possível alterar: {resultado.get('motivo') or 'tente de novo'}",
                    "error")

        self._executar(alterar, pronto)

    # ── Meu perfil ──────────────────────────────────────────────────────────
    def _construir_pagina_perfil(self, pai) -> QWidget:
        from core import dono  # noqa: PLC0415
        pagina = QWidget(pai)
        raiz = QVBoxLayout(pagina)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(14)
        cartao = GlassCard(
            "Sobre você",
            "Gravamos ao pressionar Enter ou ao sair do campo. "
            "Os valores ficam no arquivo de perfil já usado pela NIA.", pagina)
        self._perfil_salvo: dict[str, str] = {}
        self._perfil_campos: dict[str, QLineEdit] = {}
        self._perfil_status: dict[str, StatusLabel] = {}
        atual = self._service.carregar_dono()
        for chave, (rotulo, dica) in dono.CAMPOS.items():
            campo = QLineEdit(str(atual.get(chave, "") or ""), cartao)
            campo.setPlaceholderText(dica)
            campo.setAccessibleName(str(rotulo))
            status = StatusLabel(cartao)
            self._perfil_campos[chave] = campo
            self._perfil_status[chave] = status
            self._perfil_salvo[chave] = campo.text()
            cartao.body.addLayout(
                _campo(str(rotulo), campo, status, "", cartao))
            campo.returnPressed.connect(
                lambda c=chave, w=campo: self._salvar_perfil(c, w))
            campo.editingFinished.connect(
                lambda c=chave, w=campo: self._salvar_perfil(c, w))
        raiz.addWidget(cartao)
        raiz.addStretch(1)
        return pagina

    def _salvar_perfil(self, chave: str, campo: QLineEdit) -> None:
        texto = campo.text()
        if self._perfil_salvo.get(chave) == texto:
            return
        self._perfil_salvo[chave] = texto
        status = self._perfil_status[chave]
        status.mostrar("Salvando…", "info")

        def pronto(resultado):
            if self._fechado:
                return
            if isinstance(resultado, dict) and resultado.get("ok") is False:
                self._perfil_salvo[chave] = None
                status.mostrar("Não foi possível salvar. Tente de novo.", "error")
                return
            status.mostrar("Salvo", "success")

        self._executar(
            lambda: self._service.salvar_dono({chave: texto}), pronto)

    # ── Integrações ─────────────────────────────────────────────────────────
    def _construir_pagina_integracoes(self, pai) -> QWidget:
        pagina = QWidget(pai)
        raiz = QVBoxLayout(pagina)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(12)

        areas = QHBoxLayout()
        areas.setSpacing(6)
        self._grupo_integracoes = QButtonGroup(pagina)
        self._grupo_integracoes.setExclusive(True)
        self._botoes_integracoes = {}
        for nome, rotulo in (("conexoes", "WhatsApp e celular"),
                             ("secretaria", "Secretária")):
            botao = QPushButton(rotulo, pagina)
            botao.setObjectName("Segment")
            botao.setCheckable(True)
            botao.setCursor(Qt.CursorShape.PointingHandCursor)
            botao.clicked.connect(lambda _=False, n=nome: self.mostrar_integracao(n))
            self._grupo_integracoes.addButton(botao)
            self._botoes_integracoes[nome] = botao
            areas.addWidget(botao)
        areas.addStretch(1)
        raiz.addLayout(areas)

        self._stack_integracoes = QStackedWidget(pagina)
        self._area_conexoes = self._construir_area_conexoes(pagina)
        self._area_secretaria = QWidget(self._stack_integracoes)
        self._secretaria_widget = None
        self._stack_integracoes.addWidget(self._area_conexoes)
        self._stack_integracoes.addWidget(self._area_secretaria)
        raiz.addWidget(self._stack_integracoes, 1)
        raiz.addStretch(1)

        self._integracoes_seq = 0
        self.mostrar_integracao("conexoes")
        self._consultar_conexoes()
        return pagina

    def _construir_area_conexoes(self, pai) -> QWidget:
        area = QWidget(pai)
        raiz = QVBoxLayout(area)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(14)

        cartao = GlassCard("Conexões",
                           "Estado conhecido localmente. Atualize para consultar "
                           "a ponte do WhatsApp e o painel de acesso remoto.", area)
        self.whatsapp_estado = StatusLabel(cartao)
        self.remoto_estado = StatusLabel(cartao)
        cartao.body.addWidget(self.whatsapp_estado)
        cartao.body.addWidget(self.remoto_estado)
        botoes = QHBoxLayout()
        botoes.setSpacing(8)
        self.whatsapp_botao = QPushButton("Conectar WhatsApp / QR", cartao)
        self.whatsapp_botao.setObjectName("Primary")
        self.whatsapp_botao.setAccessibleName("Conectar WhatsApp e ler os QR")
        self.whatsapp_botao.clicked.connect(self._abrir_whatsapp)
        self.remoto_botao = QPushButton("Parear celular", cartao)
        self.remoto_botao.setObjectName("Secondary")
        self.remoto_botao.clicked.connect(self._abrir_remoto)
        self.revogar_botao = QPushButton("Revogar acesso", cartao)
        self.revogar_botao.setObjectName("Secondary")
        self.revogar_botao.clicked.connect(self._revogar_remoto)
        self.atualizar_conexoes = QPushButton("Atualizar status", cartao)
        self.atualizar_conexoes.setObjectName("Secondary")
        self.atualizar_conexoes.clicked.connect(self._consultar_conexoes)
        for botao in (self.whatsapp_botao, self.remoto_botao,
                      self.atualizar_conexoes, self.revogar_botao):
            botao.setMinimumHeight(36)
            botoes.addWidget(botao)
        botoes.addStretch()
        cartao.body.addLayout(botoes)
        self.integracoes_status = StatusLabel(cartao)
        cartao.body.addWidget(self.integracoes_status)
        raiz.addWidget(cartao)

        dica = QLabel(
            "A janela do WhatsApp mostra os dois QR: mensagens e, quando a "
            "Secretária está ligada, ligações. O celular usa a mesma chave "
            "temporária do painel de acesso remoto.", area)
        dica.setObjectName("Hint")
        dica.setWordWrap(True)
        raiz.addWidget(dica)
        raiz.addStretch(1)
        return area

    def mostrar_integracao(self, nome: str = "conexoes") -> str:
        area = "secretaria" if str(nome or "").strip().lower() in (
            "secretaria", "secretária", "calls", "ligacoes") else "conexoes"
        if area == "secretaria":
            self._garantir_secretaria()
        self._stack_integracoes.setCurrentWidget(
            self._area_secretaria if area == "secretaria" else self._area_conexoes)
        for chave, botao in self._botoes_integracoes.items():
            botao.setChecked(chave == area)
        self._pausar_timers_area(area == "secretaria")
        return area

    def _garantir_secretaria(self) -> None:
        if self._secretaria_widget is not None:
            return
        from core import secretaria_tela  # noqa: PLC0415
        janela = getattr(self._service.host, "_win", None)
        self._secretaria_widget = secretaria_tela.pagina(janela)
        self._area_secretaria_layout = QVBoxLayout(self._area_secretaria)
        self._area_secretaria_layout.setContentsMargins(0, 0, 0, 0)
        self._area_secretaria_layout.addWidget(self._secretaria_widget)

    def _pausar_timers_area(self, visivel: bool) -> None:
        if self._secretaria_widget is None:
            return
        for timer in self._secretaria_widget.findChildren(QTimer):
            if visivel:
                if not timer.isActive():
                    timer.start()
            elif timer.isActive():
                timer.stop()

    def _consultar_conexoes(self) -> None:
        if not hasattr(self, "whatsapp_estado"):
            return
        self._integracoes_seq += 1
        seq = self._integracoes_seq
        self.whatsapp_estado.mostrar("Consultando WhatsApp…", "info")
        self.remoto_estado.mostrar("Consultando acesso remoto…", "info")

        def consultar():
            dados = {"whatsapp": {}, "remoto": {}}
            try:
                from actions import whatsapp_bridge  # noqa: PLC0415
                bruto = whatsapp_bridge.get_status() or {}
                dados["whatsapp"] = {
                    key: bruto.get(key) for key in
                    ("connected", "session_saved", "ponte_offline", "error")}
            except Exception as exc:
                dados["whatsapp"] = {"error": f"{type(exc).__name__}"}
            try:
                from dashboard.server import REMOTE_SESSIONS_FILE  # noqa: PLC0415
                bruto = json.loads(REMOTE_SESSIONS_FILE.read_text(encoding="utf-8"))
                dispositivos = bruto.get("devices") if isinstance(bruto, dict) else None
                dados["remoto"] = {"dispositivos": len(dispositivos or {})}
            except Exception:
                dados["remoto"] = {"dispositivos": 0}
            host = self._service.host
            janela = getattr(host, "_win", None)
            dados["remoto"]["pareando"] = getattr(janela, "_remote_overlay", None) is not None
            return dados

        def pronto(dados):
            if self._fechado or seq != self._integracoes_seq:
                return
            wa = dados.get("whatsapp") or {}
            if wa.get("connected"):
                self.whatsapp_estado.mostrar("WhatsApp conectado", "success")
            elif wa.get("session_saved"):
                self.whatsapp_estado.mostrar(
                    "Sessão salva; a ponte pode estar desligada.", "warning")
            else:
                self.whatsapp_estado.mostrar("WhatsApp não conectado", "info")
            remoto = dados.get("remoto") or {}
            total = int(remoto.get("dispositivos") or 0)
            if remoto.get("pareando"):
                self.remoto_estado.mostrar("Pareamento aberto no desktop", "info")
            elif total:
                self.remoto_estado.mostrar(
                    f"{total} dispositivo(s) pareado(s)", "success")
            else:
                self.remoto_estado.mostrar("Nenhum celular pareado", "info")

        self._executar(consultar, pronto)

    def _janela_principal(self):
        return getattr(self._service.host, "_win", None)

    def _abrir_whatsapp(self) -> None:
        janela = self._janela_principal()
        abrir = getattr(janela, "_open_whatsapp", None) if janela else None
        if abrir is None:
            self.integracoes_status.mostrar(
                "A janela principal não está disponível.", "warning")
            return
        abrir()
        self.integracoes_status.mostrar(
            "Janela do WhatsApp aberta. Leia os QR de mensagens e ligações.",
            "info")
        QTimer.singleShot(1200, self._consultar_conexoes)

    def _abrir_remoto(self) -> None:
        janela = self._janela_principal()
        abrir = getattr(janela, "_open_remote", None) if janela else None
        if abrir is None:
            self.integracoes_status.mostrar(
                "A janela principal não está disponível.", "warning")
            return
        abrir()
        self.integracoes_status.mostrar(
            "QR do celular aberto; a chave expira em alguns minutos.", "info")
        QTimer.singleShot(1200, self._consultar_conexoes)

    def _revogar_remoto(self) -> None:
        if QMessageBox.question(
                self, "Revogar acesso",
                "Revogar o acesso de todos os celulares pareados? "
                "Eles precisarão ler um novo QR.") != QMessageBox.StandardButton.Yes:
            return
        casca = self._service.host
        callback = getattr(casca, "on_revoke_devices", None) if casca else None
        if callback is None:
            self.integracoes_status.mostrar(
                "O painel de acesso remoto não está disponível.", "error")
            return
        self.integracoes_status.mostrar("Revogando…", "info")

        def pronto(resultado):
            if self._fechado:
                return
            if resultado is None:
                self.integracoes_status.mostrar(
                    "Não foi possível revogar. Tente de novo.", "error")
                return
            self.integracoes_status.mostrar(
                f"Salvo · {int(resultado)} acesso(s) revogado(s).", "success")
            self._consultar_conexoes()

        self._executar(callback, pronto)

    # ── Documentos: índice textual local ───────────────────────────────────
    def _construir_pagina_documentos(self, pai) -> QWidget:
        from core import secretaria
        from core.indice_local import IndiceLocal, fts5_disponivel
        pagina = QWidget(pai)
        raiz = QVBoxLayout(pagina)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(12)

        fontes = self._service.carregar_fontes_indice()
        self._pasta_secretaria = str(secretaria.pasta_do_dono())
        self._indice = IndiceLocal(fontes=fontes)

        cartao_fontes = GlassCard(
            "Pastas indexadas",
            "A pasta da Secretária é oferecida pelo mesmo resolvedor usado "
            "por ela. Outras pastas são escolhidas explicitamente.", pagina)
        self.secretaria_check = QCheckBox(
            f'Incluir pasta da Secretária ({self._pasta_secretaria})',
            cartao_fontes)
        self.secretaria_check.setChecked(self._pasta_secretaria in fontes)
        self.secretaria_check.setAccessibleName('Incluir pasta da Secretária')
        self.secretaria_check.toggled.connect(self._fonte_secretaria_mudou)
        cartao_fontes.body.addWidget(self.secretaria_check)
        self.fontes_lista = QListWidget(cartao_fontes)
        self.fontes_lista.setAccessibleName('Pastas indexadas')
        for fonte in fontes:
            self.fontes_lista.addItem(fonte)
        cartao_fontes.body.addWidget(self.fontes_lista)
        botoes_fontes = QHBoxLayout()
        botoes_fontes.setSpacing(8)
        adicionar = QPushButton('Adicionar pasta', cartao_fontes)
        adicionar.setObjectName('Secondary')
        adicionar.clicked.connect(self._adicionar_fonte_indice)
        remover = QPushButton('Remover pasta', cartao_fontes)
        remover.setObjectName('Secondary')
        remover.clicked.connect(self._remover_fonte_indice)
        botoes_fontes.addWidget(adicionar)
        botoes_fontes.addWidget(remover)
        botoes_fontes.addStretch()
        cartao_fontes.body.addLayout(botoes_fontes)
        self.fontes_status = StatusLabel(cartao_fontes)
        cartao_fontes.body.addWidget(self.fontes_status)
        raiz.addWidget(cartao_fontes)

        cartao_indice = GlassCard(
            "Índice local",
            "Atualização manual: nenhuma varredura periódica e nenhuma "
            "chamada de rede. O banco fica em ~/.nia/indice_local.db.", pagina)
        self.indice_contagem = QLabel('Carregando estado do índice…', cartao_indice)
        self.indice_contagem.setObjectName('SectionHint')
        self.indice_contagem.setWordWrap(True)
        cartao_indice.body.addWidget(self.indice_contagem)
        botoes_indice = QHBoxLayout()
        botoes_indice.setSpacing(8)
        self.indice_atualizar = QPushButton('Atualizar índice', cartao_indice)
        self.indice_atualizar.setObjectName('Primary')
        self.indice_atualizar.clicked.connect(lambda: self._atualizar_indice_local(False))
        self.indice_reconstruir = QPushButton('Reconstruir', cartao_indice)
        self.indice_reconstruir.setObjectName('Secondary')
        self.indice_reconstruir.clicked.connect(lambda: self._atualizar_indice_local(True))
        self.indice_cancelar = QPushButton('Cancelar', cartao_indice)
        self.indice_cancelar.setObjectName('Secondary')
        self.indice_cancelar.setEnabled(False)
        self.indice_cancelar.clicked.connect(self._cancelar_indice_local)
        for botao in (self.indice_atualizar, self.indice_reconstruir,
                      self.indice_cancelar):
            botoes_indice.addWidget(botao)
        botoes_indice.addStretch()
        cartao_indice.body.addLayout(botoes_indice)
        self.indice_status = StatusLabel(cartao_indice)
        cartao_indice.body.addWidget(self.indice_status)
        raiz.addWidget(cartao_indice)

        cartao_busca = GlassCard(
            'Busca local',
            'Consulta FTS5 sobre os trechos indexados. Sem modelos, embeddings '
            'ou internet.', pagina)
        linha_busca = QHBoxLayout()
        linha_busca.setSpacing(8)
        self.busca_local_edit = QLineEdit(cartao_busca)
        self.busca_local_edit.setPlaceholderText('Ex.: recado da secretária')
        self.busca_local_edit.setAccessibleName('Buscar em documentos locais')
        self.busca_local_edit.returnPressed.connect(self._buscar_local)
        self.busca_local_botao = QPushButton('Buscar', cartao_busca)
        self.busca_local_botao.setObjectName('Secondary')
        self.busca_local_botao.clicked.connect(self._buscar_local)
        linha_busca.addWidget(self.busca_local_edit, 1)
        linha_busca.addWidget(self.busca_local_botao)
        cartao_busca.body.addLayout(linha_busca)
        self.busca_local_status = StatusLabel(cartao_busca)
        cartao_busca.body.addWidget(self.busca_local_status)
        self.busca_local_resultados = QListWidget(cartao_busca)
        self.busca_local_resultados.setAccessibleName('Resultados da busca local')
        cartao_busca.body.addWidget(self.busca_local_resultados)
        if not fts5_disponivel():
            self.busca_local_status.mostrar(
                'Este runtime não tem FTS5: a busca local está indisponível; '
                'os demais fluxos continuam funcionando.', 'warning')
            self.busca_local_botao.setEnabled(False)
        raiz.addWidget(cartao_busca)
        raiz.addStretch(1)
        self._atualizar_contagem_indice()
        return pagina

    # ── Habilidades nativas (Skill 07) ─────────────────────────────────────
    def _construir_pagina_habilidades(self, pai) -> QWidget:
        pagina = QWidget(pai)
        raiz = QVBoxLayout(pagina)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(12)

        cartao = GlassCard(
            'Habilidades nativas',
            'Cada entrada reutiliza um fluxo existente: Secretária, busca com '
            'fontes e resumo local. Decidir a rota não usa modelo, rede nem '
            'sondagem.', pagina)
        self.habilidades_lista = QWidget(cartao)
        self.habilidades_lista.setAccessibleName('Habilidades nativas')
        lista = QVBoxLayout(self.habilidades_lista)
        lista.setContentsMargins(0, 0, 0, 0)
        lista.setSpacing(10)
        self.habilidades_status: dict[str, StatusLabel] = {}
        self.habilidades_botoes: dict[str, QPushButton] = {}
        for habilidade in CH.todas():
            quadro = QFrame(cartao)
            quadro.setObjectName('ApiCard')
            caixa = QVBoxLayout(quadro)
            caixa.setContentsMargins(12, 10, 12, 10)
            caixa.setSpacing(5)

            titulo = QLabel(habilidade.nome, quadro)
            titulo.setObjectName('CardTitle')
            titulo.setWordWrap(True)
            caixa.addWidget(titulo)
            descricao = QLabel(habilidade.descricao, quadro)
            descricao.setObjectName('SectionHint')
            descricao.setWordWrap(True)
            caixa.addWidget(descricao)
            exemplo = QLabel(f'Exemplo: “{habilidade.exemplo}”', quadro)
            exemplo.setObjectName('Hint')
            exemplo.setWordWrap(True)
            caixa.addWidget(exemplo)

            disponivel = CH.disponibilidade(habilidade.id)
            estado = StatusLabel(quadro)
            estado.mostrar(disponivel.motivo,
                           'success' if disponivel.pronta else 'warning')
            self.habilidades_status[habilidade.id] = estado
            caixa.addWidget(estado)

            linha = QHBoxLayout()
            acao = QPushButton(
                'Executar' if disponivel.pronta else 'Abrir configuração',
                quadro)
            acao.setObjectName('Primary' if disponivel.pronta else 'Secondary')
            acao.setAccessibleName(f'Executar — {habilidade.nome}')
            acao.clicked.connect(
                lambda _=False, ident=habilidade.id: self._habilidade_acao(ident))
            self.habilidades_botoes[habilidade.id] = acao
            copiar = QPushButton('Copiar exemplo', quadro)
            copiar.setObjectName('CardAction')
            copiar.setAccessibleName(f'Copiar exemplo — {habilidade.nome}')
            copiar.clicked.connect(
                lambda _=False, texto=habilidade.exemplo:
                QApplication.clipboard().setText(texto))
            linha.addWidget(acao)
            linha.addWidget(copiar)
            linha.addStretch()
            caixa.addLayout(linha)
            lista.addWidget(quadro)
        cartao.body.addWidget(self.habilidades_lista)

        nota = QLabel(
            'Os atalhos do Canvas usam o mesmo catálogo. Ative-os em '
            'Aparência → Ferramentas do dock; as frases de exemplo também '
            'funcionam no chat e na voz.', cartao)
        nota.setObjectName('Hint')
        nota.setWordWrap(True)
        cartao.body.addWidget(nota)
        raiz.addWidget(cartao)
        raiz.addStretch(1)
        self._achatar_controles(pagina)
        return pagina

    def _habilidade_acao(self, identificador: str) -> None:
        try:
            ok, mensagem = CH.executar(identificador, '')
        except Exception as exc:
            ok, mensagem = False, f'Falha ao executar: {type(exc).__name__}.'
        estado = self.habilidades_status.get(identificador)
        if estado is not None:
            estado.mostrar(mensagem, 'success' if ok else 'error')

    def _fontes_indice_da_lista(self) -> list[str]:
        return [self.fontes_lista.item(i).text().strip()
                for i in range(self.fontes_lista.count())
                if self.fontes_lista.item(i).text().strip()]

    def _salvar_fontes_indice(self, mensagem: str = 'Salvo') -> None:
        fontes = self._fontes_indice_da_lista()
        try:
            self._service.salvar_fontes_indice(fontes)
            self._indice.definir_fontes(fontes)
        except Exception as exc:
            self.fontes_status.mostrar(
                f'Não foi possível salvar: {type(exc).__name__}.', 'error')
            return
        self.fontes_status.mostrar(mensagem, 'success')
        self._atualizar_contagem_indice()

    def _fonte_secretaria_mudou(self, ligado: bool) -> None:
        fontes = self._fontes_indice_da_lista()
        if ligado and self._pasta_secretaria not in fontes:
            fontes.append(self._pasta_secretaria)
        elif not ligado and self._pasta_secretaria in fontes:
            fontes.remove(self._pasta_secretaria)
        self.fontes_lista.clear()
        for fonte in dict.fromkeys(fontes):
            self.fontes_lista.addItem(fonte)
        self._salvar_fontes_indice()

    def _adicionar_fonte_indice(self) -> None:
        escolhida = QFileDialog.getExistingDirectory(self, 'Pasta para indexar')
        if not escolhida:
            return
        fontes = self._fontes_indice_da_lista()
        if escolhida in fontes:
            self.fontes_status.mostrar('Essa pasta já está na lista.', 'warning')
            return
        fontes.append(escolhida)
        self.fontes_lista.clear()
        for fonte in dict.fromkeys(fontes):
            self.fontes_lista.addItem(fonte)
        self._salvar_fontes_indice()

    def _remover_fonte_indice(self) -> None:
        atual = self.fontes_lista.currentRow()
        if atual < 0:
            return
        self.fontes_lista.takeItem(atual)
        self.secretaria_check.blockSignals(True)
        self.secretaria_check.setChecked(
            self._pasta_secretaria in self._fontes_indice_da_lista())
        self.secretaria_check.blockSignals(False)
        self._salvar_fontes_indice(
            'Salvo · documentos sem fonte autorizada foram removidos da busca.')

    def _atualizar_contagem_indice(self) -> None:
        if self._indice is None or not hasattr(self, 'indice_contagem'):
            return
        try:
            dados = self._indice.contar()
            self.indice_contagem.setText(
                f"{dados['documentos']} documento(s) · {dados['trechos']} trecho(s) "
                f"· {dados['fontes']} pasta(s)")
        except Exception as exc:
            self.indice_contagem.setText(
                f'Estado do índice indisponível: {type(exc).__name__}.')

    def _estado_indice_local(self, ativo: bool) -> None:
        self._indice_ativo = ativo
        self.indice_atualizar.setEnabled(not ativo)
        self.indice_reconstruir.setEnabled(not ativo)
        self.indice_cancelar.setEnabled(ativo)

    def _atualizar_indice_local(self, reconstruir: bool) -> None:
        if self._indice_ativo or self._indice is None:
            return
        self._estado_indice_local(True)
        self.indice_status.mostrar('Atualizando índice…', 'info')

        def terminou(resultado):
            if self._fechado:
                return
            self._estado_indice_local(False)
            if not isinstance(resultado, dict):
                self.indice_status.mostrar(
                    'Não foi possível atualizar o índice.', 'error')
                return
            partes = [f"{resultado.get('atualizados', 0)} atualizado(s)",
                      f"{resultado.get('removidos', 0)} removido(s)",
                      f"{len(resultado.get('erros') or [])} erro(s)"]
            if resultado.get('interrompido'):
                partes.append('interrompido')
            if resultado.get('pendentes'):
                partes.append(f"{resultado['pendentes']} pendente(s)")
            estado = 'warning' if (resultado.get('interrompido')
                                   or resultado.get('erros')
                                   or resultado.get('pendentes')) else 'success'
            self.indice_status.mostrar(' · '.join(partes), estado)
            self._atualizar_contagem_indice()

        acao = (lambda: self._indice.reconstruir() if reconstruir
                else self._indice.atualizar())
        self._executar(acao, terminou)

    def _cancelar_indice_local(self) -> None:
        if self._indice is not None:
            self._indice.interromper()
            self.indice_status.mostrar('Cancelando a atualização…', 'warning')

    def _buscar_local(self) -> None:
        if self._indice is None:
            return
        texto = self.busca_local_edit.text().strip()
        if not texto:
            self.busca_local_status.mostrar('Digite um termo para buscar.', 'info')
            self.busca_local_resultados.clear()
            return
        self._indice_busca_seq += 1
        seq = self._indice_busca_seq
        self.busca_local_resultados.clear()
        self.busca_local_status.mostrar('Buscando…', 'info')

        def terminou(resultados):
            if self._fechado or seq != self._indice_busca_seq:
                return
            if not isinstance(resultados, list):
                self.busca_local_status.mostrar('Busca indisponível.', 'error')
                return
            for item in resultados:
                rotulo = (f"{Path(item['arquivo']).name} · pos {item['posicao']}\n"
                          f"{item['trecho'][:180]}")
                linha = QListWidgetItem(rotulo, self.busca_local_resultados)
                linha.setToolTip(item['arquivo'])
                linha.setData(Qt.ItemDataRole.UserRole, item['arquivo'])
            if resultados:
                self.busca_local_status.mostrar(
                    f'{len(resultados)} resultado(s).', 'success')
            else:
                self.busca_local_status.mostrar(
                    'Nenhum trecho encontrado neste índice.', 'info')

        self._executar(lambda: self._indice.buscar(texto, 10), terminou)

    def _construir_pagina_voz(self) -> QScrollArea:
        pagina, layout = self._pagina_base(
            "Voz e áudio",
            "Escolha como a NIA soa, de onde ela ouve e por onde ela fala. "
            "As alterações são aplicadas ao vivo e gravadas em config/persona.json.")

        cartao_voz = GlassCard(
            "Voz",
            "A voz e o jeito de ser são independentes: dá para combinar qualquer "
            "timbre com qualquer personalidade.")
        self.voice_combo = QComboBox(cartao_voz)
        self.voice_combo.setAccessibleName("Voz da NIA")
        self.voice_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.voice_combo.setMinimumContentsLength(16)
        for chave, item in PERSONAGENS.items():
            nome = nome_da_ia(chave)
            texto = (f"{nome}  ·  voz {item['nome']}" if nome != item["nome"]
                     else item["nome"])
            self.voice_combo.addItem(texto, chave)
            indice = self.voice_combo.count() - 1
            self.voice_combo.setItemData(indice, item.get("desc", ""),
                                         Qt.ItemDataRole.ToolTipRole)
        self.voice_status = StatusLabel(cartao_voz)
        self.voice_hint = QLabel("", cartao_voz)
        self.voice_hint.setObjectName("Hint")
        self.voice_hint.setWordWrap(True)
        cartao_voz.body.addWidget(self.voice_hint)
        cartao_voz.body.addLayout(_campo("Voz  ·  como ela soa", self.voice_combo,
                                         self.voice_status, parent=cartao_voz))

        self.personality_combo = QComboBox(cartao_voz)
        self.personality_combo.setAccessibleName("Personalidade da NIA")
        self.personality_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.personality_combo.setMinimumContentsLength(16)
        for chave, item in PERSONALIDADES.items():
            self.personality_combo.addItem(item["nome"], chave)
            indice = self.personality_combo.count() - 1
            self.personality_combo.setItemData(indice, item.get("desc", ""),
                                              Qt.ItemDataRole.ToolTipRole)
        self.personality_status = StatusLabel(cartao_voz)
        self.personality_hint = QLabel("", cartao_voz)
        self.personality_hint.setObjectName("Hint")
        self.personality_hint.setWordWrap(True)
        cartao_voz.body.addWidget(self.personality_hint)
        cartao_voz.body.addLayout(_campo(
            "Jeito  ·  como ela age", self.personality_combo,
            self.personality_status, parent=cartao_voz))

        self.alias_edit = QLineEdit(cartao_voz)
        self.alias_edit.setAccessibleName("Nome da voz")
        self.alias_edit.setMaxLength(16)
        self.alias_edit.setPlaceholderText("Nome original")
        self.alias_status = StatusLabel(cartao_voz)
        cartao_voz.body.addLayout(_campo(
            "Nome da voz  ·  como ela se apresenta", self.alias_edit,
            self.alias_status,
            "Enter ou sair do campo grava. Deixe vazio para voltar ao nome original.",
            cartao_voz))

        linha = _botoes(("Ouvir voz", "Primary"))
        self.ouvir_botao = linha.itemAt(0).widget()
        cartao_voz.body.addLayout(linha)
        layout.addWidget(cartao_voz)

        cartao_audio = GlassCard(
            "Microfone e áudio",
            "O padrão do Windows continua sendo uma opção. A lista é atualizada "
            "sem trocar a preferência já gravada.")
        topo = QHBoxLayout()
        topo.setSpacing(8)
        self.devices_status = StatusLabel(cartao_audio)
        topo.addWidget(self.devices_status)
        topo.addStretch(1)
        self.refresh_botao = QPushButton("Atualizar dispositivos", cartao_audio)
        self.refresh_botao.setObjectName("Secondary")
        self.refresh_botao.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_botao.setAccessibleName("Atualizar a lista de dispositivos de áudio")
        self.refresh_botao.setMinimumHeight(32)
        topo.addWidget(self.refresh_botao)
        cartao_audio.body.addLayout(topo)
        cartao_audio.body.addWidget(_regra(cartao_audio))

        seccao_mic = QLabel("Microfone  ·  por onde ela ouve", cartao_audio)
        seccao_mic.setObjectName("Eyebrow")
        seccao_mic.setWordWrap(True)
        cartao_audio.body.addWidget(seccao_mic)
        self.mic_combo = QComboBox(cartao_audio)
        self.mic_combo.setAccessibleName("Microfone da NIA")
        self.mic_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.mic_combo.setMinimumContentsLength(16)
        self.mic_status = StatusLabel(cartao_audio)
        cartao_audio.body.addLayout(_campo(
            "Dispositivo de entrada", self.mic_combo, self.mic_status,
            "Usado na próxima captura de áudio. Abrir a janela não altera a escolha.",
            cartao_audio))
        linha_mic = _botoes(("Testar microfone", "Secondary"))
        self.testar_mic_botao = linha_mic.itemAt(0).widget()
        cartao_audio.body.addLayout(linha_mic)

        cartao_audio.body.addWidget(_regra(cartao_audio))
        seccao_saida = QLabel("Saída de áudio  ·  por onde ela fala", cartao_audio)
        seccao_saida.setObjectName("Eyebrow")
        seccao_saida.setWordWrap(True)
        cartao_audio.body.addWidget(seccao_saida)
        self.saida_combo = QComboBox(cartao_audio)
        self.saida_combo.setAccessibleName("Saída de áudio da NIA")
        self.saida_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.saida_combo.setMinimumContentsLength(16)
        self.saida_status = StatusLabel(cartao_audio)
        cartao_audio.body.addLayout(_campo(
            "Dispositivo de saída", self.saida_combo, self.saida_status,
            "A próxima fala usa esta saída. O teste toca um bip curto no aparelho.",
            cartao_audio))
        linha_saida = _botoes(("Tocar teste", "Secondary"))
        self.tocar_botao = linha_saida.itemAt(0).widget()
        cartao_audio.body.addLayout(linha_saida)
        layout.addWidget(cartao_audio)

        nota = QLabel(
            "Saudação ao abrir e iniciar com o sistema continuam nas "
            "Configurações clássicas até a página Geral ser migrada.", pagina)
        nota.setObjectName("Hint")
        nota.setWordWrap(True)
        layout.addWidget(nota)
        layout.addStretch(1)

        self.voice_combo.currentIndexChanged.connect(self._voz_mudou)
        self.personality_combo.currentIndexChanged.connect(self._personalidade_mudou)
        self.alias_edit.editingFinished.connect(self._salvar_alias)
        self.ouvir_botao.clicked.connect(self._ouvir_voz)
        self.refresh_botao.clicked.connect(self.atualizar_dispositivos)
        self.mic_combo.currentIndexChanged.connect(self._microfone_mudou)
        self.saida_combo.currentIndexChanged.connect(self._saida_mudou)
        self.testar_mic_botao.clicked.connect(self._testar_microfone)
        self.tocar_botao.clicked.connect(self._tocar_teste)
        return pagina

    def _construir_pagina_aparencia(self) -> QScrollArea:
        pagina, layout = self._pagina_base(
            "Aparência",
            "Escolha o tema do dashboard. A seleção é gravada na hora e não "
            "altera as cores personalizadas do núcleo.")
        cartao = GlassCard(
            "Tema do dashboard",
            "O tema Escuro é o padrão para quem ainda não escolheu. Use Tab para "
            "chegar às opções e Enter ou Espaço para trocar.")
        self.tema_status = StatusLabel(cartao)
        self.theme_cards: dict[str, ThemeCard] = {}
        self._grade_temas = QGridLayout()
        self._grade_temas.setSpacing(12)
        self._grade_temas.setColumnStretch(0, 1)
        self._grade_temas.setColumnStretch(1, 1)
        card_escuro = ThemeCard("escuro", "Escuro",
                                "Fundo azul-noite e destaque ciano.", cartao)
        card_claro = ThemeCard("claro", "Claro",
                               "Fundo claro e destaque petróleo.", cartao)
        self.theme_cards = {"escuro": card_escuro, "claro": card_claro}
        self._grupo_temas = QButtonGroup(self)
        self._grupo_temas.setExclusive(True)
        for card in (card_escuro, card_claro):
            self._grupo_temas.addButton(card)
        self._grade_temas.addWidget(card_escuro, 0, 0)
        self._grade_temas.addWidget(card_claro, 0, 1)
        card_escuro._vizinho = lambda direita: self._mover_tema(-1 if not direita else 1)
        card_claro._vizinho = lambda direita: self._mover_tema(1 if direita else -1)
        for nome, card in self.theme_cards.items():
            card.clicked.connect(lambda _=False, n=nome: self.escolher_tema(n))
        cartao.body.addLayout(self._grade_temas)
        cartao.body.addWidget(self.tema_status)
        layout.addWidget(cartao)

        layout.addWidget(self._construir_cartao_nucleo(pagina))
        layout.addWidget(self._construir_cartao_cores(pagina))
        layout.addWidget(self._construir_cartao_nomes(pagina))
        layout.addWidget(self._construir_cartao_interface(pagina))
        layout.addStretch(1)
        self._achatar_controles(pagina)
        self._previa_timer = QTimer(self)
        self._previa_timer.timeout.connect(self._quadro_previa)
        self._previa_t_ant = time.monotonic()
        return pagina

    def _achatar_controles(self, pai: QWidget) -> None:
        """Evita que rótulos e campos imponham largura mínima na página."""
        for cartao in pai.findChildren(GlassCard):
            cartao.setMinimumWidth(0)
            politica = cartao.sizePolicy()
            politica.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
            cartao.setSizePolicy(politica)
        for controle in pai.findChildren(
                (QComboBox, QLineEdit, QSpinBox, QSlider, QPushButton)):
            if isinstance(controle, QComboBox):
                controle.setSizeAdjustPolicy(
                    QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                controle.setMinimumContentsLength(1)
            controle.setMinimumWidth(0)
            politica = controle.sizePolicy()
            politica.setHorizontalPolicy(QSizePolicy.Policy.Preferred)
            controle.setSizePolicy(politica)
        for rotulo in pai.findChildren(QLabel):
            rotulo.setMinimumWidth(0)
            if not rotulo.wordWrap():
                rotulo.setWordWrap(True)

    def _construir_cartao_nucleo(self, pai) -> GlassCard:
        import ui as ui_mod  # noqa: PLC0415
        cartao = GlassCard(
            "Núcleo e prévia",
            "Uma única prévia do formato escolhido. As fases são simuladas: "
            "nenhum microfone, voz ou modelo é acionado.", pai)
        self.nucleo_combo = QComboBox(cartao)
        self.nucleo_combo.setAccessibleName("Formato do núcleo")
        for nid, cfg in ui_mod._NUCLEOS.items():
            self.nucleo_combo.addItem(cfg.get("nome", nid), nid)
        salvo = ui_mod._nucleo_salvo()
        self.nucleo_combo.setCurrentIndex(
            max(0, self.nucleo_combo.findData(salvo)))
        self.nucleo_combo.currentIndexChanged.connect(self._nucleo_mudou)
        cartao.body.addWidget(_rotulo_secao("Formato", cartao))
        cartao.body.addWidget(self.nucleo_combo)

        self.nucleo_preview = _NucleoPreview(self._paleta, cartao)
        self.nucleo_preview.nome = self.nucleo_combo.currentText()
        cartao.body.addWidget(self.nucleo_preview)

        fases = QHBoxLayout()
        fases.setSpacing(6)
        self._grupo_fases = QButtonGroup(cartao)
        self._grupo_fases.setExclusive(True)
        self._botoes_fases = {}
        for fase, rotulo in (("repouso", "Repouso"), ("ouvindo", "Ouvindo"),
                             ("pensando", "Pensando"), ("falando", "Falando")):
            botao = QPushButton(rotulo, cartao)
            botao.setObjectName("Segment")
            botao.setCheckable(True)
            botao.setCursor(Qt.CursorShape.PointingHandCursor)
            botao.clicked.connect(lambda _=False, f=fase: self._simular_fase(f))
            self._grupo_fases.addButton(botao)
            self._botoes_fases[fase] = botao
            fases.addWidget(botao)
        fases.addStretch()
        self._botoes_fases["repouso"].setChecked(True)
        cartao.body.addLayout(fases)
        self.nucleo_status = StatusLabel(cartao)
        cartao.body.addWidget(self.nucleo_status)
        return cartao

    def _construir_cartao_cores(self, pai) -> GlassCard:
        from core import tema  # noqa: PLC0415
        cartao = GlassCard(
            "Cores do núcleo",
            "Independentes do tema do dashboard. A cor é aplicada à janela "
            "principal aberta assim que você confirma.", pai)
        self.cor_combo = QComboBox(cartao)
        self.cor_combo.setAccessibleName("Cor do núcleo")
        for titulo, itens in tema.GRUPOS:
            for chave, rotulo, _ in itens:
                self.cor_combo.addItem(f"{titulo} · {rotulo}", chave)
        self.cor_atual = self.cor_combo.currentData()
        self.cor_botao = QPushButton(cartao)
        self.cor_botao.setObjectName("CardAction")
        self.cor_botao.setAccessibleName("Escolher cor do núcleo")
        self.cor_botao.clicked.connect(self._escolher_cor)
        self.cor_hex = QLineEdit(cartao)
        self.cor_hex.setAccessibleName("Cor em hexadecimal")
        self.cor_hex.setPlaceholderText("#RRGGBB")
        self.cor_hex.editingFinished.connect(self._cor_digitada)
        self.cor_combo.currentIndexChanged.connect(self._mostrar_cor)
        linha = QHBoxLayout()
        linha.setSpacing(8)
        linha.addWidget(self.cor_combo, 2)
        linha.addWidget(self.cor_botao, 1)
        linha.addWidget(self.cor_hex, 1)
        cartao.body.addLayout(linha)
        botoes = QHBoxLayout()
        voltar = QPushButton("Original", cartao)
        voltar.setObjectName("Secondary")
        voltar.clicked.connect(self._voltar_cor)
        tudo = QPushButton("Restaurar todas", cartao)
        tudo.setObjectName("Secondary")
        tudo.clicked.connect(self._restaurar_cores)
        botoes.addWidget(voltar)
        botoes.addWidget(tudo)
        botoes.addStretch()
        cartao.body.addLayout(botoes)
        self.cor_status = StatusLabel(cartao)
        cartao.body.addWidget(self.cor_status)
        self._mostrar_cor()
        return cartao

    def _construir_cartao_nomes(self, pai) -> GlassCard:
        from core import nomes_tela  # noqa: PLC0415
        cartao = GlassCard(
            "Nomes da interface",
            "Os rótulos da janela principal mudam ao vivo. Gravação ao sair "
            "do campo, sem duplicar a gravação do Enter.", pai)
        self._nomes_salvo: dict[str, str] = {}
        self._nomes_campos: dict[str, QLineEdit] = {}
        self._nome_timer = QTimer(self)
        self._nome_timer.setSingleShot(True)
        self._nome_timer.setInterval(300)
        self._nome_timer.timeout.connect(self._salvar_nome_pendente)
        self._nome_pendente = None
        atual = self._service.carregar_nomes()
        grade = QGridLayout()
        grade.setHorizontalSpacing(12)
        grade.setVerticalSpacing(8)
        for indice, (chave, rotulo, padrao, maximo) in enumerate(nomes_tela.CAMPOS):
            campo = QLineEdit(str(atual.get(chave, "") or ""), cartao)
            campo.setMaxLength(maximo)
            campo.setPlaceholderText(str(padrao))
            campo.setAccessibleName(str(rotulo))
            self._nomes_campos[chave] = campo
            self._nomes_salvo[chave] = campo.text()
            campo.textChanged.connect(
                lambda _t, c=chave, w=campo: self._nome_alterou(c, w))
            campo.editingFinished.connect(
                lambda c=chave, w=campo: self._salvar_nome(c, w, imediato=True))
            linha, coluna = indice % 8, (indice // 8) * 2
            grade.addWidget(QLabel(str(rotulo), cartao), linha, coluna)
            grade.addWidget(campo, linha, coluna + 1)
        cartao.body.addLayout(grade)
        voltar = QPushButton("Restaurar nomes", cartao)
        voltar.setObjectName("Secondary")
        voltar.clicked.connect(self._voltar_nomes)
        cartao.body.addWidget(voltar)
        self.nomes_status = StatusLabel(cartao)
        cartao.body.addWidget(self.nomes_status)
        return cartao

    def _construir_cartao_interface(self, pai) -> GlassCard:
        from core.interface_canvas import (DEFAULT_APPEARANCE, DockPreferences,
                                           appearance_settings, CanvasBackground)
        cartao = GlassCard(
            "Fundo e dock",
            "As mudanças aparecem na prévia durante o ajuste e são gravadas "
            "ao concluir. Ordem, itens ocultos e atalhos são preservados.", pai)
        self._dock_prefs = DockPreferences(self._service.interface_path)
        self._appearance = appearance_settings(self._dock_prefs.data)
        self.fundo_preview = CanvasBackground(
            preferences=self._dock_prefs.data, parent=cartao)
        self.fundo_preview.setMinimumHeight(150)
        self.fundo_preview.set_appearance(self._appearance)
        cartao.body.addWidget(self.fundo_preview)

        self.cor_fundo_botao = QPushButton(cartao)
        self.cor_fundo_botao.setObjectName("CardAction")
        self.cor_fundo_botao.clicked.connect(self._escolher_fundo)
        cartao.body.addWidget(self.cor_fundo_botao)
        self._atualizar_cor_fundo()

        brilho_linha = QHBoxLayout()
        brilho_linha.addWidget(_rotulo_secao("Luminosidade", cartao))
        self.brilho = QSlider(Qt.Orientation.Horizontal, cartao)
        self.brilho.setRange(40, 160)
        self.brilho.setValue(self._appearance["brightness"])
        self.brilho.setAccessibleName("Luminosidade do fundo")
        self.brilho_valor = QLabel(cartao)
        self.brilho_valor.setObjectName("Hint")
        self.brilho.sliderMoved.connect(self._brilho_previa)
        self.brilho.sliderReleased.connect(self._brilho_salvar)
        brilho_linha.addWidget(self.brilho, 1)
        brilho_linha.addWidget(self.brilho_valor)
        cartao.body.addLayout(brilho_linha)
        self._atualizar_brilho()

        tamanhos = QHBoxLayout()
        self.icone_tamanho = QSpinBox(cartao)
        self.icone_tamanho.setRange(18, 40)
        self.icone_tamanho.setSuffix(" px")
        self.icone_tamanho.setValue(self._appearance["icon_size"])
        self.icone_tamanho.setAccessibleName("Tamanho dos ícones do dock")
        self.dock_altura = QSpinBox(cartao)
        self.dock_altura.setRange(240, 900)
        self.dock_altura.setSingleStep(10)
        self.dock_altura.setSuffix(" px")
        self.dock_altura.setValue(self._appearance["dock_height"])
        self.dock_altura.setAccessibleName("Altura do dock")
        self.icone_tamanho.valueChanged.connect(self._dock_previa)
        self.dock_altura.valueChanged.connect(self._dock_previa)
        self.icone_tamanho.editingFinished.connect(self._dock_salvar)
        self.dock_altura.editingFinished.connect(self._dock_salvar)
        tamanhos.addWidget(_rotulo_secao("Ícones", cartao))
        tamanhos.addWidget(self.icone_tamanho)
        tamanhos.addWidget(_rotulo_secao("Altura", cartao))
        tamanhos.addWidget(self.dock_altura)
        tamanhos.addStretch()
        cartao.body.addLayout(tamanhos)

        from PyQt6.QtWidgets import QCheckBox
        self.janela_sem_bordas = QCheckBox(
            "Janela sem bordas do Windows (ainda maximizada, com barra de tarefas)",
            cartao)
        self.janela_sem_bordas.setObjectName("janela_sem_bordas")
        self.janela_sem_bordas.setChecked(
            self._dock_prefs.data.get("janela_sem_bordas", True))
        self.janela_sem_bordas.setToolTip(
            "Sem bordas no topo. Use o botão direito na janela para "
            "minimizar, maximizar, arrastar ou reduzir.")
        self.janela_sem_bordas.toggled.connect(self._janela_modo_salvar)
        cartao.body.addWidget(self.janela_sem_bordas)

        cartao.body.addWidget(_rotulo_secao("Ferramentas do dock", cartao))
        self.dock_lista = QListWidget(cartao)
        self.dock_lista.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.dock_lista.setAccessibleName("Ordem e visibilidade das ferramentas")
        self._preencher_dock_lista()
        self.dock_lista.model().rowsMoved.connect(lambda *_: self._salvar_ordem_dock())
        self.dock_lista.itemChanged.connect(lambda *_: self._salvar_ordem_dock())
        cartao.body.addWidget(self.dock_lista)
        acoes = QHBoxLayout()
        for rotulo, acao in (("Subir", lambda: self._mover_dock(-1)),
                             ("Descer", lambda: self._mover_dock(1)),
                             ("Adicionar app", self._adicionar_app),
                             ("Remover app", self._remover_app)):
            botao = QPushButton(rotulo, cartao)
            botao.setObjectName("CardAction")
            botao.clicked.connect(acao)
            acoes.addWidget(botao)
        acoes.addStretch()
        cartao.body.addLayout(acoes)
        restaurar = QPushButton("Restaurar padrão", cartao)
        restaurar.setObjectName("Secondary")
        restaurar.clicked.connect(self._restaurar_interface)
        cartao.body.addWidget(restaurar)

        cartao.body.addWidget(_rotulo_secao("Cartão Hoje e resumo", cartao))
        self.hoje_visivel_check = QCheckBox(
            "Mostrar o cartão Hoje no Canvas", cartao)
        self.hoje_visivel_check.setChecked(self._service.hoje_visivel())
        self.hoje_visivel_check.toggled.connect(self._hoje_visibilidade_mudou)
        cartao.body.addWidget(self.hoje_visivel_check)
        self.resumo_auto_check = QCheckBox(
            "Ler o resumo automaticamente no horário agendado", cartao)
        self.resumo_auto_check.setChecked(
            self._service.resumo_leitura_automatica())
        self.resumo_auto_check.toggled.connect(self._resumo_auto_mudou)
        cartao.body.addWidget(self.resumo_auto_check)
        self.resumo_voz_externa_check = QCheckBox(
            "Permitir voz externa na leitura do resumo", cartao)
        self.resumo_voz_externa_check.setChecked(
            self._service.resumo_voz_externa())
        self.resumo_voz_externa_check.toggled.connect(
            self._resumo_voz_externa_mudou)
        cartao.body.addWidget(self.resumo_voz_externa_check)

        self.interface_status = StatusLabel(cartao)
        cartao.body.addWidget(self.interface_status)
        return cartao

    # ── aparência: prévia, cores, nomes, fundo e dock ──────────────────────
    def _pausar_previa_nucleo(self) -> None:
        timer = getattr(self, "_previa_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()

    def _atualizar_previa_nucleo(self) -> None:
        if self._fechado or self.isMinimized() or self._pagina != 1:
            return
        timer = getattr(self, "_previa_timer", None)
        if timer is None:
            return
        self._previa_t_ant = time.monotonic()
        if not timer.isActive():
            timer.start(45)

    def _quadro_previa(self) -> None:
        if self._fechado or self._pagina != 1 or self.isMinimized():
            self._pausar_previa_nucleo()
            return
        agora = time.monotonic()
        dt = max(0.005, min(0.08, agora - self._previa_t_ant))
        self._previa_t_ant = agora
        self.nucleo_preview.avancar(dt)

    def _simular_fase(self, fase: str) -> None:
        if not hasattr(self, "nucleo_preview"):
            return
        self.nucleo_preview.fase = fase
        self.nucleo_preview.update()
        self.nucleo_status.mostrar(
            f"Prévia em {fase}. Nenhum áudio, voz ou modelo foi acionado.",
            "info")

    def _nucleo_mudou(self) -> None:
        nid = self.nucleo_combo.currentData()
        if not nid:
            return
        import ui as ui_mod  # noqa: PLC0415
        self.nucleo_preview.nome = self.nucleo_combo.currentText()
        salvo = bool(ui_mod._gravar_nucleo(nid))
        janela = self._janela_principal()
        hud = getattr(janela, "hud", None)
        aplicado = False
        if hud is not None and hasattr(hud, "trocar_nucleo"):
            try:
                hud.trocar_nucleo(nid, gravar=False)
                aplicado = True
            except Exception:
                aplicado = False
        if salvo and aplicado:
            self.nucleo_status.mostrar("Salvo", "success")
        elif salvo:
            self.nucleo_status.mostrar(
                "Salvo. A janela principal usará o formato ao reabrir.",
                "warning")
        else:
            self.nucleo_status.mostrar(
                "Não foi possível salvar o formato do núcleo.", "error")

    def _mostrar_cor(self) -> None:
        from core import tema  # noqa: PLC0415
        chave = self.cor_combo.currentData()
        self.cor_atual = chave
        cor = str(tema.atual(chave) or "")
        self.cor_botao.setText(cor or "Sem cor personalizada")
        self.cor_hex.setText(cor)

    def _escolher_cor(self) -> None:
        from core import tema  # noqa: PLC0415
        chave = self.cor_atual
        atual = QColor(str(tema.atual(chave) or "#63DAF0"))
        escolhida = QColorDialog.getColor(atual, self, "Cor do núcleo")
        if escolhida.isValid():
            self._aplicar_cor(chave, escolhida.name())

    def _cor_digitada(self) -> None:
        from core import tema  # noqa: PLC0415
        valor = tema.normalizar(self.cor_hex.text())
        if valor is None:
            self.cor_status.mostrar("Informe uma cor #RRGGBB.", "warning")
            return
        self._aplicar_cor(self.cor_atual, valor)

    def _aplicar_cor(self, chave, valor) -> None:
        from core import tema  # noqa: PLC0415
        try:
            tema.definir(chave, valor)
            self._service.aplicar_tema_no_nucleo()
            self._mostrar_cor()
            self.cor_status.mostrar("Salvo", "success")
        except Exception as exc:
            self.cor_status.mostrar(
                f"Não foi possível salvar: {type(exc).__name__}.", "error")

    def _voltar_cor(self) -> None:
        self._aplicar_cor(self.cor_atual, None)
        self.cor_botao.setText("Sem cor personalizada")

    def _restaurar_cores(self) -> None:
        from core import tema  # noqa: PLC0415
        try:
            tema.restaurar_tudo()
            self._service.aplicar_tema_no_nucleo()
            self._mostrar_cor()
            self.cor_status.mostrar("Salvo · cores restauradas.", "success")
        except Exception as exc:
            self.cor_status.mostrar(
                f"Não foi possível restaurar: {type(exc).__name__}.", "error")

    def _nome_alterou(self, chave: str, campo: QLineEdit) -> None:
        self._nome_pendente = (chave, campo)
        self._nome_timer.start()

    def _salvar_nome_pendente(self) -> None:
        pendente = getattr(self, "_nome_pendente", None)
        if pendente is None:
            return
        self._nome_pendente = None
        self._salvar_nome(*pendente)

    def _salvar_nome(self, chave: str, campo: QLineEdit,
                     imediato: bool = False) -> None:
        if imediato:
            self._nome_timer.stop()
            self._nome_pendente = None
        texto = campo.text()
        if self._nomes_salvo.get(chave) == texto:
            return
        self._nomes_salvo[chave] = texto
        try:
            self._service.salvar_nomes({chave: texto})
            self._service.aplicar_nomes()
            self.nomes_status.mostrar("Salvo", "success")
        except Exception as exc:
            self._nomes_salvo[chave] = None
            self.nomes_status.mostrar(
                f"Não foi possível salvar: {type(exc).__name__}.", "error")

    def _voltar_nomes(self) -> None:
        try:
            self._service.restaurar_nomes()
            self._service.aplicar_nomes()
            for chave, campo in self._nomes_campos.items():
                campo.blockSignals(True)
                campo.setText(str(self._service.carregar_nomes().get(chave, "")))
                campo.blockSignals(False)
                self._nomes_salvo[chave] = campo.text()
            self.nomes_status.mostrar("Salvo · nomes restaurados.", "success")
        except Exception as exc:
            self.nomes_status.mostrar(
                f"Não foi possível restaurar: {type(exc).__name__}.", "error")

    def _atualizar_cor_fundo(self) -> None:
        self.cor_fundo_botao.setText(
            f"Cor principal: {self._appearance['background_color'].upper()}")
        self.fundo_preview.set_appearance(self._appearance)

    def _escolher_fundo(self) -> None:
        atual = QColor(self._appearance["background_color"])
        escolhida = QColorDialog.getColor(atual, self, "Cor principal do fundo")
        if not escolhida.isValid():
            return
        self._appearance["background_color"] = escolhida.name()
        self._atualizar_cor_fundo()
        self._aplicar_interface({"appearance": dict(self._appearance)})

    def _atualizar_brilho(self) -> None:
        valor = int(self.brilho.value())
        self.brilho_valor.setText(f"{valor}%")

    def _brilho_previa(self, valor: int) -> None:
        self._appearance["brightness"] = int(valor)
        self._atualizar_brilho()
        self.fundo_preview.set_appearance(self._appearance)

    def _brilho_salvar(self) -> None:
        self._appearance["brightness"] = int(self.brilho.value())
        self._aplicar_interface({"appearance": dict(self._appearance)})

    def _dock_previa(self) -> None:
        self._appearance["icon_size"] = int(self.icone_tamanho.value())
        self._appearance["dock_height"] = int(self.dock_altura.value())
        self.fundo_preview.set_appearance(self._appearance)

    def _janela_modo_salvar(self, marcado: bool) -> None:
        self._aplicar_interface({"janela_sem_bordas": bool(marcado)})
        janela = self._janela_principal()
        aplicar = getattr(janela, "aplicar_modo_janela", None) if janela else None
        if aplicar is not None:
            try:
                aplicar(bool(marcado))
            except Exception:
                pass

    def _dock_salvar(self) -> None:
        self._appearance["icon_size"] = int(self.icone_tamanho.value())
        self._appearance["dock_height"] = int(self.dock_altura.value())
        self._aplicar_interface({"appearance": dict(self._appearance)})

    def _rotulo_dock(self, chave: str) -> str:
        janela = self._janela_principal()
        dock = getattr(janela, "_right_panel", None) if janela else None
        botao = getattr(dock, "buttons", {}).get(chave) if dock else None
        return str(botao.toolTip() or chave) if botao is not None else chave

    def _preencher_dock_lista(self) -> None:
        self.dock_lista.blockSignals(True)
        self.dock_lista.clear()
        entradas = list(self._dock_prefs.data.get("order") or [])
        janela = self._janela_principal()
        dock = getattr(janela, "_right_panel", None) if janela else None
        extras = list(getattr(dock, "buttons", {}) or {})
        extras += list(self._dock_prefs.data.get("apps") or [])
        for extra in extras:
            if extra not in entradas:
                entradas.append(extra)
        ocultos = set(self._dock_prefs.data.get("hidden") or [])
        for chave in entradas:
            item = QListWidgetItem(self._rotulo_dock(chave))
            item.setData(Qt.ItemDataRole.UserRole, chave)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Unchecked if chave in ocultos
                else Qt.CheckState.Checked)
            self.dock_lista.addItem(item)
        self.dock_lista.blockSignals(False)

    def _dock_lista_estado(self) -> tuple[list[str], list[str], list[str]]:
        chaves, visiveis, ocultos = [], [], []
        for i in range(self.dock_lista.count()):
            item = self.dock_lista.item(i)
            chave = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if not chave:
                continue
            chaves.append(chave)
            (visiveis if item.checkState() == Qt.CheckState.Checked
             else ocultos).append(chave)
        return chaves, visiveis, ocultos

    def _salvar_ordem_dock(self) -> None:
        chaves, _, ocultos = self._dock_lista_estado()
        janela = self._janela_principal()
        dock = getattr(janela, "_right_panel", None) if janela else None
        if dock is None:
            apps = list(self._dock_prefs.data.get("apps") or [])
        else:
            apps = [c for c in chaves if c not in getattr(dock, "buttons", {})]
        self._aplicar_interface({"order": chaves,
                                 "apps": apps,
                                 "hidden": ocultos},
                                "Salvo · dock atualizado.")

    def _mover_dock(self, delta: int) -> None:
        atual = self.dock_lista.currentRow()
        alvo = atual + delta
        if atual < 0 or not (0 <= alvo < self.dock_lista.count()):
            return
        self.dock_lista.insertItem(alvo, self.dock_lista.takeItem(atual))
        self.dock_lista.setCurrentRow(alvo)
        self._salvar_ordem_dock()

    def _adicionar_app(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "Escolher aplicativo")
        if not caminho:
            return
        item = QListWidgetItem(caminho.replace("\\", "/").rsplit("/", 1)[-1])
        item.setData(Qt.ItemDataRole.UserRole, caminho)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        self.dock_lista.addItem(item)
        self._salvar_ordem_dock()

    def _remover_app(self) -> None:
        item = self.dock_lista.currentItem()
        if item is None:
            return
        janela = self._janela_principal()
        dock = getattr(janela, "_right_panel", None) if janela else None
        if str(item.data(Qt.ItemDataRole.UserRole)) in getattr(dock, "buttons", {}):
            self.interface_status.mostrar(
                "Ferramentas fixas não podem ser removidas; oculte-as.", "warning")
            return
        self.dock_lista.takeItem(self.dock_lista.currentRow())
        self._salvar_ordem_dock()

    def _restaurar_interface(self) -> None:
        from core.interface_canvas import DEFAULT_APPEARANCE  # noqa: PLC0415
        self._appearance = dict(DEFAULT_APPEARANCE)
        self.brilho.setValue(self._appearance["brightness"])
        self.icone_tamanho.setValue(self._appearance["icon_size"])
        self.dock_altura.setValue(self._appearance["dock_height"])
        self._atualizar_cor_fundo()
        self._aplicar_interface({"appearance": dict(self._appearance)},
                                "Salvo · aparência restaurada.")

    def _hoje_visibilidade_mudou(self, ligado: bool) -> None:
        try:
            self._service.salvar_hoje_visivel(ligado)
            alterar = getattr(self._service.host, 'set_hoje_visivel', None)
            if alterar is not None:
                alterar(ligado)
        except Exception as exc:
            self.interface_status.mostrar(
                f'Não foi possível salvar: {type(exc).__name__}.', 'error')
            return
        self.interface_status.mostrar('Salvo', 'success')

    def _resumo_auto_mudou(self, ligado: bool) -> None:
        try:
            self._service.salvar_resumo_leitura_automatica(ligado)
        except Exception as exc:
            self.interface_status.mostrar(
                f'Não foi possível salvar: {type(exc).__name__}.', 'error')
            return
        self.interface_status.mostrar('Salvo', 'success')

    def _resumo_voz_externa_mudou(self, ligado: bool) -> None:
        try:
            self._service.salvar_resumo_voz_externa(ligado)
        except Exception as exc:
            self.interface_status.mostrar(
                f'Não foi possível salvar: {type(exc).__name__}.', 'error')
            return
        self.interface_status.mostrar('Salvo', 'success')

    def _aplicar_interface(self, mudancas: dict,
                           mensagem: str = "Salvo") -> None:
        from core.interface_canvas import (DockPreferences,  # noqa: PLC0415
                                           appearance_settings)
        try:
            prefs = DockPreferences(self._service.interface_path)
            prefs.data.update(mudancas)
            prefs.save()
        except Exception as exc:
            self.interface_status.mostrar(
                f"Não foi possível salvar: {type(exc).__name__}.", "error")
            return
        self._dock_prefs = prefs
        self._appearance = appearance_settings(prefs.data)
        try:
            janela = self._janela_principal()
            dock = getattr(janela, "_right_panel", None) if janela else None
            if dock is not None:
                dock.preferences.data.update(mudancas)
                dock.apply()
            central = None
            if janela is not None and hasattr(janela, "centralWidget"):
                central = janela.centralWidget()
            aplicar = getattr(central, "set_appearance", None)
            if aplicar is not None:
                aplicar(self._appearance)
        except Exception as exc:
            self.interface_status.mostrar(
                f"Salvo, mas não foi possível aplicar ao vivo: "
                f"{type(exc).__name__}.", "warning")
            return
        self.interface_status.mostrar(mensagem, "success")

    # ── valores e controles ────────────────────────────────────────────────
    def _aplicar_valores(self) -> None:
        dados = self._service.carregar_persona()
        self._dados = dados
        self._atualizar_itens_voz()
        self._selecionar(self.voice_combo, dados.get("personagem"))
        self._selecionar(self.personality_combo, dados.get("personalidade"))
        self._atualizar_textos_voz()
        self._carregar_alias()
        self._renderizar_microfones(dados)
        self._renderizar_saidas(dados)

    def _atualizar_itens_voz(self) -> None:
        """Reflete apelidos recém-gravados no texto do seletor, sem sinalizar."""
        atual = self.voice_combo.currentData()
        self.voice_combo.blockSignals(True)
        for i in range(self.voice_combo.count()):
            chave = self.voice_combo.itemData(i)
            item = PERSONAGENS.get(chave) or {}
            nome = nome_da_ia(chave)
            oficial = item.get("nome", chave)
            self.voice_combo.setItemText(
                i, f"{nome}  ·  voz {oficial}" if nome != oficial else oficial)
            self.voice_combo.setItemData(i, item.get("desc", ""),
                                         Qt.ItemDataRole.ToolTipRole)
        indice = self.voice_combo.findData(atual)
        if indice >= 0:
            self.voice_combo.setCurrentIndex(indice)
        self.voice_combo.blockSignals(False)

    @staticmethod
    def _selecionar(combo: QComboBox, valor) -> None:
        combo.blockSignals(True)
        indice = combo.findData(valor)
        if indice >= 0:
            combo.setCurrentIndex(indice)
        combo.blockSignals(False)

    def _atualizar_textos_voz(self) -> None:
        chave = self.voice_combo.currentData()
        item = PERSONAGENS.get(chave) or {}
        self.voice_hint.setText(item.get("desc", ""))
        p_chave = self.personality_combo.currentData()
        p_item = PERSONALIDADES.get(p_chave) or {}
        self.personality_hint.setText(p_item.get("desc", ""))
        nome = nome_da_ia(chave) if chave else "NIA"
        self.voice_combo.setToolTip(f"{nome} · {item.get('desc', '')}")
        self.personality_combo.setToolTip(p_item.get("desc", ""))

    def _carregar_alias(self) -> None:
        chave = self.voice_combo.currentData()
        if not chave:
            return
        apelido = nome_da_ia(chave)
        original = nome_original(chave)
        self.alias_edit.blockSignals(True)
        self.alias_edit.setPlaceholderText(original)
        self.alias_edit.setText("" if apelido == original else apelido)
        self.alias_edit.blockSignals(False)

    def _voz_mudou(self) -> None:
        chave = self.voice_combo.currentData()
        self._atualizar_textos_voz()
        self._carregar_alias()
        if chave:
            self._alterar("personagem", chave, self.voice_status,
                          ao_falhar=self._sincronizar_combo_voz)

    def _personalidade_mudou(self) -> None:
        chave = self.personality_combo.currentData()
        self._atualizar_textos_voz()
        if chave:
            self._alterar("personalidade", chave, self.personality_status,
                          ao_falhar=self._sincronizar_combo_personalidade)

    def _salvar_alias(self) -> None:
        if self._fechado or not self.alias_edit.isEnabled():
            return
        chave = self.voice_combo.currentData()
        if not chave:
            return
        texto = self.alias_edit.text().strip()
        apelido = nome_da_ia(chave)
        original = nome_original(chave)
        atual = "" if apelido == original else apelido
        if texto == atual:
            return
        pendente = (chave, texto)
        if self._alias_pendente == pendente:
            # Enter e perda de foco podem disparar `editingFinished` duas vezes
            # antes de a gravação terminar: o segundo pedido é o mesmo.
            return
        self._alias_pendente = pendente
        self.alias_status.mostrar("Salvando…", "info")

        def terminou(resultado):
            if self._alias_pendente == pendente:
                self._alias_pendente = None
            if self._fechado or self.voice_combo.currentData() != chave:
                return
            self._mostrar_resultado(self.alias_status, resultado)
            if resultado.get("salvo"):
                self._atualizar_itens_voz()
                self._carregar_alias()

        self._executar(
            lambda: self._service.alterar("apelido", (chave, texto)),
            terminou)

    def _ouvir_voz(self) -> None:
        chave = self.voice_combo.currentData()
        if not chave:
            return
        self.voice_status.mostrar("Tocando a voz selecionada…", "info")

        def terminou(resultado):
            if self._fechado or self.voice_combo.currentData() != chave:
                return
            if resultado.get("aplicado"):
                nome = nome_da_ia(chave)
                aviso = str(resultado.get("aviso") or "").strip()
                if aviso:
                    self.voice_status.mostrar(f"A voz {nome} foi aplicada. {aviso.capitalize()}.",
                                              "warning")
                else:
                    self.voice_status.mostrar(f"Pronto. Você ouviu a voz {nome}.", "success")
            else:
                erro = str(resultado.get("erro") or "tente de novo").strip()
                self.voice_status.mostrar(
                    f"Não foi possível tocar a voz agora: {erro}. "
                    "Verifique a conexão e tente de novo.", "error")

        self._executar(lambda: self._service.ouvir_voz(chave), terminou)

    def _microfone_mudou(self) -> None:
        self._mic_teste_seq += 1
        valor = normalizar_dispositivo(self.mic_combo.currentData())
        self._alterar("microfone", valor, self.mic_status,
                      ao_falhar=self._sincronizar_selecoes)

    def _saida_mudou(self) -> None:
        self._saida_teste_seq += 1
        valor = normalizar_dispositivo(self.saida_combo.currentData())
        self._alterar("saida", valor, self.saida_status,
                      ao_falhar=self._sincronizar_selecoes)

    def _alterar(self, tipo: str, chave, status: StatusLabel, ao_falhar=None,
                 forcar: bool = False, ao_terminar=None) -> None:
        status.mostrar("Salvando…", "info")

        def terminou(resultado):
            if self._fechado:
                return
            if not isinstance(resultado, dict):
                resultado = {"salvo": False, "aplicado": False,
                             "erro": "resposta inesperada do motor"}
            self._mostrar_resultado(status, resultado)
            if not resultado.get("salvo") and ao_falhar is not None:
                ao_falhar()
            if ao_terminar is not None:
                ao_terminar(resultado)

        self._executar(
            lambda: self._service.alterar(tipo, chave, forcar=forcar),
            terminou)

    def _mostrar_resultado(self, status: StatusLabel, resultado: dict) -> None:
        salvo = bool(resultado.get("salvo"))
        aplicado = bool(resultado.get("aplicado"))
        aviso = str(resultado.get("aviso") or "").strip()
        erro = str(resultado.get("erro") or "").strip()
        if salvo and aplicado:
            if aviso:
                status.mostrar(f"Salvo. {aviso.capitalize()}.", "warning")
            else:
                status.mostrar("Salvo", "success")
        elif salvo and not aplicado:
            detalhe = f": {erro}" if erro else "."
            status.mostrar(
                f"Salvo, mas não foi possível aplicar ao vivo{detalhe} "
                "A escolha será usada ao reabrir a NIA.", "warning")
        else:
            detalhe = f": {erro}" if erro else "."
            status.mostrar(
                f"Não foi possível salvar{detalhe} Verifique a permissão da "
                "pasta config e tente de novo.", "error")

    def _sincronizar_combo_voz(self) -> None:
        dados = self._service.carregar_persona()
        self._selecionar(self.voice_combo, dados.get("personagem"))
        self._atualizar_textos_voz()
        self._carregar_alias()

    def _sincronizar_combo_personalidade(self) -> None:
        dados = self._service.carregar_persona()
        self._selecionar(self.personality_combo, dados.get("personalidade"))
        self._atualizar_textos_voz()

    def _sincronizar_selecoes(self) -> None:
        dados = self._service.carregar_persona()
        self._selecionar(self.voice_combo, dados.get("personagem"))
        self._selecionar(self.personality_combo, dados.get("personalidade"))
        self._atualizar_textos_voz()
        self._carregar_alias()
        self._renderizar_microfones(dados)
        self._renderizar_saidas(dados)

    # ── dispositivos ───────────────────────────────────────────────────────
    def atualizar_dispositivos(self) -> None:
        if self._fechado:
            return
        self._mic_teste_seq += 1
        self._saida_teste_seq += 1
        self.devices_status.mostrar("Atualizando dispositivos…", "info")

        def terminou(resultado):
            if self._fechado:
                return
            if not isinstance(resultado, tuple) or len(resultado) != 2:
                erro = ""
                if isinstance(resultado, dict):
                    erro = str(resultado.get("erro") or resultado.get("__excecao__") or "")
                detalhe = f": {erro}" if erro else "."
                self.devices_status.mostrar(
                    f"Não foi possível listar os dispositivos{detalhe} "
                    "Verifique o driver de áudio e clique em Atualizar dispositivos.",
                    "error")
                return
            self._microfones, self._saidas = resultado
            dados = self._service.carregar_persona()
            self._renderizar_microfones(dados)
            self._renderizar_saidas(dados)
            self.devices_status.mostrar("Lista atualizada. A preferência gravada não mudou.",
                                        "info")

        self._executar(
            lambda: (self._service.listar_microfones(), self._service.listar_saidas()),
            terminou)

    def _renderizar_microfones(self, dados: dict) -> None:
        self._preencher_dispositivo(self.mic_combo, self._microfones,
                                    dados.get("microfone"), "Microfone")

    def _renderizar_saidas(self, dados: dict) -> None:
        self._preencher_dispositivo(self.saida_combo, self._saidas,
                                    dados.get("saida"), "Saída")

    @staticmethod
    def _preencher_dispositivo(combo: QComboBox, lista: list[dict], salvo,
                               prefixo: str) -> None:
        alvo = normalizar_dispositivo(salvo)
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Padrão do Windows", None)
        combo.setItemData(0, "Deixa o Windows escolher o dispositivo.",
                          Qt.ItemDataRole.ToolTipRole)
        encontrados = set()
        for aparelho in lista or []:
            indice = aparelho.get("indice")
            encontrados.add(indice)
            nome = str(aparelho.get("nome") or f"{prefixo} {indice}")
            api = str(aparelho.get("api") or "").strip()
            texto = f"{nome}  ·  {api}" if api else nome
            combo.addItem(texto, indice)
            pos = combo.count() - 1
            combo.setItemData(pos, texto, Qt.ItemDataRole.ToolTipRole)
        if alvo is not None and alvo not in encontrados:
            combo.addItem(f"Dispositivo salvo (indisponível)  ·  índice {alvo}", alvo)
            pos = combo.count() - 1
            combo.setItemData(
                pos,
                "O aparelho escolhido não está disponível agora. A preferência "
                "foi preservada; escolha outro ou clique em Atualizar dispositivos.",
                Qt.ItemDataRole.ToolTipRole)
        indice = combo.findData(alvo)
        combo.setCurrentIndex(indice if indice >= 0 else 0)
        combo.blockSignals(False)
        if alvo is not None and alvo not in encontrados:
            combo.setToolTip(
                f"O dispositivo salvo (índice {alvo}) não está disponível. "
                "A preferência continua gravada.")
        else:
            combo.setToolTip("")

    def _testar_microfone(self) -> None:
        indice = normalizar_dispositivo(self.mic_combo.currentData())
        self._mic_teste_seq += 1
        seq = self._mic_teste_seq
        self.mic_status.mostrar("Testando microfone…", "info")

        def terminou(resultado):
            if self._fechado or seq != self._mic_teste_seq:
                return
            if normalizar_dispositivo(self.mic_combo.currentData()) != indice:
                return
            if not isinstance(resultado, dict):
                resultado = {"ok": False, "erro": "resposta inesperada"}
            if resultado.get("ok"):
                blocos = int(resultado.get("blocos") or 0)
                nivel = float(resultado.get("nivel") or 0.0)
                self.mic_status.mostrar(
                    f"Microfone respondeu: {blocos} blocos, nível {nivel:.0f}.", "success")
            else:
                erro = str(resultado.get("erro") or "sem sinal").strip()
                self.mic_status.mostrar(
                    f"O microfone não respondeu: {erro}. Escolha outro dispositivo "
                    "ou feche programas que usam o microfone.", "error")

        self._executar(lambda: self._service.testar_microfone(indice), terminou)

    def _tocar_teste(self) -> None:
        indice = normalizar_dispositivo(self.saida_combo.currentData())
        self._saida_teste_seq += 1
        seq = self._saida_teste_seq
        self.saida_status.mostrar("Tocando o teste…", "info")

        def terminou(resultado):
            if self._fechado or seq != self._saida_teste_seq:
                return
            if normalizar_dispositivo(self.saida_combo.currentData()) != indice:
                return
            if not isinstance(resultado, dict):
                resultado = {"ok": False, "erro": "resposta inesperada"}
            if resultado.get("ok"):
                self.saida_status.mostrar(
                    "Teste enviado. Ouviu o som? Se não, escolha outra saída e "
                    "toque de novo.", "success")
            else:
                erro = str(resultado.get("erro") or "o aparelho não respondeu").strip()
                self.saida_status.mostrar(
                    f"O teste falhou: {erro}. Escolha outra saída ou clique em "
                    "Atualizar dispositivos.", "error")

        self._executar(lambda: self._service.tocar_teste(indice), terminou)

    # ── tema e navegação ───────────────────────────────────────────────────
    @property
    def tema(self) -> str:
        return self._tema_atual

    @property
    def pagina_atual(self) -> int:
        return self._pagina

    def escolher_tema(self, nome: str) -> bool:
        nome = str(nome or "").strip().lower()
        if nome not in TEMAS:
            return False
        if nome == self._tema_atual:
            self._sincronizar_tema()
            return True
        try:
            self._service.salvar_tema(nome)
        except Exception as exc:
            self._sincronizar_tema()
            self.tema_status.mostrar(
                f"Não foi possível salvar o tema: {type(exc).__name__}: "
                f"{str(exc)[:120]}. Verifique a permissão da pasta config.",
                "error")
            return False
        anterior = self._tema_atual
        self._tema_atual = nome
        self._paleta = PALETAS[nome]
        self._aplicar_tema_preservando_contexto()
        self.tema_status.mostrar("Salvo", "success")
        if anterior == nome:
            return True
        return True

    def _sincronizar_tema(self) -> None:
        for nome, card in self.theme_cards.items():
            card.blockSignals(True)
            card.setChecked(nome == self._tema_atual)
            card.blockSignals(False)

    def _aplicar_estilo(self) -> None:
        self.setStyleSheet(_qss(self._paleta))
        self._backdrop.set_paleta(self._paleta)
        self._indicador.set_paleta(self._paleta)
        self._atualizar_icones()
        self.update()

    def _atualizar_icones(self) -> None:
        cor_ativo = self._paleta["accent"]
        cor_inativo = self._paleta["muted"]
        for botao in self._nav_buttons:
            cor = cor_ativo if botao.isChecked() else cor_inativo
            botao.setIcon(icon(getattr(botao, "_icone_nome", "mic"), cor))
        self._marca_icone.setPixmap(icon("config", cor_ativo).pixmap(28, 28))

    def _aplicar_tema_preservando_contexto(self) -> None:
        pagina = self._stack.currentIndex()
        rolagens = [s.verticalScrollBar().value() for s in self._scrolls]
        foco = QApplication.focusWidget()
        self._sincronizar_tema()
        self._aplicar_estilo()
        self._stack.setCurrentIndex(pagina)
        self._pagina = pagina
        self._tema_restauracao = (pagina, rolagens, foco)
        QTimer.singleShot(0, self._restaurar_contexto_do_tema)

    def _restaurar_contexto_do_tema(self) -> None:
        if self._fechado or not self._tema_restauracao:
            return
        pagina, rolagens, foco = self._tema_restauracao
        self._tema_restauracao = None
        self._stack.setCurrentIndex(pagina)
        if foco is not None:
            try:
                if foco.window() is self:
                    foco.setFocus(Qt.FocusReason.OtherFocusReason)
            except RuntimeError:
                pass
        for rolagem, valor in zip(self._scrolls, rolagens):
            rolagem.verticalScrollBar().setValue(valor)
        self._posicionar_indicador(self._nav_buttons[pagina], animar=False)

    def _garantir_pagina_por_indice(self, indice: int) -> None:
        construtores = {
            2: ("provedores", self._garantir_pagina_provedores),
            3: ("geral", lambda: self._garantir_conteudo(
                "geral", self._construir_pagina_geral)),
            4: ("perfil", lambda: self._garantir_conteudo(
                "perfil", self._construir_pagina_perfil)),
            5: ("integracoes", lambda: self._garantir_conteudo(
                "integracoes", self._construir_pagina_integracoes)),
            6: ("documentos", lambda: self._garantir_conteudo(
                "documentos", self._construir_pagina_documentos)),
             7: ("habilidades", lambda: self._garantir_conteudo(
                 "habilidades", self._construir_pagina_habilidades)),
        }
        acao = construtores.get(indice)
        if acao is not None:
            acao[1]()

    def _ao_sair_da_pagina(self, indice: int) -> None:
        """Animações e consultas periódicas só rodam na página visível."""
        if indice == 1:
            self._pausar_previa_nucleo()
        if indice == 5 and hasattr(self, "_secretaria_widget"):
            self._pausar_timers_area(False)

    def _ao_entrar_na_pagina(self, indice: int) -> None:
        if indice == 1:
            self._atualizar_previa_nucleo()
        if indice == 5 and hasattr(self, "_secretaria_widget"):
            self._pausar_timers_area(True)

    def _ir_para_pagina(self, indice: int, animar: bool = True,
                        focar: bool = False) -> None:
        if not (0 <= indice < len(self._nav_buttons)):
            return
        anterior = getattr(self, "_pagina", 0)
        self._garantir_pagina_por_indice(indice)
        self._ao_sair_da_pagina(anterior)
        self._pagina = indice
        self._stack.setCurrentIndex(indice)
        self._ao_entrar_na_pagina(indice)
        botao = self._nav_buttons[indice]
        botao.blockSignals(True)
        botao.setChecked(True)
        botao.blockSignals(False)
        self._atualizar_icones()
        self._posicionar_indicador(botao, animar=animar)
        if focar:
            botao.setFocus(Qt.FocusReason.OtherFocusReason)

    def _mover_nav(self, delta: int) -> None:
        novo = max(0, min(len(self._nav_buttons) - 1, self._pagina + delta))
        self._ir_para_pagina(novo, focar=True)

    def _mover_tema(self, delta: int) -> None:
        ordem = ["escuro", "claro"]
        atual = ordem.index(self._tema_atual)
        alvo = ordem[max(0, min(1, atual + delta))]
        self.theme_cards[alvo].setFocus(Qt.FocusReason.OtherFocusReason)
        self.theme_cards[alvo].click()

    def _posicionar_indicador(self, botao: NavButton | None, animar: bool = True) -> None:
        if botao is None:
            botao = self._nav_buttons[self._pagina]
        ponto = botao.mapTo(self._nav_host, QPoint(0, 0))
        alvo = QRect(0, ponto.y(), self._nav_host.width(), botao.height())
        self._indicador.show()
        self._indicador.raise_()
        self._anim_indicador.stop()
        if animar and self._indicador.isVisible():
            self._anim_indicador.setStartValue(self._indicador.geometry())
            self._anim_indicador.setEndValue(alvo)
            self._anim_indicador.start()
        else:
            self._indicador.setGeometry(alvo)

    def activate_page(self, pagina) -> None:
        area_ollama = False
        area_integracoes = None
        if isinstance(pagina, str):
            texto = (pagina.strip().lower().replace("á", "a")
                     .replace("â", "a").replace("ã", "a").replace("é", "e")
                     .replace("í", "i").replace("ó", "o").replace("ú", "u"))
            if texto in ("provedores", "provedores e modelos", "apis", "api",
                         "chaves", "modelos", "ollama"):
                indice = 2
                area_ollama = texto == "ollama"
            elif texto in ("aparencia", "tema", "temas", "cores", "nomes",
                           "nucleo", "dock", "fundo"):
                indice = 1
            elif texto in ("geral", "inicio", "inicializacao", "saudacao"):
                indice = 3
            elif texto in ("perfil", "meu perfil", "dono", "sobre voce"):
                indice = 4
            elif texto in ("integracoes", "whatsapp", "secretaria", "remoto",
                           "celular", "ligacoes"):
                indice = 5
                area_integracoes = ("secretaria" if texto in
                                    ("secretaria", "ligacoes") else "conexoes")
            elif texto in ("documentos", "indice", "indice local", "busca local",
                           "arquivos", "fontes"):
                indice = 6
            elif texto in ("habilidades", "habilidade", "skills",
                           "acoes nativas"):
                indice = 7
            else:
                indice = 0
        else:
            indice = int(pagina)
        self._ir_para_pagina(indice, focar=True)
        if indice == 2 and self._painel_provedores is not None:
            self._painel_provedores.mostrar_area(
                "ollama" if area_ollama else "apis")
        if indice == 5 and area_integracoes is not None:
            self.mostrar_integracao(area_integracoes)

    # ── busca ───────────────────────────────────────────────────────────────
    def _focar_busca(self) -> None:
        if not self.busca_edit.isVisible():
            self.busca_edit.show()
        self.busca_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.busca_edit.selectAll()

    @staticmethod
    def _normalizar_busca(texto: str) -> str:
        return (str(texto or "").strip().casefold()
                .replace("á", "a").replace("â", "a").replace("ã", "a")
                .replace("é", "e").replace("ê", "e").replace("í", "i")
                .replace("ó", "o").replace("ô", "o").replace("õ", "o")
                .replace("ú", "u").replace("ç", "c"))

    def _buscar_config(self) -> None:
        termo = self.busca_edit.text().strip()
        self.busca_status.setVisible(True)
        if not termo:
            self.busca_status.mostrar("Digite um termo, por exemplo: microfone.", "info")
            return
        chave = self._normalizar_busca(termo)
        regras = (
            (("microfone", "microfono", "mic", "entrada de audio"), 0, None,
             "mic_combo", "Microfone"),
            (("saida", "saida de audio", "alto-falante", "alto falante"), 0, None,
             "saida_combo", "Saída de áudio"),
            (("voz", "personagem", "timbre", "alias"), 0, None,
             "voice_combo", "Voz"),
            (("personalidade", "jeito"), 0, None,
             "personality_combo", "Personalidade"),
            (("saudacao", "saudacao ao abrir"), 3, None,
             "saudacao_botao", "Saudação ao abrir"),
            (("inicializacao", "iniciar com o sistema", "startup", "boot"), 3, None,
             "inicio_botao", "Iniciar com o sistema"),
            (("perfil", "dono", "como chamar", "dados pessoais"), 4, None,
             "primeiro_perfil", "Meu perfil"),
            (("tema", "claro", "escuro", "appearance"), 1, None,
             "theme_cards", "Tema do dashboard"),
            (("nucleo", "previa", "animacao"), 1, None,
             "nucleo_combo", "Núcleo e prévia"),
            (("cor", "cores", "nucleo pensando"), 1, None,
             "cor_combo", "Cores do núcleo"),
            (("nome da tela", "nomes da interface", "rotulos"), 1, None,
             "primeiro_nome", "Nomes da interface"),
            (("dock", "fundo", "brilho", "icone", "atalho"), 1, None,
             "dock_lista", "Fundo e dock"),
            (("ollama", "modelo local", "modelos instalados"), 2, "ollama",
             "modelos", "Ollama"),
            (("api", "apis", "chave", "provedor", "credencial", "gemini"), 2,
             "apis", "provedor", "APIs externas"),
            (("whatsapp", "qr", "mensagem"), 5, "conexoes",
             "whatsapp_botao", "WhatsApp"),
            (("secretaria", "ligacao", "recado", "atendimento"), 5,
             "secretaria", "secretaria_widget", "Secretária"),
            (("celular", "remoto", "parear", "revogar", "acesso"), 5,
             "conexoes", "remoto_botao", "Acesso pelo celular"),
            (("documentos", "indice", "indice local", "busca local", "arquivos"), 6,
             None, "busca_local_edit", "Documentos"),
            (("habilidades", "habilidade", "skills", "acoes nativas"), 7,
             None, "habilidades_lista", "Habilidades nativas"),
            (("rotinas", "rotina", "lembrete", "agendamento"), 3,
             None, "rotina_titulo", "Rotinas"),
        )
        encontrado = None
        for palavras, indice, area, alvo, rotulo in regras:
            if any(palavra in chave for palavra in palavras):
                encontrado = (indice, area, alvo, rotulo)
                break
        if encontrado is None:
            self.busca_status.mostrar(
                f"Nenhum resultado para “{termo}”.", "warning")
            return

        indice, area, alvo, rotulo = encontrado
        self._ir_para_pagina(indice, focar=False)
        if indice == 2 and self._painel_provedores is not None:
            self._painel_provedores.mostrar_area(area or "apis")
        if indice == 5:
            self.mostrar_integracao(area or "conexoes")

        widget = self._widget_da_busca(alvo)
        if widget is None:
            widget = self._procurar_widget(indice, chave)
        if widget is None:
            self.busca_status.mostrar(
                f"Seção encontrada, mas o controle de “{termo}” não está "
                "disponível agora.", "warning")
            return
        self.busca_status.mostrar(f"Encontrado: {rotulo}", "success")

        def focar() -> None:
            if self._fechado:
                return
            try:
                widget.setFocus(Qt.FocusReason.OtherFocusReason)
                self._scrolls[indice].ensureWidgetVisible(widget, 24, 24)
            except RuntimeError:
                pass

        QTimer.singleShot(0, focar)

    def _widget_da_busca(self, alvo: str | None):
        if not alvo:
            return None
        if alvo == "theme_cards":
            return self.theme_cards.get(self._tema_atual)
        if alvo == "primeiro_perfil":
            return next(iter(getattr(self, "_perfil_campos", {}).values()), None)
        if alvo == "primeiro_nome":
            return next(iter(getattr(self, "_nomes_campos", {}).values()), None)
        if alvo == "secretaria_widget":
            widget = getattr(self, "_secretaria_widget", None)
            if widget is None:
                return None
            return next((w for w in widget.findChildren(QWidget)
                         if w.focusPolicy() != Qt.FocusPolicy.NoFocus), None)
        if alvo in ("modelos", "provedor") and self._painel_provedores is not None:
            return getattr(self._painel_provedores, alvo, None)
        return getattr(self, alvo, None)

    def _procurar_widget(self, indice: int, termo: str):
        if not (0 <= indice < len(self._scrolls)):
            return None
        for widget in self._scrolls[indice].findChildren(QWidget):
            if widget.focusPolicy() == Qt.FocusPolicy.NoFocus:
                continue
            texto = self._normalizar_busca(
                f"{widget.accessibleName()} {getattr(widget, 'text', lambda: '')()}")
            if termo.split()[0] in texto:
                return widget
        return None

    # ── infraestrutura ─────────────────────────────────────────────────────
    def _executar(self, funcao, ao_terminar) -> int:
        token = self._runner.executar(funcao)
        self._pendentes[token] = ao_terminar
        return token

    def _receber_resultado(self, token: int, resultado) -> None:
        if self._fechado:
            return
        retorno = self._pendentes.pop(token, None)
        if retorno is None:
            return
        if isinstance(resultado, dict) and "__excecao__" in resultado:
            resultado = {"salvo": False, "aplicado": False,
                         "ok": False, "erro": resultado["__excecao__"]}
        try:
            retorno(resultado)
        except RuntimeError:
            pass

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.Type.FocusIn and not self._fechado
                and isinstance(obj, QWidget) and obj is not self
                and self.isAncestorOf(obj)):
            for rolagem in self._scrolls:
                if rolagem.isAncestorOf(obj):
                    rolagem.ensureWidgetVisible(obj, 24, 24)
                    break
        return super().eventFilter(obj, event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._posicionar_indicador(self._nav_buttons[self._pagina], animar=False)
        if self._primeira_exibicao:
            self._primeira_exibicao = False
            self._nav_buttons[self._pagina].setFocus(Qt.FocusReason.OtherFocusReason)
        if not self.isMinimized() and self._pagina == 1:
            self._atualizar_previa_nucleo()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() != QEvent.Type.WindowStateChange:
            return
        if self.isMinimized():
            self._pausar_previa_nucleo()
        elif self.isVisible() and self._pagina == 1:
            self._atualizar_previa_nucleo()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._backdrop.setGeometry(self.rect())
        self._atualizar_cabecalho()
        self._posicionar_indicador(self._nav_buttons[self._pagina], animar=False)

    def _atualizar_cabecalho(self) -> None:
        """Em janelas estreitas, some o subtítulo e a pílula encurta.

        O título grande de cada página continua dentro da área rolável; o
        cabeçalho é só contexto e não pode empurrar a janela para fora da tela.
        """
        if not hasattr(self, "_pilula"):
            return
        self._atualizar_layout_temas()
        largura = self.width()
        modo = "minimo" if largura < 820 else (
            "compacto" if largura < 900 else "normal")
        if modo == self._modo_cabecalho:
            return
        self._modo_cabecalho = modo
        self._modo_compacto = modo != "normal"
        self._cabecalho_subtitulo.setVisible(modo == "normal")
        self.busca_edit.setVisible(modo != "minimo")
        if not self.busca_edit.isVisible():
            self.busca_status.setVisible(False)
        if modo == "minimo":
            # Em telas estreitas ou com escala ampliada, a pílula sai de cena;
            # o título de cada página continua dizendo onde a pessoa está.
            self._pilula.hide()
        else:
            self._pilula.show()
            self._pilula.setText("CONFIG." if modo == "compacto"
                                 else "CONFIGURAÇÕES")

    def _atualizar_layout_temas(self) -> None:
        """Empilha as opções de tema quando a área de conteúdo fica estreita."""
        if not hasattr(self, "_grade_temas"):
            return
        empilhar = self.width() < 820
        if empilhar == self._temas_empilhados:
            return
        self._temas_empilhados = empilhar
        escuro = self.theme_cards["escuro"]
        claro = self.theme_cards["claro"]
        for card in (escuro, claro):
            self._grade_temas.removeWidget(card)
        if empilhar:
            self._grade_temas.addWidget(escuro, 0, 0)
            self._grade_temas.addWidget(claro, 1, 0)
        else:
            self._grade_temas.addWidget(escuro, 0, 0)
            self._grade_temas.addWidget(claro, 0, 1)

    def closeEvent(self, event) -> None:
        self._fechado = True
        if self._indice is not None and self._indice_ativo:
            self._indice.interromper()
        self._pausar_previa_nucleo()
        if hasattr(self, "_secretaria_widget"):
            self._pausar_timers_area(False)
        if self._painel_provedores is not None:
            self._painel_provedores.encerrar()
        self._runner.encerrar()
        self._pendentes.clear()
        try:
            self._runner.bridge.terminou.disconnect(self._receber_resultado)
        except (TypeError, RuntimeError):
            pass
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self.fechada.emit()
        super().closeEvent(event)
