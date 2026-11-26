import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from actions import web_search as WS
from actions import weather_report as WR

print('=== WEB SEARCH ===')
try:
    r = WS.web_search({'query': 'noticias de tecnologia hoje', 'mode': 'search'})
    print('resultado:', str(r)[:500])
except Exception as exc:
    print('ERRO', type(exc).__name__, exc)

print('=== WEATHER ===')
try:
    r = WR.weather_action({'city': 'Sao Paulo'})
    print('resultado:', str(r)[:500])
except Exception as exc:
    print('ERRO', type(exc).__name__, exc)
