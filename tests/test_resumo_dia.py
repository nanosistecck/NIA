"""Resumo do dia: fontes locais, cache por perfil e relógio controlável."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from core import resumo_dia as RD
from core import rotinas as R


@pytest.fixture
def contexto(tmp_path, monkeypatch):
    monkeypatch.setenv('NIA_RESUMO_DIA', str(tmp_path / 'resumo.json'))
    monkeypatch.setenv('NIA_ROTINAS_DB', str(tmp_path / 'rotinas.db'))
    monkeypatch.setattr(RD.requests if hasattr(RD, 'requests') else RD,
                        'requests', Mock(side_effect=AssertionError('rede')),
                        raising=False)
    armazem = R.ArmazemRotinas(db_path=tmp_path / 'rotinas.db')
    diario = tmp_path / 'diario.jsonl'
    agora = datetime(2027, 5, 10, 14, 0, tzinfo=timezone.utc)
    return armazem, diario, agora


def _diario(diario, agora, texto='Reunião com o cliente'):
    registro = {'quando': agora.strftime('%d/%m %H:%M'),
                'tipo': 'fez', 'texto': texto, 'detalhe': '', 'sessao': 'teste'}
    diario.write_text(json.dumps(registro, ensure_ascii=False) + '\n',
                      encoding='utf-8')


def test_gera_resumo_com_rotinas_e_diario(contexto):
    armazem, diario, agora = contexto
    _diario(diario, agora)
    armazem.criar({'titulo': 'Beber água', 'mensagem': 'água',
                   'repeticao': 'diaria', 'data': '2027-05-10',
                   'hora': '09:00', 'fuso': 'UTC'})
    resultado = RD.gerar(agora=agora, armazem=armazem, diario_path=diario,
                         fuso_exibicao='UTC', perfil='p1')
    assert '09:00' in resultado['texto']
    assert 'Beber água' in resultado['texto']
    assert 'Reunião com o cliente' in resultado['texto']
    assert 'Fontes:' in resultado['texto']
    assert resultado['parcial'] is False
    assert resultado['vazio'] is False


def test_resumo_parcial_quando_diario_ilegivel(contexto):
    armazem, _, agora = contexto
    resultado = RD.gerar(agora=agora, armazem=armazem,
                         diario_path=contexto[1].with_name('ausente.jsonl'),
                         fuso_exibicao='UTC', perfil='p1')
    assert 'parcial' in resultado['texto'].lower()
    assert 'diario' in resultado['erros']


def test_resumo_vazio_e_virada_de_dia(contexto):
    armazem, diario, agora = contexto
    armazem.criar({'titulo': 'Ontem', 'mensagem': 'm', 'repeticao': 'unica',
                   'data': '2027-05-09', 'hora': '09:00', 'fuso': 'UTC'})
    vazio = RD.gerar(agora=agora, armazem=armazem, diario_path=diario,
                     fuso_exibicao='UTC', perfil='p1')
    assert vazio['vazio'] is True
    assert 'Nenhuma rotina' in vazio['texto']

    depois = datetime(2027, 5, 11, 8, 0, tzinfo=timezone.utc)
    virada = RD.gerar(agora=depois, armazem=armazem, diario_path=diario,
                      fuso_exibicao='UTC', perfil='p1')
    assert virada['data'] == '2027-05-11'
    assert 'Ontem' not in virada['texto']


def test_ultimo_resumo_por_perfil_e_falha_preserva_anterior(contexto, monkeypatch):
    armazem, diario, agora = contexto
    _diario(diario, agora)
    primeiro = RD.gerar_e_salvar(agora=agora, armazem=armazem,
                                 diario_path=diario, fuso_exibicao='UTC',
                                 perfil='p1')
    assert primeiro['ok'] and primeiro['salvo']
    guardado = RD.carregar('p1')
    assert guardado['texto'] == primeiro['texto']

    monkeypatch.setattr(RD, 'gerar', Mock(side_effect=RuntimeError('falha')))
    falha = RD.gerar_e_salvar(perfil='p1')
    assert falha['ok'] is False
    assert RD.carregar('p1')['texto'] == guardado['texto']
    assert RD.carregar('p2') is None

    with RD._TRAVA:
        assert RD.carregar('p1')['gerado_em'] == primeiro['gerado_em']


def test_agendador_gera_resumo_com_card_oculto(contexto):
    import time as _tempo
    armazem, _, _ = contexto
    rotina = armazem.criar({
        'titulo': 'Resumo', 'mensagem': '', 'acao': 'resumo',
        'repeticao': 'diaria', 'data': '2027-05-10',
        'hora': '09:00', 'fuso': 'UTC'})
    futuro = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
    with armazem._conectar() as conexao:
        conexao.execute('UPDATE rotinas SET proxima_execucao=? WHERE id=?',
                        (futuro, rotina['id']))
    geracoes, leituras = [], []
    monkeypatch = pytest.MonkeyPatch()
    from core.config_preferencias import ConfigService
    monkeypatch.setattr(ConfigService, 'hoje_visivel', lambda self: False)
    assert ConfigService().hoje_visivel() is False
    monkeypatch.setattr(RD, 'gerar_e_salvar',
                        lambda: geracoes.append(True) or {
                            'ok': True, 'texto': 'Resumo gerado'})
    agendador = R.Agendador(armazem=armazem, notificador=Mock())
    agendador.resumo_leitura_automatica = lambda: True
    agendador.ao_resumo = lambda texto: leituras.append(texto)
    agendador.iniciar()
    try:
        limite = _tempo.monotonic() + 4
        while _tempo.monotonic() < limite and not geracoes:
            _tempo.sleep(0.02)
        assert geracoes
        assert leituras == ['Resumo gerado']
        logs = [l for l in armazem.historico(rotina['id'])
                if l['origem'] == 'agendada']
        assert logs and logs[0]['resultado'] == 'ok'
    finally:
        agendador.parar()
        monkeypatch.undo()


def test_acao_resumo_e_concluida_no_texto(contexto):
    armazem, diario, agora = contexto
    rotina = armazem.criar({'titulo': 'Resumo', 'mensagem': 'm',
                            'acao': 'resumo', 'repeticao': 'diaria',
                            'data': '2027-05-10', 'hora': '09:00', 'fuso': 'UTC'})
    log = armazem.reservar(rotina['id'], '2027-05-10T09:00:00+00:00', 'agendada')
    armazem.finalizar(log, True)
    resultado = RD.gerar(agora=agora, armazem=armazem, diario_path=diario,
                         fuso_exibicao='UTC', perfil='p1')
    assert 'resumo do dia' in resultado['texto']
    assert 'concluído' in resultado['texto']
