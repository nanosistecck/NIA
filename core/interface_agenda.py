# -*- coding: utf-8 -*-
"""Janela de controle e acompanhamento da Agenda da NIA.

Grade mensal no estilo Google Calendar, com a identidade visual escura da NIA.
Toda regra de dados fica em `core.agenda`; aqui so apresentacao e acoes do dono.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from PyQt6.QtCore import QDate, QTime, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QDateEdit, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMessageBox, QPushButton, QSpinBox, QTextEdit, QTimeEdit,
    QVBoxLayout, QWidget,
)

from core import agenda as AG

COR_FUNDO = "#061524"
COR_PAINEL = "#0B2236"
COR_CAMPO = "#04121F"
COR_BORDA = "#1B4A66"
COR_ATIVO = "#00D4FF"
COR_TEXTO = "#E6F6FF"
COR_TEXTO2 = "#8FB5C9"
COR_MARCADO = "#2EE6A0"

_DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
_MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
             "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
_ESTILO = f"""
QWidget {{ background:{COR_FUNDO}; color:{COR_TEXTO};
          font-family:'Segoe UI',sans-serif; font-size:13px; }}
QFrame#painel {{ background:{COR_PAINEL}; border:1px solid {COR_BORDA};
                 border-radius:14px; }}
QLabel#titulo {{ font-size:20px; font-weight:600; }}
QPushButton {{ color:{COR_TEXTO}; background:{COR_CAMPO};
               border:1px solid {COR_BORDA}; border-radius:8px;
               padding:6px 12px; min-height:28px; }}
