# -*- coding: utf-8 -*-
"""Gerenciador de Planos da NIA — interface redesenhada.

A lógica de negócio permanece em ``core.planos``; esta janela apenas apresenta
o catálogo e delega ações. Todos os ``objectName`` usados por sinais, testes e
pelo fluxo do Canvas são preservados.
"""
from __future__ import annotations

from PyQt6.QtCore import QItemSelectionModel, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QFontMetrics, QKeySequence, QLinearGradient, QPainter, QPen, QShortcut,
)
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSizePolicy,
    QSplitter, QStyle, QStyledItemDelegate, QTextEdit, QVBoxLayout, QWidget,
)

from core import lembretes as LEM
from core import modelos_planos as MP
from core import planos as BP
from core.frame_nativo import FrameNativoMixin
from core.planos import (
    ConflitoDeRevisao, ErroPlano, PlanoInvalido, TIPOS,
    atualizar, buscar, criar, listar, restaurar,
)
from core.planos import excluir_permanentemente as _excluir_permanentemente

# ── design tokens ─────────────────────────────────────────────────────────
COR_FUNDO = "#081527"
COR_SECUNDARIO = "#0A1D33"
COR_PAINEL = "#0C2236"
COR_CAMPO = "#04121F"
COR_BORDA = "#1B4A66"
COR_BORDA_ATIVA = "#19D3F3"
COR_AZUL = "#19D3F3"
COR_AZUL_PROFUNDO = "#1673FF"
COR_VIOLETA = "#7C5CFF"
COR_TEXTO = "#E6F6FF"
COR_TEXTO2 = "#8FB5C9"
COR_TEXTO3 = "#6F93A9"          # rótulos e metadados secundários
COR_SUCESSO = "#2EE6A0"
COR_EXCLUSAO = "#FF7A7A"
COR_ATENCAO = "#F2A13B"

