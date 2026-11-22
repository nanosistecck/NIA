"""Fontes reais para os testes Qt offscreen no Windows."""
import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def fontes_qt_offscreen(request):
    # O plugin offscreen do Windows não descobre fontes do sistema sozinho.
    # Sem isso, métricas de layout medem apenas quadrados de glifos ausentes.
    if 'app' not in request.fixturenames or os.name != 'nt':
        return
    request.getfixturevalue('app')
    from PyQt6.QtGui import QFontDatabase
    if not QFontDatabase.families():
        for nome in ('segoeui.ttf', 'segoeuib.ttf', 'bahnschrift.ttf'):
            fonte = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / nome
            if fonte.exists():
                QFontDatabase.addApplicationFont(str(fonte))
