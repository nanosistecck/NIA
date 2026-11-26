# -*- coding: utf-8 -*-
"""Painel de diagnóstico sob demanda, com captura inspecionada."""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from core import painel_laboratorio as PL


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_painel_nao_executa_ate_clique(app, monkeypatch):
    """Quebra: painel poderia rodar testes ao ser construído."""
    chamadas = []
    monkeypatch.setattr(PL._TrabalhadorLaboratorio, 'executar',
                        lambda self: chamadas.append(self.modo))
    painel = PL.PainelLaboratorio()
    assert chamadas == []
    painel.btn_quick.click()
    QTest.qWait(100)
    assert chamadas == ['quick']
    painel.cancelar()
    painel._thread.wait(1000)


def test_painel_atualiza_metricas(app, monkeypatch):
    """Quebra: resultado do laboratório não aparecia na interface."""
    Metricas = {'aprovados': 31, 'avaliaveis': 31, 'bloqueados': 6,
                'total': 37, 'reprovados': 0}

    def falso(self):
        self.concluido.emit(Metricas)

    monkeypatch.setattr(PL._TrabalhadorLaboratorio, 'executar', falso)
    painel = PL.PainelLaboratorio()
    painel.btn_quick.click()
    QTest.qWait(300)
    assert '31/31' in painel.metricas.text()
    assert painel.status.estado == 'normal'
    painel.cancelar()
    painel._thread.wait(1000)


def test_captura_do_painel(app, tmp_path):
    """Quebra: nenhuma evidência visual do painel foi produzida."""
    painel = PL.PainelLaboratorio()
    painel.resize(520, 320)
    app.processEvents()
    destino = Path('logs') / 'captura_painel_laboratorio.png'
    destino.parent.mkdir(parents=True, exist_ok=True)
    assert painel.grab().save(str(destino)) is True
    assert destino.stat().st_size > 3000
