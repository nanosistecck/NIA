# -*- coding: utf-8 -*-
"""Gerenciador de Planos da NIA — interface redesenhada.

A lógica de negócio permanece em ``core.planos``; esta janela apenas apresenta
o catálogo e delega ações. Todos os ``objectName`` usados por sinais, testes e
pelo fluxo do Canvas são preservados.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QStyledItemDelegate, QTextEdit,
    QVBoxLayout, QWidget,
)

from core import lembretes as LEM
from core import modelos_planos as MP
from core import planos as BP
from core.planos import (
    ConflitoDeRevisao, ErroPlano, PlanoInvalido, TIPOS,
    atualizar, buscar, criar, listar, restaurar,
)
from core.planos import excluir_permanentemente as _excluir_permanentemente

# ── design tokens ─────────────────────────────────────────────────────────
COR_FUNDO = "#0A0F1E"
COR_SECUNDARIO = "#0D1930"
COR_PAINEL = "#10213B"
COR_CAMPO = "#0E2038"
COR_BORDA = "#254666"
COR_BORDA_ATIVA = "#00B8FF"
COR_AZUL = "#00B8FF"
COR_AZUL_PROFUNDO = "#176BFF"
COR_VIOLETA = "#8A5CFF"
COR_TEXTO = "#EAF2FF"
COR_TEXTO2 = "#9FB3C8"
COR_TEXTO3 = "#7089A4"
COR_SUCESSO = "#22C55E"
COR_EXCLUSAO = "#EF4444"
COR_ATENCAO = "#F5B942"

_ESTILO = f"""
QWidget#PlanosRoot {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 {COR_FUNDO}, stop:0.6 #0B1930, stop:1 #101C38);
}}
QLabel {{ color: {COR_TEXTO}; background: transparent; }}
QLabel#TituloJanela {{ font-size: 18px; font-weight: 600; }}
QLabel#SubtituloJanela {{ color: {COR_TEXTO2}; font-size: 12px; }}
QLabel#TituloSecao {{ color: {COR_TEXTO}; font-size: 14px; font-weight: 600; }}
QLabel#Meta {{ color: {COR_TEXTO3}; font-size: 12px; }}
QLineEdit, QTextEdit, QComboBox {{
    color: {COR_TEXTO}; background: {COR_CAMPO};
    border: 1px solid {COR_BORDA}; border-radius: 9px; padding: 6px 10px;
    font-size: 13px; selection-background-color: #176BFF;
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 2px solid {COR_BORDA_ATIVA}; background: #102a46;
}}
QLineEdit:read-only {{ color: {COR_TEXTO2}; }}
QComboBox {{ min-height: 42px; padding-left: 12px; }}
QListWidget {{
    background: {COR_SECUNDARIO}; border: 1px solid {COR_BORDA};
    border-radius: 14px; padding: 12px;
}}
QListWidget::item {{ border-radius: 12px; padding: 6px; }}
QListWidget::item:selected {{
    border: 1px solid {COR_BORDA_ATIVA}; background: #173E63;
}}
QScrollBar:vertical {{ background: transparent; width: 5px; }}
QScrollBar::handle:vertical {{
    background: rgba(66,97,124,180); border-radius: 3px; min-height: 24px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QPushButton {{
    color: {COR_TEXTO}; background: #11243E;
    border: 1px solid {COR_BORDA}; border-radius: 10px;
    padding: 8px 14px; min-height: 40px; font-size: 13px;
}}
QPushButton:hover {{ background: #17395B; border-color: {COR_AZUL}; }}
QPushButton:focus {{ border: 2px solid {COR_AZUL}; }}
QPushButton:disabled {{ color: {COR_TEXTO3}; background: #0D1B2E; }}
QPushButton#salvar_plano {{
    color: white; font-weight: 600; font-size: 14px; min-height: 44px;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #00C8F8, stop:0.55 {COR_AZUL_PROFUNDO}, stop:1 {COR_VIOLETA});
    border: none; border-radius: 10px;
}}
QFrame#PlanosForm {{
    background: {COR_PAINEL}; border: 1px solid {COR_BORDA};
    border-radius: 14px;
}}
QFrame#PlanosHeader {{
    background: rgba(16,33,59,170); border: 1px solid {COR_BORDA};
    border-radius: 14px;
}}
QFrame#PlanosFiltros {{
    background: rgba(13,25,48,170); border: 1px solid {COR_BORDA};
    border-radius: 12px;
}}
QWidget#PlanosAcoes {{
    background: rgba(16,33,59,150); border: 1px solid {COR_BORDA};
    border-radius: 12px;
}}
QLabel#Status {{ color: {COR_TEXTO2}; font-size: 11px; }}
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


