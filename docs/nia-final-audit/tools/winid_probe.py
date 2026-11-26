import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))
os.environ['QT_QPA_PLATFORM'] = 'windows'

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt

app = QApplication([])
w = QWidget()
w.setWindowTitle('probe')
w.setWindowFlags(Qt.WindowType.Window)
w.resize(320, 200)
handle = w.winId()
print('platform', app.platformName())
print('winId type', type(handle), 'value', handle)
print('hwnd int', int(handle))
from core.frame_nativo import aplicar_frame_nativo
from PyQt6.QtWidgets import QVBoxLayout, QLabel
layout = QVBoxLayout(w)
layout.addWidget(QLabel('teste'))
print('install', aplicar_frame_nativo(w, cor='#00060a'))
print('active', getattr(w._frame_nativo, 'active', None))
print('erro', getattr(w._frame_nativo, 'erro', None))
