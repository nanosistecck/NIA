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
    QPushButton, QSpinBox, QTextEdit, QTimeEdit, QVBoxLayout, QWidget,
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
QPushButton[selecionado="true"] {{ background:{COR_ATIVO}; color:{COR_FUNDO};
                                   font-weight:700; }}
QPushButton[comPromisso="true"] {{ border-color:{COR_MARCADO}; }}
QLineEdit, QComboBox, QSpinBox, QDateEdit, QTimeEdit {{ background:{COR_CAMPO};
    color:{COR_TEXTO}; border:1px solid {COR_BORDA}; border-radius:8px;
    padding:5px 8px; }}
QTextEdit {{ background:{COR_CAMPO}; color:{COR_TEXTO};
             border:1px solid {COR_BORDA}; border-radius:10px; padding:8px; }}
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
        self._construir()
        self.recarregar()

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
        self.btn_novo.clicked.connect(self._adicionar)
        self.btn_fechar = QPushButton("×")
        self.btn_fechar.setObjectName("agenda_fechar")
        self.btn_fechar.clicked.connect(self.close)
        cabecalho.addWidget(self.btn_anterior)
        cabecalho.addWidget(self.lbl_mes, 1)
        cabecalho.addWidget(self.btn_proximo)
        cabecalho.addWidget(self.btn_novo)
        cabecalho.addWidget(self.btn_fechar)
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
        for rotulo, campo in (("Título", self.campo_titulo), ("Data", self.campo_data),
                              ("Hora", self.campo_hora), ("Tipo", self.campo_tipo),
                              ("Preparo", self.campo_preparo)):
            caixa = QVBoxLayout()
            caixa.addWidget(QLabel(rotulo))
            caixa.addWidget(campo)
            formulario.addLayout(caixa)
        colunas.addLayout(formulario)

        self.txt_compromissos = QTextEdit()
        self.txt_compromissos.setObjectName("agenda_compromissos")
        self.txt_compromissos.setReadOnly(True)
        colunas.addWidget(QLabel("Compromissos do dia"))
        colunas.addWidget(self.txt_compromissos, 1)
        raiz.addWidget(painel, 1)

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
            f"{self.mes_atual.strftime('%B %Y')}".capitalize())
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
        linhas = []
        for item in sorted(itens, key=lambda i: str(i.get("inicio") or "")):
            try:
                inicio = datetime.fromisoformat(str(item["inicio"]))
            except (TypeError, ValueError):
                continue
            if inicio.date() != self.dia_selecionado:
                continue
            preparo = inicio - timedelta(minutes=int(item.get("preparo_minutos") or 0))
            linhas.append(
                f"{inicio:%H:%M}  {item['titulo']}  ·  preparar às {preparo:%H:%M}")
        self.txt_compromissos.setPlainText(
            "\n".join(linhas) if linhas else "Nenhum compromisso neste dia.")

    def _adicionar(self) -> None:
        titulo = self.campo_titulo.text().strip()
        if not titulo:
            self.txt_compromissos.setPlainText("Dê um título ao compromisso.")
            return
        momento = datetime.combine(
            self.campo_data.date().toPyDate(),
            self.campo_hora.time().toPyTime()).astimezone()
        AG.criar(titulo, momento.isoformat(), self.campo_tipo.currentText(),
                 self.campo_preparo.value())
        self.campo_titulo.clear()
        self.dia_selecionado = momento.date()
        self.mes_atual = self.dia_selecionado.replace(day=1)
        self._selecao_explicita = True
        self.recarregar()
        self.alterado.emit()

    def closeEvent(self, event) -> None:
        self.fechada.emit()
        super().closeEvent(event)
