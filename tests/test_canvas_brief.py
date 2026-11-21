"""Cards temporários do Canvas: hora, data e clima (sem rede e sem áudio)."""
import json
import os
import time
from datetime import date, timedelta
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel

import main
import ui
from actions.weather_report import _card_do_tempo
from core.canvas_brief import (
    BriefCard, BriefDeck, ClockDateBrief, ModernClock, WeatherBrief, WeatherWeek,
)


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(ui.MainWindow, '_check_config', lambda self: True)
    w = ui.MainWindow('face.png')
    w.resize(1280, 820)
    w.show()
    app.processEvents()
    yield w
    for timer in w.findChildren(QTimer):
        timer.stop()
    w.hide()
    w.deleteLater()
    app.processEvents()


def settle(app):
    QTest.qWait(800)
    app.processEvents()


def _dados_tempo(**extras):
    hoje = date(2026, 11, 19)
    dados = {
        'timezone': 'America/Sao_Paulo',
        'current': {
            'temperature_2m': 18.4,
            'apparent_temperature': 17.2,
            'relative_humidity_2m': 81,
            'wind_speed_10m': 9.6,
        },
        'daily': {
            'time': [(hoje + timedelta(days=i)).isoformat() for i in range(7)],
            'weather_code': [0, 2, 61, 95, 45, 71, 3],
            'temperature_2m_min': [14.2, 15.0, 16.1, 17.0, 13.4, 10.0, 12.5],
            'temperature_2m_max': [25.6, 26.0, 23.4, 22.1, 24.0, 18.0, 21.5],
            'precipitation_probability_max': [0, 10, 80, 90, 20, 30, 5],
        },
    }
    dados.update(extras)
    return dados


# ── dados do clima ────────────────────────────────────────────────────────
def test_card_do_tempo_hoje_traz_metricas_e_zero_de_chuva():
    card = _card_do_tempo(_dados_tempo(), 'Curitiba', 'hoje', False)
    assert card and card['tipo'] == 'clima'
    assert card['cidade'] == 'Curitiba'
    assert card['fuso'] == 'America/Sao_Paulo'
    assert card['semana'] is False
    assert len(card['dias']) == 7
    destaque = card['destaque']
    assert destaque['data'] == '2026-11-19'
    assert destaque['agora'] == 18.4
    assert destaque['sensacao'] == 17.2
    assert destaque['umidade'] == 81.0
    assert destaque['vento'] == 9.6
    # 0% é resposta válida: não pode virar None nem sumir da lista.
    assert destaque['chuva'] == 0.0
    assert card['dias'][0]['chuva'] == 0.0
    assert [d['codigo'] for d in card['dias']] == [0, 2, 61, 95, 45, 71, 3]
    assert card['dias'][2]['condicao'] == 'chuva fraca'


def test_card_do_tempo_amanha_e_semana_nao_inventam_metricas_atuais():
    amanha = _card_do_tempo(_dados_tempo(), 'Curitiba', 'amanha', False)
    assert amanha['semana'] is False
    assert amanha['destaque']['data'] == '2026-11-20'
    assert 'agora' not in amanha['destaque']

    semana = _card_do_tempo(_dados_tempo(), 'Curitiba', 'semana', False)
    assert semana['semana'] is True
    assert semana['destaque']['data'] == '2026-11-19'
    assert semana['destaque']['agora'] == 18.4


def test_card_do_tempo_sem_metricas_e_sem_dias():
    dados = _dados_tempo()
    dados.pop('current')
    dados['daily']['temperature_2m_min'] = []
    dados['daily']['precipitation_probability_max'] = []
    card = _card_do_tempo(dados, 'Curitiba', 'hoje', False)
    assert card['destaque']['agora'] is None
    assert card['destaque']['sensacao'] is None
    assert card['destaque']['umidade'] is None
    assert card['destaque']['vento'] is None
    assert all(d['min'] is None and d['chuva'] is None for d in card['dias'])
    assert _card_do_tempo({'daily': {}}, 'Curitiba', 'hoje', False) is None


