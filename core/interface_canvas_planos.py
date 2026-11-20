# -*- coding: utf-8 -*-
"""Overlay do editor de mapa dentro da janela principal da NIA.

O overlay é filho do ``CanvasStage`` — e não do ``centralWidget`` — para que
``stage.hud_stack.raise_()`` mantenha o núcleo acima dele. Toda mudança de
layout (dock e núcleo) é de sessão: nada é gravado em preferências.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QRect, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.interface_mapa import EditorMapa

_PRI = "#00d4ff"
_TEXT = "#d8f8ff"

_ESTILO = f"""
QWidget#CanvasEditorOverlay {{ background: rgba(1,13,20,238); border-radius: 12px; }}
QLabel {{ color: {_TEXT}; background: transparent; }}
QPushButton {{
    color: {_TEXT}; background: #011520;
    border: 1px solid #0f4060; border-radius: 6px; padding: 6px 11px;
}}
QPushButton:hover, QPushButton:focus {{ border: 2px solid {_PRI}; }}
"""


class CanvasEditor(QWidget):
    """Editor do mapa mais toolbar de retorno, encaixado no Canvas."""

    voltar = pyqtSignal()

    def __init__(self, stage, parent=None):
        super().__init__(stage if parent is None else parent)
        self._stage = stage
        self.setObjectName("CanvasEditorOverlay")
        self.setStyleSheet(_ESTILO)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        topo = QHBoxLayout()
        botao = QPushButton("← Voltar aos planos", self)
        botao.setObjectName("voltar_planos")
        botao.clicked.connect(self.voltar.emit)
        topo.addWidget(botao)
        self.status = QLabel("", self)
        self.status.setObjectName("status_canvas_editor")
        topo.addWidget(self.status, 1)
        root.addLayout(topo)

        self.editor_internal = EditorMapa(self)
        self.editor_internal.estado_salvamento.connect(self.status.setText)
        root.addWidget(self.editor_internal, 1)
        self._reposicionar()

    @property
    def mudancas_pendentes(self) -> bool:
        return self.editor_internal.mudancas_pendentes

    def abrir(self, plano) -> None:
        self.editor_internal.carregar(plano)
        self.status.setText(f"{plano.titulo} · {plano.tipo}")

    def contexto(self) -> dict:
        plano = self.editor_internal.plano_atual()
        return {
            "plano_id": plano.id,
            "card_id": self.editor_internal.card_selecionado_id,
            "plano": plano,
        }

    def selecionar_card(self, card_id: str | None) -> None:
        self.editor_internal.selecionar(card_id)

    def fechar_com_seguranca(self) -> bool:
        return self.editor_internal.fechar_com_seguranca()

    def _reposicionar(self) -> None:
        pai = self.parentWidget()
        if pai is None:
            return
        w, h = pai.width(), pai.height()
        reserva = min(210, max(120, int(w * 0.18))) + 16
        self.setGeometry(QRect(0, 0, max(1, w - reserva), max(1, h)))

    def resizeEvent(self, event):  # noqa: N802 (Qt)
        super().resizeEvent(event)
        self._reposicionar()
