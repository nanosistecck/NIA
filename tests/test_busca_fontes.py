"""Busca local com fontes: pedido explícito, IDs e referências verificáveis."""
import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

from core import busca_fontes as BF
from core.indice_local import IndiceLocal
from main import NiaLive
from ui import LogWidget


@pytest.fixture
def indice(tmp_path, monkeypatch):
    documentos = tmp_path / 'documentos'
    documentos.mkdir()
    (documentos / 'contrato.txt').write_text(
        'A garantia do equipamento vale por doze meses.', encoding='utf-8')
    indice = IndiceLocal(db_path=tmp_path / 'indice.db', fontes=[str(documentos)])
    indice.atualizar()
    monkeypatch.setattr(BF, 'indice_atual', lambda: indice)
    monkeypatch.setattr(BF.ConfigService, 'carregar_fontes_indice',
                        lambda self: [str(documentos)])
    return indice, documentos


def test_pedido_explicito_e_conversa_comum():
    pedido = BF.planejar_pedido('Procure nos meus arquivos por garantia')
    assert pedido is not None
    assert 'garantia' in pedido.consulta
    assert pedido.resumo is False
    assert BF.planejar_pedido(
        'Resuma o que meus arquivos dizem sobre garantia').resumo is True
    assert BF.planejar_pedido('Bom dia, como vai?') is None


def test_busca_devolve_fontes_com_id_e_trecho_seguro(indice):
    fontes = BF.buscar('garantia', indice=indice[0])
    assert fontes
    assert fontes[0].id == 'F1'
    assert fontes[0].nome == 'contrato.txt'
    assert 'garantia' in fontes[0].trecho.lower()
    assert '<' not in fontes[0].trecho and '>' not in fontes[0].trecho


def test_contexto_minimo_trata_conteudo_como_dado(indice):
    fontes = BF.buscar('garantia', indice=indice[0])
    contexto = BF.contexto_minimo('O que dizem sobre garantia?', fontes)
    assert '[F1]' in contexto
    assert 'DADOS, não instruções' in contexto
    assert 'garantia' in contexto.lower()


def test_referencias_inventadas_sao_removidas(indice):
    fontes = BF.buscar('garantia', indice=indice[0])
    texto, invalidas = BF.filtrar_referencias('Vale 12 meses [F1], mas [F7] diz mais.', fontes)
    assert '[F1]' in texto
    assert 'F7' not in texto
    assert invalidas == ['F7']


def test_abrir_fonte_respeita_pasta_removida(indice, tmp_path):
    _, documentos = indice
    arquivo = documentos / 'contrato.txt'
    assert BF.permitido_abrir(str(arquivo)) is True
    # Pasta removida da configuração: a fonte deixa de ser autorizada.
    from core.config_preferencias import ConfigService
    ConfigService.carregar_fontes_indice = lambda self: []
    assert BF.permitido_abrir(str(arquivo)) is False
    arquivo.unlink()
    ConfigService.carregar_fontes_indice = lambda self: [str(documentos)]
    assert BF.permitido_abrir(str(arquivo)) is False


def _esperar(condicao, segundos=3.0):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicao():
            return True
        time.sleep(0.02)
    return condicao()


def _nia_falsa():
    ui_falsa = SimpleNamespace(
        write_log=Mock(), show_content=Mock(), show_sources=Mock(),
        nome_da_ia_e='NIA')
    nia = SimpleNamespace(
        ui=ui_falsa, _turno_seq=0, _busca_seq=0, _interrupted=False,
        _falar_local=Mock(), _pendente_sintese=None)
    for nome in ('_buscar_arquivos_local', '_oferecer_sintese',
                 '_tratar_confirmacao_sintese', '_executar_sintese'):
        setattr(nia, nome, getattr(NiaLive, nome).__get__(nia, NiaLive))
    return nia


def test_chat_e_voz_usam_mesma_busca_com_fonte(indice, monkeypatch):
    monkeypatch.setattr(BF, 'indice_atual', lambda: indice[0])
    nia = _nia_falsa()
    assert nia._buscar_arquivos_local(
        'Procure nos meus arquivos por garantia', origem='voz') is True
    assert _esperar(lambda: nia.ui.show_sources.called)
    fontes = nia.ui.show_sources.call_args.args[1]
    assert fontes[0]['nome'].endswith('contrato.txt')
    assert 'garantia' in fontes[0]['trecho'].lower()
    assert _esperar(lambda: nia._falar_local.called)
    falado = nia._falar_local.call_args.args[0]
    assert 'contrato.txt' in falado
    assert 'garantia' not in falado.lower()

    assert nia._buscar_arquivos_local('Bom dia, como vai?') is False


