# -*- coding: utf-8 -*-
"""Gerenciador de Planos da NIA (Etapa 1 do Canvas Infinito).

Janela não modal que reutiliza a base local de ``core.planos``: catálogo com
busca tolerante a acento/caixa, filtros por tipo e status, formulário de
criação/visualização/edição e estados explícitos de lista vazia e falha.

Sem rede, sem modelos, sem dependências além de PyQt6 e do módulo de dados.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSplitter,
    QVBoxLayout, QWidget,
)

from core import planos as BP
from core.planos import (
    ConflitoDeRevisao, ErroPlano, PlanoInvalido, TIPOS,
    arquivar, atualizar, buscar, criar, listar, restaurar,
)

# Mesma família de cores do dock/canvas da NIA (core/ui.py, classe C).
_PRI = "#00d4ff"
_TEXT = "#8ffcff"
_MUTED = "#5ab8cc"
_BG = "#010d14"
_PANEL = "#011520"
_BORDER = "#0f4060"

_ESTILO = f"""
QWidget#PlanosRoot {{ background: {_BG}; }}
QLabel {{ color: {_TEXT}; background: transparent; }}
QLineEdit, QComboBox {{
    color: {_TEXT}; background: {_PANEL};
    border: 1px solid {_BORDER}; border-radius: 6px; padding: 5px 8px;
}}
QLineEdit:focus, QComboBox:focus {{ border: 2px solid {_PRI}; }}
QLineEdit:read-only {{ color: {_MUTED}; border-style: dashed; }}
QListWidget {{
    color: {_TEXT}; background: {_PANEL};
    border: 1px solid {_BORDER}; border-radius: 8px; padding: 4px;
}}
QListWidget::item {{ padding: 6px; border-radius: 4px; }}
QListWidget::item:selected {{ border: 2px solid {_PRI}; background: #003044; }}
QPushButton {{
    color: {_TEXT}; background: {_PANEL};
    border: 1px solid {_BORDER}; border-radius: 6px; padding: 6px 10px;
}}
QPushButton:hover, QPushButton:focus {{ border: 2px solid {_PRI}; }}
QPushButton:disabled {{ color: #3a6a7a; }}
QFrame#PlanosForm {{ background: {_PANEL}; border: 1px solid {_BORDER}; border-radius: 8px; }}
"""


class PlanosWindow(QWidget):
    """Catálogo e formulário de planos, reaproveitando `core.planos`."""

    fechada = pyqtSignal()
    abrir_canvas = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setObjectName("PlanosRoot")
        self.setWindowTitle("NIA · Planos")
        self.setMinimumSize(760, 480)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(_ESTILO)

        self._planos: list[BP.Plano] = []
        self.plano_selecionado_id: str | None = None
        self._modo: str | None = None

        self._construir()
        self._conectar()
        self.recarregar()

    # ── construção ──────────────────────────────────────────────────────
    def _construir(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        filtros = QHBoxLayout()
        self.campo_busca = QLineEdit(self)
        self.campo_busca.setObjectName("campo_busca")
        self.campo_busca.setPlaceholderText("Buscar por título ou objetivo")
        self.campo_busca.setClearButtonEnabled(True)
        filtros.addWidget(self.campo_busca, 2)

        self.filtro_tipo = QComboBox(self)
        self.filtro_tipo.setObjectName("filtro_tipo")
        self.filtro_tipo.addItems(["Todos", *TIPOS])
        filtros.addWidget(self.filtro_tipo, 1)

        self.filtro_status = QComboBox(self)
        self.filtro_status.setObjectName("filtro_status")
        self.filtro_status.addItems(["Ativos", "Arquivados", "Todos"])
        filtros.addWidget(self.filtro_status, 1)
        root.addLayout(filtros)

        corpo = QSplitter(Qt.Orientation.Horizontal, self)
        esquerda = QWidget(corpo)
        ev = QVBoxLayout(esquerda)
        ev.setContentsMargins(0, 0, 0, 0)
        self.lista = QListWidget(esquerda)
        self.lista.setObjectName("lista_planos")
        ev.addWidget(self.lista, 1)
        acoes = QHBoxLayout()
        self.botoes = {}
        for nome, rotulo in (
            ("novo_plano", "Novo plano"),
            ("visualizar", "Visualizar"),
            ("editar", "Editar"),
            ("abrir_canvas", "Editar no Canvas"),
            ("arquivar", "Arquivar"),
            ("restaurar", "Restaurar"),
        ):
            botao = QPushButton(rotulo, esquerda)
            botao.setObjectName(nome)
            self.botoes[nome] = botao
            acoes.addWidget(botao)
        ev.addLayout(acoes)
        corpo.addWidget(esquerda)

        formulario = QFrame(corpo)
        formulario.setObjectName("PlanosForm")
        fv = QVBoxLayout(formulario)
        fv.setContentsMargins(12, 12, 12, 12)
        self.titulo_form = QLabel("Dados do plano", formulario)
        self.titulo_form.setStyleSheet(f"color: {_PRI}; font-weight: 600;")
        fv.addWidget(self.titulo_form)
        campos = QFormLayout()
        self.campo_titulo = QLineEdit(formulario)
        self.campo_titulo.setObjectName("campo_titulo")
        self.campo_titulo.setPlaceholderText("Título do plano")
        self.campo_objetivo = QLineEdit(formulario)
        self.campo_objetivo.setObjectName("campo_objetivo")
        self.campo_objetivo.setPlaceholderText("Objetivo do plano")
        self.campo_tipo = QComboBox(formulario)
        self.campo_tipo.setObjectName("campo_tipo")
        self.campo_tipo.addItems(list(TIPOS))
        campos.addRow("Título", self.campo_titulo)
        campos.addRow("Objetivo", self.campo_objetivo)
        campos.addRow("Tipo", self.campo_tipo)
        fv.addLayout(campos)
        self.salvar = QPushButton("Salvar plano", formulario)
        self.salvar.setObjectName("salvar_plano")
        self.botao_cancelar = QPushButton("Cancelar", formulario)
        self.botao_cancelar.setObjectName("cancelar")
        fv.addWidget(self.salvar)
        fv.addWidget(self.botao_cancelar)
        fv.addStretch(1)
        corpo.addWidget(formulario)
        corpo.setStretchFactor(0, 3)
        corpo.setStretchFactor(1, 2)
        root.addWidget(corpo, 1)

        self.status = QLabel("", self)
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

    def _conectar(self) -> None:
        self.campo_busca.textChanged.connect(lambda *_: self.aplicar_filtros())
        self.filtro_tipo.currentTextChanged.connect(lambda *_: self.aplicar_filtros())
        self.filtro_status.currentTextChanged.connect(lambda *_: self.aplicar_filtros())
        self.lista.currentItemChanged.connect(
            lambda atual, _antigo: self._item_selecionado(atual))
        self.botoes["novo_plano"].clicked.connect(self.novo_plano)
        self.botoes["visualizar"].clicked.connect(self.visualizar)
        self.botoes["editar"].clicked.connect(self.editar)
        self.botoes["abrir_canvas"].clicked.connect(self._abrir_canvas)
        self.botoes["arquivar"].clicked.connect(self._arquivar)
        self.botoes["restaurar"].clicked.connect(self._restaurar)
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
            item = QListWidgetItem(
                f"{plano.titulo}  ·  {plano.tipo}  ·  {plano.status}  ·  "
                f"{str(plano.atualizado_em)[:16].replace('T', ' ')}")
            item.setData(Qt.ItemDataRole.UserRole, plano.id)
            self.lista.addItem(item)
        filtro_ativo = (bool(self.campo_busca.text())
                        or self.filtro_tipo.currentIndex() > 0
                        or self.filtro_status.currentIndex() > 0)
        if not resultados and (filtro_ativo or self._planos):
            self.status.setText("Nenhum resultado para os filtros atuais.")
        elif not self._planos:
            self.status.setText("Nenhum plano. Crie o primeiro.")
        else:
            self.status.setText(f"{len(resultados)} plano(s).")
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
            return
        self.campo_titulo.setText(plano.titulo)
        self.campo_objetivo.setText(plano.objetivo)
        self.campo_tipo.setCurrentText(plano.tipo)
        self.titulo_form.setText(
            f"{plano.titulo} · {plano.tipo} · rev {plano.revisao}")

    def _set_formulario(self, editable: bool) -> None:
        for campo in (self.campo_titulo, self.campo_objetivo, self.campo_tipo):
            campo.setReadOnly(not editable) if isinstance(campo, QLineEdit) \
                else campo.setEnabled(editable)
        self.salvar.setEnabled(editable)
        self.botao_cancelar.setEnabled(editable)

    def _atualizar_botoes(self) -> None:
        selecionado = self._por_id(self.plano_selecionado_id)
        self.botoes["visualizar"].setEnabled(selecionado is not None)
        self.botoes["editar"].setEnabled(selecionado is not None)
        self.botoes["abrir_canvas"].setEnabled(
            selecionado is not None and selecionado.status == "ativo")
        self.botoes["arquivar"].setEnabled(
            selecionado is not None and selecionado.status == "ativo")
        self.botoes["restaurar"].setEnabled(
            selecionado is not None and selecionado.status == "arquivado")

    # ── ações ───────────────────────────────────────────────────────────
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
        objetivo = self.campo_objetivo.text().strip()
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
        self._modo = None
        self.recarregar()
        self.selecionar(plano.id)
        self.status.setText("Salvo.")

    def cancelar(self) -> None:
        self._modo = None
        plano = self._por_id(self.plano_selecionado_id)
        self._preencher_formulario(plano)
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
            atualizar(plano.id, {"status": "ativo"}, plano.revisao)
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

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt)
        self.fechada.emit()
        super().closeEvent(event)