_ESTILO = f"""
QWidget#PlanosRoot {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 #0C3646, stop:0.45 {COR_FUNDO}, stop:1 #0E1D40);
}}

/* ── textos ─────────────────────────────────────────────────────────── */
QLabel {{ color: {COR_TEXTO}; background: transparent; }}
QLabel#TituloJanela {{ font-size: 22px; font-weight: 600; }}
QLabel#SubtituloJanela {{ color: {COR_TEXTO2}; font-size: 12px; }}
QLabel#TituloSecao {{
    color: {COR_TEXTO2}; font-size: 12px; font-weight: 600;
}}
QLabel#Campo {{
    color: {COR_TEXTO2}; font-size: 11px; font-weight: 600;
}}
QLabel#Meta {{ color: {COR_TEXTO3}; font-size: 12px; }}
QLabel#Status {{ color: {COR_TEXTO2}; font-size: 12px; }}
QLabel#TituloForm {{ font-size: 18px; font-weight: 600; }}

/* ── campos ─────────────────────────────────────────────────────────── */
QLineEdit, QTextEdit, QComboBox {{
    color: {COR_TEXTO}; background: {COR_CAMPO};
    border: 1px solid rgba(25,211,243,40); border-radius: 10px;
    padding: 0 14px; font-size: 13px; selection-background-color: #176BFF;
}}
QTextEdit {{ padding: 10px 14px; }}
QLineEdit:hover, QTextEdit:hover, QComboBox:hover {{
    border-color: rgba(25,211,243,110);
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 1px solid {COR_BORDA_ATIVA}; background: #061A2B;
}}
QLineEdit:read-only, QTextEdit:read-only {{
    color: {COR_TEXTO2}; background: rgba(4,18,31,160);
    border-color: rgba(25,211,243,22);
}}
QLineEdit#campo_busca {{
    background: transparent; border: none; padding: 0 4px; font-size: 14px;
}}
QLineEdit#campo_busca:focus {{ background: transparent; }}
QComboBox {{ min-height: 36px; padding-left: 16px; border-radius: 18px; }}
QComboBox:disabled {{ color: {COR_TEXTO3}; background: rgba(4,18,31,160); }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    color: {COR_TEXTO}; background: #061A2B;
    border: 1px solid {COR_BORDA}; border-radius: 10px; padding: 4px;
    outline: 0; selection-background-color: rgba(25,211,243,40);
}}

/* ── listas ─────────────────────────────────────────────────────────── */
QListWidget#lista_planos {{
    background: rgba(8,26,44,150); border: 1px solid rgba(25,211,243,40);
    border-radius: 18px; padding: 10px; outline: 0;
}}
QListWidget::item {{ border-radius: 14px; padding: 6px; }}
QListWidget#lista_planos::item,
QListWidget#lista_planos::item:selected,
QListWidget#lista_planos::item:hover {{
    background: transparent; border: none; padding: 0;
}}
QListWidget#lista_lembretes {{
    background: {COR_SECUNDARIO}; border: 1px solid {COR_BORDA};
    border-radius: 14px; padding: 8px; outline: 0;
}}
QListWidget#lista_lembretes::item:selected {{
    border: 1px solid {COR_BORDA_ATIVA}; background: #173E63;
}}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{
    background: rgba(25,211,243,70); border-radius: 3px; min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: rgba(25,211,243,160); }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QSplitter::handle {{ background: transparent; }}

/* ── botões ─────────────────────────────────────────────────────────── */
QPushButton {{
    color: #D9EEFA; background: rgba(10,36,58,140);
    border: 1px solid rgba(25,211,243,50); border-radius: 10px;
    padding: 0 16px; min-height: 38px; font-size: 13px;
}}
QPushButton:hover {{
    background: rgba(18,58,88,200); border-color: rgba(25,211,243,140);
}}
QPushButton:pressed {{ background: rgba(10,40,64,220); }}
QPushButton:focus {{ border: 1px solid {COR_AZUL}; }}
QPushButton:disabled {{
    color: rgba(143,181,201,90); background: rgba(10,36,58,50);
    border-color: rgba(25,211,243,18);
}}
QPushButton#novo_plano {{
    color: white; font-weight: 600; border: none;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #14C8EE, stop:0.6 {COR_AZUL_PROFUNDO}, stop:1 {COR_VIOLETA});
}}
QPushButton#novo_plano:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #3ED8F5, stop:0.6 #3585FF, stop:1 #9274FF);
}}
QPushButton#salvar_plano {{
    color: white; font-weight: 600; font-size: 14px; min-height: 44px;
    border: none;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #14C8EE, stop:0.6 {COR_AZUL_PROFUNDO}, stop:1 {COR_VIOLETA});
}}
QPushButton#salvar_plano:disabled {{
    color: rgba(143,181,201,90); background: rgba(10,36,58,50);
    border: 1px solid rgba(25,211,243,18);
}}
QPushButton#excluir_permanentemente {{
    color: #FF9A9A; border-color: rgba(255,122,122,90);
}}
QPushButton#excluir_permanentemente:hover {{
    color: white; background: rgba(90,26,36,200); border-color: {COR_EXCLUSAO};
}}
QPushButton#excluir_permanentemente:disabled {{
    color: rgba(143,181,201,90); background: rgba(10,36,58,50);
    border-color: rgba(25,211,243,18);
}}

/* ── molduras ───────────────────────────────────────────────────────── */
QFrame#PlanosForm {{
    background: rgba(12,34,54,190); border: 1px solid rgba(25,211,243,46);
    border-radius: 18px;
}}
QFrame#PlanosHeader {{
    background: rgba(12,38,60,150); border: 1px solid rgba(25,211,243,40);
    border-radius: 18px;
}}
QFrame#PlanosFiltros {{
    background: transparent; border: none;
}}
QFrame#PlanosBuscaBox {{
    background: rgba(12,38,60,150); border: 1px solid rgba(25,211,243,40);
    border-radius: 12px;
}}
QWidget#PlanosAcoes {{
    background: rgba(12,38,60,160); border: 1px solid rgba(25,211,243,40);
    border-radius: 18px;
}}
"""

# Ícones por tipo — letras curtas, sem emoji, legíveis sem cor.
_ICONE_TIPO = {
    "Geral": "G", "Produto": "P", "Projeto": "J", "Conteúdo": "C",
    "Estudos": "E", "Finanças": "F",
}
_COR_TIPO = {
    "Geral": COR_AZUL, "Produto": COR_VIOLETA, "Projeto": COR_AZUL_PROFUNDO,
    "Conteúdo": COR_SUCESSO, "Estudos": COR_ATENCAO, "Finanças": COR_EXCLUSAO,
}

QStyleState_Selected = QStyle.StateFlag.State_Selected
QStyleState_MouseOver = QStyle.StateFlag.State_MouseOver