def test_weather_action_emite_um_card_so_depois_do_sucesso(monkeypatch):
    import actions.weather_report as WR

    cartoes = []
    player = SimpleNamespace(write_log=lambda *_: None,
                             show_canvas_brief=cartoes.append)
    monkeypatch.setattr(WR, '_cidade_da_memoria', lambda: 'Curitiba')
    monkeypatch.setattr(WR, '_onde', lambda cidade: (-25.4, -49.2, 'Curitiba'))
    monkeypatch.setattr(WR, '_baixar', lambda url: _dados_tempo())
    resultado = WR.weather_action(
        {'city': 'Curitiba', 'time': 'hoje', '_brief_token': 7}, player=player)
    assert 'Curitiba' in resultado and len(cartoes) == 1
    assert cartoes[0]['token'] == 7
    assert cartoes[0]['destaque']['agora'] == 18.4

    # Falha de rede: nenhum card novo (e o antigo já foi limpo pelo main).
    cartoes.clear()

    def sem_rede(url):
        raise OSError('sem rede')

    monkeypatch.setattr(WR, '_baixar', sem_rede)
    monkeypatch.setattr(WR.webbrowser, 'open', lambda *a, **k: True)
    WR.weather_action({'city': 'Curitiba', '_brief_token': 8}, player=player)
    assert cartoes == []


def test_cidade_do_dono_vem_do_memoria_do_endereco(tmp_path, monkeypatch):
    """A identidade guarda o endereco completo, nao apenas `city`."""
    import actions.weather_report as WR
    memoria = tmp_path / 'memory'
    memoria.mkdir()
    (memoria / 'long_term.json').write_text(json.dumps({
        'identity': {'address': {'value': 'Santa Maria das Barreiras, Estado do Pará'}}}), encoding='utf-8')
    monkeypatch.setattr(WR, '_RAIZ', tmp_path)
    assert WR._cidade_da_memoria() == 'Santa Maria das Barreiras, Estado do Pará'


def test_previsao_sem_cidade_puxa_da_memoria_do_dono(monkeypatch):
    """Sem cidade: a previsao usa a cidade do dono (memoria), nao a do PC."""
    import actions.weather_report as WR
    cidade = 'Santa Maria das Barreiras, Estado do Pará'
    vistas = []

    def geolocaliza(c):
        vistas.append(c)
        return (-2.6, -40.4, c.split(',')[0])

    monkeypatch.setattr(WR, '_cidade_da_memoria', lambda: cidade)
    monkeypatch.setattr(WR, '_onde', geolocaliza)
    monkeypatch.setattr(WR, '_baixar', lambda url: _dados_tempo())
    cartoes = []
    player = SimpleNamespace(write_log=lambda *_: None, show_canvas_brief=cartoes.append)
    WR.weather_action({'time': 'hoje'}, player=player)
    assert vistas == [cidade]
    assert cartoes[0]['cidade'] == 'Santa Maria das Barreiras'


def test_previsao_sem_memoria_puxa_da_internet(monkeypatch):
    """Memoria vazia: o fallback para a internet do PC continua valendo."""
    import actions.weather_report as WR
    monkeypatch.setattr(WR, '_cidade_da_memoria', lambda: '')
    monkeypatch.setattr(WR, '_cidade_da_internet', lambda: 'Sao Paulo')
    monkeypatch.setattr(WR, '_onde', lambda c: (-23.5, -46.6, c.split(',')[0]))
    monkeypatch.setattr(WR, '_baixar', lambda url: _dados_tempo())
    cartoes = []
    player = SimpleNamespace(write_log=lambda *_: None, show_canvas_brief=cartoes.append)
    WR.weather_action({'time': 'hoje'}, player=player)
    assert cartoes and cartoes[0]['cidade'] == 'Sao Paulo'


def test_weather_brief_omite_campos_ausentes_mas_mostra_zero(app):
    breve = WeatherBrief()
    breve.set_data({
        'cidade': 'Curitiba',
        'destaque': {
            'data': '2026-11-19', 'codigo': 0, 'condicao': 'ceu limpo',
            'min': 14, 'max': 25, 'chuva': 0,
        },
        'dias': [{'data': '2026-11-19', 'codigo': 0, 'min': 14, 'max': 25,
                  'chuva': 0}],
    })
    textos = [lbl.text() for lbl in breve.findChildren(QLabel)]
    assert 'Chuva 0%' in textos
    assert not any('Agora' in t or 'Umidade' in t or 'Vento' in t for t in textos)
    assert any('14°' in t and '25°' in t for t in textos)
    breve.deleteLater()
    app.processEvents()


