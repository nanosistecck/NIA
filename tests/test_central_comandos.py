# -*- coding: utf-8 -*-
"""Controle da Central por voz/texto usando o roteamento local existente."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import main
from core import registro_aplicativos as RA
from core.registro_aplicativos import reconhecer_comando_central


@pytest.fixture(autouse=True)
def registro(monkeypatch):
    monkeypatch.setattr(RA, '_DESCRITORS', {})
    RA.registrar(RA.DescritorApp(id='agenda', nome='Agenda',
        descricao='Compromissos', categoria='produtividade',
        possui_interface=True, janela='agenda', dominio_ferramenta='agenda'))
    RA.registrar(RA.DescritorApp(id='globo', nome='Globo',
        descricao='Terra 3D', categoria='conhecimento',
        possui_interface=True, janela='globo', dominio_ferramenta='globo'))
    yield


def nia():
    obj = object.__new__(main.NiaLive)
    obj.ui = SimpleNamespace(
        abrir_central=Mock(), abrir_manual=Mock(), executar_dominio=Mock(),
        write_log=Mock(), muted=True)
    return obj


@pytest.mark.parametrize('frase,tipo', [
    ('NIA, abra a Central de Aplicativos.', 'abrir_central'),
    ('feche a central', 'fechar_central'),
    ('abra o manual', 'abrir_manual'),
    ('quais comandos você entende?', 'ajuda'),
    ('mostre todas as suas ferramentas', 'listar'),
    ('quais ferramentas de pesquisa você possui?', 'ferramentas_pesquisa'),
    ('quais aplicativos precisam ser configurados?', 'config_pendente'),
    ('abra a agenda', 'abrir_app'),
    ('abra o globo', 'abrir_app'),
    ('fixe o globo no dock', 'dock'),
    ('remova a agenda do dock', 'dock'),
])
def test_reconhecer_frases(frase, tipo):
    assert reconhecer_comando_central(frase)[0] == tipo
    assert reconhecer_comando_central('fazer café com açúcar')[0] == ''


def test_dados_da_acao_de_dock():
    tipo, dados = reconhecer_comando_central('fixe o globo no dock')
    assert tipo == 'dock' and dados['acao'] == 'dock_fixar'
    _, dados = reconhecer_comando_central('remova a agenda do dock')
    assert dados['acao'] == 'dock_remover'


def test_executar_por_frase_chama_ponte_de_ui():
    obj = nia()
    assert obj._executar_central_por_frase('abra a central', 'voz') is True
    obj.ui.abrir_central.assert_called_with(True)
    assert obj._executar_central_por_frase('feche a central', 'texto') is True
    obj.ui.abrir_central.assert_called_with(False)
    assert obj._executar_central_por_frase('abra o manual', 'voz') is True
    obj.ui.abrir_manual.assert_called_once_with()
    assert obj._executar_central_por_frase('abra a agenda', 'voz') is True
    obj.ui.executar_dominio.assert_called_with('__ui__', 'abrir_app',
                                               {'id': 'agenda'})
    assert obj._executar_central_por_frase('fixe o globo no dock', 'voz') is True
    obj.ui.executar_dominio.assert_called_with('__ui__', 'dock_fixar',
                                               {'id': 'globo'})


def test_listagem_compacta_sem_abrir_central():
    obj = nia()
    assert obj._executar_central_por_frase('quais ferramentas você possui?', 'voz') is True
    assert 'Agenda' in obj.ui.write_log.call_args.args[0]
    obj.ui.abrir_central.assert_not_called()


def test_frase_desconhecida_nao_e_consumida():
    obj = nia()
    assert obj._executar_central_por_frase('qual é a hora?', 'voz') is False
