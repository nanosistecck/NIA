# -*- coding: utf-8 -*-
"""Mixin de janela secundária não pode abortar ao criar o HWND (PyQt6)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

CODIGO = """
import os, sys
sys.path.insert(0, r'{raiz}')
os.environ['QT_QPA_PLATFORM'] = 'windows'
from PyQt6.QtWidgets import QApplication, QWidget
from core.frame_nativo import FrameNativoMixin
app = QApplication([])
class W(FrameNativoMixin, QWidget):
    pass
w = W()
w.resize(320, 200)
print(int(w.winId()))
print('OK')
""".format(raiz=str(RAIZ))


def test_winid_com_mixin_nao_aborta():
    """Quebra: super().nativeEvent() em PyQt6 causa access violation."""
    ambiente = dict(os.environ)
    ambiente['QT_QPA_PLATFORM'] = 'windows'
    resultado = subprocess.run(
        [sys.executable, '-c', CODIGO], cwd=str(RAIZ),
        env=ambiente, capture_output=True, text=True, timeout=60)
    assert resultado.returncode == 0, resultado.stderr[-2000:]
    assert 'OK' in resultado.stdout