def _fonte(pixels: int, peso: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """Fonte em pixels: o tamanho não muda com o DPI e o card não estoura."""
    fonte = QFont("Segoe UI")
    fonte.setPixelSize(pixels)
    fonte.setWeight(peso)
    return fonte


class _ItemPlanoDelegate(QStyledItemDelegate):
    """Card do plano desenhado localmente, sem widgets por item."""

    ALTURA = 78

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), self.ALTURA)

    def paint(self, painter, option, index):
        plano = index.data(Qt.ItemDataRole.UserRole + 1)
        tipo = getattr(plano, "tipo", "Geral")
        cor_tipo = QColor(_COR_TIPO.get(tipo, COR_AZUL))
        selecionado = bool(option.state & QStyleState_Selected)
        sobre = bool(option.state & QStyleState_MouseOver)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # moldura do card: vidro escuro, brilho quando selecionado
        ret = QRectF(option.rect).adjusted(4, 4, -4, -4)
        if selecionado:
            grad = QLinearGradient(ret.left(), ret.top(), ret.right(), ret.bottom())
            grad.setColorAt(0, QColor(23, 76, 110, 210))
            grad.setColorAt(1, QColor(40, 36, 104, 140))
            painter.setBrush(grad)
            painter.setPen(QPen(QColor(25, 211, 243, 170), 1))
        elif sobre:
            painter.setBrush(QColor(16, 40, 66, 200))
            painter.setPen(QPen(QColor(25, 211, 243, 90), 1))
        else:
            painter.setBrush(QColor(8, 26, 44, 115))
            painter.setPen(QPen(QColor(25, 211, 243, 28), 1))
        painter.drawRoundedRect(ret, 14, 14)

        # barra de acento à esquerda, mais forte no card selecionado
        painter.setPen(Qt.PenStyle.NoPen)
        cor_acento = QColor(cor_tipo)
        cor_acento.setAlpha(255 if selecionado else 90)
        painter.setBrush(cor_acento)
        painter.drawRoundedRect(QRectF(ret.left(), ret.top() + 16,
                                       3, ret.height() - 32), 2, 2)

        # ícone do tipo
        lado = 42
        quadrado = QRectF(ret.left() + 18, ret.center().y() - lado / 2, lado, lado)
        painter.setBrush(QColor(8, 28, 46, 230))
        painter.setPen(QPen(cor_tipo, 1))
        painter.drawRoundedRect(quadrado, 12, 12)
        painter.setPen(cor_tipo)
        painter.setFont(_fonte(16, QFont.Weight.DemiBold))
        painter.drawText(quadrado, Qt.AlignmentFlag.AlignCenter,
                         _ICONE_TIPO.get(tipo, "G"))

        # área de texto
        esquerda = quadrado.right() + 16
        direita = ret.right() - 18
        largura = direita - esquerda
        topo = ret.center().y() - 20
        alinhar = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        # data, alinhada à direita na linha do título
        data = str(getattr(plano, "atualizado_em", ""))[:16].replace("T", " ")
        fonte_data = _fonte(11)
        largura_data = QFontMetrics(fonte_data).horizontalAdvance(data)
        painter.setFont(fonte_data)
        painter.setPen(QColor(COR_TEXTO3))
        painter.drawText(QRectF(direita - largura_data, topo, largura_data, 22),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         data)

        # título, truncado com reticências em vez de cortado
        fonte_titulo = _fonte(16, QFont.Weight.DemiBold)
        titulo = getattr(plano, "titulo", "") if plano is not None else ""
        titulo = QFontMetrics(fonte_titulo).elidedText(
            titulo, Qt.TextElideMode.ElideRight, int(largura - largura_data - 12))
        painter.setFont(fonte_titulo)
        painter.setPen(QColor(COR_TEXTO))
        painter.drawText(QRectF(esquerda, topo, largura, 22), alinhar, titulo)

        # tipo · status
        status = str(getattr(plano, "status", ""))
        painter.setFont(_fonte(12))
        painter.setPen(QColor(COR_ATENCAO if status == "arquivado" else COR_TEXTO2))
        painter.drawText(QRectF(esquerda, topo + 24, largura, 18), alinhar,
                         f"{getattr(plano, 'tipo', '')}  ·  {status}")
        painter.restore()


