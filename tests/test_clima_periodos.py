from unittest.mock import patch

import pytest

from actions import weather_report as wr


@pytest.mark.parametrize('pedido,turno', [
    ('amanhã', ''), ('depois de amanhã', ''), ('amanhã pela manhã', 'manha'),
    ('amanhã à tarde', 'tarde'), ('hoje à noite', 'noite'),
    ('de madrugada', 'madrugada'), ('tomorrow morning', 'manha'),
    ('amanhã às 3h da tarde', '15'), ('às 23:00', '23'), ('às 25h', ''),
])
def test_interpreta_periodo_sem_confundir_amanha(pedido, turno):
    assert wr._qual_turno(pedido) == turno


@pytest.fixture
def dados():
    dias = ['2026-11-22', '2026-11-23']
    horas = [f'{dia}T{h:02}:00' for dia in dias for h in range(24)]
    return {
        'daily': {'time': dias, 'weather_code': [95, 95],
                  'temperature_2m_min': [10, 10], 'temperature_2m_max': [35, 35],
                  'precipitation_probability_max': [90, 90]},
        'current': {'temperature_2m': 30},
        'hourly': {'time': horas,
                   'temperature_2m': [20 if h < 12 else 28 for _ in dias for h in range(24)],
                   'precipitation_probability': [0 if h < 12 else 80 for _ in dias for h in range(24)],
                   'weather_code': [0 if h < 12 else 61 for _ in dias for h in range(24)]},
    }


def consultar(dados, pedido):
    with patch.object(wr, '_em_ingles', return_value=False), \
         patch.object(wr, '_onde', return_value=(0, 0, 'Cidade')), \
         patch.object(wr, '_baixar', return_value=dados):
        return wr.weather_action({'city': 'Cidade', 'time': pedido})


def test_amanha_usa_as_24_horas_corretas(dados):
    card = wr._card_do_tempo(dados, 'Cidade', 'amanhã', False)
    assert len(card['horas']) == 24
    assert card['horas'][0]['hora'] == '00:00'


def test_fala_apenas_do_periodo_pedido(dados):
    manha = consultar(dados, 'amanhã pela manhã')
    tarde = consultar(dados, 'amanhã à tarde')
    assert 'céu limpo' in manha and '0% de chance' in manha
    assert '20 a 20 graus' in manha and '35' not in manha
    assert 'chuva fraca' in tarde and '80% de chance' in tarde
    assert '28 a 28 graus' in tarde and 'Agora' not in tarde


def test_dia_inteiro_preserva_resumo(dados):
    for pedido in ('hoje', 'amanhã', 'depois de amanhã'):
        msg = consultar(dados, pedido)
        if pedido != 'depois de amanhã':
            assert '10 a 35 graus' in msg and '90% de chance' in msg
    assert 'Agora faz 30 graus' in consultar(dados, 'hoje')


def test_periodo_sem_dados_nao_inventa_resumo_diario(dados):
    dados['hourly'] = {}
    msg = consultar(dados, 'amanhã à noite')
    assert 'indisponível' in msg and '35' not in msg


def test_series_incompletas_nao_abrem_navegador(dados):
    dados['hourly']['temperature_2m'] = [20]
    msg = consultar(dados, 'amanhã à tarde')
    assert '80% de chance' in msg and 'navegador' not in msg


def test_noite_e_madrugada_sao_intervalos_distintos():
    horas = [{'hora': f'{h:02}:00'} for h in range(24)]
    assert len(wr._filtrar_horas(horas, 'noite')) == 6
    assert len(wr._filtrar_horas(horas, 'madrugada')) == 5
