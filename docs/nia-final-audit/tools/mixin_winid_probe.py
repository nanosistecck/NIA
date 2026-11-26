import faulthandler
import os
import sys
from pathlib import Path

faulthandler.enable()
RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))
os.environ['QT_QPA_PLATFORM'] = 'windows'

from PyQt6.QtWidgets import QApplication, QWidget
from core.frame_nativo import FrameNativoMixin

app = QApplication([])

class W(FrameNativoMixin, QWidget):
    pass

print('criando W', flush=True)
w = W()
w.resize(300, 200)
print('winId', flush=True)
print(int(w.winId()), flush=True)
print('FIM', flush=True)
