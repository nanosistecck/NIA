import os
import sys
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import main
from tests.intelligence.fixtures.environment import LabEnvironment
from tests.intelligence.datasets.scenarios import CENARIOS

eventos = []
with LabEnvironment() as lab, patch.object(main, '_voice_diag',
                                           lambda nome, detalhe='': eventos.append((nome, str(detalhe)[:80]))):
    motor = lab.motor()
    print('frase result', motor._executar_frase_habilidade(
        'Vamos criar um produto.', 'texto'))
    print('observado', lab.observado)
    print('respostas', lab.respostas)
    print('eventos', eventos[:40])
