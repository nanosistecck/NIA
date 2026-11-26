# -*- coding: utf-8 -*-
"""Manual local: arquivo válido, sem recursos externos e abertura pela ponte."""
import os
import re

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtWidgets import QApplication

import ui
from core import registro_aplicativos as RA
from core.manual_uso import caminho_manual, disponivel


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_manual_existe_e_e_autocontido():
    assert disponivel()
    texto = caminho_manual().read_text(encoding='utf-8')
    assert '<html' in texto and '<script>' in texto and '</html>' in texto
    for secao in ('Central', 'Manual', 'Interface'):
        assert '"' + secao + '"' in texto
    # Nenhum recurso externo: sem src/href de rede, sem CDN e sem @import.
    assert not re.search(r'<(?:script|link|img)[^>]+(?:src|href)\s*=\s*["\']https?://', texto)
    assert '@import' not in texto and 'cdn.' not in texto.lower()


def test_frases_do_manual_sao_reconhecidas():
    assert RA.reconhecer_comando_central('abra o manual')[0] == 'abrir_manual'
    assert RA.reconhecer_comando_central('mostre o manual da NIA')[0] == 'abrir_manual'
    assert RA.reconhecer_comando_central('quais comandos você entende?')[0] == 'ajuda'
    assert RA.reconhecer_comando_central('como uso a NIA')[0] == 'ajuda'


def test_nia_abre_manual_por_frase():
    from main import NiaLive
    chamadas = []

    class UI:
        def abrir_manual(self):
            chamadas.append(True)

    obj = object.__new__(NiaLive)
    obj.ui = UI()
    assert obj._executar_central_por_frase('abra o manual', 'voz') is True
    assert chamadas == [True]


def test_sinal_da_ui_abre_arquivo_local(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(ui.MainWindow, '_check_config', lambda self: True)
    for chave in ('NIA_PLANOS_DIR', 'NIA_AGENDA', 'NIA_PERFIL'):
        monkeypatch.setenv(chave, str(tmp_path / chave))
    vistos = []
    monkeypatch.setattr('PyQt6.QtGui.QDesktopServices.openUrl',
                        staticmethod(lambda url: vistos.append(url.toLocalFile()) or True))
    w = ui.MainWindow('face.png'); w.show(); app.processEvents()
    try:
        ponte = object.__new__(ui.NiaUI)
        ponte._win = w
        ponte.abrir_manual()
        app.processEvents()
        assert vistos and vistos[-1].endswith('index.html')
    finally:
        for t in w.findChildren(__import__('PyQt6.QtCore', fromlist=['QTimer']).QTimer):
            t.stop()
        w.hide(); w.deleteLater(); app.processEvents()
