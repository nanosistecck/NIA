"""Canvas, vidro e personalização da janela principal (sem motores de IA)."""
from pathlib import Path
import json
import time

from PyQt6.QtCore import (
    Qt, QPointF, QUrl, QPropertyAnimation, QEasingCurve, QByteArray, QRect,
    QRectF, QSize, QTimer, pyqtSignal,
)
from PyQt6.QtGui import QColor, QPainter, QPixmap, QRadialGradient, QDesktopServices, QIcon, QFont
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit,
    QApplication, QScrollArea, QMessageBox, QMenu, QGraphicsOpacityEffect,
)

from core.canvas_brief import BriefDeck

GLASS = """QFrame#Glass { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
 stop:0 rgba(111,157,185,95),stop:0.5 rgba(38,77,104,125),stop:1 rgba(80,115,157,85));
 border:1px solid rgba(158,207,232,100); border-radius:22px; }
QLabel {color:#e4f4fc; background:transparent; border:none;}
QPushButton {color:#d7f5ff; background:rgba(120,184,207,22); border:1px solid rgba(149,209,229,55);
 border-radius:12px; padding:8px;}
QPushButton:hover, QPushButton:focus {background:rgba(50,215,232,65); border-color:#6deaf1;}
QPushButton:checked {background:rgba(35,207,220,100); border-color:#80f6fc;}
QTextEdit {color:#e4f4fc; background:transparent; border:none; selection-background-color:#246981;}
QScrollBar:vertical {background:transparent; width:5px; margin:0; border:none;}
QScrollBar::handle:vertical {background:rgba(116,220,236,110); min-height:22px; border-radius:2px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:transparent;}
"""

# Traços vetoriais independem das fontes de ícones instaladas no computador.
_ICONS = {
    'save':'<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h12l4 4v12a2 2 0 0 1-2 2z"/><path d="M7 3v6h10V3M7 21v-8h10v8M14 5v2"/>',
    'mute':'<rect x="9" y="3" width="6" height="12" rx="3"/><path d="M6 10v2a6 6 0 0 0 12 0v-2M12 18v3M9 21h6"/>',
    'interrupt':'<rect x="5" y="5" width="14" height="14" rx="2"/>',
    'so_nome':'<rect x="6" y="10" width="12" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>',
    'remote':'<rect x="3" y="4" width="13" height="11" rx="2"/><rect x="16" y="10" width="5" height="11" rx="1"/><path d="M7 19h7M10 15v4"/>',
    'webcam':'<rect x="3" y="6" width="18" height="15" rx="3"/><circle cx="12" cy="13" r="4"/><path d="M7 6l2-3h6l2 3"/>',
    'cowork':'<path d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"/>',
    'computer_use':'<rect x="3" y="3" width="18" height="13" rx="2"/><path d="M7 21h10M12 16v5M9 7l6 3-3 1-1 3z"/>',
    'globo':'<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18M5 7h14M5 17h14"/>',
    'segundo_plano':'<path d="M20 15A9 9 0 0 1 9 4a9 9 0 1 0 11 11z"/>',
    'config':'<path d="m9.6 3-.5 2.1-1.6.9-2.1-.6-2.4 4.2 1.6 1.5v1.8L3 14.4l2.4 4.2 2.1-.6 1.6.9.5 2.1h4.8l.5-2.1 1.6-.9 2.1.6 2.4-4.2-1.6-1.5v-1.8L21 9.6l-2.4-4.2-2.1.6-1.6-.9L14.4 3z"/><circle cx="12" cy="12" r="3.4"/>',
    'mic':'<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7"/>',
    'system':'<path d="M4 20V9M9 20V4M14 20V12M19 20V7"/>',
    'attach':'<path d="M8 14l7-7a3 3 0 0 1 4 4l-9 9a5 5 0 0 1-7-7L13 3M6 16l9-9"/>',
    'send':'<path d="M3 3l19 9-19 9 4-9zM7 12h15"/>',
    'history':'<path d="M3 10a9 9 0 1 1 1 7M3 4v6h6M12 7v5l4 2"/>',
    'edit':'<path d="M4 7h6m4 0h6M4 17h10m4 0h2"/><circle cx="12" cy="7" r="2"/><circle cx="16" cy="17" r="2"/>',
    'menu':'<rect x="4" y="4" width="6" height="6" rx="1.5"/><rect x="14" y="4" width="6" height="6" rx="1.5"/><rect x="4" y="14" width="6" height="6" rx="1.5"/><rect x="14" y="14" width="6" height="6" rx="1.5"/>',
    'collapse':'<path d="m14 6-6 6 6 6"/>',
    'expand':'<path d="m10 6 6 6-6 6"/>',
    'palette':'<path d="M12 3a9 9 0 1 0 0 18h1a2 2 0 0 0 1-3.7 1.6 1.6 0 0 1 1-2.8h2a4 4 0 0 0 4-4C21 6 17 3 12 3z"/><circle cx="7" cy="11" r=".7"/><circle cx="10" cy="7" r=".7"/><circle cx="15" cy="7" r=".7"/>',
    'whatsapp':'<path d="M5 19l-2 3 5-2a9 9 0 1 0-3-1zM8 7c0 5 4 9 9 9"/>',
    'planos':'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><path d="M14 17.5h7M17.5 14v7"/>',
}


