# -*- coding: utf-8 -*-
"""Medição real de CPU/RAM do motor adaptativo (F13), sem rede e sem dados privados."""
from __future__ import annotations

import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import psutil  # noqa: E402

from core.aprendizado_adaptativo.avaliador import AvaliadorCapacidade  # noqa: E402
from core.aprendizado_adaptativo.consolidacao import Consolidador  # noqa: E402
from core.aprendizado_adaptativo.memoria import MemoriaProcedural  # noqa: E402

proc = psutil.Process()
resultado = {
    'ambiente': {'plataforma': sys.platform, 'python': sys.version.split()[0],
                 'cpu_logicos': psutil.cpu_count(),
                 'modo': 'offscreen'},
    'amostras': {},
}


def amostrar(nome: str, segundos: float) -> None:
    proc.cpu_percent(None)
    rss0 = proc.memory_info().rss
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        time.sleep(0.02)
    resultado['amostras'][nome] = {
        'segundos': segundos,
        'cpu_percent': round(proc.cpu_percent(None), 2),
        'rss_inicial_bytes': rss0,
        'rss_final_bytes': proc.memory_info().rss,
        'rss_delta_bytes': proc.memory_info().rss - rss0,
        'threads': proc.num_threads(),
    }


amostrar('repouso', 2.0)

with tempfile.TemporaryDirectory() as tmp:
    mem = MemoriaProcedural(Path(tmp) / 'm.db')
    avaliador = AvaliadorCapacidade(
        resolver=lambda t: 'demo.abrir' if 'abrir' in t else None,
        evidencias={'demo.abrir': {'confirmado_em': time.time()}})
    consolidador = Consolidador(mem)
    latencias = []
    for i in range(100):
        t0 = time.perf_counter()
        avaliador.avaliar(f'abra demo {i}')
        latencias.append((time.perf_counter() - t0) * 1000)
    pid = mem.registrar_procedimento('demo.abrir', objetivo='medicao', origem='instrucao')
    consolidador.consolidar({'procedimento_id': pid, 'resultado': 'sucesso',
                             'evidencia': {'estado': 'medido'}, 'origem': 'execucao'})
    amostrar('com_memoria_e_avaliacao', 2.0)
    resultado['avaliacao_ms'] = {
        'p50': round(statistics.median(latencias), 3),
        'p95': round(sorted(latencias)[94], 3),
        'max': round(max(latencias), 3),
        'chamadas': len(latencias),
    }
    resultado['registros'] = {
        'knowledge': len(mem.listar('knowledge')),
        'procedures': len(mem.listar('procedures')),
        'experiences': len(mem.listar('experiences')),
    }
    mem.fechar()

amostrar('depois', 2.0)
destino = RAIZ / 'NIA_Adaptive_Learning' / 'docs' / 'adaptive_learning' / 'progress' / 'performance.json'
destino.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(resultado, indent=2, ensure_ascii=False))