class _ItemPlanoDelegate(QStyledItemDelegate):
    """Card do plano desenhado localmente, sem widgets por item."""

    def sizeHint(self, option, index):
        from PyQt6.QtCore import QSize
        return QSize(option.rect.width(), 76)

    def paint(self, painter, option, index):
        from PyQt6.QtCore import QRectF
        painter.save()
        ret = QRectF(option.rect).adjusted(2, 2, -2, -2)
        selecionado = bool(option.state & QStyleState_Selected)
        if selecionado:
            grad = QLinearGradient(ret.left(), ret.top(), ret.right(), ret.bottom())
            grad.setColorAt(0, QColor("#173E63"))
            grad.setColorAt(0.7, QColor("#192A54"))
            grad.setColorAt(1, QColor("#34236A"))
            painter.setBrush(grad)
            painter.setPen(QColor(COR_BORDA_ATIVA))
        else:
            painter.setBrush(QColor(13, 25, 48, 220))
            painter.setPen(QColor(COR_BORDA))
        painter.drawRoundedRect(ret, 12, 12)
        identificador = index.data(Qt.ItemDataRole.UserRole) or ""
        plano = index.data(Qt.ItemDataRole.UserRole + 1)
        simbolo = _ICONE_TIPO.get(getattr(plano, "tipo", "Geral"), "G")
        quadrado = QRectF(ret.left() + 14, ret.top() + 18, 40, 40)
        painter.setBrush(QColor(20, 56, 86))
        painter.setPen(QColor(_COR_TIPO.get(getattr(plano, "tipo", "Geral"), COR_AZUL)))
        painter.drawRoundedRect(quadrado, 10, 10)
        painter.setPen(QColor(COR_TEXTO))
        fonte = QFont("Segoe UI", 14)
        fonte.setWeight(QFont.Weight.DemiBold)
        painter.setFont(fonte)
        painter.drawText(quadrado, Qt.AlignmentFlag.AlignCenter, simbolo)
        titulo = getattr(plano, "titulo", "") if plano is not None else ""
        painter.setPen(QColor(COR_TEXTO))
        fonte.setPointSize(15)
        painter.setFont(fonte)
        painter.drawText(QRectF(ret.left() + 66, ret.top() + 12,
                                ret.width() - 90, 24),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         titulo[:48])
        fonte.setPointSize(12)
        fonte.setWeight(QFont.Weight.Normal)
        painter.setFont(fonte)
        painter.setPen(QColor(COR_TEXTO2))
        meta = f"{getattr(plano, 'tipo', '')}  ·  {getattr(plano, 'status', '')}"
        painter.drawText(QRectF(ret.left() + 66, ret.top() + 38,
                                ret.width() - 90, 18),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, meta)
        data = str(getattr(plano, "atualizado_em", ""))[:16].replace("T", " ")
        painter.setPen(QColor(COR_TEXTO3))
        painter.drawText(QRectF(ret.left() + 66, ret.top() + 54,
                                ret.width() - 90, 18),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, data)
        painter.restore()


QStyleState_Selected = QAbstractItemView.SelectionMode.ExtendedSelection  # placeholder substituído abaixo
from PyQt6.QtWidgets import QStyle  # noqa: E402

QStyleState_Selected = QStyle.StateFlag.State_Selected