def test_cartao_hora_data_desenha_e_para_o_relogio_ao_esconder(app):
    cartao = BriefCard()
    cartao.resize(520, 320)
    cartao.set_content({'tipo': 'tudo'})
    assert isinstance(cartao.conteudo, ClockDateBrief)
    relogio = cartao.conteudo.clock
    assert isinstance(relogio, ModernClock)
    assert relogio._tmr.interval() == 1000

    cartao.show()
    app.processEvents()
    assert relogio._tmr.isActive()
    imagem = cartao.grab().toImage()
    assert not imagem.isNull()
    assert imagem.width() / imagem.devicePixelRatio() == 520

    cartao.conteudo.set_paused(True)
    assert not relogio._tmr.isActive()
    cartao.conteudo.set_paused(False)
    assert relogio._tmr.isActive()

    cartao.hide()
    app.processEvents()
    assert not relogio._tmr.isActive()
    cartao.deleteLater()
    app.processEvents()


# ── ciclo de vida no Canvas ───────────────────────────────────────────────
def test_brief_abre_troca_expira_e_volta_o_layout(window, app):
    w = window
    w._stage.set_hoje_visible(False)
    settle(app)
    hud_antes = w._hud_cam_stack.geometry()

    w._brief_sig.emit({'tipo': 'hora', 'token': 1})
    settle(app)
    assert w._stage.brief_visivel and w._stage.brief_tipo == 'hora'
    assert w._hud_cam_stack.geometry() != hud_antes
    card = w._stage.brief_host.geometry()
    hud = w._hud_cam_stack.geometry()
    assert not card.intersects(hud)

    # Substituir durante a apresentação: um card, sem sobreposição.
    clima = _card_do_tempo(_dados_tempo(), 'Curitiba', 'hoje', False)
    clima['token'] = 2
    w._brief_sig.emit(clima)
    settle(app)
    assert w._stage.brief_tipo == 'clima'
    assert not w._stage.brief_host.geometry().intersects(
        w._hud_cam_stack.geometry())

    # O × fecha pela animação e devolve a esfera ao lugar.
    w._stage.brief_host.cartoes[0]._fechar.click()
    QTest.qWait(800)
    app.processEvents()
    # QPropertyAnimation não garante `finished` no event loop offscreen;
    # conclui o fade explicitamente para verificar o layout final.
    w._stage._brief_fade_finished()
    app.processEvents()
    QTest.qWait(300)
    app.processEvents()
    assert not w._stage.brief_visivel
    # O núcleo deve voltar ao tamanho/posição normais (o card de hora usa
    # ~180 px na direita; a esfera em repouso usa muito mais e centraliza).
    hud = w._hud_cam_stack.geometry()
    assert hud.width() >= hud_antes.width() - 4
    assert hud.x() < w._stage.width() // 2


def test_token_velho_nao_substitui_card_novo(window, app):
    w = window
    w._brief_sig.emit({'tipo': 'hora', 'token': 10})
    settle(app)
    assert w._stage.brief_tipo == 'hora'

    # Consulta antiga chegando atrasada: ignorada, o card atual fica.
    atrasado = _card_do_tempo(_dados_tempo(), 'Curitiba', 'hoje', False)
    atrasado['token'] = 9
    w._brief_sig.emit(atrasado)
    settle(app)
    assert w._stage.brief_tipo == 'hora'

    novo = _card_do_tempo(_dados_tempo(), 'Curitiba', 'hoje', False)
    novo['token'] = 11
    w._brief_sig.emit(novo)
    settle(app)
    assert w._stage.brief_tipo == 'clima'


def test_brief_respeita_hoje_e_empilha_em_janela_estreita(window, app):
    w = window
    w._stage.set_hoje_visible(True)
    settle(app)
    w._brief_sig.emit({'tipo': 'hora', 'token': 1})
    settle(app)
    assert w._stage.hoje_visivel
    assert not w._stage.brief_host.geometry().intersects(
        w._stage.hoje_host.geometry())

    w.resize(820, 580)
    settle(app)
    card = w._stage.brief_host.geometry()
    hud = w._hud_cam_stack.geometry()
    assert not card.intersects(hud)
    assert hud.top() >= card.bottom()
    assert not card.intersects(w._stage.hoje_host.geometry())
    assert not hud.intersects(w._stage.hoje_host.geometry())


