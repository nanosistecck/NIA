import faulthandler
import os
import sys
import tempfile
from pathlib import Path

faulthandler.enable()
RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))
os.environ['QT_QPA_PLATFORM'] = 'windows'

with tempfile.TemporaryDirectory(prefix='nia-janelas-') as tmp:
    base = Path(tmp)
    for chave in ('NIA_PLANOS_DIR', 'NIA_AGENDA', 'NIA_PERFIL'):
        os.environ[chave] = str(base / chave)
    from PyQt6.QtWidgets import QApplication
    app = QApplication([])
    print('platform', app.platformName(), flush=True)

    print('construindo PlanosWindow', flush=True)
    from core.interface_planos import PlanosWindow
    w1 = PlanosWindow()
    print('planos ok, frame', getattr(w1._frame_nativo, 'active', None), flush=True)
    w1.close()

    print('construindo AgendaWindow', flush=True)
    from core.interface_agenda import AgendaWindow
    w2 = AgendaWindow()
    print('agenda ok, frame', getattr(w2._frame_nativo, 'active', None), flush=True)
    w2.close()
print('FIM', flush=True)
