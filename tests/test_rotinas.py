"""Rotinas locais: persistência, recorrência, atrasos e reserva atômica."""
from datetime import date, datetime, time, timedelta, timezone

import pytest

from core import rotinas as R


@pytest.fixture
def armazem(tmp_path):
    return R.ArmazemRotinas(db_path=tmp_path / 'rotinas.db')


def _em_utc(ano, mes, dia, hora=0, minuto=0):
    return datetime(ano, mes, dia, hora, minuto, tzinfo=timezone.utc)


def test_criar_persistir_e_recuperar(armazem):
    criada = armazem.criar({
        'titulo': 'Beber água', 'mensagem': 'Hora de beber água',
        'repeticao': 'diaria', 'hora': '09:00', 'fuso': 'UTC'})
    assert criada['estado'] == 'ativo'
    assert criada['proxima_execucao']

    outro = R.ArmazemRotinas(db_path=armazem.db_path)
    itens = outro.listar()
    assert len(itens) == 1
    assert itens[0]['titulo'] == 'Beber água'
    assert itens[0]['proxima_execucao'] == criada['proxima_execucao']
    assert outro.historico(criada['id']) == []


def test_recorrencia_unica_diaria_e_dias_uteis():
    base = {'hora': '09:00', 'fuso': 'UTC', 'data': '2027-01-10'}
    unica = R.proxima_ocorrencia({**base, 'repeticao': 'unica'},
                                 _em_utc(2027, 1, 9))
    assert unica.date() == date(2027, 1, 10)

    diaria = R.proxima_ocorrencia({**base, 'repeticao': 'diaria'},
                                  _em_utc(2027, 1, 9, 10))
    assert diaria.date() == date(2027, 1, 10)

    # Sexta depois das 9h: próximo dias úteis é segunda.
    sexta = _em_utc(2027, 1, 8, 12)   # sexta
    util = R.proxima_ocorrencia({**base, 'repeticao': 'dias_uteis'}, sexta)
    assert util.date() == date(2027, 1, 11)
    assert util.weekday() == 0


def test_horario_inexistente_e_ambiguos():
    # Primavera em Nova York: 02:30 não existe; primeiro instante válido 03:00.
    faltando = R.resolver_hora(date(2027, 3, 14), time(2, 30),
                               'America/New_York')
    local = faltando.astimezone(R._fuso('America/New_York'))
    assert (local.hour, local.minute) == (3, 0)

    # Outono: 01:30 é ambíguo; usa a primeira ocorrência (EDT, -04:00).
    ambiguo = R.resolver_hora(date(2027, 11, 7), time(1, 30),
                              'America/New_York')
    local = ambiguo.astimezone(R._fuso('America/New_York'))
    assert (local.hour, local.minute) == (1, 30)
    assert local.utcoffset().total_seconds() == -4 * 3600


def test_editar_pausar_reativar_e_executar_manual(armazem):
    rotina = armazem.criar({
        'titulo': 'Rotina', 'mensagem': 'texto', 'repeticao': 'diaria',
        'hora': '09:00', 'fuso': 'UTC'})
    original = rotina['proxima_execucao']

    armazem.atualizar(rotina['id'], {'hora': '10:00'})
    editada = armazem.obter(rotina['id'])
    assert editada['hora'] == '10:00'
    assert editada['proxima_execucao'] != original

    armazem.pausar(rotina['id'])
    pausada = armazem.obter(rotina['id'])
    assert pausada['estado'] == 'pausado'
    assert pausada['proxima_execucao'] is None

    armazem.reativar(rotina['id'])
    reativada = armazem.obter(rotina['id'])
    proxima = R._de_iso(reativada['proxima_execucao'])
    assert reativada['estado'] == 'ativo' and proxima > datetime.now(timezone.utc)

    ocorrencia = 'manual-' + '1'
    log = armazem.reservar(rotina['id'], ocorrencia, 'manual')
    assert log is not None
    armazem.finalizar(log, True)
    historico = armazem.historico(rotina['id'])
    assert historico[0]['origem'] == 'manual'
    assert historico[0]['resultado'] == 'ok'
    # Executar agora não desloca a próxima ocorrência agendada.
    assert armazem.obter(rotina['id'])['proxima_execucao'] == reativada['proxima_execucao']


def test_reserva_atomica_e_interrompida(armazem):
    rotina = armazem.criar({
        'titulo': 'Rotina', 'mensagem': 'texto', 'repeticao': 'diaria',
        'hora': '09:00', 'fuso': 'UTC'})
    ocorrencia = '2027-01-10T09:00:00+00:00'
    primeiro = armazem.reservar(rotina['id'], ocorrencia, 'agendada')
    segundo = armazem.reservar(rotina['id'], ocorrencia, 'agendada')
    assert primeiro is not None and segundo is None
    # Cancelada antes do resultado: recuperação marca como interrompida.
    # Agora antes da próxima agendada real: só a reserva pendente é recuperada.
    atrasadas = armazem.recuperar(_em_utc(2026, 11, 19, 12))
    assert atrasadas == []
    historico = armazem.historico(rotina['id'])
    assert 'interrompida' in {item['resultado'] for item in historico}


def test_retomada_apos_suspensao_registra_apenas_uma_atrasada(armazem):
    rotina = armazem.criar({
        'titulo': 'Diária', 'mensagem': 'texto', 'repeticao': 'diaria',
        'hora': '09:00', 'fuso': 'UTC'})
    agora = _em_utc(2027, 1, 20, 15)
    atrasadas = armazem.recuperar(agora)
    assert atrasadas == [rotina['id']]
    logs = armazem.historico(rotina['id'])
    assert len([l for l in logs if l['resultado'] == 'atrasada']) == 1
    proxima = R._de_iso(armazem.obter(rotina['id'])['proxima_execucao'])
    assert proxima > agora


def test_agendador_dispara_uma_vez_e_nao_repete(armazem):
    import time as _tempo
    from unittest.mock import Mock
    rotina = armazem.criar({
        'titulo': 'Agora', 'mensagem': 'Beber água', 'repeticao': 'diaria',
        'hora': '09:00', 'fuso': 'UTC'})
    futuro = (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()
    with armazem._conectar() as conexao:
        conexao.execute(
            'UPDATE rotinas SET proxima_execucao=? WHERE id=?',
            (futuro, rotina['id']))
    notificador = Mock(return_value=True)
    agendador = R.Agendador(armazem=armazem, notificador=notificador)
    agendador.iniciar()
    try:
        limite = _tempo.monotonic() + 5
        while _tempo.monotonic() < limite and not notificador.called:
            _tempo.sleep(0.02)
        assert notificador.call_count == 1
        notificador.assert_called_with('Beber água')
        logs = [l for l in armazem.historico(rotina['id'])
                if l['origem'] == 'agendada']
        assert logs and all(l['resultado'] == 'ok' for l in logs)
    finally:
        agendador.parar()