QPushButton:hover {{ border-color:{COR_ATIVO}; }}
QPushButton:focus {{ border:2px solid {COR_ATIVO}; outline:none; }}
QPushButton:disabled {{ color:#5b7286; border-color:#234054; }}
QPushButton[selecionado="true"] {{ background:{COR_ATIVO}; color:{COR_FUNDO};
                                   font-weight:700; }}
QPushButton[comPromisso="true"] {{ border-color:{COR_MARCADO}; }}
QLineEdit, QComboBox, QSpinBox, QDateEdit, QTimeEdit {{ background:{COR_CAMPO};
    color:{COR_TEXTO}; border:1px solid {COR_BORDA}; border-radius:8px;
    padding:5px 8px; }}
QTextEdit {{ background:{COR_CAMPO}; color:{COR_TEXTO};
             border:1px solid {COR_BORDA}; border-radius:10px; padding:8px; }}
QListWidget {{ background:{COR_CAMPO}; color:{COR_TEXTO};
               border:1px solid {COR_BORDA}; border-radius:10px; padding:4px; }}
QListWidget::item:selected {{ background:{COR_ATIVO}; color:{COR_FUNDO};
                              border-radius:6px; }}
"""


class AgendaWindow(QWidget):
    """Janela unica da Agenda; sinais avisam fechamento e mudancas."""

    fechada = pyqtSignal()
    alterado = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agenda — N.I.A")
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(1000, 700)
        self.setStyleSheet(_ESTILO)
        self.mes_atual = date.today().replace(day=1)
        self.dia_selecionado = date.today()
        self._selecao_explicita = False
        self._item_selecionado_id = None
        self._construir()
        self.recarregar()

    @property
    def item_selecionado_id(self):
        return self._item_selecionado_id

    def _construir(self) -> None:
        raiz = QVBoxLayout(self)
        cabecalho = QHBoxLayout()
        self.btn_anterior = QPushButton("‹")
        self.btn_anterior.setObjectName("agenda_anterior")
        self.btn_anterior.clicked.connect(lambda: self._ir_mes(-1))
        self.lbl_mes = QLabel("")
        self.lbl_mes.setObjectName("titulo")
        self.btn_proximo = QPushButton("›")
        self.btn_proximo.setObjectName("agenda_proximo")
        self.btn_proximo.clicked.connect(lambda: self._ir_mes(1))
        self.btn_novo = QPushButton("+ Compromisso")
        self.btn_novo.setObjectName("agenda_novo")
        self.btn_novo.clicked.connect(self._novo)
        self.btn_novo.hide()
        self.btn_salvar = QPushButton("+ Compromisso")
        self.btn_salvar.setObjectName("agenda_salvar")
        self.btn_salvar.clicked.connect(self._salvar_ou_novo)
        self.btn_cancelar = QPushButton("Cancelar edição")
        self.btn_cancelar.setObjectName("agenda_cancelar")
        self.btn_cancelar.clicked.connect(self._cancelar_edicao)
        self.btn_concluir = QPushButton("Concluir")
        self.btn_concluir.setObjectName("agenda_concluir")
        self.btn_concluir.clicked.connect(self._concluir)
        self.btn_reabrir = QPushButton("Reabrir")
        self.btn_reabrir.setObjectName("agenda_reabrir")
        self.btn_reabrir.clicked.connect(self._reabrir)
        self.btn_excluir = QPushButton("Excluir")
        self.btn_excluir.setObjectName("agenda_excluir")
        self.btn_excluir.clicked.connect(self._excluir)
        self.btn_fechar = QPushButton("×")
        self.btn_fechar.setObjectName("agenda_fechar")
        self.btn_fechar.clicked.connect(self.close)
        for botao in (self.btn_anterior, self.lbl_mes, self.btn_proximo,
                      self.btn_novo, self.btn_salvar, self.btn_cancelar,
                      self.btn_concluir, self.btn_reabrir, self.btn_excluir,
                      self.btn_fechar):
            cabecalho.addWidget(botao)
        raiz.addLayout(cabecalho)

        painel = QFrame()
        painel.setObjectName("painel")
        colunas = QVBoxLayout(painel)
        self.grade = QGridLayout()
        colunas.addLayout(self.grade)

        formulario = QHBoxLayout()
        self.campo_titulo = QLineEdit()
        self.campo_titulo.setPlaceholderText("Título do compromisso")
        self.campo_titulo.setObjectName("agenda_titulo")
        self.campo_data = QDateEdit()
        self.campo_data.setCalendarPopup(True)
        self.campo_data.setDisplayFormat("yyyy-MM-dd")
        self.campo_hora = QTimeEdit()
        self.campo_hora.setDisplayFormat("HH:mm")
        self.campo_tipo = QComboBox()
        self.campo_tipo.addItems(list(AG.TIPOS))
        self.campo_preparo = QSpinBox()
        self.campo_preparo.setRange(0, 480)
        self.campo_preparo.setSuffix(" min")
        self.campo_preparo.setValue(30)
        self.campo_notas = QTextEdit()
        self.campo_notas.setObjectName("agenda_notas")
        self.campo_notas.setFixedHeight(58)
        self.campo_notas.setPlaceholderText("Notas e preparo")
        self.campo_estado = QComboBox()
        self.campo_estado.setObjectName("agenda_estado")
        self.campo_estado.addItems(list(AG.ESTADOS))
        for rotulo, campo in (("Título", self.campo_titulo), ("Data", self.campo_data),
                              ("Hora", self.campo_hora), ("Tipo", self.campo_tipo),
                              ("Preparo", self.campo_preparo), ("Notas", self.campo_notas),
                              ("Estado", self.campo_estado)):
            caixa = QVBoxLayout()
            caixa.addWidget(QLabel(rotulo))
            caixa.addWidget(campo)
            formulario.addLayout(caixa)
        colunas.addLayout(formulario)

        self.lista = QListWidget()
        self.lista.setObjectName("agenda_lista")
        self.lista.itemClicked.connect(self._item_clicado)
        self.txt_compromissos = QTextEdit()
        self.txt_compromissos.setObjectName("agenda_compromissos")
        self.txt_compromissos.setReadOnly(True)
        self.txt_compromissos.setFixedHeight(64)
        colunas.addWidget(QLabel("Compromissos do dia"))
        colunas.addWidget(self.lista, 1)
        colunas.addWidget(self.txt_compromissos)
        raiz.addWidget(painel, 1)
        self._atualizar_botoes()

    def _atualizar_botoes(self) -> None:
        selecionado = self._item_selecionado_id is not None
        self.btn_salvar.setText(
            "Salvar alterações" if selecionado else "+ Compromisso")
        self.btn_cancelar.setVisible(selecionado)
        self.btn_concluir.setEnabled(selecionado)
        self.btn_reabrir.setEnabled(selecionado)
        self.btn_excluir.setEnabled(selecionado)

    def _ir_mes(self, delta: int) -> None:
        ano = self.mes_atual.year + (self.mes_atual.month - 1 + delta) // 12
        mes = (self.mes_atual.month - 1 + delta) % 12 + 1
        self.mes_atual = date(ano, mes, 1)
        self.recarregar()

    def _selecionar(self, dia: date) -> None:
        self.dia_selecionado = dia
        self._selecao_explicita = True
        self.recarregar()

    def recarregar(self) -> None:
        itens = AG.listar()
        dias_com_item = set()
        for item in itens:
            try:
                dias_com_item.add(datetime.fromisoformat(str(item["inicio"])).date())
            except (TypeError, ValueError):
                continue
        if not self._selecao_explicita:
            proximo = AG.proximo()
            if proximo is not None:
                try:
                    alvo = datetime.fromisoformat(str(proximo["inicio"])).date()
                    self.mes_atual = alvo.replace(day=1)
                    self.dia_selecionado = alvo
                except (TypeError, ValueError):
                    pass
        self.lbl_mes.setText(
            f"{_MESES_PT[self.mes_atual.month - 1]} {self.mes_atual.year}")
        while self.grade.count():
            item = self.grade.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for coluna, nome in enumerate(_DIAS):
            cabecalho = QLabel(nome)
            cabecalho.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grade.addWidget(cabecalho, 0, coluna)
        primeiro = self.mes_atual.weekday()
        quantos = (date(self.mes_atual.year + (self.mes_atual.month // 12),
                        self.mes_atual.month % 12 + 1, 1) - self.mes_atual).days
        for dia in range(1, quantos + 1):
            data = date(self.mes_atual.year, self.mes_atual.month, dia)
            botao = QPushButton(str(dia))
            botao.setObjectName(f"agenda_dia_{dia}")
            botao.setProperty("selecionado", data == self.dia_selecionado)
            botao.setProperty("comPromisso", data in dias_com_item)
            botao.clicked.connect(lambda _=False, d=data: self._selecionar(d))
            self.grade.addWidget(botao, 1 + (primeiro + dia - 1) // 7,
                                 (primeiro + dia - 1) % 7)
        self._mostrar_dia(itens)

    def _mostrar_dia(self, itens: list) -> None:
        do_dia = []
        for item in sorted(itens, key=lambda i: str(i.get("inicio") or "")):
            try:
                inicio = datetime.fromisoformat(str(item["inicio"]))
            except (TypeError, ValueError):
                continue
            if inicio.date() == self.dia_selecionado:
                do_dia.append((item, inicio))
        self.lista.clear()
        linhas = []
        for item, inicio in do_dia:
            preparo = inicio - timedelta(minutes=int(item.get("preparo_minutos") or 0))
            linha = (f"{inicio:%H:%M}  {item['titulo']}  ·  preparar às {preparo:%H:%M}"
                     f"  [{item.get('estado')}]")
            linhas.append(linha.replace(f"  [{item.get('estado')}]", ""))
            from PyQt6.QtWidgets import QListWidgetItem
            entrada = QListWidgetItem(linha)
            entrada.setData(Qt.ItemDataRole.UserRole, item.get("id"))
            self.lista.addItem(entrada)
        self.txt_compromissos.setPlainText(
            "\n".join(linhas) if linhas else "Nenhum compromisso neste dia.")
        if self._item_selecionado_id:
            for indice in range(self.lista.count()):
                if (self.lista.item(indice).data(Qt.ItemDataRole.UserRole)
                        == self._item_selecionado_id):
                    self.lista.setCurrentRow(indice)
                    break

    def _item_clicado(self, item) -> None:
        self.selecionar_item(item.data(Qt.ItemDataRole.UserRole))

    def selecionar_item(self, item_id: str | None) -> None:
        self._item_selecionado_id = item_id
        if item_id is None:
            self._limpar_formulario()
        else:
            item = next((i for i in AG.listar() if i.get("id") == item_id), None)
            if item is None:
                self._item_selecionado_id = None
                self._limpar_formulario()
            else:
                self._preencher_formulario(item)
        self._atualizar_botoes()

    def _preencher_formulario(self, item: dict) -> None:
        self.campo_titulo.setText(str(item.get("titulo") or ""))
        try:
            inicio = datetime.fromisoformat(str(item["inicio"]))
        except (TypeError, ValueError):
            inicio = datetime.now().astimezone()
        self.campo_data.setDate(QDate(inicio.year, inicio.month, inicio.day))
        self.campo_hora.setTime(QTime(inicio.hour, inicio.minute))
        tipo = str(item.get("tipo") or "outro")
        indice = self.campo_tipo.findText(tipo)
        self.campo_tipo.setCurrentIndex(max(0, indice))
        self.campo_preparo.setValue(int(item.get("preparo_minutos") or 0))
        self.campo_notas.setPlainText(str(item.get("notas") or ""))
        estado = str(item.get("estado") or "pendente")
        indice_estado = self.campo_estado.findText(estado)
        self.campo_estado.setCurrentIndex(max(0, indice_estado))
        self.dia_selecionado = inicio.date()
        self.mes_atual = inicio.date().replace(day=1)
        self._selecao_explicita = True

    def _limpar_formulario(self) -> None:
        self.campo_titulo.clear()
        self.campo_notas.clear()
        self.campo_data.setDate(QDate.currentDate())
        self.campo_hora.setTime(QTime(9, 0))
        self.campo_tipo.setCurrentIndex(0)
        self.campo_preparo.setValue(30)
        self.campo_estado.setCurrentIndex(0)

    def _momento_formulario(self) -> str:
        return datetime.combine(
            self.campo_data.date().toPyDate(),
            self.campo_hora.time().toPyTime()).astimezone().isoformat()

    def _salvar_ou_novo(self) -> None:
        if self._item_selecionado_id:
            self._salvar()
        else:
            self._novo()

    def _novo(self) -> None:
        titulo = self.campo_titulo.text().strip()
        if not titulo:
            self.txt_compromissos.setPlainText("Dê um título ao compromisso.")
            return
        try:
            AG.criar(titulo, self._momento_formulario(),
                     self.campo_tipo.currentText(),
                     self.campo_preparo.value(),
                     notas=self.campo_notas.toPlainText())
        except ValueError as exc:
            self.txt_compromissos.setPlainText(str(exc))
            return
        self._limpar_formulario()
        self.recarregar()
        self.alterado.emit()

    def _salvar(self) -> None:
        if not self._item_selecionado_id:
            return
        try:
            AG.editar(self._item_selecionado_id, {
                "titulo": self.campo_titulo.text().strip(),
                "inicio": self._momento_formulario(),
                "tipo": self.campo_tipo.currentText(),
                "preparo_minutos": self.campo_preparo.value(),
                "notas": self.campo_notas.toPlainText(),
                "estado": self.campo_estado.currentText(),
            })
        except ValueError as exc:
            self.txt_compromissos.setPlainText(str(exc))
            return
        self.recarregar()
        self.alterado.emit()

    def _cancelar_edicao(self) -> None:
        self.selecionar_item(None)

    def _mudar_estado(self, estado: str) -> None:
        if not self._item_selecionado_id:
            return
        try:
            AG.editar(self._item_selecionado_id, {"estado": estado})
        except ValueError as exc:
            self.txt_compromissos.setPlainText(str(exc))
            return
        self.recarregar()
        self.alterado.emit()

    def _concluir(self) -> None:
        self._mudar_estado("concluido")

    def _reabrir(self) -> None:
        self._mudar_estado("pendente")

    def _confirmar_exclusao(self) -> bool:
        resposta = QMessageBox.question(
            self, "Excluir compromisso", "Excluir este compromisso?",
            QMessageBox.StandardButton.No | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.No)
        return resposta == QMessageBox.StandardButton.Yes

    def _excluir(self) -> None:
        if not self._item_selecionado_id or not self._confirmar_exclusao():
            return
        AG.excluir(self._item_selecionado_id)
        self.selecionar_item(None)
        self.recarregar()
        self.alterado.emit()

    def closeEvent(self, event) -> None:
        self.fechada.emit()
        super().closeEvent(event)
