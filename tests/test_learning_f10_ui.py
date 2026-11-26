# -*- coding: utf-8 -*-
"""RED F10: interface real da Central de Aprendizado (offscreen)."""
from __future__ import annotations

import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtWidgets import QApplication

from core.aprendizado_adaptativo.memoria import MemoriaProcedural


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_painel_lista_conhecimentos_e_procedimentos(app, tmp_path):
    from core.aprendizado_adaptativo.ui import PainelAprendizado

    mem = MemoriaProcedural(tmp_path / 'm.db')
    mem.registrar_conhecimento('Fluxo novo', 'Aprendido por instrução',
                               origem='instrucao', tipo='procedimento')
    pid = mem.registrar_procedimento('demo.fluxo', objetivo='Abrir demo',
                                     origem='instrucao')
    mem.registrar_versao(pid, versao=1, payload={'ok': True})

    painel = PainelAprendizado(memoria=mem)
    assert painel.windowTitle()
    assert painel.minimumWidth() <= 760
    assert painel.minimumHeight() <= 520
    assert painel.lista_conhecimentos.count() == 1
    assert painel.lista_procedimentos.count() == 1
    painel.filtro.setText('inexistente')
    assert painel.lista_conhecimentos.count() == 0
    painel.close()
    mem.fechar()


def test_workspace_split_38_62(app, tmp_path):
    from core.aprendizado_adaptativo.ui import PainelAprendizado

    mem = MemoriaProcedural(tmp_path / 'm.db')
    painel = PainelAprendizado(memoria=mem)
    painel.definir_workspace('# Plano\n\nTexto do documento', [
        {'titulo': 'Doc oficial', 'url': 'https://example.invalid/doc'}])
    painel.show()
    app.processEvents()
    sizes = painel.splitter.sizes()
    total = sum(sizes)
    fracao = sizes[0] / max(1, total)
    assert 0.25 <= fracao <= 0.65
    assert '# Plano' in painel.editor_documento.toPlainText()
    assert painel.navegador.count() == 1
    painel.close()
    mem.fechar()


def test_exportacao_e_tema(app, tmp_path):
    from core.aprendizado_adaptativo.ui import PainelAprendizado

    mem = MemoriaProcedural(tmp_path / 'm.db')
    mem.registrar_conhecimento('Tema', 'Conteúdo', origem='instrucao')
    painel = PainelAprendizado(memoria=mem)
    assert '# Aprendizado Adaptativo' in painel.exportar()
    assert painel.estilo('dark').startswith('QWidget')
    assert '#0B111C' in painel.estilo('dark')
    painel.close()
    mem.fechar()