def test_tamanho_do_card_acompanhe_o_conteudo(window, app):
    w = window
    w._stage.set_hoje_visible(False)
    settle(app)

    # Hora: relógio+data não viram cartão de altura fixa grande demais.
    w._brief_sig.emit({'tipo': 'hora', 'token': 1})
    settle(app)
    assert w._stage.brief_host.geometry().height() <= 160

    # Clima com um só dia: o card não abre lista/espaco para nada.
    um_dia = {'tipo': 'clima', 'cidade': 'Curitiba', 'token': 2,
              'semana': False,
              'destaque': {'data': '2026-11-19', 'codigo': 0, 'condicao': 'ceu limpo',
                           'min': 14, 'max': 25, 'chuva': 0},
              'dias': [{'data': '2026-11-19', 'codigo': 0, 'condicao': 'ceu limpo',
                        'min': 14, 'max': 25, 'chuva': 0}]}
    w._brief_sig.emit(um_dia)
    settle(app)
    assert w._stage.brief_host.geometry().height() < 220

    # Semana com sete dias: o card cresce para a lista real.
    semana = _card_do_tempo(_dados_tempo(), 'Curitiba', 'semana', False)
    semana['token'] = 3
    w._brief_sig.emit(semana)
    settle(app)
    assert w._stage.brief_host.geometry().height() > 220


def test_fala_estende_o_card_e_teto_encerra(window, app, monkeypatch):
    w = window
    w._brief_sig.emit({'tipo': 'hora', 'token': 1})
    settle(app)
    etapa = w._stage
    assert etapa._brief_timer.isActive()

    # A fala desta resposta segura o card...
    etapa.set_brief_speaking(True)
    assert etapa._brief_speaking
    # ...e o fim dela dá a margem de leitura, em vez dos 7 s originais.
    etapa.set_brief_speaking(False)
    restante = etapa._brief_timer.remainingTime()
    assert 1500 <= restante <= 2200

    # Fala que nunca avisa o fim: o teto continua armado.
    etapa.show_brief({'tipo': 'hora'})
    etapa.set_brief_speaking(True)
    assert etapa._brief_timer.remainingTime() <= 30000


def test_esc_fecha_o_card_e_interrompe(window, app):
    w = window
    w._brief_sig.emit({'tipo': 'hora', 'token': 1})
    settle(app)
    assert w._stage.brief_visivel
    parado = []
    w.on_interrupt = lambda: parado.append(True)
    w._do_interrupt()
    w._stage._brief_fade_finished()
    app.processEvents()
    assert not w._stage.brief_visivel
    assert parado == [True]


# ── ponte do main ─────────────────────────────────────────────────────────
def test_main_emite_card_do_relogio_uma_vez_por_pedido():
    enviados = []
    nia = SimpleNamespace(
        _brief_lock=__import__('threading').Lock(),
        _brief_token=0,
        ui=SimpleNamespace(show_canvas_brief=enviados.append),
    )
    for nome in ('_novo_brief_token', '_mostrar_brief', '_brief_do_relogio'):
        setattr(nia, nome, getattr(main.NiaLive, nome).__get__(nia, main.NiaLive))

    nia._brief_do_relogio({'pedido': 'hora', 'hora': '10:20'})
    nia._brief_do_relogio({'pedido': 'data', 'data': '19/11/2026'}, juntas=True)
    assert [c['tipo'] for c in enviados] == ['hora', 'tudo']
    assert enviados[0]['token'] < enviados[1]['token']

    # UI quebrada não derruba a resposta.
    def quebrada(dados):
        raise RuntimeError('sem janela')
    nia.ui.show_canvas_brief = quebrada
    nia._brief_do_relogio({'pedido': 'hora'})


def test_dia_indisponivel_nao_reaproveita_a_ultima_previsao():
    dados = _dados_tempo()
    dados['daily'] = {chave: valores[:1] for chave, valores in dados['daily'].items()}
    card = _card_do_tempo(dados, 'Curitiba', 'amanha', False)
    assert card['destaque']['data'] == '2026-11-20'
    assert card['destaque'].get('max') is None
    assert card['destaque']['condicao'] == 'Previsão indisponível'
    assert len(card['dias']) == 1


