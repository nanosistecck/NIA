import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from tests.intelligence.datasets.scenarios import CENARIOS
from tests.intelligence.runners.engine import executar

for identificador in sys.argv[1:]:
    c = next(x for x in CENARIOS if x.id == identificador)
    a = executar(c)
    print(identificador, a.as_dict())
