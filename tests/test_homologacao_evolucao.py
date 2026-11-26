# -*- coding: utf-8 -*-
"""Homologação cruzada do que ficou: sem rede, processo ou WebEngine."""
import subprocess
import sys
import threading

import pytest

from core import busca_fontes, permissoes_ferramentas as PF
from core.contexto_ferramentas import ContextoFerramentas
from core.registro_aplicativos import buscar, registrar, DescritorApp
from core import registro_aplicativos as RA


@pytest.fixture(autouse=True)
def registro_limpo(monkeypatch):
    monkeypatch.setattr(RA, '_DESCRITORS', {})
    registrar(DescritorApp(id='config', nome='Configurações',
        descricao='Ajustes', categoria='sistema',
        possui_interface=True, janela='config', dominio_ferramenta='configuracoes'))


def test_modulos_que_ficaram_nao_importam_rede_ou_webengine():
    for nome in ('janelas_ferramentas', 'contexto_ferramentas', 'registro_aplicativos'):
        __import__('core.' + nome)
    assert not any('QtWebEngine' in m for m in sys.modules)
    assert not any(m.startswith('ddgs') or m.startswith('duckduckgo')
                   for m in sys.modules)


def test_cenario_cruzado_contexto_permissao_registro():
    ctx = ContextoFerramentas()
    acao = ctx.iniciar('file_controller', {'action': 'read', 'path': '/tmp/x'})
    assert ctx.resolver('repita').argumentos == acao.argumentos
    assert ctx.concluir(True, 'ok').sequencia == 1
    with pytest.raises(PermissionError):
        PF.verificar('file_controller', {'action': 'read', 'path': '/tmp/x'},
                     ('arquivos:acessar',))
    assert [i.id for i in buscar('config')] == ['config']
    assert 'DADOS' in busca_fontes._seguro('DADOS')


def test_sem_subprocess_ou_threads_ao_carregar():
    antes = set(threading.enumerate())
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(subprocess, 'Popen', lambda *a, **k: pytest.fail('processo'))
        mp.setattr(subprocess, 'run', lambda *a, **k: pytest.fail('processo'))
        for nome in ('janelas_ferramentas', 'contexto_ferramentas',
                     'registro_aplicativos'):
            __import__('core.' + nome)
    assert set(threading.enumerate()) == antes
