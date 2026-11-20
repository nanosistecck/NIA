"""Skill 07: chat e voz acionam o mesmo executor das habilidades nativas."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import catalogo_habilidades as CH
from core.catalogo_habilidades import Disponibilidade
from main import NiaLive


def _nia_falsa():
    ui = SimpleNamespace(
        write_log=Mock(), abrir_pagina_config=Mock(),
        focar_busca_canvas=Mock(), gerar_resumo_agora=Mock())
    nia = SimpleNamespace(
        ui=ui, _ferramenta_secretaria=Mock(return_value='Abri a Secretária.'),
        _buscar_arquivos_local=Mock(return_value=True))
    for nome in ('_executar_habilidade', '_executar_frase_habilidade'):
        setattr(nia, nome, getattr(NiaLive, nome).__get__(nia, NiaLive))
    return nia


@pytest.fixture
def ponte(monkeypatch):
    nia = _nia_falsa()
    monkeypatch.setattr(CH, 'disponibilidade',
                        lambda ident: Disponibilidade(True, 'Pronta.'))
    monkeypatch.setattr(CH, '_EXECUTOR', nia._executar_habilidade)
    return nia


def test_frases_de_chat_e_voz_chegam_a_mesma_operacao(ponte):
    assert ponte._executar_frase_habilidade(
        'NIA, prepare o resumo do dia.', 'voz') is True
    ponte.ui.gerar_resumo_agora.assert_called_once_with()

    assert ponte._executar_frase_habilidade(
        'NIA, abra a Secretaria.', 'texto') is True
    ponte._ferramenta_secretaria.assert_called_once_with({'acao': 'abrir'})

    assert ponte._executar_frase_habilidade(
        'NIA, procure nos meus arquivos por garantia.', 'voz') is True
    args, kwargs = ponte._buscar_arquivos_local.call_args
    assert args[0] == 'procure nos meus arquivos por garantia'
    assert kwargs['origem'] == 'voz'

    assert ponte._executar_frase_habilidade('Bom dia, como vai?', 'texto') is False
    assert ponte.ui.write_log.call_count == 4


def test_sem_termo_abre_campo_de_entrada_local(ponte):
    ok, mensagem = CH.executar('buscar_arquivos')
    assert ok and 'Digite o termo' in mensagem
    ponte.ui.focar_busca_canvas.assert_called_once_with()
    assert not ponte._buscar_arquivos_local.called


def test_frase_reconhecida_nao_cai_no_modelo_mesmo_em_falha(monkeypatch):
    nia = _nia_falsa()
    monkeypatch.setattr(CH, '_EXECUTOR',
                        lambda ident, termo: (False, 'sem candidato local'))
    assert nia._executar_frase_habilidade(
        'NIA, prepare o resumo do dia.', 'texto') is True
    assert any('sem candidato local' in c.args[0]
               for c in nia.ui.write_log.call_args_list)


def test_habilidade_indisponivel_abre_configuracao(monkeypatch):
    nia = _nia_falsa()
    monkeypatch.setattr(CH, 'disponibilidade', lambda ident: Disponibilidade(
        False, 'Secretária desligada; ative em Configurações.'))
    monkeypatch.setattr(CH, '_EXECUTOR', nia._executar_habilidade)

    ok, mensagem = CH.executar('secretaria')
    assert ok and 'Configurações' in mensagem
    nia.ui.abrir_pagina_config.assert_called_once_with('secretaria')
    assert not nia._ferramenta_secretaria.called
