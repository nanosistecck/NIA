"""Cards temporarios do Canvas: hora, data e previsao do tempo.

Este modulo cuida SO do desenho. Quem decide quando o card aparece e por
quanto tempo e a `CanvasStage` (ver `core/interface_canvas.py`), e quem
informa o clima e a `weather_action`.

O relogio usa tipografia local e os icones do tempo usam `QPainter`:
nao dependem de imagem em disco nem de rede.
"""
from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QBoxLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)


# ── idioma ────────────────────────────────────────────────────────────────
_DIAS_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
            "sexta-feira", "sábado", "domingo"]
_DIAS_CURTO_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
_MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
             "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
_DIAS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
            "Saturday", "Sunday"]
_DIAS_CURTO_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MESES_EN = ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]


def _em_ingles() -> bool:
    try:
        from core.idioma import em_ingles  # noqa: PLC0415
        return bool(em_ingles())
    except Exception:
        return False


def _dia_semana(d: date, curto: bool = False) -> str:
    en = _em_ingles()
    lista = (_DIAS_CURTO_EN if curto else _DIAS_EN) if en else (
        _DIAS_CURTO_PT if curto else _DIAS_PT)
    return lista[d.weekday()]


def _graus(valor) -> str:
    if valor is None:
        return ""
    try:
        return f"{round(float(valor))}°"
    except (TypeError, ValueError):
        return ""


def _cor_tema(valor: str, alpha: int = 255) -> QColor:
    from core import tema
    cor = QColor(tema.cor(valor))
    cor.setAlpha(alpha)
    return cor


# ── relogio moderno ───────────────────────────────────────────────────────
_FONTE_RELOJIO = ("Bahnschrift", "Segoe UI", "DejaVu Sans", "Helvetica", "Arial")


@lru_cache(maxsize=16)
def _fonte_relogio(tamanho: float, peso: int = 700) -> QFont:
    """Fonte do relogio moderno: primeira familia com a variante disponivel."""
    familias = QFontDatabase.families()
    familia = next((f for f in _FONTE_RELOJIO if f in familias), "DejaVu Sans")
    return QFont(familia, max(6, int(round(tamanho))), peso)


class ModernClock(QWidget):
    """Relogio moderno: hora e minutos grandes, segundos menores; data embaixo."""

    date_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._agora = datetime.now()
        self._pausado = False
        self._tmr = QTimer(self)
        self._tmr.setInterval(1000)
        self._tmr.setTimerType(Qt.TimerType.CoarseTimer)
        self._tmr.timeout.connect(self._tick)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(64)

    @property
    def agora(self) -> datetime:
        return self._agora

    def showEvent(self, event):
        super().showEvent(event)
        self._tick()
        if not self._pausado:
            self._tmr.start()

    def hideEvent(self, event):
        self._tmr.stop()
        super().hideEvent(event)

    def set_paused(self, pausado: bool) -> None:
        self._pausado = bool(pausado)
        if self._pausado:
            self._tmr.stop()
        elif self.isVisible():
            self._tick()
            self._tmr.start()

    def sizeHint(self) -> QSize:
        """`HH:MM` grande + segundos menores, na forma de uma unidade."""
        return QSize(int(4 * 0.62 * 56) + 8, int(56 * 1.35) + 6)

    def _tick(self) -> None:
        anterior = self._agora.date()
        self._agora = datetime.now()
        if self._agora.date() != anterior:
            self.date_changed.emit(self._agora)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        area = self.rect().adjusted(6, 6, -6, -6)
        if area.width() < 30 or area.height() < 20:
            return
        agora = self._agora
        tamanho = min(56, max(18, area.width() / 5.8), max(18, area.height() / 1.9))
        grande = _fonte_relogio(tamanho, 700)
        pequeno = _fonte_relogio(tamanho * .43, 600)
        fm, fm2 = QFontMetricsF(grande), QFontMetricsF(pequeno)
        digito = max(fm.horizontalAdvance(str(n)) for n in range(10))
        menor = max(fm2.horizontalAdvance(str(n)) for n in range(10))
        dois_pontos = fm.horizontalAdvance(':')
        total = 4 * digito + dois_pontos + 10 + 2 * menor
        x = area.left() + (area.width() - total) / 2
        y = area.top() + (area.height() - fm.height()) / 2
        p.setFont(grande)
        p.setPen(_cor_tema('#eafcff'))
        for caractere in f'{agora.hour:02d}:{agora.minute:02d}':
            largura = dois_pontos if caractere == ':' else digito
            p.drawText(QRectF(x, y, largura, fm.height()), Qt.AlignmentFlag.AlignCenter, caractere)
            x += largura
        p.setFont(pequeno)
        p.setPen(_cor_tema('#8ceaf0'))
        x += 10
        for caractere in f'{agora.second:02d}':
            p.drawText(QRectF(x, y, menor, fm2.height()), Qt.AlignmentFlag.AlignCenter, caractere)
            x += menor
        p.end()