def vector_icon(name,color='#dcf7ff'):
    body = _ICONS.get(name,_ICONS['system'])
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    return QSvgRenderer(QByteArray(svg.encode()))


def icon(name,color='#dcf7ff'):
    pixmap = QPixmap(96,96); pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap); vector_icon(name,color).render(painter); painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


DEFAULT_APPEARANCE = {
    'background_color': '#10283e', 'brightness': 90,
    'icon_size': 28, 'dock_height': 570,
}


def appearance_settings(data):
    """Migração aditiva: preferências antigas e valores inválidos usam padrões."""
    result = dict(DEFAULT_APPEARANCE)
    saved = data.get('appearance', {})
    if not isinstance(saved, dict):
        return result
    color = saved.get('background_color')
    if isinstance(color, str) and QColor(color).isValid():
        result['background_color'] = QColor(color).name()
    for key, lower, upper in (('brightness',40,160),('icon_size',18,40),('dock_height',240,900)):
        value = saved.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            result[key] = max(lower, min(upper, value))
    return result


class CanvasBackground(QWidget):
    def __init__(self, parent=None, preferences=None):
        super().__init__(parent)
        self._key = None
        self.appearance = appearance_settings(preferences or {})

    def set_appearance(self, settings):
        self.appearance = appearance_settings({'appearance':settings})
        self.update()

    def _palette_color(self, source):
        from core import tema
        color = QColor(tema.cor(source))
        selected = QColor(self.appearance['background_color'])
        reference = QColor(DEFAULT_APPEARANCE['background_color'])
        if selected == reference:
            return color
        h, s, lightness, _ = color.getHslF()
        rh, rs, rl, _ = reference.getHslF()
        sh, ss, sl, _ = selected.getHslF()
        # Transformação monotônica: mantém a ordem das luzes sem recortar os tons.
        sl = max(.005, min(.995, sl))
        odds = (sl / (1-sl)) / (rl / (1-rl))
        lightness = odds*lightness / (1-lightness+odds*lightness)
        return QColor.fromHslF((h+max(0,sh)-rh) % 1, min(1,s*ss/rs), lightness)

    def _ensure_cache(self):
        from core import tema
        key = (self.size(), self.devicePixelRatioF(), tema.versao(), tuple(self.appearance.items()))
        if key != self._key:
            self._key = key
            dpr = self.devicePixelRatioF()
            self._cache = QPixmap(int(self.width()*dpr), int(self.height()*dpr))
            self._cache.setDevicePixelRatio(dpr)
            self._cache.fill(self._palette_color('#10283e'))
            p = QPainter(self._cache)
            for x, y, radius, color in ((.18,.72,.42,'#127688'),(.85,.32,.43,'#086879'),(.74,.86,.35,'#243f81')):
                g = QRadialGradient(QPointF(self.width()*x,self.height()*y), self.width()*radius)
                c = self._palette_color(color); c.setAlpha(125)
                g.setColorAt(0,c); c.setAlpha(0); g.setColorAt(1,c)
                p.fillRect(self.rect(),g)
            # Escurece a composição pronta em ~2%, preservando seus gradientes.
            p.fillRect(self.rect(), QColor(0, 0, 0, 5))
            brightness = self.appearance['brightness']
            if brightness < 100:
                p.fillRect(self.rect(), QColor(0,0,0,round(255*(1-brightness/100))))
            elif brightness > 100:
                p.fillRect(self.rect(), QColor(255,255,255,round(255*(brightness/100-1))))
            p.end()
    def paintEvent(self, event):
        self._ensure_cache()
        p = QPainter(self); p.drawPixmap(0,0,self._cache)



