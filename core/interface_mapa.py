# -*- coding: utf-8 -*-
"""Editor visual do mapa de um plano (Etapa 2 do Canvas Infinito).

``QGraphicsScene``/``QGraphicsView`` com cards e conexões desenhados por
``QPainter`` (sem proxy widgets, sem timer de repaint em repouso). Comandos
``QUndoCommand`` cobrem criação, edição, movimento, progresso, conexões e
exclusão. A gravação reusa ``core.planos.atualizar`` (atômica, com revisão).
"""
from __future__ import annotations

import copy
from typing import Any

from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QKeySequence, QPainter, QPainterPath, QPen,
    QShortcut, QUndoCommand, QUndoStack,
)
from PyQt6.QtWidgets import (
    QComboBox, QFormLayout, QGraphicsItem, QGraphicsPathItem, QGraphicsScene,
    QGraphicsTextItem, QGraphicsView, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from core import planos as BP
from core.planos import (
    FORMATO, TIPOS_CARD, STATUS_TAREFA, ConflitoDeRevisao, Plano,
    atualizar, novo_id, validar_mapa,
)

_PRI = "#00d4ff"
_TEXT = "#d8f8ff"
_MUTED = "#8fb8cc"
_BG = "#011520"
_CARD_W = 196.0
_CARD_H = 84.0

_ESTILO = f"""
QWidget#EditorMapaRoot {{ background: #00060a; }}
QGraphicsView {{ background: {_BG}; border: 1px solid #0f4060; border-radius: 8px; }}
QLabel {{ color: {_TEXT}; background: transparent; }}
QLineEdit, QComboBox {{
    color: {_TEXT}; background: {_BG};
    border: 1px solid #0f4060; border-radius: 5px; padding: 4px 7px;
}}
QLineEdit:focus, QComboBox:focus {{ border: 2px solid {_PRI}; }}
QPushButton {{
    color: {_TEXT}; background: {_BG};
    border: 1px solid #0f4060; border-radius: 5px; padding: 5px 9px;
}}
QPushButton:hover, QPushButton:focus {{ border: 2px solid {_PRI}; }}
QPushButton:disabled {{ color: #3a6a7a; }}
QWidget#Detalhes {{ background: {_BG}; border: 1px solid #0f4060; border-radius: 8px; }}
"""

_COR_STATUS = {
    "pendente": "#ffcc00",
    "em_andamento": "#00d4ff",
    "bloqueado": "#ff3355",
    "concluido": "#00ff88",
}
_ROTULO_STATUS = {
    "pendente": "PENDENTE", "em_andamento": "EM ANDAMENTO",
    "bloqueado": "BLOQUEADO", "concluido": "CONCLUÍDO",
}


class CardItem(QGraphicsItem):
    """Card do mapa: título, resumo curto e badge de progresso para tarefas."""

    def __init__(self, dados: dict[str, Any]):
        super().__init__()
        self.dados = dict(dados)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self._pos_antes: QPointF | None = None

    def boundingRect(self) -> QRectF:
        return QRectF(0.0, 0.0, _CARD_W, _CARD_H)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        ret = self.boundingRect()
        selecionado = self.isSelected()
        tarefa = self.dados.get("tipo") == "tarefa"
        painter.setPen(QPen(QColor(_PRI if selecionado else "#1a5c7a"),
                            2.5 if selecionado else 1.4))
        painter.setBrush(QBrush(QColor("#082538")))
        painter.drawRoundedRect(ret, 10, 10)
        if selecionado:
            painter.setPen(QPen(QColor(_TEXT), 1.2, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(ret.adjusted(-5, -5, 5, 5), 13, 13)
        fonte = QFont("Segoe UI", 10)
        fonte.setBold(True)
        painter.setFont(fonte)
        painter.setPen(QColor(_TEXT))
        painter.drawText(
            QRectF(10, 8, _CARD_W - 20, 26),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            str(self.dados.get("titulo") or "Sem título")[:34])
        fonte.setBold(False)
        fonte.setPointSize(8)
        painter.setFont(fonte)
        painter.setPen(QColor(_MUTED))
        painter.drawText(
            QRectF(10, 34, _CARD_W - 20, 30),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            str(self.dados.get("resumo") or "")[:70])
        if tarefa:
            status = str(self.dados.get("status") or "pendente")
            painter.setPen(QPen(QColor(_COR_STATUS.get(status, _MUTED))))
            painter.drawText(
                QRectF(10, _CARD_H - 20, _CARD_W - 20, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                _ROTULO_STATUS.get(status, status.upper()))

    def itemChange(self, change, value):
        if (change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged
                and self.scene() is not None):
            atualizar = getattr(self.scene(), "atualizar_conexoes", None)
            if atualizar:
                atualizar(self.dados.get("id"))
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self._pos_antes = self.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        antes = self._pos_antes
        self._pos_antes = None
        cena = self.scene()
        if antes is None or cena is None or antes == self.pos():
            return
        pilha = getattr(cena, "pilha", None)
        if pilha is not None:
            pilha.push(MoverCardCommand(
                cena.editor, self.dados["id"],
                (antes.x(), antes.y()), (self.pos().x(), self.pos().y())))

    def atualizar_dados(self, dados: dict) -> None:
        self.dados = dict(dados)
        self.update()


class ConexaoItem(QGraphicsPathItem):
    """Curva entre dois cards, com rótulo opcional."""

    def __init__(self, dados: dict, cena: "CenaMapa"):
        super().__init__()
        self.dados = dict(dados)
        self._cena = cena
        self.setPen(QPen(QColor("#3d9ab5"), 1.8))
        self.setZValue(-1)
        self._rotulo = QGraphicsTextItem(self)
        self._rotulo.setDefaultTextColor(QColor(_MUTED))
        self._rotulo.setFont(QFont("Segoe UI", 8))
        self.atualizar()

    def atualizar(self) -> None:
        origem = self._cena.itens_cards.get(self.dados.get("origem"))
        destino = self._cena.itens_cards.get(self.dados.get("destino"))
        if origem is None or destino is None:
            return
        a = origem.pos() + QPointF(_CARD_W / 2, _CARD_H / 2)
        b = destino.pos() + QPointF(_CARD_W / 2, _CARD_H / 2)
        meio_x = (a.x() + b.x()) / 2
        curva = QPainterPath()
        curva.moveTo(a)
        curva.cubicTo(QPointF(meio_x, a.y()), QPointF(meio_x, b.y()), b)
        self.setPath(curva)
        self._rotulo.setPlainText(str(self.dados.get("rotulo") or ""))
        self._rotulo.setPos(QPointF(meio_x - 40, (a.y() + b.y()) / 2 - 10))

    def atualizar_dados(self, dados: dict) -> None:
        self.dados = dict(dados)
        self.atualizar()


class CenaMapa(QGraphicsScene):
    """Cena com os itens vivos; a fonte de verdade é `mapa_atual()`."""

    def __init__(self, editor=None):
        super().__init__()
        self.editor = editor
        self.pilha: QUndoStack | None = None
        self.itens_cards: dict[str, CardItem] = {}
        self.itens_conexoes: dict[str, ConexaoItem] = {}

    def montar(self, mapa: dict) -> None:
        self.itens_cards.clear()
        self.itens_conexoes.clear()
        self.clear()
        for dados in mapa.get("cards", []):
            item = CardItem(dados)
            item.setPos(float(dados.get("x") or 0.0), float(dados.get("y") or 0.0))
            self.addItem(item)
            self.itens_cards[dados["id"]] = item
        for dados in mapa.get("conexoes", []):
            item = ConexaoItem(dados, self)
            self.addItem(item)
            self.itens_conexoes[dados["id"]] = item

    def adicionar_card(self, dados: dict) -> CardItem:
        item = CardItem(dados)
        item.setPos(float(dados.get("x") or 0.0), float(dados.get("y") or 0.0))
        self.addItem(item)
        self.itens_cards[dados["id"]] = item
        return item

    def remover_card(self, card_id: str) -> dict | None:
        item = self.itens_cards.pop(card_id, None)
        if item is None:
            return None
        dados = copy.deepcopy(item.dados)
        self.removeItem(item)
        return dados

    def adicionar_conexao(self, dados: dict) -> ConexaoItem:
        item = ConexaoItem(dados, self)
        self.addItem(item)
        self.itens_conexoes[dados["id"]] = item
        return item

    def remover_conexao(self, lig_id: str) -> dict | None:
        item = self.itens_conexoes.pop(lig_id, None)
        if item is None:
            return None
        dados = copy.deepcopy(item.dados)
        self.removeItem(item)
        return dados

    def atualizar_conexoes(self, card_id: str | None) -> None:
        for lig in self.itens_conexoes.values():
            if card_id in (lig.dados.get("origem"), lig.dados.get("destino")):
                lig.atualizar()

    def mapa_atual(self) -> dict:
        cards = []
        for ident, item in self.itens_cards.items():
            dados = copy.deepcopy(item.dados)
            dados["id"] = ident
            dados["x"] = float(item.pos().x())
            dados["y"] = float(item.pos().y())
            cards.append(dados)
        conexoes = [copy.deepcopy(l.dados) for l in self.itens_conexoes.values()]
        return {"cards": cards, "conexoes": conexoes}


class MapaView(QGraphicsView):
    """Pan, zoom ancorado no ponteiro e enquadramento sem reconstruir a cena."""

    def __init__(self, cena: CenaMapa):
        super().__init__(cena)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event):
        fator = 1.18 if event.angleDelta().y() > 0 else 1 / 1.18
        atual = self.transform().m11()
        if 0.2 <= atual * fator <= 3.0:
            self.scale(fator, fator)

    def posicao_central(self) -> tuple[float, float, float]:
        centro = self.mapToScene(self.viewport().rect().center())
        return float(centro.x()), float(centro.y()), float(self.transform().m11())

    def aplicar_camera(self, cx: float, cy: float, zoom: float) -> None:
        self.resetTransform()
        self.scale(max(0.2, min(3.0, zoom or 1.0)), max(0.2, min(3.0, zoom or 1.0)))
        self.centerOn(QPointF(cx, cy))

    def enquadrar(self) -> None:
        ret = self.scene().itemsBoundingRect()
        if ret.isEmpty():
            ret = QRectF(-200, -120, 400, 240)
        ret.adjust(-60, -60, 60, 60)
        self.fitInView(ret, Qt.AspectRatioMode.KeepAspectRatio)


# ── comandos de desfazer/refazer ────────────────────────────────────────
class _Comando(QUndoCommand):
    def __init__(self, editor: "EditorMapa", texto: str):
        super().__init__(texto)
        self.editor = editor

    def _sincronizar(self) -> None:
        self.editor._apos_mudanca()


class CriarCardCommand(_Comando):
    def __init__(self, editor, dados):
        super().__init__(editor, "Criar card")
        self.dados = copy.deepcopy(dados)

    def redo(self):
        self.editor.cena.adicionar_card(self.dados)
        self._sincronizar()

    def undo(self):
        self.editor.cena.remover_card(self.dados["id"])
        self._sincronizar()


class EditarCardCommand(_Comando):
    def __init__(self, editor, card_id, antes, depois):
        super().__init__(editor, "Editar card")
        self.card_id = card_id
        self.antes = copy.deepcopy(antes)
        self.depois = copy.deepcopy(depois)

    def _aplicar(self, dados):
        item = self.editor.cena.itens_cards.get(self.card_id)
        if item is not None:
            item.atualizar_dados(dados)
            self.editor._selecionar_dados(item)
        self._sincronizar()

    def redo(self):
        self._aplicar(self.depois)

    def undo(self):
        self._aplicar(self.antes)


class MoverCardCommand(_Comando):
    def __init__(self, editor, card_id, antes, depois):
        super().__init__(editor, "Mover card")
        self.card_id = card_id
        self.antes = antes
        self.depois = depois

    def _aplicar(self, pos):
        item = self.editor.cena.itens_cards.get(self.card_id)
        if item is not None:
            item.setPos(QPointF(*pos))
        self._sincronizar()

    def redo(self):
        self._aplicar(self.depois)

    def undo(self):
        self._aplicar(self.antes)


class CriarConexaoCommand(_Comando):
    def __init__(self, editor, dados):
        super().__init__(editor, "Criar conexão")
        self.dados = copy.deepcopy(dados)

    def redo(self):
        self.editor.cena.adicionar_conexao(self.dados)
        self._sincronizar()

    def undo(self):
        self.editor.cena.remover_conexao(self.dados["id"])
        self._sincronizar()


class ExcluirConexaoCommand(_Comando):
    def __init__(self, editor, dados):
        super().__init__(editor, "Excluir conexão")
        self.dados = copy.deepcopy(dados)

    def redo(self):
        self.editor.cena.remover_conexao(self.dados["id"])
        self._sincronizar()

    def undo(self):
        self.editor.cena.adicionar_conexao(self.dados)
        self._sincronizar()


class ExcluirCardCommand(_Comando):
    """Card e conexões incidentes são uma única operação atômica."""

    def __init__(self, editor, card_id):
        super().__init__(editor, "Excluir card")
        self.card_id = card_id
        self._card: dict | None = None
        self._ligacoes: list[dict] = []

    def _capturar(self):
        if self._card is not None:
            return
        item = self.editor.cena.itens_cards.get(self.card_id)
        if item is None:
            return
        self._card = copy.deepcopy(item.dados)
        for lig in self.editor.cena.itens_conexoes.values():
            if self.card_id in (lig.dados.get("origem"), lig.dados.get("destino")):
                self._ligacoes.append(copy.deepcopy(lig.dados))

    def redo(self):
        self._capturar()
        for lig in self._ligacoes:
            self.editor.cena.remover_conexao(lig["id"])
        self.editor.cena.remover_card(self.card_id)
        self._sincronizar()
        self._lembretes(suspender=True)

    def undo(self):
        if self._card is not None:
            self.editor.cena.adicionar_card(self._card)
            for lig in self._ligacoes:
                self.editor.cena.adicionar_conexao(lig)
        self._sincronizar()
        self._lembretes(suspender=False)

    def _lembretes(self, suspender: bool) -> None:
        plano = getattr(self.editor, "_plano", None)
        if plano is None:
            return
        try:
            from core import lembretes as _lembretes  # noqa: PLC0415
            if suspender:
                _lembretes.suspender_por_card(plano.id, self.card_id)
            else:
                _lembretes.restaurar_por_card(plano.id, self.card_id)
        except Exception:
            pass


class EditorMapa(QWidget):
    """Editor do mapa: cena, painel de detalhes, undo e autosave."""

    estado_salvamento = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("EditorMapaRoot")
        self.setStyleSheet(_ESTILO)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._plano: Plano | None = None
        self._camera = {"cx": 0.0, "cy": 0.0, "zoom": 1.0}
        self.mudancas_pendentes = False
        self._selecionado: str | None = None
        self._selecionado_tipo: str = "card"
        self.pilha = QUndoStack(self)
        self.cena = CenaMapa(self)
        self.cena.pilha = self.pilha
        self._view = MapaView(self.cena)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.salvar)
        self._construir()
        self._conectar()

    # ── construção ──────────────────────────────────────────────────────
    def _construir(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        barra = QHBoxLayout()
        self.botoes = {}
        for nome, rotulo in (
            ("novo_card", "Novo card"),
            ("adicionar_conectado", "Card conectado"),
            ("conectar", "Conectar"),
            ("excluir", "Excluir"),
            ("desfazer", "Desfazer"),
            ("refazer", "Refazer"),
            ("enquadrar", "Enquadrar"),
            ("central", "Card central"),
            ("salvar", "Salvar"),
        ):
            botao = QPushButton(rotulo, self)
            botao.setObjectName(nome)
            self.botoes[nome] = botao
            barra.addWidget(botao)
        root.addLayout(barra)

        corpo = QSplitter(Qt.Orientation.Horizontal, self)
        corpo.addWidget(self._view)
        detalhes = QWidget(corpo)
        detalhes.setObjectName("Detalhes")
        dv = QVBoxLayout(detalhes)
        dv.setContentsMargins(10, 10, 10, 10)
        self.rotulo_detalhes = QLabel("Nenhum card selecionado", detalhes)
        dv.addWidget(self.rotulo_detalhes)
        campos = QFormLayout()
        self.campo_titulo = QLineEdit(detalhes)
        self.campo_titulo.setObjectName("mapa_titulo")
        self.campo_resumo = QLineEdit(detalhes)
        self.campo_resumo.setObjectName("mapa_resumo")
        self.campo_descricao = QLineEdit(detalhes)
        self.campo_descricao.setObjectName("mapa_descricao")
        self.combo_tipo = QComboBox(detalhes)
        self.combo_tipo.addItems(list(TIPOS_CARD))
        self.combo_status = QComboBox(detalhes)
        self.combo_status.addItems(list(STATUS_TAREFA))
        self.campo_rotulo = QLineEdit(detalhes)
        self.campo_rotulo.setPlaceholderText("Rótulo da conexão")
        campos.addRow("Título", self.campo_titulo)
        campos.addRow("Resumo", self.campo_resumo)
        campos.addRow("Descrição", self.campo_descricao)
        campos.addRow("Tipo", self.combo_tipo)
        campos.addRow("Progresso", self.combo_status)
        campos.addRow("Rótulo", self.campo_rotulo)
        dv.addLayout(campos)
        self.salvar_detalhes = QPushButton("Salvar detalhes", detalhes)
        self.salvar_detalhes.setObjectName("salvar_detalhes")
        dv.addWidget(self.salvar_detalhes)
        dv.addStretch(1)
        corpo.addWidget(detalhes)
        corpo.setStretchFactor(0, 4)
        corpo.setStretchFactor(1, 1)
        root.addWidget(corpo, 1)
        self.status = QLabel("Pronto.", self)
        self.status.setObjectName("status_mapa")
        root.addWidget(self.status)

    def _conectar(self) -> None:
        self.botoes["novo_card"].clicked.connect(self._novo_card)
        self.botoes["adicionar_conectado"].clicked.connect(self._adicionar_conectado)
        self.botoes["conectar"].clicked.connect(self._conectar_selecionados)
        self.botoes["excluir"].clicked.connect(self.excluir_selecionado)
        self.botoes["desfazer"].clicked.connect(self.desfazer)
        self.botoes["refazer"].clicked.connect(self.refazer)
        self.botoes["enquadrar"].clicked.connect(self.enquadrar)
        self.botoes["central"].clicked.connect(self.voltar_ao_central)
        self.botoes["salvar"].clicked.connect(self.salvar)
        self.salvar_detalhes.clicked.connect(self._salvar_detalhes)
        self.cena.selectionChanged.connect(self._on_selection)
        for seq, destino in (
            ("Delete", self.excluir_selecionado),
            ("Backspace", self.excluir_selecionado),
            ("Ctrl+Z", self.desfazer),
            ("Ctrl+Y", self.refazer),
            ("Ctrl+Shift+Z", self.refazer),
        ):
            atalho = QShortcut(QKeySequence(seq), self)
            atalho.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            atalho.activated.connect(destino)

    # ── API pública ─────────────────────────────────────────────────────
    def carregar(self, plano: Plano) -> None:
        self._timer.stop()
        self._plano = plano
        mapa, avisos = validar_mapa(plano.mapa)
        self.cena.montar(mapa)
        self.pilha.clear()
        camera = mapa.get("camera") or {}
        self._camera = {
            "cx": float(camera.get("cx") or 0.0),
            "cy": float(camera.get("cy") or 0.0),
            "zoom": float(camera.get("zoom") or 1.0),
        }
        self._view.aplicar_camera(
            self._camera["cx"], self._camera["cy"], self._camera["zoom"])
        self._selecionado = None
        self.mudancas_pendentes = False
        self.status.setText(
            f"{len(mapa['cards'])} card(s)."
            + (f" {len(avisos)} aviso(s)." if avisos else ""))

    def plano_atual(self) -> Plano:
        mapa = self.cena.mapa_atual()
        return BP.replace(self._plano, mapa={
            **mapa,
            "versao_mapa": 1,
            "inicializado": bool(self._plano.mapa.get("inicializado")),
            "raiz_id": str(self._plano.mapa.get("raiz_id") or ""),
            "camera": dict(self._camera),
        }, formato=FORMATO)

    @property
    def card_selecionado_id(self) -> str | None:
        return self._selecionado if self._selecionado_tipo == "card" else None

    def selecionar(self, card_id: str | None) -> None:
        self._selecionado = card_id
        self._selecionado_tipo = "card"
        for ident, item in self.cena.itens_cards.items():
            item.setSelected(ident == card_id)
        for item in self.cena.itens_conexoes.values():
            item.setSelected(False)
        self._selecionar_dados(self.cena.itens_cards.get(card_id) if card_id else None)

    def _selecionar_dados(self, item: CardItem | None) -> None:
        if item is None:
            return
        dados = item.dados
        self.campo_titulo.setText(str(dados.get("titulo") or ""))
        self.campo_resumo.setText(str(dados.get("resumo") or ""))
        self.campo_descricao.setText(str(dados.get("descricao") or ""))
        tipo = str(dados.get("tipo") or "ideia")
        self.combo_tipo.setCurrentText(tipo if tipo in TIPOS_CARD else "ideia")
        status = str(dados.get("status") or "")
        self.combo_status.setCurrentText(status if status in STATUS_TAREFA else "pendente")
        self.rotulo_detalhes.setText(f"Card: {dados.get('titulo') or 'sem título'}")

    def criar_card(self, titulo: str, resumo: str = "", descricao: str = "",
                   tipo: str = "ideia", status: str = "",
                   x: float = 0.0, y: float = 0.0,
                   modelo: str = "", estado: str = "",
                   valor=None, acumulado=None,
                   restrito: bool = False, financeiro: bool = False) -> str:
        ident = novo_id()
        if tipo not in TIPOS_CARD:
            tipo = "ideia"
        if tipo == "tarefa" and status not in STATUS_TAREFA:
            status = "pendente"
        self.pilha.push(CriarCardCommand(self, {
            "id": ident, "tipo": tipo, "titulo": titulo, "resumo": resumo,
            "descricao": descricao, "status": status,
            "x": float(x), "y": float(y),
            "modelo": str(modelo or ""), "estado": str(estado or ""),
            "valor": valor, "acumulado": acumulado,
            "restrito": bool(restrito), "financeiro": bool(financeiro),
        }))
        return ident

    def adicionar_conectado(self, origem_id: str, titulo: str = "Novo card") -> str:
        origem = self.cena.itens_cards.get(origem_id)
        if origem is None:
            raise BP.PlanoInvalido("card de origem inexistente")
        filhos = sum(1 for l in self.cena.itens_conexoes.values()
                     if l.dados.get("origem") == origem_id)
        ident = novo_id()
        x = float(origem.pos().x()) + 250.0
        y = float(origem.pos().y()) + 40.0 * (filhos + 1)
        self.pilha.beginMacro("Adicionar card conectado")
        self.pilha.push(CriarCardCommand(self, {
            "id": ident, "tipo": "ideia", "titulo": titulo, "resumo": "",
            "descricao": "", "status": "", "x": x, "y": y,
        }))
        self.conectar(origem_id, ident)
        self.pilha.endMacro()
        return ident

    def conectar(self, origem_id: str, destino_id: str, rotulo: str = "") -> str:
        if origem_id == destino_id:
            raise BP.PlanoInvalido("conexão de um card para ele mesmo")
        if origem_id not in self.cena.itens_cards or destino_id not in self.cena.itens_cards:
            raise BP.PlanoInvalido("card inexistente")
        if any(l.dados.get("origem") == origem_id and l.dados.get("destino") == destino_id
               for l in self.cena.itens_conexoes.values()):
            raise BP.PlanoInvalido("conexão já existe")
        ident = novo_id()
        self.pilha.push(CriarConexaoCommand(self, {
            "id": ident, "origem": origem_id, "destino": destino_id,
            "rotulo": rotulo,
        }))
        return ident

    def mover_card(self, card_id: str, x: float, y: float) -> None:
        item = self.cena.itens_cards.get(card_id)
        if item is None:
            return
        self.pilha.push(MoverCardCommand(
            self, card_id, (item.pos().x(), item.pos().y()), (float(x), float(y))))

    def editar_card(self, card_id: str, mudancas: dict) -> None:
        item = self.cena.itens_cards.get(card_id)
        if item is None:
            return
        antes = copy.deepcopy(item.dados)
        depois = copy.deepcopy(antes)
        permitidas = (
            "titulo", "resumo", "descricao", "tipo", "status", "modelo",
            "estado", "valor", "acumulado", "restrito", "financeiro",
        )
        depois.update({k: v for k, v in mudancas.items() if k in permitidas})
        if depois.get("tipo") == "tarefa" and depois.get("status") not in STATUS_TAREFA:
            depois["status"] = "pendente"
        if depois != antes:
            self.pilha.push(EditarCardCommand(self, card_id, antes, depois))

    def definir_progresso(self, card_id: str, status: str) -> None:
        if status not in STATUS_TAREFA:
            raise BP.PlanoInvalido("status desconhecido")
        self.editar_card(card_id, {"tipo": "tarefa", "status": status})

    def excluir_selecionado(self) -> None:
        if self._selecionado_tipo == "conexao" and self._selecionado:
            lig = self.cena.itens_conexoes.get(self._selecionado)
            if lig is not None:
                self.pilha.push(ExcluirConexaoCommand(self, copy.deepcopy(lig.dados)))
            return
        ident = self.card_selecionado_id
        if not ident or ident not in self.cena.itens_cards:
            return
        raiz = str((self._plano.mapa if self._plano else {}).get("raiz_id") or "")
        if ident == raiz:
            self.status.setText("O card central não pode ser excluído.")
            return
        self.pilha.push(ExcluirCardCommand(self, ident))
        self.selecionar(None)

    def desfazer(self) -> None:
        if self.pilha.canUndo():
            self.pilha.undo()

    def refazer(self) -> None:
        if self.pilha.canRedo():
            self.pilha.redo()

    def definir_camera(self, cx: float, cy: float, zoom: float) -> None:
        self._camera = {"cx": float(cx), "cy": float(cy), "zoom": float(zoom)}
        self._view.aplicar_camera(cx, cy, zoom)
        self._apos_mudanca()

    def enquadrar(self) -> None:
        self._view.enquadrar()
        cx, cy, zoom = self._view.posicao_central()
        self._camera = {"cx": cx, "cy": cy, "zoom": zoom}
        self._apos_mudanca()

    def voltar_ao_central(self) -> None:
        raiz = str((self._plano.mapa if self._plano else {}).get("raiz_id") or "")
        item = self.cena.itens_cards.get(raiz)
        if item is not None:
            self._view.centerOn(item)
            cx, cy, zoom = self._view.posicao_central()
            self._camera = {"cx": cx, "cy": cy, "zoom": zoom}
            self._apos_mudanca()

    def salvar(self) -> tuple[bool, str]:
        if self._plano is None:
            return False, "Nenhum plano carregado."
        self.status.setText("Salvando…")
        self.estado_salvamento.emit("Salvando…")
        try:
            atualizado = atualizar(
                self._plano.id,
                {"mapa": self.plano_atual().mapa, "formato": FORMATO},
                self._plano.revisao)
        except ConflitoDeRevisao:
            self.status.setText("Conflito de revisão.")
            self.estado_salvamento.emit("Conflito de revisão")
            return False, "Conflito de revisão"
        except (OSError, ValueError):
            self.status.setText("Falha ao salvar. Tente novamente.")
            self.estado_salvamento.emit("Falha ao salvar")
            return False, "Falha ao salvar"
        self._plano = atualizado
        self.mudancas_pendentes = False
        self.status.setText("Salvo.")
        self.estado_salvamento.emit("Salvo")
        return True, "Salvo"

    def fechar_com_seguranca(self) -> bool:
        if not self.mudancas_pendentes:
            return True
        return self.salvar()[0]

    # ── internos ────────────────────────────────────────────────────────
    def _apos_mudanca(self) -> None:
        self.mudancas_pendentes = True
        self._timer.start(600)

    def _on_selection(self) -> None:
        itens = [i for i in self.cena.selectedItems()
                 if isinstance(i, (CardItem, ConexaoItem))]
        if not itens:
            return
        item = itens[0]
        if isinstance(item, CardItem):
            self.selecionar(item.dados.get("id"))
        else:
            self._selecionado = item.dados.get("id")
            self._selecionado_tipo = "conexao"
            self.campo_rotulo.setText(str(item.dados.get("rotulo") or ""))
            self.rotulo_detalhes.setText("Conexão selecionada")

    def _novo_card(self) -> None:
        self.criar_card("Novo card")

    def _adicionar_conectado(self) -> None:
        if self.card_selecionado_id:
            self.adicionar_conectado(self.card_selecionado_id)

    def _conectar_selecionados(self) -> None:
        selecionados = [i.dados.get("id") for i in self.cena.selectedItems()
                        if isinstance(i, CardItem)]
        if len(selecionados) == 2:
            self.conectar(selecionados[0], selecionados[1])

    def _salvar_detalhes(self) -> None:
        ident = self.card_selecionado_id
        if ident:
            self.editar_card(ident, {
                "titulo": self.campo_titulo.text(),
                "resumo": self.campo_resumo.text(),
                "descricao": self.campo_descricao.text(),
                "tipo": self.combo_tipo.currentText(),
                "status": self.combo_status.currentText(),
            })
        elif self._selecionado_tipo == "conexao" and self._selecionado:
            lig = self.cena.itens_conexoes.get(self._selecionado)
            if lig is not None:
                dados = copy.deepcopy(lig.dados)
                self.cena.remover_conexao(self._selecionado)
                dados["rotulo"] = self.campo_rotulo.text()
                self.cena.adicionar_conexao(dados)
                self._apos_mudanca()
