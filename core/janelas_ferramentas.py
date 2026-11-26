# -*- coding: utf-8 -*-
"""Janelas de ferramentas sob demanda, com instância única e foco.

Reutiliza PyQt6, ``core.tema`` e ``ConfigService``. Nenhuma janela é criada no
__init__: cada ferramenta registra uma fábrica preguiçosa e só é construída
quando o usuário abre. Não importa WebEngine — janelas que realmente precisam
dele (Globo, Secretaria) mantêm fábrica própria e processo separado.

O gerenciador não substitui as janelas existentes do dock: ele é o ponto de
reuso para as novas ferramentas das etapas 07–16 e expõe ``abrir(chave)`` com
foco, tema claro/escuro, estados de carregamento/erro e fechamento por teclado.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
import math
from typing import Callable

from PyQt6.QtCore import (QEvent, QObject, QRect, QSize, Qt, pyqtSignal)
from PyQt6.QtGui import QColor, QKeySequence, QPalette, QShortcut
from PyQt6.QtWidgets import QApplication, QWidget

_LOG = logging.getLogger(__name__)

TEMAS = ("claro", "escuro")


@dataclass(frozen=True)
class EstadoFerramenta:
    """Estado publicado para a casca (log/card), sem tocar na janela."""
    chave: str
    titulo: str = ""
    carregando: bool = False
    erro: str = ""


def geometry_ferramenta(viewport: QRect, tamanho: QSize, *,
                        fracao: float = 0.82, dpr: float = 1.0) -> QRect:
    """Geometria centralizada e contida no viewport, em coordenadas lógicas.

    ``dpr`` é o devicePixelRatio: em DPI 150% a mesma largura física exige
    menos pixels lógicos, então o mínimo lógico encolhe (480 px físicos).
    Nunca devolve retângulo maior que o viewport ou com origem negativa.
    """
    f = max(0.3, min(1.0, float(fracao)))
    escala = max(0.5, float(dpr or 1.0))
    min_w = max(240, math.ceil(480 / escala))
    min_h = max(180, math.ceil(360 / escala))
    vw, vh = max(1, viewport.width()), max(1, viewport.height())
    largura = max(min(min_w, vw), min(int(tamanho.width() or min_w), int(vw * f)))
    altura = max(min(min_h, vh), min(int(tamanho.height() or min_h), int(vh * f)))
    return QRect(viewport.x() + (vw - largura) // 2,
                 viewport.y() + (vh - altura) // 2,
                 largura, altura)


class GerenciadorJanelas(QObject):
    """Abre, foca e fecha janelas de ferramentas sem duplicar instâncias."""

    estado = pyqtSignal(object)  # EstadoFerramenta

    def __init__(self, parent: QWidget | None = None, *, tema=None, log=None,
                 fracao: float = 0.82):
        super().__init__(parent)
        self._janelas: dict[str, QWidget] = {}
        self._registros: dict[str, dict] = {}
        self._tema = tema if callable(tema) else None
        self._log = log if callable(log) else None
        self._fracao = max(0.3, min(1.0, float(fracao)))

    # ── cadastro ────────────────────────────────────────────────────────────
    def registrar(self, chave: str, fabrica: Callable[[], QWidget], *,
                  titulo: str = "", atalho: str | None = None,
                  ao_abrir: Callable[[QWidget], None] | None = None) -> None:
        if not isinstance(chave, str) or not chave.strip() or not callable(fabrica):
            raise ValueError('Chave e fábrica são obrigatórias.')
        registro = {"titulo": str(titulo or chave), "fabrica": fabrica,
                    "ao_abrir": ao_abrir if callable(ao_abrir) else None,
                    "atalho_obj": None}
        if atalho and isinstance(self.parent(), QWidget):
            atalho_obj = QShortcut(QKeySequence(str(atalho)), self.parent())
            atalho_obj.activated.connect(lambda: self.abrir(chave))
            registro["atalho_obj"] = atalho_obj
        self._registros[chave] = registro

    def registradas(self) -> tuple[str, ...]:
        return tuple(self._registros)

    # ── ciclo de vida ───────────────────────────────────────────────────────
    def abrir(self, chave: str) -> QWidget | None:
        registro = self._registros.get(chave)
        if registro is None:
            self._erro(chave, 'Ferramenta não registrada.')
            return None
        atual = self._janelas.get(chave)
        if self._valido(atual):
            self._foco(atual)
            self._posicionar(atual)
            self._avisar(f"{registro['titulo']} em foco.")
            self._reabrir(registro, atual)
            return atual
        self._janelas.pop(chave, None)
        self.estado.emit(EstadoFerramenta(chave, registro['titulo'], carregando=True))
        self._avisar(f"Abrindo {registro['titulo']}...")
        try:
            janela = registro['fabrica']()
        except Exception as exc:  # fábrica de terceiros nunca derruba a casca
            self._erro(chave, f'{type(exc).__name__}: {str(exc)[:120]}')
            return None
        if not isinstance(janela, QWidget):
            self._erro(chave, 'A fábrica não devolveu uma janela Qt.')
            return None
        self._posicionar(janela)
        self._aplicar_tema(janela)
        janela.installEventFilter(self)
        identificador = id(janela)
        registro_vivo = self._janelas  # dict Python: sobrevive ao wrapper Qt
        def limpar():
            try:
                if id(registro_vivo.get(chave)) == identificador:
                    registro_vivo.pop(chave, None)
            except Exception:
                pass
        janela.destroyed.connect(limpar)
        self._janelas[chave] = janela
        self._foco(janela)
        self._reabrir(registro, janela)
        self.estado.emit(EstadoFerramenta(chave, registro['titulo']))
        return janela

    def fechar(self, chave: str) -> bool:
        janela = self._janelas.get(chave)
        if not self._valido(janela):
            self._janelas.pop(chave, None)
            return False
        janela.close()
        return True

    def fechar_todas(self) -> int:
        return sum(1 for chave in tuple(self._janelas) if self.fechar(chave))

    def abertas(self) -> dict[str, QWidget]:
        return {chave: janela for chave, janela in self._janelas.items()
                if self._valido(janela)}

    def atualizar_tema(self) -> None:
        for janela in self.abertas().values():
            self._aplicar_tema(janela)

    # ── Qt ──────────────────────────────────────────────────────────────────
    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (API Qt)
        if (event.type() == QEvent.Type.KeyPress
                and event.key() == Qt.Key.Key_Escape
                and isinstance(obj, QWidget)):
            for chave, janela in tuple(self.abertas().items()):
                if janela is obj or janela is obj.window():
                    self.fechar(chave)
                    self._avisar(f'{chave} fechada por Escape.')
                    return True
        return super().eventFilter(obj, event)

    # ── internos ────────────────────────────────────────────────────────────
    @staticmethod
    def _valido(janela) -> bool:
        if not isinstance(janela, QWidget):
            return False
        try:
            return bool(janela.isVisible())
        except RuntimeError:  # C++ deletado
            return False

    def _foco(self, janela: QWidget) -> None:
        try:
            if janela.isMinimized():
                janela.showNormal()
            else:
                janela.show()
            janela.raise_()
            janela.activateWindow()
        except RuntimeError:
            pass

    def _posicionar(self, janela: QWidget) -> None:
        try:
            dpr = janela.devicePixelRatioF() or 1.0
        except RuntimeError:
            dpr = 1.0
        parent = self.parent() if isinstance(self.parent(), QWidget) else None
        viewport = None
        if parent is not None:
            try:
                if parent.isVisible():
                    viewport = parent.rect()
            except RuntimeError:
                parent = None
        if viewport is None:
            tela = janela.screen() or QApplication.primaryScreen()
            viewport = (tela.availableGeometry() if tela is not None
                        else QRect(0, 0, 1024, 768))
        tamanho = janela.sizeHint()
        if not tamanho.isValid() or tamanho.isEmpty():
            tamanho = QSize(960, 640)
        janela.setGeometry(geometry_ferramenta(viewport, tamanho,
                                               fracao=self._fracao, dpr=dpr))

    def _aplicar_tema(self, janela: QWidget) -> None:
        # Paleta em vez de folha de estilo: janelas existentes (dashboard,
        # agenda, planos) mantêm o CSS próprio; o tema só altera a base.
        from core import tema  # importação preguiçosa, stdlib
        tema_nome = str(self._tema()).strip().lower() if self._tema else 'escuro'
        if tema_nome not in TEMAS:
            tema_nome = 'escuro'
        fundo = '#eef4f8' if tema_nome == 'claro' else '#00060a'
        texto = '#10232b' if tema_nome == 'claro' else '#8ffcff'
        paleta = QPalette(janela.palette())
        paleta.setColor(QPalette.ColorRole.Window, QColor(tema.cor(fundo)))
        paleta.setColor(QPalette.ColorRole.WindowText, QColor(tema.cor(texto)))
        paleta.setColor(QPalette.ColorRole.Base, QColor(tema.cor(fundo)))
        paleta.setColor(QPalette.ColorRole.Text, QColor(tema.cor(texto)))
        janela.setPalette(paleta)
        janela.setProperty('ferramenta_tema', tema_nome)

    def _reabrir(self, registro: dict, janela: QWidget) -> None:
        callback = registro.get('ao_abrir')
        if callback is not None:
            try:
                callback(janela)
            except Exception as exc:
                _LOG.warning('ao_abrir falhou: %s', exc)

    def _avisar(self, texto: str) -> None:
        if self._log is not None:
            try:
                self._log('SIS: ' + texto)
            except Exception:
                pass

    def _erro(self, chave: str, motivo: str) -> None:
        self.estado.emit(EstadoFerramenta(chave, '', erro=motivo))
        self._avisar(f'Falha ao abrir {chave}: {motivo}')