class LembretesDialog(QDialog):
    """Consulta local de próximos e vencidos, com ações manuais."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NIA · Lembretes")
        self.setMinimumSize(520, 360)
        self.setStyleSheet(_ESTILO)
        layout = QVBoxLayout(self)
        self.lista = QListWidget(self)
        self.lista.setObjectName("lista_lembretes")
        layout.addWidget(self.lista, 1)
        botoes = QHBoxLayout()
        for nome, rotulo in (("adiar_lembrete", "Adiar"),
                             ("concluir_lembrete", "Concluir"),
                             ("cancelar_lembrete", "Cancelar"),
                             ("fechar_lembretes", "Fechar")):
            botao = QPushButton(rotulo, self)
            botao.setObjectName(nome)
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
            lista_item.setData(0x0100, item.get("id"))
            self.lista.addItem(lista_item)

    def _selecionado(self):
        atual = self.lista.currentItem()
        return atual.data(0x0100) if atual else None

    def _adiar(self) -> None:
        ident = self._selecionado()
        if ident:
            LEM.adiar(ident, str(LEM.proximo().get("horario"))
                      if LEM.proximo() else str(LEM.carregar(ident).get("horario")))
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


class PlanosWindow(QWidget):
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
        self.resize(1280, 720)
        self.setMinimumSize(960, 540)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(_ESTILO)
        self._planos: list[BP.Plano] = []
        self.plano_selecionado_id: str | None = None
        self._modo: str | None = None
        self._timer_busca = QTimer(self)
        self._timer_busca.setSingleShot(True)
        self._timer_busca.setInterval(180)
        self._timer_busca.timeout.connect(self.aplicar_filtros)
        self._construir()
        self._conectar()
        self.recarregar()

    # ── construção ──────────────────────────────────────────────────────
    def _construir(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        cabecalho = QFrame(self)
        cabecalho.setObjectName("PlanosHeader")
        cabecalho.setFixedHeight(64)
        cab = QHBoxLayout(cabecalho)
        cab.setContentsMargins(18, 8, 18, 8)
        simbolo = QLabel("N", cabecalho)
        simbolo.setFixedSize(36, 36)
        simbolo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        simbolo.setStyleSheet(
            f"background: {COR_AZUL_PROFUNDO}; color: white; border-radius: 10px;"
            " font-weight: 600; font-size: 16px;")
        cab.addWidget(simbolo)
        titulos = QVBoxLayout()
        lbl = QLabel("NIA — Planos", cabecalho)
        lbl.setObjectName("TituloJanela")
        sub = QLabel("Organize ideias, estudos e objetivos", cabecalho)
        sub.setObjectName("SubtituloJanela")
        titulos.addWidget(lbl)
        titulos.addWidget(sub)
        cab.addLayout(titulos, 1)
        root.addWidget(cabecalho)

        filtros = QFrame(self)
        filtros.setObjectName("PlanosFiltros")
        filtros.setFixedHeight(48)
        fl = QHBoxLayout(filtros)
        fl.setContentsMargins(10, 3, 10, 3)
        fl.setSpacing(10)
        self.campo_busca = QLineEdit(filtros)
        self.campo_busca.setObjectName("campo_busca")
        self.campo_busca.setPlaceholderText("Buscar por título ou objetivo...")
        self.campo_busca.setFixedHeight(42)
        self.campo_busca.setClearButtonEnabled(True)
        fl.addWidget(self.campo_busca, 2)
        self.filtro_tipo = QComboBox(filtros)
        self.filtro_tipo.setObjectName("filtro_tipo")
        self.filtro_tipo.addItems(["Todos", *TIPOS])
        self.filtro_tipo.setFixedWidth(220)
        fl.addWidget(self.filtro_tipo)
        self.filtro_status = QComboBox(filtros)
        self.filtro_status.setObjectName("filtro_status")
        self.filtro_status.addItems(["Ativos", "Arquivados", "Todos"])
        self.filtro_status.setFixedWidth(200)
        fl.addWidget(self.filtro_status)
        root.addWidget(filtros)

        corpo = QSplitter(Qt.Orientation.Horizontal, self)
        esquerda = QWidget(corpo)
        ev = QVBoxLayout(esquerda)
        ev.setContentsMargins(0, 0, 0, 0)
        ev.setSpacing(8)
        titulo_lista = QLabel("LISTA DE PLANOS", esquerda)
        titulo_lista.setObjectName("TituloSecao")
        ev.addWidget(titulo_lista)
        self.lista = QListWidget(esquerda)
        self.lista.setObjectName("lista_planos")
        self.lista.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.lista.setItemDelegate(_ItemPlanoDelegate(self.lista))
        ev.addWidget(self.lista, 1)
        corpo.addWidget(esquerda)
        formulario = QFrame(corpo)
        formulario.setObjectName("PlanosForm")
        fv = QVBoxLayout(formulario)
        fv.setContentsMargins(16, 16, 16, 16)
        fv.setSpacing(10)
        cab_form = QHBoxLayout()
        self.icone_form = QLabel("G", formulario)
        self.icone_form.setFixedSize(40, 40)
        self.icone_form.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icone_form.setStyleSheet(
            f"background: {COR_AZUL_PROFUNDO}; color: white; border-radius: 10px;")
        cab_form.addWidget(self.icone_form)
        self.titulo_form = QLabel("Dados do plano", formulario)
        self.titulo_form.setObjectName("TituloSecao")
        cab_form.addWidget(self.titulo_form, 1)
        fv.addLayout(cab_form)
        campos = QFormLayout()
        self.campo_titulo = QLineEdit(formulario)
        self.campo_titulo.setObjectName("campo_titulo")
        self.campo_titulo.setPlaceholderText("Título do plano")
        self.campo_objetivo = QTextEdit(formulario)
        self.campo_objetivo.setObjectName("campo_objetivo")
        self.campo_objetivo.setPlaceholderText("Objetivo do plano")
        self.campo_objetivo.setMinimumHeight(100)
        self.campo_tipo = QComboBox(formulario)
        self.campo_tipo.setObjectName("campo_tipo")
        self.campo_tipo.addItems(list(TIPOS))
        campos.addRow("TÍTULO", self.campo_titulo)
        campos.addRow("OBJETIVO", self.campo_objetivo)
        campos.addRow("TIPO", self.campo_tipo)
        fv.addLayout(campos)
        fv.addStretch(1)
        self.salvar = QPushButton("Salvar plano", formulario)
        self.salvar.setObjectName("salvar_plano")
        self.botao_cancelar = QPushButton("Cancelar", formulario)
        self.botao_cancelar.setObjectName("cancelar")
        fv.addWidget(self.salvar)
        fv.addWidget(self.botao_cancelar)
        corpo.addWidget(formulario)
        corpo.setStretchFactor(0, 3)
        corpo.setStretchFactor(1, 1)
        corpo.setMinimumHeight(240)
        root.addWidget(corpo, 1)

        acoes = QWidget(self)
        acoes.setObjectName("PlanosAcoes")
        acoes.setFixedHeight(64)
        al = QHBoxLayout(acoes)
        al.setContentsMargins(12, 8, 12, 8)
        al.setSpacing(8)
        self.botoes = {}
        primarios = (
            ("novo_plano", "Novo plano", 140),
            ("visualizar", "Visualizar", 110),
            ("editar", "Editar", 100),
            ("abrir_canvas", "Editar no Canvas", 160),
            ("abrir_canvas_ia", "Editar com a NIA", 165),
        )
        secundarios = (
            ("lembretes", "Lembretes", 120),
            ("excluir_permanentemente", "Excluir", 110),
            ("arquivar", "Arquivar", 110),
            ("restaurar", "Restaurar", 110),
        )
        for nome, rotulo, largura in (*primarios, *secundarios):
            botao = QPushButton(rotulo, acoes)
            botao.setObjectName(nome)
            botao.setFixedWidth(largura)
            self.botoes[nome] = botao
            al.addWidget(botao)
        al.addStretch()
        root.addWidget(acoes)

        self.status = QLabel("", self)
        self.status.setObjectName("Status")
        self.status.setFixedHeight(28)
        root.addWidget(self.status)

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
        self.salvar.clicked.connect(self.salvar_plano)
        self.botao_cancelar.clicked.connect(self.cancelar)
        self._set_formulario(editable=False)
        self._atualizar_botoes()

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
        self.lista.clear()
        for plano in resultados:
            item = QListWidgetItem(plano.titulo)
            item.setData(Qt.ItemDataRole.UserRole, plano.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, plano)
            self.lista.addItem(item)
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
            return
        self.plano_selecionado_id = item.data(Qt.ItemDataRole.UserRole)
        self._preencher_formulario(self._por_id(self.plano_selecionado_id))
        self._atualizar_botoes()

    def _preencher_formulario(self, plano: BP.Plano | None) -> None:
        if plano is None:
            self.campo_titulo.clear()
            self.campo_objetivo.clear()
            self.campo_tipo.setCurrentText("Geral")
            self.icone_form.setText("G")
            self.titulo_form.setText("Dados do plano")
            return
        self.campo_titulo.setText(plano.titulo)
        self.campo_objetivo.setPlainText(plano.objetivo)
        self.campo_tipo.setCurrentText(plano.tipo)
        self.icone_form.setText(_ICONE_TIPO.get(plano.tipo, "G"))
        self.titulo_form.setText(f"{plano.titulo} · rev {plano.revisao}")

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
        for nome in ("abrir_canvas", "abrir_canvas_ia", "arquivar"):
            self.botoes[nome].setEnabled(
                habilitado and selecionado.status == "ativo")
        self.botoes["restaurar"].setEnabled(
            habilitado and selecionado.status == "arquivado")
        selecionados = self.lista.selectedItems()
        fora = [i for i in selecionados
                if (BP.carregar(i.data(Qt.ItemDataRole.UserRole)) or None) is None
                or BP.carregar(i.data(Qt.ItemDataRole.UserRole)).status != "arquivado"]
        self.botoes["excluir_permanentemente"].setEnabled(bool(selecionados))
        self.botoes["lembretes"].setEnabled(habilitado)
        if fora:
            self.status.setText(
                f"{len(selecionados)} selecionado(s); "
                f"{len(fora)} fora do filtro de arquivados.")

    # ── ações (backend inalterado) ───────────────────────────────────────
    def novo_plano(self) -> None:
        self._modo = "novo"
        self.plano_selecionado_id = None
        self.lista.clearSelection()
        self._preencher_formulario(None)
        self.titulo_form.setText("Novo plano")
        self._set_formulario(editable=True)
        self.status.setText("Preencha título e objetivo.")

    def visualizar(self) -> None:
        plano = self._por_id(self.plano_selecionado_id)
        if plano is None:
            return
        self._modo = "visualizar"
        self._preencher_formulario(plano)
        self._set_formulario(editable=False)

    def editar(self) -> None:
        plano = self._por_id(self.plano_selecionado_id)
        if plano is None:
            return
        self._modo = "editar"
        self._preencher_formulario(plano)
        self._set_formulario(editable=True)

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
        self.status.setText(aviso or "✓ Alterações salvas")

    def cancelar(self) -> None:
        self._modo = None
        self._preencher_formulario(self._por_id(self.plano_selecionado_id))
        self._set_formulario(editable=False)
        self.status.setText("Alterações descartadas.")

    def _arquivar(self) -> None:
        plano = self._por_id(self.plano_selecionado_id)
        if plano is None:
            return
        try:
            atualizar(plano.id, {"status": "arquivado"}, plano.revisao)
        except ConflitoDeRevisao:
            self.status.setText("Conflito de revisão. Recarregue os planos.")
            self.recarregar()
            return
        except (OSError, ValueError):
            self.status.setText("Falha ao salvar. Tente novamente.")
            return
        self.recarregar()
        self.selecionar(plano.id)

    def _restaurar(self) -> None:
        plano = self._por_id(self.plano_selecionado_id)
        if plano is None:
            return
        try:
            restaurar(plano.id, plano.revisao)
        except ConflitoDeRevisao:
            self.status.setText("Conflito de revisão. Recarregue os planos.")
            self.recarregar()
            return
        except (OSError, ValueError):
            self.status.setText("Falha ao salvar. Tente novamente.")
            return
        self.recarregar()
        self.selecionar(plano.id)

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
                 "Esta ação é definitiva.")
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Excluir planos permanentemente?")
        caixa.setText(texto)
        caixa.setIcon(QMessageBox.Icon.Warning)
        cancelar = caixa.addButton(QMessageBox.StandardButton.Cancel)
        caixa.addButton("Excluir permanentemente",
                        QMessageBox.StandardButton.DestructiveRole)
        caixa.setDefaultButton(cancelar)
        return caixa.exec() == 1

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
            if plano.status != "arquivado":
                falhas.append(ident)
                continue
            try:
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
