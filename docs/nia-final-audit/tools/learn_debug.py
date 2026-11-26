import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from core import aprendizado as AP
from core import registro_nativo as RN
from core import registro_aplicativos as RA
from tests.intelligence.fixtures.environment import LabEnvironment

with LabEnvironment() as lab:
    RN.registrar_nativos()
    RA.sincronizar_habilidades()
    caps = tuple(h.id for h in __import__('main').CH.todas()) + tuple(
        i.id for i in RA.todos() if i.tipo != 'ferramenta')
    print('planos in caps', 'planos' in caps)
    m = AP.Aprendizado(caminho=lab.raiz / '.nia' / 'aprendizado.json', capacidades=caps)
    print('learn', m.aprender('escritório', 'planos'))
    print('listar', m.listar())
    print('resolve', m.resolver('NIA, abra meu escritório.'))
    motor = lab.motor()
    print('motor helper', motor._habilidade_aprendida('NIA, abra meu escritório.')[0])