def test_clima_incompleto_chega_ao_canvas_pelo_fluxo_normal(monkeypatch):
    import actions.weather_report as WR
    dados = _dados_tempo()
    dados['daily'].pop('temperature_2m_min')
    dados['daily']['precipitation_probability_max'] = []
    monkeypatch.setattr(WR, '_onde', lambda cidade: (-25.4, -49.2, 'Curitiba'))
    monkeypatch.setattr(WR, '_baixar', lambda url: dados)
    cartoes = []
    player = SimpleNamespace(write_log=lambda *_: None, show_canvas_brief=cartoes.append)
    resposta = WR.weather_action({'city': 'Curitiba', 'time': 'amanha'}, player=player)
    assert 'máxima de 26 graus' in resposta
    assert len(cartoes) == 1
    assert cartoes[0]['destaque']['min'] is None
    assert cartoes[0]['destaque']['chuva'] is None


def test_data_invalida_na_lista_nao_desloca_o_destaque():
    dados = _dados_tempo()
    dados['daily']['time'][1] = 'invalida'
    card = _card_do_tempo(dados, 'Curitiba', 'depois de amanha', False)
    assert card['destaque']['data'] == '2026-11-21'
    assert card['destaque']['codigo'] == 61


def test_trocar_deck_para_timer_antigo_e_separa_dia_da_semana(app):
    deck = BriefDeck()
    deck.resize(760, 400)
    deck.set_conteudo('hora', {'tipo': 'hora'})
    deck.show()
    app.processEvents()
    antigo = deck.cartoes[0]
    timer = antigo.conteudo.clock._tmr
    assert timer.isActive()
    deck.set_conteudo('clima', _card_do_tempo(_dados_tempo(), 'Curitiba', 'amanha', False))
    app.processEvents()
    assert not timer.isActive() and not antigo.isVisible()
    assert len(deck.findChildren(BriefCard)) == 2
    assert isinstance(deck.cartoes[0].conteudo, WeatherBrief)
    assert isinstance(deck.cartoes[1].conteudo, WeatherWeek)
    assert deck.cartoes[0].conteudo._scroll.isHidden()
    deck.resize(380, 460)
    app.processEvents()
    assert not deck._horizontal
    deck.resize(760, 300)
    app.processEvents()
    assert deck._horizontal
    deck.hide()
    deck.deleteLater()


def test_fecha_durante_entrada_cancela_reentrada_e_timer(window, app):
    stage = window._stage
    stage.show_brief({'tipo': 'hora'})
    relogio = stage.brief_host.cartoes[0].conteudo.clock
    assert stage._brief_entry.isActive()
    stage.dismiss_brief()
    QTest.qWait(800)
    assert not stage._brief_entry.isActive()
    assert not stage.brief_visivel
    assert not relogio._tmr.isActive()
    stage.show_brief({'tipo': 'data'})
    QTest.qWait(800)
    assert stage.brief_visivel and stage.brief_tipo == 'data'
    assert stage._brief_effect.opacity() == 1.0


def test_clima_estatico_nao_tem_timer_de_decoracao(app):
    deck = BriefDeck()
    deck.set_conteudo('clima', _card_do_tempo(_dados_tempo(), 'Curitiba', 'hoje', False))
    deck.show()
    app.processEvents()
    assert deck.findChildren(QTimer) == []
    deck.hide()
    deck.deleteLater()


def test_clima_com_paineis_preserva_area_e_oferece_rolagem(window, app):
    window.resize(820, 580)
    stage = window._stage
    stage.set_hoje_visible(True)
    stage.chat_open = True
    stage.show_brief(_card_do_tempo(_dados_tempo(), 'Curitiba', 'amanha', False))
    QTest.qWait(800)
    deck = stage.brief_host
    assert not deck.geometry().intersects(stage.hoje_host.geometry())
    assert not deck.geometry().intersects(window._hud_cam_stack.geometry())
    assert stage.rect().contains(deck.geometry())
    assert deck._scroll.verticalScrollBar().maximum() > 0
    for card in deck.cartoes:
        assert card.height() >= card.minimumSizeHint().height()