class LembretesDialog(QDialog):
    """Consulta local de próximos e vencidos, com ações manuais."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NIA · Lembretes")
        self.setMinimumSize(520, 360)
        self.setStyleSheet(_ESTILO)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        self.lista = QListWidget(self)
        self.lista.setObjectName("lista_lembretes")
        layout.addWidget(self.lista, 1)
        botoes = QHBoxLayout()
        botoes.setSpacing(8)
        for nome, rotulo in (("adiar_lembrete", "Adiar"),
                             ("concluir_lembrete", "Concluir"),
                             ("cancelar_lembrete", "Cancelar"),
                             ("fechar_lembretes", "Fechar")):
            botao = QPushButton(rotulo, self)
            botao.setObjectName(nome)
            botao.setCursor(Qt.CursorShape.PointingHandCursor)
            botoes.addWidget(botao)
            setattr(self, nome, botao)
        layout.addLayout(botoes)
        self.adiar_lembrete.clicked.connect(self._adiar)
        self.concluir_lembrete.clicked.connect(self._concluir)
        self.cancelar_lembrete.clicked.connect(self._cancelar)
        self.fechar_lembretes.clicked.connect(self.close)
        self.recarregar()

    def recarregar(self) -> None:
        self.lista.clear()
        for item in LEM.listar_todos():
            if item.get("estado") != "pendente":
                continue
            rotulo = (f"{item.get('estado')} · {str(item.get('horario'))[:16]} · "
                      f"{item.get('assunto')} · {item.get('plano_id')}")
            lista_item = QListWidgetItem(rotulo)
            lista_item.setData(Qt.ItemDataRole.UserRole, item.get("id"))
            self.lista.addItem(lista_item)

    def _selecionado(self):
        atual = self.lista.currentItem()
        return atual.data(Qt.ItemDataRole.UserRole) if atual else None

    def _adiar(self) -> None:
        ident = self._selecionado()
        if not ident:
            return
        proximo = LEM.proximo()
        horario = (proximo if proximo else LEM.carregar(ident)).get("horario")
        LEM.adiar(ident, str(horario))
        self.recarregar()

    def _concluir(self) -> None:
        ident = self._selecionado()
        if ident:
            LEM.concluir(ident)
            self.recarregar()

    def _cancelar(self) -> None:
        ident = self._selecionado()
        if ident:
            LEM.cancelar(ident)
            self.recarregar()


class PlanosWindow(FrameNativoMixin, QWidget):
    """Catálogo e formulário de planos, reaproveitando `core.planos`."""

    fechada = pyqtSignal()
    abrir_canvas = pyqtSignal(str)
    abrir_canvas_assistido = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setObjectName("PlanosRoot")
        self.setWindowTitle("NIA · Planos")
        self.resize(1440, 810)
        self.setMinimumSize(1100, 640)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(_ESTILO)
        self._planos: list[BP.Plano] = []
        self._ids_pendentes_exclusao: list[str] = []
        self.plano_selecionado_id: str | None = None
        self._modo: str | None = None
        self._timer_busca = QTimer(self)
        self._timer_busca.setSingleShot(True)
        self._timer_busca.setInterval(180)
        self._timer_busca.timeout.connect(self.aplicar_filtros)
        self._construir()
        self._conectar()
        self.recarregar()
        self._instalar_frame_nativo(cor=COR_FUNDO)

    # ── construção ──────────────────────────────────────────────────────
    def _construir(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(14)
        coluna = root

        # cabeçalho: marca, título e busca
        cabecalho = QFrame(self)
        cabecalho.setObjectName("PlanosHeader")
        cabecalho.setFixedHeight(68)
        cab = QHBoxLayout(cabecalho)
        cab.setContentsMargins(20, 10, 20, 10)
        cab.setSpacing(14)
        simbolo = QLabel("N", cabecalho)
        simbolo.setFixedSize(38, 38)
        simbolo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        simbolo.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f" stop:0 #14C8EE, stop:1 {COR_VIOLETA});"
            " color: white; border-radius: 12px; font-weight: 600; font-size: 17px;")
        cab.addWidget(simbolo)
        titulos = QVBoxLayout()
        titulos.setSpacing(0)
        lbl = QLabel("NIA — Planos", cabecalho)
        lbl.setObjectName("TituloJanela")
        sub = QLabel("Organize ideias, estudos e objetivos", cabecalho)
        sub.setObjectName("SubtituloJanela")
        titulos.addWidget(lbl)
        titulos.addWidget(sub)
        cab.addLayout(titulos, 1)
        busca_box = QFrame(cabecalho)
        busca_box.setObjectName("PlanosBuscaBox")
        busca_box.setFixedSize(360, 42)
        bl = QHBoxLayout(busca_box)
        bl.setContentsMargins(14, 0, 8, 0)
        bl.setSpacing(8)
        lupa = QLabel("⌕", busca_box)
        lupa.setStyleSheet(f"color: {COR_TEXTO3}; font-size: 16px;")
        bl.addWidget(lupa)
        self.campo_busca = QLineEdit(busca_box)
        self.campo_busca.setObjectName("campo_busca")
        self.campo_busca.setPlaceholderText("Buscar por título ou objetivo...")
        self.campo_busca.setClearButtonEnabled(True)
        bl.addWidget(self.campo_busca, 1)
        cab.addWidget(busca_box)
        coluna.addWidget(cabecalho)

        # filtros em pílula, alinhados à direita
        filtros = QFrame(self)
        filtros.setObjectName("PlanosFiltros")
        filtros.setFixedHeight(38)
        fl = QHBoxLayout(filtros)
        fl.setContentsMargins(4, 0, 4, 0)
        fl.setSpacing(10)
        rotulo_filtro = QLabel("FILTRAR", filtros)
        rotulo_filtro.setObjectName("TituloSecao")
        fl.addWidget(rotulo_filtro)
        fl.addStretch(1)
        self.filtro_tipo = QComboBox(filtros)
        self.filtro_tipo.setObjectName("filtro_tipo")
        self.filtro_tipo.addItems(["Todos", *TIPOS])
        self.filtro_tipo.setFixedSize(200, 36)
        fl.addWidget(self.filtro_tipo)
        self.filtro_status = QComboBox(filtros)
        self.filtro_status.setObjectName("filtro_status")
        self.filtro_status.addItems(["Ativos", "Arquivados", "Todos"])
        self.filtro_status.setFixedSize(180, 36)
        fl.addWidget(self.filtro_status)
        coluna.addWidget(filtros)

        # corpo: lista + painel de detalhes
        corpo = QSplitter(Qt.Orientation.Horizontal, self)
        corpo.setHandleWidth(16)
        corpo.setChildrenCollapsible(False)
        esquerda = QWidget(corpo)
        ev = QVBoxLayout(esquerda)
        ev.setContentsMargins(0, 0, 0, 0)
        ev.setSpacing(10)
        titulo_lista = QLabel("LISTA DE PLANOS", esquerda)
        titulo_lista.setObjectName("TituloSecao")
        ev.addWidget(titulo_lista)
        self.lista = QListWidget(esquerda)
        self.lista.setObjectName("lista_planos")
        self.lista.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.lista.setItemDelegate(_ItemPlanoDelegate(self.lista))
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lista.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.lista.setUniformItemSizes(True)
        self.lista.setMouseTracking(True)
        ev.addWidget(self.lista, 1)
        corpo.addWidget(esquerda)

        formulario = QFrame(corpo)
        formulario.setObjectName("PlanosForm")
        formulario.setMinimumWidth(360)
        fv = QVBoxLayout(formulario)
        fv.setContentsMargins(22, 22, 22, 22)
        fv.setSpacing(12)
        cab_form = QHBoxLayout()
        cab_form.setSpacing(14)
        self.icone_form = QLabel("G", formulario)
        self.icone_form.setFixedSize(42, 42)
        self.icone_form.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._estilizar_icone("Geral")
        cab_form.addWidget(self.icone_form)
        self.titulo_form = QLabel("Dados do plano", formulario)
        self.titulo_form.setObjectName("TituloForm")
        self.titulo_form.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        cab_form.addWidget(self.titulo_form, 1)
        fv.addLayout(cab_form)

        campos = QFormLayout()
        campos.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        campos.setContentsMargins(0, 6, 0, 0)
        campos.setVerticalSpacing(6)
        self.campo_titulo = QLineEdit(formulario)
        self.campo_titulo.setObjectName("campo_titulo")
        self.campo_titulo.setPlaceholderText("Título do plano")
        self.campo_titulo.setFixedHeight(40)
        self.campo_objetivo = QTextEdit(formulario)
        self.campo_objetivo.setObjectName("campo_objetivo")
        self.campo_objetivo.setPlaceholderText("Objetivo do plano")
        self.campo_objetivo.setMinimumHeight(120)
        self.campo_tipo = QComboBox(formulario)
        self.campo_tipo.setObjectName("campo_tipo")
        self.campo_tipo.addItems(list(TIPOS))
        self.campo_tipo.setFixedHeight(40)
        campos.addRow("TÍTULO", self.campo_titulo)
        campos.addRow("OBJETIVO", self.campo_objetivo)
        campos.addRow("TIPO", self.campo_tipo)
        for campo in (self.campo_titulo, self.campo_objetivo, self.campo_tipo):
            campos.labelForField(campo).setObjectName("Campo")
        fv.addLayout(campos)
        fv.addStretch(1)
        self.salvar = QPushButton("Salvar plano", formulario)
        self.salvar.setObjectName("salvar_plano")
        self.botao_cancelar = QPushButton("Cancelar", formulario)
        self.botao_cancelar.setObjectName("cancelar")
        for botao in (self.salvar, self.botao_cancelar):
            botao.setCursor(Qt.CursorShape.PointingHandCursor)
            fv.addWidget(botao)
        corpo.addWidget(formulario)
        corpo.setStretchFactor(0, 3)
        corpo.setStretchFactor(1, 1)
        corpo.setSizes([860, 380])
        corpo.setMinimumHeight(240)
        coluna.addWidget(corpo, 1)

        # barra de ações: primárias à esquerda, secundárias à direita
        acoes = QFrame(self)
        acoes.setObjectName("PlanosAcoes")
        acoes.setFixedHeight(66)
        al = QHBoxLayout(acoes)
        al.setContentsMargins(14, 10, 14, 10)
        al.setSpacing(8)
        self.botoes = {}
        primarios = (
            ("novo_plano", "+ Novo plano", 140),
            ("visualizar", "Visualizar", 110),
            ("editar", "Editar", 100),
            ("abrir_canvas", "Editar no Canvas", 150),
            ("abrir_canvas_ia", "Editar com a NIA", 155),
        )
        secundarios = (
            ("lembretes", "Lembretes", 115),
            ("arquivar", "Arquivar", 105),
            ("restaurar", "Desarquivar", 105),
            ("excluir_permanentemente", "Excluir", 100),
        )
        for grupo in (primarios, secundarios):
            for nome, rotulo, largura in grupo:
                botao = QPushButton(rotulo, acoes)
                botao.setObjectName(nome)
                botao.setMinimumWidth(largura)
                botao.setCursor(Qt.CursorShape.PointingHandCursor)
                self.botoes[nome] = botao
                al.addWidget(botao)
            if grupo is primarios:
                al.addStretch(1)
        coluna.addWidget(acoes)

        self.status = QLabel("", self)
        self.status.setObjectName("Status")
        self.status.setFixedHeight(22)
        coluna.addWidget(self.status)

    def _conectar(self) -> None:
        self.campo_busca.textChanged.connect(lambda *_: self._timer_busca.start())
        self.filtro_tipo.currentTextChanged.connect(lambda *_: self.aplicar_filtros())
        self.filtro_status.currentTextChanged.connect(lambda *_: self.aplicar_filtros())
        self.lista.currentItemChanged.connect(
            lambda atual, _antigo: self._item_selecionado(atual))
        self.lista.itemSelectionChanged.connect(self._atualizar_botoes)
        for nome, funcao in (
            ("novo_plano", self.novo_plano),
            ("visualizar", self.visualizar),
            ("editar", self.editar),
            ("abrir_canvas", self._abrir_canvas),
            ("abrir_canvas_ia", self._abrir_canvas_assistido),
            ("lembretes", self._abrir_lembretes),
            ("excluir_permanentemente", self._excluir_permanentemente),
            ("arquivar", self._arquivar),
            ("restaurar", self._restaurar),
        ):
            self.botoes[nome].clicked.connect(funcao)
        self._atalho_excluir = QShortcut(QKeySequence(Qt.Key.Key_Delete), self.lista)
        self._atalho_excluir.setContext(Qt.ShortcutContext.WidgetShortcut)
        self._atalho_excluir.setAutoRepeat(False)
        self._atalho_excluir.activated.connect(self._excluir_permanentemente)
        self.lista.setToolTip("Ctrl+clique ou Shift+clique para selecionar vários; Delete para excluir.")
        self.salvar.clicked.connect(self.salvar_plano)
        self.botao_cancelar.clicked.connect(self.cancelar)
        self._set_formulario(editable=False)
        self._atualizar_botoes()

    def _estilizar_icone(self, tipo: str) -> None:
        """Ícone do formulário no mesmo padrão visual do card da lista."""
        cor = _COR_TIPO.get(tipo, COR_AZUL)
        self.icone_form.setStyleSheet(
            f"background: rgba(8,28,46,230); color: {cor}; border: 1px solid {cor};"
            " border-radius: 12px; font-weight: 600; font-size: 17px;")

    # ── catálogo ────────────────────────────────────────────────────────
    def recarregar(self) -> None:
        self._planos, avisos = listar()
        if avisos:
            self.status.setText(
                f"{len(avisos)} plano(s) não puderam ser lidos; os demais estão disponíveis.")
        self.aplicar_filtros()

    def aplicar_filtros(self) -> None:
        sit = self.filtro_status.currentText()
        status = {"Ativos": "ativo", "Arquivados": "arquivado"}.get(sit, "")
        tipo = self.filtro_tipo.currentText()
        resultados = buscar(
            self._planos, self.campo_busca.text(),
            "" if tipo == "Todos" else tipo, status)
        ids_selecionados = {i.data(Qt.ItemDataRole.UserRole)
                            for i in self.lista.selectedItems()}
        atual_id = self.plano_selecionado_id
        self.lista.clear()
        for plano in resultados:
            item = QListWidgetItem(plano.titulo)
            item.setData(Qt.ItemDataRole.UserRole, plano.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, plano)
            self.lista.addItem(item)
        atual = None
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            ident = item.data(Qt.ItemDataRole.UserRole)
            if ident in ids_selecionados:
                item.setSelected(True)
                if atual is None or ident == atual_id:
                    atual = item
        if atual is not None:
            self.lista.setCurrentItem(atual, QItemSelectionModel.SelectionFlag.NoUpdate)
        elif self.lista.count():
            self.lista.setCurrentRow(0)
        filtro_ativo = (bool(self.campo_busca.text())
                        or self.filtro_tipo.currentIndex() > 0
                        or self.filtro_status.currentIndex() > 0)
        if not resultados and (filtro_ativo or self._planos):
            self.status.setText("Nenhum plano encontrado · limpar filtros")
        elif not self._planos:
            self.status.setText("Nenhum plano · crie o primeiro plano")
        else:
            selecionados = len(self.lista.selectedItems())
            self.status.setText(
                f"{len(resultados)} plano(s) · {selecionados} selecionado(s)")
        self._atualizar_botoes()

    def selecionar(self, plano_id: str) -> None:
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == plano_id:
                self.lista.setCurrentItem(item)
                return
        self.plano_selecionado_id = plano_id
        self._preencher_formulario(self._por_id(plano_id))
        self._atualizar_botoes()

    def _por_id(self, plano_id: str | None) -> BP.Plano | None:
        return next((p for p in self._planos if p.id == plano_id), None)

    def _item_selecionado(self, item: QListWidgetItem | None) -> None:
        if item is None:
            self.plano_selecionado_id = None
            self._modo = None
            self._preencher_formulario(None)
            self._set_formulario(editable=False)
            self._atualizar_botoes()
            return
        self._modo = None
        self._set_formulario(editable=False)
        self.plano_selecionado_id = item.data(Qt.ItemDataRole.UserRole)
        self._preencher_formulario(self._por_id(self.plano_selecionado_id))
        self._atualizar_botoes()

    def _preencher_formulario(self, plano: BP.Plano | None) -> None:
        if plano is None:
            self.campo_titulo.clear()
            self.campo_objetivo.clear()
            self.campo_tipo.setCurrentText("Geral")
            self.icone_form.setText("G")
            self._estilizar_icone("Geral")
            self.titulo_form.setText("Dados do plano")
            self.titulo_form.setToolTip("")
            return
        self.campo_titulo.setText(plano.titulo)
        self.campo_objetivo.setPlainText(plano.objetivo)
        self.campo_tipo.setCurrentText(plano.tipo)
        self.icone_form.setText(_ICONE_TIPO.get(plano.tipo, "G"))
        self._estilizar_icone(plano.tipo)
        self.titulo_form.setText(f"{plano.titulo} · rev {plano.revisao}")
        self.titulo_form.setToolTip(plano.titulo)

    def _set_formulario(self, editable: bool) -> None:
        self.campo_titulo.setReadOnly(not editable)
        self.campo_objetivo.setReadOnly(not editable)
        self.campo_tipo.setEnabled(editable)
        self.salvar.setEnabled(editable)
        self.botao_cancelar.setEnabled(editable)

    def _atualizar_botoes(self) -> None:
        selecionado = self._por_id(self.plano_selecionado_id)
        habilitado = selecionado is not None
        for nome in ("visualizar", "editar"):
            self.botoes[nome].setEnabled(habilitado)
        for nome in ("abrir_canvas", "abrir_canvas_ia"):
            self.botoes[nome].setEnabled(
                habilitado and selecionado.status == "ativo")
        selecionados = self.lista.selectedItems()
        planos = [self._por_id(i.data(Qt.ItemDataRole.UserRole)) for i in selecionados]
        self.botoes["arquivar"].setEnabled(any(p and p.status == "ativo" for p in planos))
        self.botoes["restaurar"].setEnabled(any(p and p.status == "arquivado" for p in planos))
        self.botoes["excluir_permanentemente"].setEnabled(bool(selecionados))
        self.botoes["lembretes"].setEnabled(habilitado)
        if selecionados:
            self.status.setText(
                f"{self.lista.count()} plano(s) · {len(selecionados)} selecionado(s)")

    # ── ações (backend inalterado) ───────────────────────────────────────
    def novo_plano(self) -> None:
        self._modo = "novo"
        self.plano_selecionado_id = None
        self.lista.clearSelection()
        self._preencher_formulario(None)
        self.titulo_form.setText("Novo plano")
        self._set_formulario(editable=True)
        self.campo_titulo.setFocus()
        self.status.setText("Preencha título e objetivo.")

    def visualizar(self) -> None:
        plano = self._por_id(self.plano_selecionado_id)
        if plano is None:
            return
        self._modo = "visualizar"
        self._preencher_formulario(plano)
        self._set_formulario(editable=False)
        dialogo = QDialog(self)
        dialogo.setObjectName("visualizacao_plano")
        dialogo.setWindowTitle(f"NIA Planos · {plano.titulo}")
        dialogo.resize(640, 440)
        layout = QVBoxLayout(dialogo)
        titulo = QLineEdit(plano.titulo, dialogo)
        titulo.setReadOnly(True)
        layout.addWidget(titulo)
        layout.addWidget(QLabel(
            f"{plano.tipo} · {plano.status} · revisão {plano.revisao}", dialogo))
        objetivo = QTextEdit(dialogo)
        objetivo.setPlainText(plano.objetivo)
        objetivo.setReadOnly(True)
        layout.addWidget(objetivo)
        fechar = QPushButton("Fechar", dialogo)
        fechar.clicked.connect(dialogo.accept)
        layout.addWidget(fechar)
        dialogo.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialogo.setWindowModality(Qt.WindowModality.WindowModal)
        dialogo.show()

    def editar(self) -> None:
        plano = self._por_id(self.plano_selecionado_id)
        if plano is None:
            return
        self._modo = "editar"
        self._preencher_formulario(plano)
        self._set_formulario(editable=True)
        self.campo_titulo.setFocus()

    def salvar_plano(self) -> None:
        titulo = self.campo_titulo.text().strip()
        objetivo = self.campo_objetivo.toPlainText().strip()
        tipo = self.campo_tipo.currentText()
        try:
            if self._modo == "novo":
                plano = criar(titulo, objetivo, tipo)
            else:
                atual = self._por_id(self.plano_selecionado_id)
                if atual is None:
                    raise PlanoInvalido("plano inexistente")
                plano = atualizar(
                    atual.id,
                    {"titulo": titulo, "objetivo": objetivo, "tipo": tipo},
                    atual.revisao)
        except ConflitoDeRevisao:
            self.status.setText("Conflito de revisão. Recarregue os planos.")
            return
        except (PlanoInvalido, ErroPlano):
            self.status.setText("Título e objetivo são obrigatórios.")
            return
        except (OSError, ValueError):
            self.status.setText("Falha ao salvar. Tente novamente.")
            return
        aviso = ""
        if plano.tipo in MP.TIPOS_MODELO:
            try:
                plano = BP.inicializar_mapa(plano.id)
                mapa = MP.aplicar_estrutura_no_mapa(
                    plano.mapa,
                    MP.estrutura_modelo(plano.tipo, plano.titulo, plano.objetivo),
                    plano.mapa.get("raiz_id"))
                plano = BP.atualizar(plano.id, {"mapa": mapa}, plano.revisao)
            except (BP.ErroPlano, OSError, ValueError):
                aviso = "Plano criado, mas a estrutura inicial falhou."
        self._modo = None
        self.recarregar()
        self.selecionar(plano.id)
        self._set_formulario(editable=False)
        self.status.setText(aviso or "✓ Alterações salvas")

    def cancelar(self) -> None:
        self._modo = None
        self._preencher_formulario(self._por_id(self.plano_selecionado_id))
        self._set_formulario(editable=False)
        self.status.setText("Alterações descartadas.")

    def _arquivar(self) -> None:
        self._alterar_status_selecionados("arquivado")

    def _restaurar(self) -> None:
        self._alterar_status_selecionados("ativo")

    def _alterar_status_selecionados(self, destino: str) -> None:
        planos = [self._por_id(item.data(Qt.ItemDataRole.UserRole))
                  for item in self.lista.selectedItems()]
        alterados, falhas = 0, []
        for plano in planos:
            if plano is None or plano.status == destino:
                continue
            try:
                acao = BP.arquivar if destino == "arquivado" else restaurar
                acao(plano.id, plano.revisao)
                alterados += 1
            except (BP.ErroPlano, OSError, ValueError):
                falhas.append(plano.titulo)
        self.recarregar()
        verbo = "arquivado(s)" if destino == "arquivado" else "desarquivado(s)"
        mensagem = f"{alterados} plano(s) {verbo}."
        if falhas:
            mensagem += f" Falha em {len(falhas)}: " + ", ".join(falhas) + "."
        self.status.setText(mensagem)

    def _abrir_canvas(self) -> None:
        if self.plano_selecionado_id:
            self.abrir_canvas.emit(self.plano_selecionado_id)

    def _abrir_canvas_assistido(self) -> None:
        if self.plano_selecionado_id:
            self.abrir_canvas_assistido.emit(self.plano_selecionado_id)

    def _confirmar_exclusao(self, ids: list[str]) -> bool:
        planos = [BP.carregar(i) for i in ids]
        planos = [p for p in planos if p is not None]
        titulos = "\n".join(f"• {p.titulo} ({p.id[:8]})" for p in planos)
        texto = (f"Excluir permanentemente {len(planos)} plano(s)?\n\n{titulos}\n\n"
                 "Planos ativos serão arquivados antes da exclusão.\n"
                 "Esta ação é definitiva.")
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Excluir planos permanentemente?")
        caixa.setText(texto)
        caixa.setIcon(QMessageBox.Icon.Warning)
        cancelar = caixa.addButton(QMessageBox.StandardButton.Cancel)
        excluir = caixa.addButton("Excluir permanentemente",
                                  QMessageBox.ButtonRole.DestructiveRole)
        caixa.setDefaultButton(cancelar)
        caixa.exec()
        return caixa.clickedButton() is excluir

    def _excluir_permanentemente(self) -> None:
        ids = [item.data(Qt.ItemDataRole.UserRole)
               for item in self.lista.selectedItems()]
        if not ids or not self._confirmar_exclusao(ids):
            return
        excluidos, falhas = [], []
        for ident in ids:
            plano = BP.carregar(ident)
            if plano is None:
                continue
            try:
                if plano.status != "arquivado":
                    plano = BP.arquivar(ident, plano.revisao)
                _excluir_permanentemente(ident, plano.revisao)
                excluidos.append(ident)
            except (BP.ErroPlano, OSError):
                falhas.append(ident)
        self.recarregar()
        if falhas:
            self.status.setText(
                f"Excluídos {len(excluidos)}; falharam {len(falhas)}: "
                + ", ".join(f[:8] for f in falhas) + ".")
            self._ids_pendentes_exclusao = falhas
        else:
            self.status.setText(f"{len(excluidos)} plano(s) excluído(s).")

    def _abrir_lembretes(self) -> None:
        LembretesDialog(self).exec()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt)
        self.fechada.emit()
        super().closeEvent(event)