class DateBrief(QWidget):
    """Dia da semana, dia, mes e ano por extenso, lidos do sistema."""

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 4, 0, 4)
        v.setSpacing(0)
        v.addStretch(1)
        self._dia_semana = QLabel("")
        self._dia_semana.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dia_semana.setFont(QFont("Segoe UI", 22, QFont.Weight.DemiBold))
        self._dia_semana.setStyleSheet("color:#8ceaf0; background:transparent;")
        v.addWidget(self._dia_semana)
        self._dia = QLabel("")
        self._dia.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont("Segoe UI", 54, QFont.Weight.Bold)
        self._dia.setFont(f)
        self._dia.setStyleSheet("color:#e8fbff; background:transparent;")
        v.addWidget(self._dia)
        self._mes_ano = QLabel("")
        self._mes_ano.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mes_ano.setFont(QFont("Segoe UI", 14))
        self._mes_ano.setStyleSheet("color:#c8edf5; background:transparent;")
        v.addWidget(self._mes_ano)
        v.addStretch(1)
        self._agora = datetime.now()
        self.set_date()

    @property
    def agora(self) -> datetime:
        return self._agora

    def sizeHint(self) -> QSize:
        """Semana do dia por extenso: semana + dia + mês + ano."""
        return QSize(320, 150)

    def set_date(self, agora: datetime | None = None) -> None:
        self._agora = agora or datetime.now()
        en = _em_ingles()
        d = self._agora
        self._dia_semana.setText(_dia_semana(d).upper())
        self._dia.hide()
        mes = (_MESES_EN if en else _MESES_PT)[d.month - 1]
        self._mes_ano.setText(f"{mes} {d.day}, {d.year}" if en else f"{d.day} de {mes} de {d.year}")
        self.update()


class ClockDateBrief(QWidget):
    """Relogio, data ou os dois no mesmo card."""

    def __init__(self, tipo: str, parent=None):
        super().__init__(parent)
        self.tipo = tipo
        v = QVBoxLayout(self)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(2)
        self.clock = ModernClock(self)
        self.date = DateBrief(self)
        self.clock.date_changed.connect(self.date.set_date)
        v.addWidget(self.clock, 1)
        v.addWidget(self.date, 0)
        if tipo == "hora":
            self.date._dia_semana.hide()
        elif tipo == "data":
            self.clock.hide()
            v.setStretch(1, 1)
        elif tipo == "tudo":
            v.setStretch(0, 1)

    def set_paused(self, pausado: bool) -> None:
        self.clock.set_paused(pausado)

    def set_date(self, agora: datetime | None = None) -> None:
        self.date.set_date(agora)

    def sizeHint(self) -> QSize:
        """Uma unidade só: hora, data ou relógio e data juntos."""
        if self.tipo == "tudo":
            return QSize(380, 280)
        if self.tipo == "data":
            return QSize(320, 150)
        return QSize(320, 106)


# ── icones do tempo (WMO) ─────────────────────────────────────────────────
_COR_SOL = QColor("#ffd45e")
_COR_NUVEM = QColor("#c8dbe5")
_COR_NUVEM_ESCURA = QColor("#8fa9b8")
_COR_CHUVA = QColor("#65c8ff")
_COR_TEMPESTADE = QColor("#ffe66d")
_COR_NEVE = QColor("#e6f7ff")
_COR_NEUTRO = QColor("#9fb7c2")


def _nuvem(p: QPainter, r: QRectF, cor: QColor = _COR_NUVEM) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(cor)
    p.drawEllipse(QRectF(r.left() + r.width() * 0.02, r.top() + r.height() * 0.44,
                         r.width() * 0.44, r.height() * 0.34))
    p.drawEllipse(QRectF(r.left() + r.width() * 0.22, r.top() + r.height() * 0.20,
                         r.width() * 0.42, r.height() * 0.46))
    p.drawEllipse(QRectF(r.left() + r.width() * 0.42, r.top() + r.height() * 0.38,
                         r.width() * 0.52, r.height() * 0.36))
    p.drawRect(QRectF(r.left() + r.width() * 0.10, r.top() + r.height() * 0.60,
                      r.width() * 0.78, r.height() * 0.18))


