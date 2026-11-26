import faulthandler
import os
import sys

faulthandler.enable()
os.environ['QT_QPA_PLATFORM'] = 'windows'
from PyQt6.QtWidgets import QApplication, QWidget

app = QApplication([])

class A(QWidget):
    def nativeEvent(self, event_type, message):
        return super().nativeEvent(event_type, message)

class B(QWidget):
    def nativeEvent(self, event_type, message):
        return False, 0

for nome, cls in (('B-false', B),):
    print('construindo', nome, flush=True)
    w = cls()
    w.resize(200, 100)
    print('winId', nome, int(w.winId()), flush=True)
print('FIM', flush=True)