class ResultCard(QFrame):
    def __init__(self, title, text, close, parent=None):
        super().__init__(parent)
        self.setObjectName('Glass'); self.setStyleSheet(GLASS)
        self.title = title
        self.pinned = False
        v = QVBoxLayout(self); v.setContentsMargins(18,14,18,14)
        row = QHBoxLayout()
        self.label = QLabel(); self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setWordWrap(True); self.label.setText(title)
        self.label.setFont(QFont('Segoe UI',13))
        row.addWidget(self.label,1)
        copy = QPushButton('Copiar'); copy.clicked.connect(lambda: QApplication.clipboard().setText(self.text.toPlainText()))
        pin = QPushButton('Fixar'); pin.setCheckable(True)
        pin.toggled.connect(self._pin)
        dismiss = QPushButton('×'); dismiss.setAccessibleName('Fechar resultado')
        dismiss.clicked.connect(lambda: close(self))
        for button in (copy,pin,dismiss): row.addWidget(button)
        v.addLayout(row)
        self.text = QTextEdit(); self.text.setReadOnly(True)
        self.text.setFont(QFont('Segoe UI',11))
        self.set_content(text)
        v.addWidget(self.text)
        self.setMinimumHeight(150)
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        self.fade = QPropertyAnimation(effect,b'opacity',self)
        self.fade.setDuration(160); self.fade.setStartValue(0.0); self.fade.setEndValue(1.0)
        self.fade.start()

    def _pin(self, value):
        self.pinned = value

    def set_content(self,text):
        self.text.setPlainText(text)
        lines = max(text.count('\n')+1,len(text)//55)
        self.setMaximumHeight(min(340,max(160,100+lines*20)))


class CanvasStage(QWidget):
    """O motor conserva o desenho; este widget decide somente a composição."""

    hoje_gerar = pyqtSignal()
    hoje_ouvir = pyqtSignal()
    hoje_rotinas = pyqtSignal()
    hoje_visibilidade = pyqtSignal(bool)

    def __init__(self, hud_stack, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hud_stack = hud_stack; hud_stack.setParent(self)
        self.cards = []
        self.tools_open = False
        # Sessão do editor de planos: suspende resultados/HOJE sem tocar em
        # preferências; nunca gravado em config/interface.json.
        self._canvas_editor_ativo = False
        self.results = QScrollArea(self)
        self.results.setWidgetResizable(True)
        self.results.setFrameShape(QFrame.Shape.NoFrame)
        self.results.setStyleSheet('QScrollArea {background:transparent;border:none;}')
        self.results.viewport().setStyleSheet('background:transparent;')
        self.card_host = QWidget()
        self.card_host.setStyleSheet('background:transparent;')
        self.card_layout = QVBoxLayout(self.card_host)
        self.card_layout.setContentsMargins(0,0,4,0)
        self.card_layout.setSpacing(12)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.results.setWidget(self.card_host)
        self.results.hide()

        # Cartão Hoje: separado dos cartões de resultado para não ser fechado
        # por show_content() e para não ocupar espaço quando estiver oculto.
        self.hoje_host = QFrame(self)
        self.hoje_host.setObjectName('Glass')
        self.hoje_host.setStyleSheet(GLASS + '\nQFrame#Glass {border-radius:18px;}')
        hoje_layout = QVBoxLayout(self.hoje_host)
        hoje_layout.setContentsMargins(14, 12, 14, 12)
        hoje_layout.setSpacing(8)
        topo_hoje = QHBoxLayout()
        topo_hoje.setContentsMargins(0, 0, 0, 0)
        topo_hoje.setSpacing(6)
        self.hoje_titulo = QLabel('HOJE', self.hoje_host)
        self.hoje_titulo.setObjectName('HojeTitulo')
        self.hoje_titulo.setWordWrap(True)
        self.hoje_titulo.setStyleSheet('color:#8ceaf0; font-weight:600;')
        topo_hoje.addWidget(self.hoje_titulo, 1)
        self.hoje_fechar = QPushButton('×', self.hoje_host)
        self.hoje_fechar.setObjectName('HojeFechar')
        self.hoje_fechar.setAccessibleName('Fechar cartão Hoje')
        self.hoje_fechar.setToolTip('Fechar cartão Hoje')
        self.hoje_fechar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hoje_fechar.setFixedSize(22, 22)
        self.hoje_fechar.setStyleSheet(
            'QPushButton {color:#8ceaf0; background:transparent; border:none;'
            ' border-radius:11px; padding:0; font-size:15px; font-weight:600;}'
            'QPushButton:hover, QPushButton:focus {color:#ffffff;'
            ' background:rgba(50,215,232,65); border:none;}')
        self.hoje_fechar.clicked.connect(lambda: self.set_hoje_visible(False))
        topo_hoje.addWidget(self.hoje_fechar, 0, Qt.AlignmentFlag.AlignTop)
        hoje_layout.addLayout(topo_hoje)
        self.hoje_texto = QLabel('Carregando resumo…', self.hoje_host)
        self.hoje_texto.setWordWrap(True)
        self.hoje_texto.setTextFormat(Qt.TextFormat.PlainText)
        self.hoje_texto.setStyleSheet('color:#d8f8ff;')
        hoje_layout.addWidget(self.hoje_texto, 1)
        self.hoje_status = QLabel('', self.hoje_host)
        self.hoje_status.setWordWrap(True)
        self.hoje_status.setStyleSheet('color:#7892a8;')
        hoje_layout.addWidget(self.hoje_status)
        hoje_botoes = QHBoxLayout()
        hoje_botoes.setSpacing(6)
        for rotulo, sinal in (('Gerar agora', self.hoje_gerar),
                              ('Ouvir', self.hoje_ouvir),
                              ('Rotinas', self.hoje_rotinas)):
            b = QPushButton(rotulo, self.hoje_host)
            b.setObjectName('glass-button')
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(sinal.emit)
            hoje_botoes.addWidget(b)
        hoje_botoes.addStretch(1)
        hoje_layout.addLayout(hoje_botoes)
        self.hoje_host.hide()

        # Card temporário (hora, data ou clima): ciclo próprio, um por vez.
        # Não entra em `self.cards` para não ser fechado por show_content().
        self.brief_host = BriefDeck(self)
        self.brief_host.hide()
        self.brief_host.fechar.connect(self.dismiss_brief)
        self._brief_kind = ''
        self._brief_created = 0.0
        self._brief_deadline = 0.0
        self._brief_speaking = False
        self._brief_speech_seen = False
        self._brief_closing = False
        self._brief_timer = QTimer(self)
        self._brief_timer.setSingleShot(True)
        self._brief_timer.timeout.connect(self._expire_brief)
        self._brief_effect = QGraphicsOpacityEffect(self.brief_host)
        self.brief_host.setGraphicsEffect(self._brief_effect)
        self._brief_fade = QPropertyAnimation(self._brief_effect, b'opacity', self)
        self._brief_fade.setDuration(200)
        self._brief_fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._brief_fade.finished.connect(self._brief_fade_finished)
        self._brief_fade.valueChanged.connect(self.brief_host.set_entry_progress)
        self._brief_entry = QTimer(self)
        self._brief_entry.setSingleShot(True)
        self._brief_entry.timeout.connect(lambda: self._fade_brief(0.0, 1.0))

        self.anchor = 'center'
        self.chat_open = False
        self.motion = QPropertyAnimation(hud_stack,b'geometry',self)
        self.motion.setDuration(220); self.motion.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_hoje_visible(self, visivel: bool) -> None:
        self.hoje_host.setVisible(bool(visivel))
        self.arrange(True)
        self.hoje_visibilidade.emit(bool(visivel))

    @property
    def hoje_visivel(self) -> bool:
        return self.hoje_host.isVisible()

    def set_hoje_texto(self, texto: str, gerado_em: str = '') -> None:
        self.hoje_texto.setText(str(texto or 'Sem resumo salvo.')[:700])
        if gerado_em:
            self.hoje_status.setText(f'Gerado em {str(gerado_em)[:16].replace("T", " ")}')
        else:
            self.hoje_status.setText('')

    def set_hoje_status(self, texto: str) -> None:
        self.hoje_status.setText(str(texto or '')[:160])

    def show_content(self,title,text):
        match = next((c for c in self.cards if c.title == title and not c.pinned),None)
        if match:
            match.set_content(text)
        else:
            for card in list(self.cards):
                if not card.pinned: self.close_card(card)
            card = ResultCard(title,text,self.close_card,self.card_host)
            self.card_layout.addWidget(card)
            self.cards.append(card); card.show()
        self.arrange(True)

    def close_card(self,card):
        self.cards.remove(card); self.card_layout.removeWidget(card)
        card.hide(); card.deleteLater(); self.arrange(True)

    # ── CARD TEMPORÁRIO (hora, data e clima) ─────────────────────────────
    @property
    def brief_visivel(self) -> bool:
        return self.brief_host.isVisible()

    @property
    def brief_tipo(self) -> str:
        return self._brief_kind

    def show_brief(self, dados) -> None:
        """Mostra/substitui o card temporário. O token é filtrado pela janela."""
        dados = dict(dados or {})
        tipo = str(dados.get('tipo') or '')
        if tipo not in ('hora', 'data', 'tudo', 'clima'):
            return
        self._brief_entry.stop()
        self._brief_fade.stop()
        self._brief_effect.setOpacity(0.0)
        self._brief_timer.stop()
        self._brief_closing = False
        self._brief_kind = tipo
        self.brief_host.set_conteudo(tipo, dados)
        self.brief_host.show()
        self.brief_host.raise_()
        self._brief_created = time.monotonic()
        self._brief_speaking = False
        self._brief_speech_seen = False
        segundos = 11 if tipo == 'clima' else 7
        self._brief_deadline = self._brief_created + segundos
        self._brief_timer.start(int(segundos * 1000))
        self.arrange(True)
        self._brief_entry.start(self.motion.duration())

    def dismiss_brief(self, *_):
        """Fecha o card temporário. A composição volta ao estado atual."""
        self._brief_timer.stop()
        self._brief_entry.stop()
        self.brief_host.set_paused(True)
        self._brief_speaking = False
        if not self.brief_host.isVisible():
            return
        self._brief_closing = True
        self._fade_brief(self._brief_effect.opacity(), 0.0)

    def set_brief_speaking(self, falando: bool) -> None:
        """Estende o card enquanto a fala DESTA resposta estiver no ar.

        Só a primeira fala que começar logo depois de o card aparecer conta:
        uma fala do resumo HOJE, minutos depois, não pode manter o relógio
        na tela para sempre.
        """
        if not self.brief_host.isVisible() or self._brief_closing:
            return
        agora = time.monotonic()
        clima = self._brief_kind == 'clima'
        # Teto duro: mesmo que a fala nunca avise o fim, o card sai.
        teto = self._brief_created + (60.0 if clima else 30.0)
        if falando:
            if self._brief_speech_seen:
                return
            # A fala da previsao pode demorar mais para comecar (sintese).
            if agora - self._brief_created > (12.0 if clima else 6.0):
                return
            self._brief_speaking = True
            self._brief_speech_seen = True
            self._brief_deadline = teto
            self._brief_timer.start(max(0, int((teto - agora) * 1000)))
            return
        if not self._brief_speaking:
            return
        self._brief_speaking = False
        margem = 3.0 if clima else 2.0
        prazo = min(agora + margem, teto)
        self._brief_deadline = prazo
        self._brief_timer.start(max(0, int((prazo - agora) * 1000)))

    def set_brief_paused(self, pausado: bool) -> None:
        """Janela escondida: os segundos do relógio param de ser redesenhados."""
        try:
            self.brief_host.set_paused(bool(pausado))
        except Exception:
            pass

    def _expire_brief(self) -> None:
        self.dismiss_brief()

    def _fade_brief(self, inicio: float, fim: float) -> None:
        self._brief_fade.stop()
        self._brief_effect.setOpacity(float(inicio))
        self._brief_fade.setStartValue(float(inicio))
        self._brief_fade.setEndValue(float(fim))
        self._brief_fade.start()

    def _brief_fade_finished(self) -> None:
        if not self._brief_closing:
            return
        self._brief_closing = False
        self.brief_host.hide()
        self._brief_effect.setOpacity(1.0)
        # Volta imediata da geometria: `arrange(True)` compete com o
        # resizeEvent do relógio e podia deixar a esfera no tamanho do card.
        self.arrange(False)

    def _left_occupied(self, w: int) -> int:
        """Até onde os painéis da esquerda vão. O card não pisa neles."""
        direita = 0
        if self.tools_open:
            direita = max(direita, 12 + min(344, max(220, int(w * .5) - 24)))
        if self.results.isVisible():
            direita = max(direita, 12 + max(220, int(w * .50) - 24))
        if self.hoje_host.isVisible():
            direita = max(direita, 12 + max(220, min(320, int(w * .36))))
        return direita

    def _brief_geometries(self, w: int, bottom: int):
        """(card, reator) sem sobreposição, respeitando HOJE/resultados/dock.

        O tamanho do card nasce do conteúdo: a hora não vira um retângulo
        gigante de sobra e a previsão não abre área vazia quando os dias
        retornados não justificam a altura.
        """
        obstaculo = self._left_occupied(w)
        fx = obstaculo + 12 if obstaculo else 12
        fw = max(1, w - fx - 12)
        lado = max(56, min(190, int(bottom * .28)))
        espaco = fw - lado - 16
        lado_a_lado = espaco >= 280
        disponivel = espaco if lado_a_lado else fw
        largura = min(disponivel, 760 if self._brief_kind == 'clima' else 380)
        largura = max(1, largura)
        desejado = self.brief_host.tamanho_para_largura(largura)
        limite = bottom - 16 if lado_a_lado else bottom - lado - 24
        altura = max(1, min(desejado.height(), limite))
        # Centraliza no espaço liberado à esquerda do núcleo em repouso.
        x = fx + max(0, (disponivel - largura) // 2)
        y = max(8, (bottom - altura) // 2 - 18) if lado_a_lado else 8
        card = QRect(x, y, largura, altura)
        if lado_a_lado:
            hud = QRect(w - lado - 12, max(8, (bottom - lado) // 2), lado, lado)
        else:
            hud = QRect(fx + max(0, (fw - lado) // 2), card.bottom() + 8, lado, lado)
        return card, hud

    def contextMenuEvent(self,event):
        menu = QMenu(self)
        for label,anchor in (('Centro','center'),('Esquerda','left'),('Direita','right'),
                             ('Superior esquerdo','top-left'),('Superior direito','top-right'),
                             ('Inferior esquerdo','bottom-left'),('Inferior direito','bottom-right')):
            action = menu.addAction('Reator: '+label)
            action.triggered.connect(lambda checked=False,a=anchor:self.set_anchor(a))
        menu.exec(event.globalPos())

    def set_anchor(self,anchor):
        self.anchor = anchor
        self.arrange(True)

    def resizeEvent(self,event):
        super().resizeEvent(event); self.arrange()

    def arrange(self,animate=False):
        if not hasattr(self,'motion'): return
        if self._canvas_editor_ativo and self.hud_stack.parentWidget() is not self:
            self.motion.stop()
            self.hud_stack.parentWidget()._reposicionar()
            return
        w,h = self.width(),self.height()
        bottom = max(160,h - (min(260,h//2) if self.chat_open else 0))
        if self.brief_host.isVisible():
            card, target = self._brief_geometries(w, bottom)
            self.motion.stop()
            if animate and self.isVisible():
                self.motion.setStartValue(self.hud_stack.geometry())
                self.motion.setEndValue(target)
                self.motion.start()
            else:
                self.hud_stack.setGeometry(target)
            self.brief_host.setGeometry(card)
            self.brief_host.raise_()
        else:
            occupied = (bool(self.cards) or self.tools_open
                        or self.hoje_host.isVisible())
            size = min(bottom,w if not occupied else int(w*.48))
            x = (w-size)//2
            if occupied: x = w-size
            elif self.anchor in ('left','top-left','bottom-left'): x = 0
            elif self.anchor in ('right','top-right','bottom-right'): x = w-size
            y = max(0,(bottom-size)//2)
            if self.anchor.startswith('top'): y = 0
            elif self.anchor.startswith('bottom'): y = max(0,bottom-size)
            target = QRect(x,y,max(1,size),max(1,size))
            self.motion.stop()
            if animate and self.isVisible():
                self.motion.setStartValue(self.hud_stack.geometry()); self.motion.setEndValue(target); self.motion.start()
            else: self.hud_stack.setGeometry(target)
        self.results.setGeometry(12,8,max(220,int(w*.50)-24),max(80,bottom-16))
        self.results.setVisible(bool(self.cards) and not self.tools_open
                                and not self._canvas_editor_ativo)
        self.results.raise_()
        if self.hoje_host.isVisible() and not self._canvas_editor_ativo:
            largura = max(220, min(320, int(w * .36)))
            altura = max(150, min(240, bottom - 16))
            self.hoje_host.setGeometry(QRect(12, 8, largura, altura))
            self.hoje_host.raise_()


class DockPreferences:
    """Mesmo diretório e gravação atômica usados pelas preferências de tema."""
    def __init__(self,path):
        self.path = Path(path)
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            self.data = data if isinstance(data,dict) else {}
            for key in ('order','hidden','apps'):
                if key in self.data:
                    value = self.data[key]
                    self.data[key] = [v for v in value if isinstance(v,str)] if isinstance(value,list) else []
            if 'cards' in self.data and isinstance(self.data['cards'], dict):
                self.data['cards'] = {
                    k: bool(v) for k, v in self.data['cards'].items()
                    if k in ('hoje',)}
        except (OSError,ValueError): self.data = {}

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.data,ensure_ascii=False,indent=2),encoding='utf-8')
        tmp.replace(self.path)


class VerticalDock(QFrame):
    appearance_changed = pyqtSignal(dict)

    def __init__(self,buttons,config,parent=None):
        super().__init__(parent)
        self.setObjectName('Glass')
        # Vidro escuro do dock: borda ciano suave e cantos de ~22 px,
        # isolado dos demais widgets que compartilham `GLASS`.
        self.setStyleSheet(
            GLASS + '\nQFrame#Glass {'
            ' background: qlineargradient(x1:0,y1:0,x2:0,y2:1,'
            ' stop:0 rgba(10,34,50,205), stop:1 rgba(5,18,32,215));'
            ' border:1px solid rgba(25,211,243,55); border-radius:22px; }')
        self.setFixedWidth(70)
        self.buttons = dict(buttons); self.preferences = DockPreferences(config)
        if 'hidden' not in self.preferences.data:
            defaults = ['mute','cowork','globo','webcam','config','planos']
            self.preferences.data['hidden'] = [k for k in self.buttons if k not in defaults]
            self.preferences.data.setdefault('order',[k for k in defaults if k in self.buttons]+list(self.buttons))
        elif not self.preferences.data.get('skill_atalhos_v1'):
            # Skill 07: em perfis existentes os atalhos novos entram ocultos,
            # para nao mudar posicoes nem a altura do dock. O dono ativa cada
            # um em Aparência -> Ferramentas do dock, se quiser.
            novos = [k for k in self.buttons
                     if k.startswith('skill_') and k not in self.preferences.data['hidden']]
            if novos:
                self.preferences.data['hidden'].extend(novos)
            self.preferences.data['skill_atalhos_v1'] = True
            try:
                self.preferences.save()
            except OSError:
                pass
        if not self.preferences.data.get('dock_planos_v1'):
            # Perfis existentes nao mudam de altura/posicoes: o atalho de
            # Planos entra oculto e o dono o ativa em Ferramentas do dock.
            if 'planos' in self.buttons and 'hidden' in self.preferences.data \
                    and 'planos' not in self.preferences.data['hidden']:
                self.preferences.data['hidden'].append('planos')
            self.preferences.data['dock_planos_v1'] = True
            try:
                self.preferences.save()
            except OSError:
                pass
        self.expanded = self.preferences.data.get('expanded',True)
        v = QVBoxLayout(self); v.setContentsMargins(5,12,5,10); v.setSpacing(6)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet('QScrollArea {background:transparent;border:none;} QScrollBar:vertical {width:4px;}')
        self.scroll.viewport().setStyleSheet('background:transparent;')
        self.items = QWidget(); self.items.setStyleSheet('background:transparent;')
        self.row = QVBoxLayout(self.items); self.row.setContentsMargins(0,0,0,0); self.row.setSpacing(6)
        self.scroll.setWidget(self.items); v.addWidget(self.scroll,1)
        self.edit = QPushButton(); self.edit.setIcon(icon('edit')); self.edit.setToolTip('Editar dock'); self.edit.clicked.connect(self.edit_dock); v.addWidget(self.edit)
        self.menu_button = QPushButton()
        self.menu_button.setIcon(icon('menu'))
        self.menu_button.setToolTip('Todas as ferramentas, incluindo ícones ocultos')
        self.menu_button.setAccessibleName('Todas as ferramentas')
        self.menu_button.clicked.connect(self.show_tools)
        v.addWidget(self.menu_button)
        self.toggle = QPushButton(); self.toggle.setToolTip('Mostrar ou recolher dock')
        self.edit.setIconSize(QSize(26,26))
        self.menu_button.setFont(QFont('Segoe UI',16))
        self.toggle.setFont(QFont('Segoe UI',18))
        for control in (self.edit,self.menu_button,self.toggle):
            control.setFixedHeight(42)
        self.edit.setAccessibleName('Editar dock')
        self.toggle.setAccessibleName('Mostrar ou recolher dock')
        self.toggle.clicked.connect(self.toggle_dock); v.addWidget(self.toggle)
        self.shortcuts = []
        self.apply()

    def entries(self):
        paths = self.preferences.data.get('apps',[])
        return list(self.buttons) + [p for p in paths if isinstance(p,str)]

    def apply(self):
        while self.row.count():
            item = self.row.takeAt(0)
            if item.widget(): item.widget().hide()
        for b in self.shortcuts: b.deleteLater()
        self.shortcuts = []
        entries = self.entries()
        order = self.preferences.data.get('order',entries)
        order = list(dict.fromkeys([k for k in order if k in entries]+entries))
        hidden = self.preferences.data.get('hidden',[])
        for key in order:
            if key in self.buttons: b = self.buttons[key]
            else:
                path = Path(key); b = QPushButton(path.stem[:2].upper())
                b.setFixedSize(54,48); b.setToolTip(key)
                b.setEnabled(path.is_file())
                b.clicked.connect(lambda checked=False,p=key: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
                self.shortcuts.append(b)
            self.row.addWidget(b); b.setVisible(key not in hidden)
        self.row.addStretch(); self.scroll.setVisible(self.expanded); self.edit.setVisible(self.expanded)
        self.toggle.setIcon(icon('collapse' if self.expanded else 'expand'))
        self._apply_appearance()

    def sizeHint(self):
        settings = appearance_settings(self.preferences.data)
        return QSize(self.width(), settings['dock_height'] if self.expanded else 112)

    def minimumSizeHint(self):
        return QSize(self.width(), 180 if self.expanded else 112)

    def _apply_appearance(self):
        settings = appearance_settings(self.preferences.data)
        size = settings['icon_size']
        extent = max(46, size + 12)
        self.setFixedWidth(extent+16)
        for button in list(self.buttons.values())+self.shortcuts:
            button.setFixedSize(extent,extent)
            button.setIconSize(QSize(size,size))
            button.setProperty('dock_icon_size',size)
            button.update()
        for button in (self.edit,self.menu_button,self.toggle):
            button.setIconSize(QSize(min(32,size),min(32,size)))
        self.setMaximumHeight(settings['dock_height'] if self.expanded else 112)
        self.updateGeometry()
        self.appearance_changed.emit(settings)

    def show_tools(self):
        menu = QMenu(self)
        for key, button in self.buttons.items():
            action = menu.addAction(button.toolTip() or key)
            action.setEnabled(button.isEnabled())
            action.triggered.connect(button.click)
        menu.addSeparator()
        menu.addAction('Editar dock', self.edit_dock)
        menu.exec(self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft()))

    def toggle_dock(self):
        self.expanded = not self.expanded; self.preferences.data['expanded'] = self.expanded
        self.apply(); self.persist()

    def persist(self):
        try: self.preferences.save()
        except OSError as exc: QMessageBox.warning(self,'Preferências',f'Não foi possível salvar o dock: {exc}')

    def edit_dock(self):
        """Abre a página Aparência do dashboard: uma única implementação.

        O antigo diálogo de três abas foi migrado para o dashboard. O gancho
        ``abrir_configuracoes`` é injetado pela janela principal; quando a dock
        está sozinha (testes isolados), tentamos o método da janela ancestral.
        """
        callback = getattr(self, 'abrir_configuracoes', None)
        if callback is not None:
            callback('aparencia')
            return
        janela = self.window()
        abrir = getattr(janela, '_abrir_dashboard_config', None)
        if abrir is not None:
            abrir('aparencia')