def _sol(p: QPainter, r: QRectF) -> None:
    centro = r.center()
    raio = min(r.width(), r.height()) * 0.24
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_COR_SOL)
    p.drawEllipse(centro, raio, raio)
    p.setPen(QPen(_COR_SOL, max(1.5, raio * 0.16),
                  Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0),
                   (-0.7, -0.7), (0.7, -0.7), (-0.7, 0.7), (0.7, 0.7)):
        p.drawLine(QPointF(centro.x() + dx * raio * 1.45,
                           centro.y() + dy * raio * 1.45),
                   QPointF(centro.x() + dx * raio * 2.0,
                           centro.y() + dy * raio * 2.0))


def _chuva(p: QPainter, r: QRectF, quantidade: int = 3) -> None:
    p.setPen(QPen(_COR_CHUVA, max(1.6, r.width() * 0.06),
                  Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for i in range(quantidade):
        x = r.left() + r.width() * (0.27 + 0.20 * i)
        y = r.top() + r.height() * (0.60 + 0.06 * (i % 2))
        p.drawLine(QPointF(x, y), QPointF(x - r.width() * 0.05,
                                          y + r.height() * 0.24))


def _raio(p: QPainter, r: QRectF) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_COR_TEMPESTADE)
    poly = QPolygonF([
        QPointF(r.left() + r.width() * 0.48, r.top() + r.height() * 0.52),
        QPointF(r.left() + r.width() * 0.68, r.top() + r.height() * 0.52),
        QPointF(r.left() + r.width() * 0.56, r.top() + r.height() * 0.78),
        QPointF(r.left() + r.width() * 0.72, r.top() + r.height() * 0.78),
        QPointF(r.left() + r.width() * 0.40, r.top() + r.height() * 1.02),
        QPointF(r.left() + r.width() * 0.49, r.top() + r.height() * 0.76),
        QPointF(r.left() + r.width() * 0.34, r.top() + r.height() * 0.76),
    ])
    p.drawPolygon(poly)


def _neve(p: QPainter, r: QRectF) -> None:
    p.setPen(QPen(_COR_NEVE, max(1.3, r.width() * 0.045),
                  Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for i in range(3):
        x = r.left() + r.width() * (0.28 + 0.20 * i)
        y = r.top() + r.height() * (0.68 + 0.08 * (i % 2))
        s = r.width() * 0.07
        p.drawLine(QPointF(x - s, y), QPointF(x + s, y))
        p.drawLine(QPointF(x, y - s), QPointF(x, y + s))
        p.drawLine(QPointF(x - s * 0.7, y - s * 0.7),
                   QPointF(x + s * 0.7, y + s * 0.7))
        p.drawLine(QPointF(x - s * 0.7, y + s * 0.7),
                   QPointF(x + s * 0.7, y - s * 0.7))


def _nevoa(p: QPainter, r: QRectF) -> None:
    p.setPen(QPen(_COR_NUVEM_ESCURA, max(1.6, r.width() * 0.055),
                  Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for i in range(3):
        y = r.top() + r.height() * (0.52 + 0.16 * i)
        p.drawLine(QPointF(r.left() + r.width() * 0.18, y),
                   QPointF(r.right() - r.width() * 0.14, y))


class WeatherIcon(QWidget):
    """Icone leve, desenhado em QPainter, para o codigo WMO."""

    def __init__(self, parent=None, compacto: bool = False):
        super().__init__(parent)
        self._codigo = -1
        self._compacto = compacto
        lado = 30 if compacto else 58
        self.setFixedSize(QSize(lado, lado))

    @property
    def codigo(self) -> int:
        return self._codigo

    def set_codigo(self, codigo) -> None:
        try:
            self._codigo = int(codigo)
        except (TypeError, ValueError):
            self._codigo = -1
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        c = self._codigo
        if c in (0,):
            _sol(p, r)
        elif c in (1, 2):
            _sol(p, QRectF(r.left() - r.width() * 0.06,
                           r.top() - r.height() * 0.06,
                           r.width() * 0.72, r.height() * 0.72))
            _nuvem(p, QRectF(r.left() + r.width() * 0.22,
                             r.top() + r.height() * 0.34,
                             r.width() * 0.78, r.height() * 0.62))
        elif c == 3:
            _nuvem(p, r, _COR_NUVEM_ESCURA)
        elif c in (45, 48):
            _nevoa(p, r)
        elif c in (51, 53, 55, 56, 57):
            _nuvem(p, QRectF(r.left(), r.top(), r.width(), r.height() * 0.78))
            _chuva(p, r, 2)
        elif c in (61, 63, 65, 66, 67, 80, 81, 82):
            _nuvem(p, QRectF(r.left(), r.top(), r.width(), r.height() * 0.78),
                   _COR_NUVEM_ESCURA)
            _chuva(p, r, 3)
        elif c in (71, 73, 75, 77, 85, 86):
            _nuvem(p, QRectF(r.left(), r.top(), r.width(), r.height() * 0.78),
                   _COR_NUVEM)
            _neve(p, r)
        elif c in (95, 96, 99):
            _nuvem(p, QRectF(r.left(), r.top(), r.width(), r.height() * 0.78),
                   _COR_NUVEM_ESCURA)
            _raio(p, r)
        else:
            # Codigo desconhecido: icone neutro, sem inventar sol nem chuva.
            p.setPen(QPen(_COR_NEUTRO, max(1.4, r.width() * 0.05)))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(r.center(), r.width() * 0.26, r.height() * 0.26)
            p.drawLine(QPointF(r.center().x(), r.center().y() + r.height() * 0.08),
                       QPointF(r.center().x(), r.center().y() - r.height() * 0.10))
            p.drawPoint(QPointF(r.center().x(), r.center().y() + r.height() * 0.17))
        p.end()


class WeatherBrief(QWidget):
    """Destaque do dia pedido e a lista dos dias reais devolvidos."""

    def __init__(self, parent=None, modo='completo'):
        super().__init__(parent)
        self._modo = modo
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(7)

        topo = QHBoxLayout()
        topo.setContentsMargins(0, 0, 0, 0)
        topo.setSpacing(10)
        self._icone = WeatherIcon(self)
        topo.addWidget(self._icone, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)
        self._cidade = QLabel("")
        self._cidade.setWordWrap(True)
        self._cidade.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self._cidade.setStyleSheet("color:#e8fbff; background:transparent;")
        col.addWidget(self._cidade)
        self._rotulo = QLabel("")
        self._rotulo.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self._rotulo.setStyleSheet("color:#8ceaf0; background:transparent;")
        col.addWidget(self._rotulo)
        self._condicao = QLabel("")
        self._condicao.setWordWrap(True)
        self._condicao.setFont(QFont("Segoe UI", 11))
        self._condicao.setStyleSheet("color:#d8f8ff; background:transparent;")
        col.addWidget(self._condicao)
        self._temperaturas = QLabel("")
        self._temperaturas.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._temperaturas.setStyleSheet("color:#ffffff; background:transparent;")
        col.addWidget(self._temperaturas)
        self._chuva = QLabel("")
        self._chuva.setFont(QFont("Segoe UI", 10))
        self._chuva.setStyleSheet("color:#65c8ff; background:transparent;")
        col.addWidget(self._chuva)
        self._atuais = QLabel("")
        self._atuais.setWordWrap(True)
        self._atuais.setFont(QFont("Segoe UI", 9))
        self._atuais.setStyleSheet("color:#9fc4d2; background:transparent;")
        col.addWidget(self._atuais)
        topo.addLayout(col, 1)
        v.addLayout(topo)
        self._cabecalho = topo

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea {background:transparent; border:none;}"
            "QScrollBar:vertical {background:transparent; width:5px; margin:0;}"
            "QScrollBar::handle:vertical {background:rgba(116,220,236,110);"
            " min-height:18px; border-radius:2px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}"
            "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical"
            " {background:transparent;}")
        self._scroll.viewport().setStyleSheet("background:transparent;")
        self._lista = QWidget()
        self._lista.setStyleSheet("background:transparent;")
        self._lista_lay = QVBoxLayout(self._lista)
        self._lista_lay.setContentsMargins(0, 2, 2, 0)
        self._lista_lay.setSpacing(2)
        self._lista_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._lista)
        v.addWidget(self._scroll, 1)
        self._dados: dict = {}
        self._destaque: dict = {}

    @property
    def dados(self) -> dict:
        return self._dados

    def sizeHint(self) -> QSize:
        """Altura proporcional ao que há para desenhar (cabeçalho + até 7 dias)."""
        altura = 150 if self._modo != 'semana' else 0
        if self._modo == 'dia':
            return QSize(320, altura)
        for dia in (self._dados.get("dias") or [])[:7]:
            if isinstance(dia, dict):
                altura += 34
        return QSize(320, int(altura))

    def set_data(self, dados: dict) -> None:
        dados = dict(dados or {})
        self._dados = dados
        self._scroll.setVisible(self._modo != 'dia')
        dest = dict(dados.get("destaque") or {})
        self._cidade.setText(str(dados.get("cidade") or ""))
        self._rotulo.setText(_rotulo_do_destaque(dest))
        self._icone.set_codigo(dest.get("codigo"))
        self._condicao.setText(str(dest.get("condicao") or ""))
        self._condicao.setVisible(bool(self._condicao.text()))
        self._temperaturas.setText(_faixa_de_temperatura(dest))
        self._temperaturas.setVisible(bool(self._temperaturas.text()))
        chuva = dest.get("chuva")
        self._chuva.setText("" if chuva is None else _texto_chuva(chuva))
        self._chuva.setVisible(chuva is not None)
        self._atuais.setText(_texto_atuais(dest))
        self._atuais.setVisible(bool(self._atuais.text()))
        if self._modo == 'semana':
            for i in range(self._cabecalho.count()):
                item = self._cabecalho.itemAt(i)
                if item.widget():
                    item.widget().hide()
                elif item.layout():
                    for j in range(item.layout().count()):
                        widget = item.layout().itemAt(j).widget()
                        if widget:
                            widget.hide()

        while self._lista_lay.count():
            item = self._lista_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        dest_iso = str(dest.get("data") or "")
        for dia in (dados.get("dias") or [])[:7]:
            if not isinstance(dia, dict):
                continue
            self._lista_lay.addWidget(_linha_do_dia(dia, dia.get("data") == dest_iso))
        self._lista_lay.addStretch(1)


def _rotulo_do_destaque(dest: dict) -> str:
    iso = str(dest.get("data") or "")
    try:
        d = date.fromisoformat(iso[:10])
    except Exception:
        return _h("Data indisponível", "Date unavailable")
    hoje = date.today()
    if d == hoje:
        return _h("HOJE", "TODAY") + f' · {d:%d/%m/%Y}'
    if d == date.fromordinal(hoje.toordinal() + 1):
        return _h("AMANHÃ", "TOMORROW") + f' · {d:%d/%m/%Y}'
    return _dia_semana(d).upper() + f' · {d:%d/%m/%Y}'


def _faixa_de_temperatura(dest: dict) -> str:
    minimo = _graus(dest.get("min"))
    maximo = _graus(dest.get("max"))
    if minimo and maximo:
        return f"min. {minimo}   max. {maximo}"
    if minimo:
        return f"min. {minimo}"
    if maximo:
        return f"max. {maximo}"
    return ""


def _temperaturas_curtas(dia: dict) -> str:
    """Mínima e máxima da lista; o que não veio não vira barra solta."""
    minimo = _graus(dia.get("min"))
    maximo = _graus(dia.get("max"))
    if minimo and maximo:
        return f"{minimo} / {maximo}"
    return minimo or maximo


def _texto_chuva(valor) -> str:
    try:
        n = int(round(float(valor)))
    except (TypeError, ValueError):
        return ""
    return _h(f"Chuva {n}%", f"Rain {n}%")


def _texto_atuais(dest: dict) -> str:
    en = _em_ingles()
    partes = []
    campos = (
        ("agora", "Agora", "Now", ""),
        ("sensacao", "Sensacao", "Feels like", ""),
        ("umidade", "Umidade", "Humidity", "%"),
        ("vento", "Vento", "Wind", " km/h"),
    )
    for chave, pt, ingles, sufixo in campos:
        valor = dest.get(chave)
        if valor is None:
            continue
        try:
            numero = round(float(valor))
        except (TypeError, ValueError):
            continue
        rotulo = ingles if en else pt
        if chave in ("agora", "sensacao"):
            partes.append(f"{rotulo} {numero}°")
        else:
            partes.append(f"{rotulo} {numero}{sufixo}")
    return "  ·  ".join(partes)


def _h(pt: str, en: str) -> str:
    return en if _em_ingles() else pt


def _linha_do_dia(dia: dict, selecionado: bool = False) -> QWidget:
    linha = QFrame()
    linha.setObjectName("LinhaDia")
    cor = ("rgba(50,215,232,34)" if selecionado else "transparent")
    linha.setStyleSheet(
        f"QFrame#LinhaDia {{ background:{cor}; border:none;"
        " border-radius:8px; }"
        "QLabel { background:transparent; border:none; }")
    h = QHBoxLayout(linha)
    h.setContentsMargins(6, 2, 4, 2)
    h.setSpacing(6)
    try:
        d = date.fromisoformat(str(dia.get("data") or "")[:10])
        nome = _dia_semana(d, curto=True)
        data_txt = f"{d.day:02d}/{d.month:02d}"
    except Exception:
        nome = str(dia.get("dia_semana") or "")[:3]
        data_txt = str(dia.get("data") or "")[:5]

    nome_lbl = QLabel(nome)
    nome_lbl.setFixedWidth(42)
    nome_lbl.setStyleSheet("color:#c8edf5;")
    h.addWidget(nome_lbl)
    data_lbl = QLabel(data_txt)
    data_lbl.setFixedWidth(46)
    data_lbl.setStyleSheet("color:#7892a8;")
    h.addWidget(data_lbl)
    icone = WeatherIcon(compacto=True)
    icone.set_codigo(dia.get("codigo"))
    h.addWidget(icone, 0)
    temps = QLabel(_temperaturas_curtas(dia))
    temps.setStyleSheet("color:#e8fbff;")
    temps.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    h.addWidget(temps, 1)
    chuva = dia.get("chuva")
    chuva_lbl = QLabel("" if chuva is None else _texto_chuva(chuva))
    chuva_lbl.setFixedWidth(62)
    chuva_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    chuva_lbl.setStyleSheet("color:#65c8ff;")
    h.addWidget(chuva_lbl)
    return linha


# ── cartao ────────────────────────────────────────────────────────────────
class WeatherWeek(QWidget):
    """Dias reais em uma faixa, reorganizada em duas linhas quando necessário."""

    def __init__(self, dados, parent=None):
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(4)
        self._dias = []
        self._colunas = 0
        selecionada = (dados.get('destaque') or {}).get('data')
        for dia in (dados.get('dias') or [])[:7]:
            if not isinstance(dia, dict):
                continue
            tile = QFrame(self)
            realce = dia.get('data') == selecionada
            tile.setStyleSheet('QFrame {background:rgba(50,215,232,%d); border-radius:8px;}'
                              'QLabel {background:transparent; color:#e8fbff; border:none;}' % (35 if realce else 8))
            v = QVBoxLayout(tile)
            v.setContentsMargins(3, 6, 3, 6)
            v.setSpacing(3)
            try:
                d = date.fromisoformat(dia['data'])
                rotulo = f'{_dia_semana(d, True)}\n{d:%d/%m}'
            except (ValueError, KeyError, TypeError):
                rotulo = str(dia.get('data') or '')
            for item in (QLabel(rotulo), WeatherIcon(compacto=True), QLabel(_temperaturas_curtas(dia))):
                if isinstance(item, QLabel):
                    item.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setFont(QFont('Segoe UI', 9))
                else:
                    item.set_codigo(dia.get('codigo'))
                v.addWidget(item, 0, Qt.AlignmentFlag.AlignCenter)
            tile.setToolTip(str(dia.get('condicao') or ''))
            self._dias.append(tile)
        self._reorganizar()

    def largura_dia(self):
        return max(64, int(QFontMetricsF(QFont('Segoe UI', 9)).horizontalAdvance('00° / 00°')) + 12)

    def altura_para_largura(self, largura):
        colunas = max(1, min(len(self._dias) or 1, largura // self.largura_dia()))
        return ((len(self._dias) + colunas - 1) // colunas) * 105

    def sizeHint(self):
        return QSize(4 * self.largura_dia(), self.altura_para_largura(self.width()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reorganizar()

    def _reorganizar(self):
        colunas = max(1, min(len(self._dias) or 1, self.width() // self.largura_dia()))
        if colunas == self._colunas:
            return
        for i in range(self._colunas):
            self._grid.setColumnStretch(i, 0)
        while self._grid.count():
            self._grid.takeAt(0)
        self._colunas = colunas
        for i, tile in enumerate(self._dias):
            self._grid.addWidget(tile, i // colunas, i % colunas)
            self._grid.setColumnStretch(i % colunas, 1)


_TITULOS = {
    "hora": ("HORA CERTA", "CURRENT TIME"),
    "data": ("DATA DE HOJE", "TODAY'S DATE"),
    "tudo": ("HORA E DATA", "TIME AND DATE"),
    "clima": ("PREVISAO DO TEMPO", "WEATHER"),
}


class BriefCard(QFrame):
    """O cartao temporario do Canvas. Um por vez, com o seu proprio fechar."""

    fechar = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BriefGlass")
        self.setAutoFillBackground(False)
        self.setStyleSheet(
            "QFrame#BriefGlass {"
            " background:transparent; border:none; }"
            "QLabel { color:#e4f4fc; background:transparent; border:none; }"
            "QPushButton { color:#d7f5ff; background:rgba(120,184,207,22);"
            " border:1px solid rgba(149,209,229,55); border-radius:12px;"
            " padding:8px; }")
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 11, 16, 13)
        v.setSpacing(6)
        topo = QHBoxLayout()
        topo.setContentsMargins(0, 0, 0, 0)
        topo.setSpacing(6)
        self._titulo = QLabel("")
        self._titulo.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self._titulo.setStyleSheet(
            "color:#8ceaf0; background:transparent; letter-spacing:1px;")
        topo.addWidget(self._titulo, 1)
        self._fechar = QPushButton("×", self)
        self._fechar.setObjectName("BriefFechar")
        self._fechar.setAccessibleName("Fechar card")
        self._fechar.setToolTip("Fechar")
        self._fechar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fechar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._fechar.setFixedSize(24, 24)
        self._fechar.setStyleSheet(
            "QPushButton {color:#8ceaf0; background:transparent; border:none;"
            " border-radius:12px; padding:0; font-size:16px; font-weight:600;}"
            "QPushButton:hover, QPushButton:focus {color:#ffffff;"
            " background:rgba(50,215,232,65); border:none;}")
        self._fechar.clicked.connect(lambda _=False: self.fechar.emit())
        topo.addWidget(self._fechar, 0, Qt.AlignmentFlag.AlignTop)
        v.addLayout(topo)
        self._corpo = QWidget(self)
        self._corpo.setStyleSheet("background:transparent;")
        self._corpo_lay = QVBoxLayout(self._corpo)
        self._corpo_lay.setContentsMargins(0, 0, 0, 0)
        self._corpo_lay.setSpacing(0)
        v.addWidget(self._corpo, 1)
        self._conteudo: QWidget | None = None
        self._tipo = ""
        self._entrada = 1.0

    @property
    def tipo(self) -> str:
        return self._tipo

    @property
    def conteudo(self) -> QWidget | None:
        return self._conteudo

    def set_content(self, dados: dict) -> None:
        dados = dict(dados or {})
        tipo = str(dados.get("tipo") or "")
        self._tipo = tipo
        pt, en = _TITULOS.get(tipo, ("AGORA", "NOW"))
        self._titulo.setText(en if _em_ingles() else pt)
        while self._corpo_lay.count():
            item = self._corpo_lay.takeAt(0)
            antigo = item.widget()
            if antigo is not None:
                antigo.setParent(None)
                antigo.deleteLater()
        self._conteudo = None
        if tipo == "clima":
            corpo = dados.get("dados") if isinstance(dados.get("dados"), dict) else dados
            if dados.get('modo') == 'semana':
                self._titulo.setText(_h('PRÓXIMOS DIAS', 'NEXT DAYS'))
                widget = WeatherWeek(corpo, self._corpo)
            else:
                widget = WeatherBrief(self._corpo, dados.get('modo', 'completo'))
                widget.set_data(corpo)
        else:
            widget = ClockDateBrief(tipo if tipo in ("hora", "data", "tudo")
                                    else "tudo", self._corpo)
            widget.set_date()
        self._corpo_lay.addWidget(widget)
        self._conteudo = widget

    def tamanho_conteudo(self) -> QSize | None:
        """QSize preferido do conteúdo visível (sem as margens do próprio cartão)."""
        if self._conteudo is None:
            return None
        try:
            alvo = self._conteudo.sizeHint()
            return QSize(int(alvo.width()), int(alvo.height()))
        except Exception:
            return None

    def paintEvent(self, event):
        """Vidro glassmorphism: preenchimento translúcido, gradiente, contorno
        parcial e reflexo curvo. Pintura CPU, sem blur por quadro nem shader."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        raio = 20.0
        gradiente = QLinearGradient(r.left(), r.top(), r.right(), r.bottom())
        gradiente.setColorAt(0, _cor_tema('#183a50', 236))
        gradiente.setColorAt(1, _cor_tema('#14203e', 236))
        p.setBrush(gradiente)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, raio, raio)
        recorte = QPainterPath()
        recorte.addRoundedRect(r, raio, raio)
        p.setClipPath(recorte)
        reflexo = QPainterPath(QPointF(r.left(), r.top() + 32))
        reflexo.cubicTo(r.width() * .25, r.top() - 10,
                       r.width() * .55, r.top() + 40, r.right(), r.top() + 12)
        reflexo.translate((1 - self._entrada) * -14, 0)
        p.setPen(QPen(_cor_tema('#9b85ff', 52), 12))
        p.drawPath(reflexo)
        p.setPen(QPen(_cor_tema('#7df9ff', 145), 1))
        borda = QPainterPath(QPointF(r.left(), r.top() + 65))
        borda.lineTo(r.left(), r.top() + raio)
        borda.quadTo(r.topLeft(), QPointF(r.left() + raio, r.top()))
        borda.lineTo(r.left() + r.width() * .52, r.top())
        p.drawPath(borda)
        p.end()

    def set_entry_progress(self, progresso):
        self._entrada = float(progresso)
        self.update(self.rect().adjusted(0, 0, 0, -max(0, self.height() - 65)))

    def set_paused(self, pausado: bool) -> None:
        if hasattr(self._conteudo, "set_paused"):
            self._conteudo.set_paused(bool(pausado))


class BriefDeck(QWidget):
    """Deck de blocos temporarios do Canvas.

    Um bloco para hora/data; dois blocos para o clima (dia pedido + semana),
    que entram, sao substituídos, fecham e expiram juntos — uma unica resposta.
    """

    fechar = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background:transparent; border:none;")
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet('QScrollArea {background:transparent; border:none;}'
                                  'QScrollBar:vertical {width:6px; background:transparent;}'
                                  'QScrollBar::handle:vertical {background:rgba(116,220,236,100); min-height:20px;}'
                                  'QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}')
        self._canvas = QWidget()
        self._scroll.setWidget(self._canvas)
        externo.addWidget(self._scroll)
        self._lay = QBoxLayout(QBoxLayout.Direction.TopToBottom, self._canvas)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(10)
        self._cartoes: list = []
        self._horizontal = False
        self._montar()

    def _montar(self) -> None:
        while self._lay.count():
            self._lay.takeAt(0)
        for cartao in self._cartoes:
            self._lay.addWidget(cartao, 1)
        self._reconfigurar()

    def _reconfigurar(self) -> None:
        minimo = max(280, QFontMetricsF(QFont('Segoe UI', 10)).horizontalAdvance('Máxima 00°  Mínima 00°') + 40)
        if len(self._cartoes) > 1 and self.width() >= minimo * 2 + 10:
            self._lay.setDirection(QBoxLayout.Direction.LeftToRight)
            self._horizontal = True
        else:
            self._lay.setDirection(QBoxLayout.Direction.TopToBottom)
            self._horizontal = False
        self._canvas.setMinimumHeight(self.tamanho_para_largura(max(1, self.width() - 6)).height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reconfigurar()

    @property
    def cartoes(self) -> list:
        return list(self._cartoes)

    def set_conteudo(self, tipo: str, dados: dict) -> None:
        """(tipo, dados) -> cartoes do deck. Clima abre dois blocos."""
        while self._lay.count():
            self._lay.takeAt(0)
        for antigo in self._cartoes:
            antigo.set_paused(True)
            antigo.hide()
            antigo.setParent(None)
            antigo.deleteLater()
        self._cartoes = []
        if str(tipo or '') == 'clima':
            dia = BriefCard()
            corpo = dados.get('dados') if isinstance(dados.get('dados'), dict) else dados
            dia.set_content({'tipo': 'clima', 'dados': corpo, 'modo': 'dia'})
            semana = BriefCard()
            semana.set_content({
                'tipo': 'clima',
                'modo': 'semana',
                'dados': {
                    'cidade': corpo.get('cidade'),
                    'semana': True,
                    'destaque': corpo.get('destaque') or {},
                    'dias': corpo.get('dias') or [],
                },
            })
            self._cartoes = [dia, semana] if corpo.get('dias') else [dia]
            if not corpo.get('dias'):
                semana.deleteLater()
        else:
            cartao = BriefCard()
            cartao.set_content({'tipo': tipo})
            self._cartoes = [cartao]
        for cartao in self._cartoes:
            cartao.fechar.connect(lambda: self.fechar.emit())
        self._montar()
        self._reconfigurar()
        self._scroll.verticalScrollBar().setValue(0)

    def set_paused(self, pausado: bool) -> None:
        for cartao in self._cartoes:
            if hasattr(cartao, 'set_paused'):
                cartao.set_paused(bool(pausado))

    def set_entry_progress(self, progresso):
        for cartao in self._cartoes:
            cartao.set_entry_progress(progresso)

    def tamanho_conteudo(self) -> QSize | None:
        if not self._cartoes:
            return None
        hints = []
        for cartao in self._cartoes:
            hint = cartao.tamanho_conteudo()
            hints.append(hint or QSize(320, 150))
        if self._horizontal and len(self._cartoes) > 1:
            return QSize(sum(int(h.width()) for h in hints),
                         max(int(h.height()) for h in hints))
        return QSize(max(int(h.width()) for h in hints),
                     sum(int(h.height()) for h in hints))

    def tamanho_para_largura(self, largura):
        """Calcula sem depender da geometria antiga do deck durante o resize."""
        minimo = max(280, QFontMetricsF(QFont('Segoe UI', 10)).horizontalAdvance('Máxima 00°  Mínima 00°') + 40)
        horizontal = len(self._cartoes) > 1 and largura >= minimo * 2 + 10
        largura_cartao = (largura - 10) // 2 if horizontal else largura
        alturas = []
        for cartao in self._cartoes:
            conteudo = cartao.conteudo
            if isinstance(conteudo, WeatherWeek):
                altura = conteudo.altura_para_largura(max(1, largura_cartao - 32))
            else:
                altura = conteudo.sizeHint().height()
            alturas.append(altura + 54)
        return QSize(largura, max(alturas, default=120) if horizontal else sum(alturas) + 10 * max(0, len(alturas) - 1))
