# -*- coding: utf-8 -*-
"""Overlay do editor de mapa dentro da janela principal da NIA.

O overlay é filho do ``CanvasStage`` — e não do ``centralWidget`` — para que
``stage.hud_stack.raise_()`` mantenha o núcleo acima dele. Toda mudança de
layout (dock e núcleo) é de sessão: nada é gravado em preferências.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QRect, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout, QInputDialog, QLabel, QMenu, QPushButton, QVBoxLayout, QWidget,
)

from core import assistencia_planos as AP
from core import lembretes as LEM
from core.comandos_lembretes import assunto_de
from core import modelos_planos as MP
from core.interface_mapa import EditorMapa

_PRI = "#00d4ff"
_TEXT = "#d8f8ff"

# Glass escuro estático: gradientes e bordas de 1 px sem blur em tempo real.
_ESTILO = f"""
QWidget#CanvasEditorOverlay {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 rgba(6,22,34,252), stop:0.5 rgba(3,15,26,250),
        stop:1 rgba(9,28,42,252));
    border: none; border-radius: 0px;
}}
QLabel {{ color: {_TEXT}; background: transparent; }}
QPushButton {{
    color: {_TEXT};
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(38,84,110,180), stop:1 rgba(12,40,58,190));
    border: 1px solid rgba(150,215,240,70); border-radius: 9px;
    padding: 7px 13px; min-height: 32px;
}}
QPushButton:hover {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(52,112,142,205), stop:1 rgba(18,54,76,210));
    border: 1px solid rgba(160,230,255,120);
}}
QPushButton:focus {{ border: 2px solid {_PRI}; outline: none; }}
QPushButton:checked {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(24,150,175,220), stop:1 rgba(8,70,92,225));
    border: 2px solid #80f6fc;
}}
"""


class CanvasEditor(QWidget):
    """Editor do mapa mais toolbar de retorno, encaixado no Canvas."""

    voltar = pyqtSignal()
    contexto_mudou = pyqtSignal(dict)
    modo_mudou = pyqtSignal(bool)

    def __init__(self, stage, parent=None):
        super().__init__(stage if parent is None else parent)
        self._stage = stage
        self.setObjectName("CanvasEditorOverlay")
        self.setStyleSheet(_ESTILO)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.modo_assistido = False
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        topo = QHBoxLayout()
        botao = QPushButton("← Voltar aos planos", self)
        botao.setObjectName("voltar_planos")
        botao.clicked.connect(self.voltar.emit)
        topo.addWidget(botao)
        self.botao_modo = QPushButton("Modo: Manual", self)
        self.botao_modo.setObjectName("alternar_modo")
        self.botao_modo.setCheckable(True)
        self.botao_modo.clicked.connect(self.definir_modo)
        topo.addWidget(self.botao_modo)
        self.botao_modelo = QPushButton("Adicionar modelo como ramo", self)
        self.botao_modelo.setObjectName("adicionar_modelo")
        self.botao_modelo.clicked.connect(self._mostrar_menu_modelos)
        topo.addWidget(self.botao_modelo)
        self.botao_lembrete = QPushButton("Definir lembrete", self)
        self.botao_lembrete.setObjectName("definir_lembrete")
        self.botao_lembrete.clicked.connect(self.definir_lembrete)
        topo.addWidget(self.botao_lembrete)
        self.botao_perguntar = QPushButton("Perguntar à NIA sobre este card", self)
        self.botao_perguntar.setObjectName("perguntar_nia_card")
        self.botao_perguntar.clicked.connect(self._perguntar_nia)
        topo.addWidget(self.botao_perguntar)
        self.botao_salvar = QPushButton("Salvar", self)
        self.botao_salvar.setObjectName("salvar_canvas")
        self.botao_salvar.setMinimumSize(76, 32)
        self.botao_salvar.clicked.connect(self._salvar)
        topo.addWidget(self.botao_salvar)
        self.status = QLabel("", self)
        self.status.setObjectName("status_canvas_editor")
        topo.addWidget(self.status, 1)
        root.addLayout(topo)

        self.editor_internal = EditorMapa(self)
        self.editor_internal.estado_salvamento.connect(self.status.setText)
        self.editor_internal.estado_editado.connect(
            lambda: self.contexto_mudou.emit(self.contexto()))
        root.addWidget(self.editor_internal, 1)
        self._reposicionar()
        # O núcleo muda de tamanho durante a animação de 220 ms da âncora;
        # acompanhar cada quadro evita que o mapa fique sob ele.
        animacao = getattr(stage, "motion", None)
        if animacao is not None:
            animacao.valueChanged.connect(lambda *_: self._reposicionar())

    def definir_modo(self, assistido: bool) -> None:
        """Alterna Manual/Com a NIA sem tocar no mapa, seleção ou câmera."""
        self.modo_assistido = bool(assistido)
        self.botao_modo.setChecked(self.modo_assistido)
        self.botao_modo.setText(
            "Modo: Com a NIA" if self.modo_assistido else "Modo: Manual")
        self.modo_mudou.emit(self.modo_assistido)

    @property
    def card_selecionado_id(self) -> str | None:
        return self.editor_internal.card_selecionado_id

    @property
    def mudancas_pendentes(self) -> bool:
        return self.editor_internal.mudancas_pendentes

    def abrir(self, plano) -> None:
        self.editor_internal.carregar(plano)
        self.status.setText(f"{plano.titulo} · {plano.tipo}")
        self.contexto_mudou.emit(self.contexto())

    def contexto(self) -> dict:
        plano = self.editor_internal.plano_atual()
        return {
            "plano_id": plano.id,
            "card_id": self.editor_internal.card_selecionado_id,
            "plano": plano,
        }

    def selecionar_card(self, card_id: str | None) -> None:
        self.editor_internal.selecionar(card_id)
        self.contexto_mudou.emit(self.contexto())

    def adicionar_modelo(self, tipo: str) -> bool:
        """Adiciona um modelo como ramo do card selecionado, em um só undo."""
        if tipo not in MP.TIPOS_MODELO:
            return False
        card_id = self.card_selecionado_id
        if not card_id:
            self.status.setText("Selecione um card para receber o ramo.")
            return False
        plano = self.editor_internal.plano_atual()
        origem = next((c for c in plano.mapa.get("cards", [])
                       if c.get("id") == card_id), None)
        if origem is None:
            self.status.setText("O card de origem não existe mais.")
            return False
        ops = MP.ramo_modelo(tipo, card_id, origem)
        contexto = AP.montar_contexto(plano, card_id)
        validas, erros = AP.validar_lote(ops, plano, contexto)
        if erros or not validas:
            self.status.setText(erros[0] if erros else "Ramo inválido.")
            return False
        AP.aplicar_lote(self.editor_internal, validas, f"Modelo {tipo}")
        self.status.setText(f"Modelo {tipo} adicionado como ramo.")
        self.contexto_mudou.emit(self.contexto())
        return True

    def definir_lembrete(self, card_id: str | None = None) -> bool:
        """Cria lembrete local para o card selecionado (ou para o plano)."""
        texto, ok = QInputDialog.getText(
            self, "Definir lembrete", "Quando? Ex.: amanhã às 19h revisar exercício")
        if not ok or not str(texto or "").strip():
            return False
        horario, mensagem = LEM.interpretar(texto)
        if not horario:
            self.status.setText(mensagem)
            return False
        plano = self.editor_internal.plano_atual()
        alvo = card_id if card_id is not None else self.card_selecionado_id
        LEM.criar(plano.id, assunto_de(texto), horario,
                  "America/Sao_Paulo", alvo)
        self.status.setText(mensagem)
        return True

    def _salvar(self) -> None:
        """Salva pelo mesmo fluxo do editor, com retorno visível no Canvas."""
        ok, mensagem = self.editor_internal.salvar()
        self.status.setText(mensagem)
        if not ok:
            self.status.setText(f"{mensagem}. Tente novamente.")

    def _perguntar_nia(self) -> None:
        janela = self.window()
        casca = getattr(janela, "_ui", None)
        if casca is not None:
            casca.perguntar_sobre_card(self.card_selecionado_id)
        else:
            self.status.setText("Abra a conversa para perguntar sobre o card.")

    def fechar_com_seguranca(self) -> bool:
        return self.editor_internal.fechar_com_seguranca()

    def _mostrar_menu_modelos(self) -> None:
        menu = QMenu(self)
        for tipo in MP.TIPOS_MODELO:
            menu.addAction(tipo, lambda checked=False, t=tipo: self.adicionar_modelo(t))
        menu.addSeparator()
        menu.addAction("Complementar ramo selecionado",
                       self._complementar_ramo)
        menu.exec(self.botao_modelo.mapToGlobal(
            self.botao_modelo.rect().bottomLeft()))

    def _complementar_ramo(self) -> None:
        """Adiciona cards ao ramo já existente sem duplicar sua raiz."""
        card_id = self.card_selecionado_id
        if not card_id:
            self.status.setText("Selecione um card para complementar.")
            return
        plano = self.editor_internal.plano_atual()
        existentes = {c.get("modelo") for c in plano.mapa.get("cards", [])
                      if c.get("modelo")}
        if not existentes:
            self.status.setText("Ainda não há ramo para complementar.")
            return
        self.adicionar_modelo(next(iter(existentes)))

    def _reposicionar(self) -> None:
        pai = self.parentWidget()
        if pai is None:
            return
        w, h = pai.width(), pai.height()
        # O canvas cobre a JANELA INTEIRA — sem borda interna, sem moldura.
        # A reserva para o núcleo vai para as margens do conteúdo, não para
        # o tamanho do overlay: assim o fundo do mapa continua até as bordas
        # e o núcleo flutua no canto inferior direito sobre o glass.
        self.setGeometry(QRect(0, 0, max(1, w), max(1, h)))
        nucleo = getattr(pai, "hud_stack", None)
        reserva = max(150, nucleo.width() + 18) if nucleo is not None else 150
        self.layout().setContentsMargins(14, 14, reserva, 14)
        self.updateGeometry()

    def resizeEvent(self, event):  # noqa: N802 (Qt)
        super().resizeEvent(event)
        self._reposicionar()