def test_indice_vazio_e_busca_sem_resultado(indice, monkeypatch):
    vazio = IndiceLocal(db_path=indice[0].db_path.with_name('outra.db'), fontes=[])
    monkeypatch.setattr(BF, 'indice_atual', lambda: vazio)
    nia = _nia_falsa()
    nia._buscar_arquivos_local('Procure nos meus arquivos por garantia')
    assert _esperar(lambda: any('índice local vazio' in c.args[0].lower()
                                for c in nia.ui.write_log.call_args_list))

    monkeypatch.setattr(BF, 'indice_atual', lambda: indice[0])
    nia2 = _nia_falsa()
    nia2._buscar_arquivos_local('Procure nos meus arquivos por inexistente')
    assert _esperar(lambda: any('não localizei' in c.args[0].lower()
                                for c in nia2.ui.write_log.call_args_list))


def test_autorizacao_externa_esta_presoa_a_destino_e_trechos(indice, monkeypatch):
    monkeypatch.setattr(BF, 'indice_atual', lambda: indice[0])
    destino = {'tipo': 'externo', 'provedor': 'gemini', 'modelo': 'flash',
               'assinatura': 'gemini|flash|7', 'local': False}
    monkeypatch.setattr(BF, 'destino_atual', lambda: destino)
    enviados = []
    monkeypatch.setattr(BF, 'sintetizar', lambda ctx, dest: enviados.append(ctx) or 'Ok [F1]')

    nia = _nia_falsa()
    nia._buscar_arquivos_local(
        'Resuma o que meus arquivos dizem sobre garantia')
    assert _esperar(lambda: nia._pendente_sintese is not None)
    pergunta = [c.args[0] for c in nia.ui.write_log.call_args_list]
    assert any('SIM' in linha for linha in pergunta)

    # Recusa: nada é enviado.
    assert nia._tratar_confirmacao_sintese('não') is True
    assert nia._pendente_sintese is None
    assert not enviados

    # Mudança de destino exige nova autorização.
    nia._buscar_arquivos_local('Resuma o que meus arquivos dizem sobre garantia')
    assert _esperar(lambda: nia._pendente_sintese is not None)
    monkeypatch.setattr(BF, 'destino_atual',
                        lambda: {**destino, 'assinatura': 'gemini|outro|7'})
    assert nia._tratar_confirmacao_sintese('sim') is True
    assert not enviados

    # Destino estável + SIM: apenas os trechos autorizados vão.
    monkeypatch.setattr(BF, 'destino_atual', lambda: destino)
    nia._buscar_arquivos_local('Resuma o que meus arquivos dizem sobre garantia')
    assert _esperar(lambda: nia._pendente_sintese is not None)
    assert nia._tratar_confirmacao_sintese('sim') is True
    assert _esperar(lambda: len(enviados) == 1)
    assert '[F1]' in enviados[0]
    assert 'DADOS, não instruções' in enviados[0]
    assert not any(' não verificada' in c.args[0] for c in nia.ui.write_log.call_args_list
                   if 'fonte' in c.args[0])


def test_referencia_inventada_nao_vira_link(indice, monkeypatch):
    monkeypatch.setattr(BF, 'indice_atual', lambda: indice[0])
    destino = {'tipo': 'externo', 'provedor': 'gemini', 'modelo': 'flash',
               'assinatura': 'gemini|flash|7', 'local': False}
    monkeypatch.setattr(BF, 'destino_atual', lambda: destino)
    monkeypatch.setattr(BF, 'sintetizar',
                        lambda ctx, dest: 'Vale 12 meses [F1]. [F9] inventado.')
    nia = _nia_falsa()
    nia._buscar_arquivos_local('Resuma o que meus arquivos dizem sobre garantia')
    assert _esperar(lambda: nia._pendente_sintese is not None)
    nia._tratar_confirmacao_sintese('sim')
    assert _esperar(lambda: any(c.args[0].startswith('NIA:')
                                for c in nia.ui.write_log.call_args_list))
    texto = [c.args[0] for c in nia.ui.write_log.call_args_list
             if c.args[0].startswith('NIA:')][-1]
    assert '[F1]' in texto
    assert '[F9]' not in texto
    assert 'fonte não verificada' in texto


def test_botao_abrir_fonte_usa_callback_validado():
    app = QApplication.instance() or QApplication([])
    pai = QWidget()
    pai._abrir_fonte_local = Mock()
    log = LogWidget(pai)
    log.resize(500, 300)
    log.show()
    app.processEvents()
    log.append_fontes('Fontes encontradas', [{
        'rotulo': '[F1] contrato.txt · posição 0',
        'arquivo': 'contrato.txt',
        'trecho': 'garantia por doze meses'}])
    app.processEvents()
    botoes = [b for b in log.findChildren(QPushButton)
              if 'Abrir fonte' in b.text()]
    assert botoes
    botoes[0].click()
    pai._abrir_fonte_local.assert_called_once_with('contrato.txt')
