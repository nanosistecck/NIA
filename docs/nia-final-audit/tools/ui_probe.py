# -*- coding: utf-8 -*-
"""Capturas de UI em múltiplas resoluções/escalas, offscreen, sem dados reais."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
RAIZ = Path(__file__).resolve().parents[3]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication

from core.config_dashboard import ConfigDashboardWindow
from core.config_preferencias import ConfigService
from core.personas import ESCOLHA_PADRAO

RESOLUCOES = ((1280, 720), (1366, 768), (1920, 1080), (2560, 1440))
ESCALAS = ('1.0', '1.25', '1.5')
SAIDA = RAIZ / 'logs' / 'audit-ui'


def main() -> int:
    escala = os.environ.get('QT_SCALE_FACTOR', '1.0')
    app = QApplication.instance() or QApplication([])
    if not QFontDatabase.families():
        for nome in ('segoeui.ttf', 'segoeuib.ttf', 'bahnschrift.ttf'):
            caminho_fonte = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / nome
            if caminho_fonte.exists():
                QFontDatabase.addApplicationFont(str(caminho_fonte))
    SAIDA.mkdir(parents=True, exist_ok=True)
    resultados = []
    for largura, altura in RESOLUCOES:
        base = Path(os.environ.get('TEMP', str(RAIZ))) / f'nia-ui-{largura}x{altura}'
        base.mkdir(parents=True, exist_ok=True)
        persona = base / 'persona.json'
        persona.write_text(json.dumps(dict(ESCOLHA_PADRAO, personagem='sulafat')),
                           encoding='utf-8')
        servico = ConfigService(persona_path=persona,
                                dashboard_path=base / 'dashboard.json',
                                interface_path=base / 'interface.json')
        janela = ConfigDashboardWindow(servico, refresh_on_open=False)
        janela.activate_page('geral')
        janela.resize(largura, altura)
        app.processEvents()
        alvo = SAIDA / f'geral-{largura}x{altura}-escala{escala.replace(".", "_")}.png'
        ok = janela.grab().save(str(alvo))
        resultados.append({
            'resolucao': f'{largura}x{altura}', 'escala': escala,
            'captura': alvo.name, 'ok': ok, 'bytes': alvo.stat().st_size if ok else 0,
            'minimum_width': janela.minimumSizeHint().width(),
            'overflow': janela.minimumSizeHint().width() > largura,
        })
        janela.close()
    print(json.dumps({'resultados': resultados}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
