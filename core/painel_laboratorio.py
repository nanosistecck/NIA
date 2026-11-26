# -*- coding: utf-8 -*-
"""Painel de diagnóstico do laboratório de inteligência (carregamento sob demanda).

Não importa testes, não roda nada até o usuário pedir e nunca bloqueia a
thread da interface: a execução vai para uma QThread e os resultados voltam
por sinal.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core import nia_ui_kit as UK
from core import tema


class _TrabalhadorLaboratorio(QObject):
    concluido = pyqtSignal(dict)
    falhou = pyqtSignal(str)

    def __init__(self, modo: str):
        super().__init__()
        self.modo = modo

    def executar(self) -> None:
        try:
            from tests.intelligence.runners.cli import _gravar, _metricas, executar, selecionar
            cenarios = selecionar(self.modo)
            avaliacoes = [executar(c) for c in cenarios]
            metricas = _metricas(avaliacoes)
            _gravar(self.modo, cenarios, avaliacoes)
            self.concluido.emit(metricas)
        except Exception as exc:
            self.falhou.emit(type(exc).__name__ + ': ' + str(exc)[:160])


class PainelLaboratorio(QWidget):
    """Cartão com última execução, métricas e botões de teste."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('PainelLaboratorio')
        self._thread = None
        self._trabalhador = None
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(12, 12, 12, 12)
        raiz.setSpacing(8)

        self.titulo = QLabel('Laboratório de Inteligência')
        self.titulo.setObjectName('nia_ui_kit_titulo')
        self.ultima = UK.IndicadorEstado('Nenhuma execução nesta sessão')
        self.metricas = QLabel('Aprovados: —/— · Bloqueados: —')
        self.status = UK.IndicadorEstado('Pronto')

        botoes = QHBoxLayout()
        self.btn_quick = QPushButton('Teste rápido')
        self.btn_full = QPushButton('Teste completo')
        for botao in (self.btn_quick, self.btn_full):
            botao.setMinimumHeight(34)
            botoes.addWidget(botao)
        self.btn_cancelar = QPushButton('Cancelar')
        self.btn_cancelar.setEnabled(False)
        botoes.addWidget(self.btn_cancelar)

        raiz.addWidget(self.titulo)
        raiz.addWidget(self.ultima)
        raiz.addWidget(self.metricas)
        raiz.addLayout(botoes)
        raiz.addWidget(self.status)
        fundo = tema.cor(tema.ORIGINAL['fundo'])
        texto = tema.cor(tema.ORIGINAL['texto'])
        principal = tema.cor(tema.ORIGINAL['principal'])
        self.setStyleSheet(
            f'QWidget#PainelLaboratorio {{ background: {fundo}; '
            f'border: 1px solid {principal}; border-radius: 8px; }}'
            f'QLabel {{ color: {texto}; }}'
            f'QPushButton {{ background: {fundo}; color: {texto}; '
            f'border: 1px solid {principal}; border-radius: 8px; padding: 6px; }}'
            f'QPushButton:disabled {{ color: {texto}; }}')

        self.btn_quick.clicked.connect(lambda: self.executar('quick'))
        self.btn_full.clicked.connect(lambda: self.executar('full'))
        self.btn_cancelar.clicked.connect(self.cancelar)

    def executar(self, modo: str) -> None:
        if self._thread is not None and self._thread.isRunning():
            return
        self.status.definir_estado('carregando')
        self.status.definir_texto(f'Executando {modo}…')
        self.btn_cancelar.setEnabled(True)
        self._thread = QThread(self)
        self._trabalhador = _TrabalhadorLaboratorio(modo)
        self._trabalhador.moveToThread(self._thread)
        self._thread.started.connect(self._trabalhador.executar)
        self._trabalhador.concluido.connect(self._concluido)
        self._trabalhador.falhou.connect(self._falhou)
        self._thread.start()

    def cancelar(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            self._thread.requestInterruption()
            self._thread.quit()
            self.status.definir_estado('desativado')
            self.status.definir_texto('Execução cancelada')
            self.btn_cancelar.setEnabled(False)

    def _concluido(self, metricas: dict) -> None:
        self.ultima.definir_texto('Última execução concluída')
        self.metricas.setText(
            f'Aprovados: {metricas["aprovados"]}/{metricas["avaliaveis"]} · '
            f'Bloqueados: {metricas["bloqueados"]}/{metricas["total"]}')
        self.status.definir_estado('normal' if not metricas['reprovados'] else 'erro')
        self.status.definir_texto('Concluído' if not metricas['reprovados'] else 'Falhas encontradas')
        self.btn_cancelar.setEnabled(False)
        if self._thread:
            self._thread.quit()

    def _falhou(self, motivo: str) -> None:
        self.status.definir_estado('erro')
        self.status.definir_texto(motivo[:60])
        self.btn_cancelar.setEnabled(False)
        if self._thread:
            self._thread.quit()
