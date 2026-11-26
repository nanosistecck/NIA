import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))

from core import preflight as PF
import importlib.util

for nome, funcao in (
    ('python', lambda: PF.verificar_python(sys.version_info)),
    ('deps', lambda: [importlib.util.find_spec(n) is not None for n in PF.ESSENCIAIS]),
    ('modulos', lambda: [importlib.util.find_spec('core.' + n) is not None for n in PF.MODULOS_NUCLEO]),
    ('declaracoes', PF._declaracoes),
    ('sintaxe', PF._syntaxe_core),
    ('bancos', lambda: [PF._banco(Path.home() / '.nia' / n) for n in ('rotinas.db',)]),
):
    t0 = time.perf_counter()
    funcao()
    print(nome, round(time.perf_counter() - t0, 3), flush=True)
