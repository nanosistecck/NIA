# -*- coding: utf-8 -*-
"""Tokens visuais do NIA Control Overlay (Fase 03).

As cores são fixas de propósito: o manual de voo manda reproduzir a referência
aprovada, não a paleta personalizável do restante da interface.
"""
from __future__ import annotations

from dataclasses import dataclass

AZUL = '#008CFF'
CIANO = '#00D9FF'
CRISTAL = '#B4F1FF'
TEXTO = '#F0F7FF'
TEXTO_SUAVE = '#BFD9F2'
VERDE = '#00E676'
AMBAR = '#FFB547'
VERMELHO = '#FF4757'

BANNER_INICIO = '#123B70'
BANNER_FIM = '#06152F'
VIDRO_INICIO = '#0B2748'
VIDRO_FIM = '#04101F'

MARGEM = 8
RAIO_BORDA = 32


def rgba(hexa: str, alpha: float) -> str:
    """'#RRGGBB' + 0..1 → 'rgba(r, g, b, a)'."""
    valor = hexa.lstrip('#')
    r, g, b = int(valor[0:2], 16), int(valor[2:4], 16), int(valor[4:6], 16)
    return f'rgba({r}, {g}, {b}, {max(0.0, min(1.0, float(alpha))):.3f})'


@dataclass(frozen=True)
class Metricas:
    largura: int
    altura: int
    banner_largura: int
    banner_altura: int
    borda: int
    atividades_largura: int
    atividades_altura: int
    escala: float
    compacto: bool

    @property
    def banner_x(self) -> int:
        return (self.largura - self.banner_largura) // 2

    @property
    def banner_y(self) -> int:
        return 8

    @property
    def status_largura(self) -> int:
        return max(186, min(232, int(232 * self.escala)))

    @property
    def status_altura(self) -> int:
        return max(36, round(46 * self.escala))

    @property
    def status_x(self) -> int:
        return self.largura - 32 - self.status_largura

    @property
    def status_y(self) -> int:
        return 40

    @property
    def atividades_x(self) -> int:
        return 32

    @property
    def atividades_y(self) -> int:
        # 54 px de folga inferior para não encostar na barra de tarefas.
        return self.altura - 54 - self.atividades_altura


def metricas(largura: int, altura: int) -> Metricas:
    """Medidas responsivas em pixels lógicos (Qt já aplica o DPI)."""
    largura = max(640, int(largura))
    altura = max(480, int(altura))
    compacto = largura < altura
    if compacto:
        banner = max(360, int(largura * 0.82))
        borda = 2
        ativ = max(240, min(320, int(largura * 0.7)))
        escala = 0.72
    elif largura <= 1280:
        banner, borda, ativ, escala = 600, 2, 260, 0.78
    elif largura <= 1400:
        banner, borda, ativ, escala = 650, 2, 280, 0.82
    elif largura <= 2000:
        banner, borda, ativ, escala = 940, 3, 370, 1.0
    elif largura <= 2800:
        banner, borda, ativ, escala = 1040, 3, 400, 1.08
    else:
        banner, borda, ativ, escala = 1040, 4, 440, 1.12

    banner = min(banner, largura - 96)
    ativ = min(ativ, largura - 80)
    banner_altura = max(64, int(88 * min(1.0, escala + 0.04)))
    ativ_altura = max(150, int(190 * min(1.0, escala + 0.06)))
    return Metricas(largura, altura, banner, banner_altura, borda, ativ,
                    ativ_altura, escala, compacto)


def fonte(tamanho: float, peso=None, familia: str = ''):
    """QFont com a família preferida e fallback para Segoe UI."""
    from PyQt6.QtGui import QFont  # noqa: PLC0415
    if not familia:
        familia = 'Segoe UI Variable'
    f = QFont(familia)
    f.setFamilies(['Segoe UI Variable', 'Segoe UI', 'Arial'])
    f.setPixelSize(max(8, int(round(tamanho))))
    if peso is not None:
        f.setWeight(peso)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return f
