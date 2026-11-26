import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from core import aprendizado as AP
from core import registro_aplicativos as RA

chave = RA.normalizar('NIA, abra meu escritório.').casefold()
alvo = RA.normalizar('escritório').casefold()
print(repr(chave), repr(alvo))
tokens = {t for t in chave.split() if len(t) > 2 and t not in AP._PARAR}
alvos = {t for t in alvo.split() if len(t) > 2 and t not in AP._PARAR}
print(tokens, alvos, len(tokens & alvos) / max(1, len(alvos)))
