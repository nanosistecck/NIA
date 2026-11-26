# -*- coding: utf-8 -*-
"""NIA UI Kit — componentes PyQt6 pequenos e reutilizáveis (Fase 17).

Usa exclusivamente os tokens semânticos de ``core.tema`` e a arquitetura Qt
já existente. Não importa ``main`` nem abre janelas por conta própria; o host
decide onde encaixar cada componente. A identidade visual da NIA (tema escuro
com ciano/laranja) prevalece sobre qualquer tema genérico.
"""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

from core import tema

ESPACO_XS = 4
ESPACO_SM = 8
ESPACO_MD = 12
RAIO = 8

COR_STATUS = {
    'normal': 'verde',
    'carregando': 'dourado',
    'erro': 'vermelho',
    'desativado': 'texto',
}


def _cor(familia: str) -> str:
    return tema.cor(tema.ORIGINAL[familia])


class IndicadorEstado(QLabel):
    """Etiqueta de estado com quatro variantes visuais e texto curto."""

    def __init__(self, texto: str = ''):
        super().__init__(texto or '—')
        # QLabel herda QFrame no PyQt6: sem objectName, um seletor QFrame
        # genérico do painel também desenharia borda nos rótulos.
        self.setObjectName('nia_ui_kit_indicador')
        self._estado = 'normal'
        self._texto = texto or '—'
        self.setWordWrap(True)
        self.definir_estado('normal')

    @property
    def estado(self) -> str:
        return self._estado

    def definir_estado(self, estado: str) -> None:
        if estado not in COR_STATUS:
            raise ValueError('Estado desconhecido: ' + str(estado))
        self._estado = estado
        cor = _cor(COR_STATUS[estado])
        self.setStyleSheet(
            f'QLabel#nia_ui_kit_indicador {{ color: {cor}; font-weight: 600; '
            f'padding: {ESPACO_XS}px; border: none; '
            f'border-radius: {ESPACO_XS}px; }}'
        )

    def definir_texto(self, texto: str) -> None:
        self._texto = str(texto or '—')
        self.setText(self._texto)


class BotaoAcao(QPushButton):
    """Botão com estados padrão/hover/foco/desativado e sinal próprio."""

    acionado = pyqtSignal()

    def __init__(self, texto: str):
        super().__init__(texto)
        self.setObjectName('nia_ui_kit_botao')
        self.clicked.connect(self._ao_clicar)
        seletor = 'QPushButton#nia_ui_kit_botao'
        self.setStyleSheet(
            f'{seletor} {{ background: {_cor("fundo")}; '
            f'color: {_cor("texto")}; border: 1px solid {_cor("principal")}; '
            f'border-radius: {RAIO}px; padding: {ESPACO_SM}px {ESPACO_MD}px; }}'
            f'{seletor}:hover {{ border-color: {_cor("destaque")}; }}'
            f'{seletor}:focus {{ outline: 1px solid {_cor("principal")}; }}'
            f'{seletor}:pressed {{ color: {_cor("fundo")}; '
            f'background: {_cor("principal")}; }}'
            f'{seletor}:disabled {{ color: {_cor("texto")}; '
            f'border-color: {_cor("texto")}; }}'
        )

    def _ao_clicar(self) -> None:
        if self.isEnabled():
            self.acionado.emit()


class PainelEstado(QFrame):
    """Cartão simples: título, descrição e indicador de estado."""

    def __init__(self, titulo: str, descricao: str = ''):
        super().__init__()
        self.setObjectName('nia_ui_kit_painel')
        self._indicador = IndicadorEstado(descricao or '—')
        rotulo = QLabel(str(titulo or ''))
        rotulo.setObjectName('nia_ui_kit_titulo')
        rotulo.setStyleSheet(
            f'QLabel#nia_ui_kit_titulo {{ color: {_cor("texto")}; font-weight: 600; }}')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ESPACO_MD, ESPACO_MD, ESPACO_MD, ESPACO_MD)
        layout.setSpacing(ESPACO_SM)
        layout.addWidget(rotulo)
        layout.addWidget(self._indicador)
        layout.addStretch(1)
        self.setStyleSheet(
            f'QFrame#nia_ui_kit_painel {{ background: {_cor("fundo")}; '
            f'border: 1px solid {_cor("principal")}; '
            f'border-radius: {RAIO}px; }}'
        )

    @property
    def estado(self) -> str:
        return self._indicador.estado

    def definir_estado(self, estado: str) -> None:
        self._indicador.definir_estado(estado)

    def definir_texto(self, texto: str) -> None:
        self._indicador.definir_texto(texto)
