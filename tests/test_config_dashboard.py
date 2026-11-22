"""Dashboard experimental de Configurações: persistência, tema e feedback.

Roda sem hardware de áudio: os serviços são reais (arquivos temporários), mas
as listas e os testes de dispositivo são simulados onde a chamada bloquearia.
"""
import json
import os
import time
from unittest.mock import Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtCore import QAbstractAnimation, Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from core.config_dashboard import ConfigDashboardWindow, PALETAS
from core.config_preferencias import (ConfigService, PreferenciaInvalida,
                                      carregar_persona, carregar_tema,
                                      normalizar_dispositivo, salvar_persona,
                                      salvar_tema)
from core.personas import ESCOLHA_PADRAO


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


class HostFalso:
    """Imita a ponte da NiaUI sem abrir áudio nem a conversa ao vivo."""

    def __init__(self, aplicado=True, erro=''):
        self.persona_atual = dict(ESCOLHA_PADRAO)
        self.aplicado = aplicado
        self.erro = erro
        self.chamadas = []
        self.logs = []

    def write_log(self, texto):
        self.logs.append(texto)

    def on_persona_change(self, tipo, chave, **kwargs):
        self.chamadas.append((tipo, chave, dict(kwargs)))
        return {'tipo': tipo, 'chave': chave, 'aplicado': self.aplicado,
                'salvo': None, 'aviso': '', 'erro': self.erro}


def esperar(app, condicao, limite=4.0):
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        if condicao():
            return True
        QTest.qWait(15)
        app.processEvents()
    return condicao()


def criar_janela(app, tmp_path, host=None, refresh=False):
    service = criar_service(tmp_path, host)
    janela = ConfigDashboardWindow(service, refresh_on_open=refresh)
    return janela, service, service.persona_path


def criar_service(tmp_path, host=None):
    persona = tmp_path / 'persona.json'
    if not persona.exists():
        persona.write_text(json.dumps(dict(ESCOLHA_PADRAO, personagem='sulafat')),
                           encoding='utf-8')
    return ConfigService(host=host, persona_path=persona,
                         dashboard_path=tmp_path / 'dashboard_config.json',
                         interface_path=tmp_path / 'interface.json')


@pytest.fixture
def config_isolada(tmp_path, monkeypatch):
    """Nenhuma página da etapa 3 mexe nos arquivos reais do usuário."""
    import ui
    from core import dono, nomes_tela, tema
    monkeypatch.setattr(dono, 'ARQUIVO', tmp_path / 'dono.json')
    monkeypatch.setattr(nomes_tela, 'ARQUIVO', tmp_path / 'nomes_tela.json')
    # O cache e global e sobrevive ao monkeypatch do ARQUIVO: sem limpar aqui,
    # "Nome de teste" vaza para os testes seguintes.
    monkeypatch.setattr(nomes_tela, '_cache', None)
    monkeypatch.setattr(tema, 'ARQUIVO', tmp_path / 'cores.json')
    monkeypatch.setattr(ui, 'NUCLEO_FILE', tmp_path / 'nucleo.json')
    monkeypatch.setattr(tema, '_escolhas', {})
    monkeypatch.setattr(tema, '_versao', 0)
    tema.carregar()
    return tmp_path


# ── persistência ────────────────────────────────────────────────────────────
def test_tema_padrao_escuro_e_gravacao_separada(tmp_path):
    caminho = tmp_path / 'dashboard_config.json'
    assert carregar_tema(caminho) == 'escuro'
    caminho.write_text('{quebrado', encoding='utf-8')
    assert carregar_tema(caminho) == 'escuro'
    assert salvar_tema('claro', caminho) == 'claro'
    assert carregar_tema(caminho) == 'claro'
    with pytest.raises(PreferenciaInvalida):
        salvar_tema('roxo', caminho)
    # O arquivo do tema não carrega (nem apaga) as cores do núcleo.
    assert json.loads(caminho.read_text(encoding='utf-8')) == {'tema': 'claro'}
    caminho.write_text(json.dumps({'tema': 'claro', 'futuro': 1}), encoding='utf-8')
    salvar_tema('escuro', caminho)
    assert json.loads(caminho.read_text(encoding='utf-8')) == {'tema': 'escuro',
                                                              'futuro': 1}


def test_persona_faz_merge_e_preserva_chaves_desconhecidas(tmp_path):
    caminho = tmp_path / 'persona.json'
    caminho.write_text(json.dumps({'personagem': 'lia', 'futuro': 7,
                                   'microfone': 'nao-definido'}),
                       encoding='utf-8')
    dados = carregar_persona(caminho)
    assert dados['personagem'] == 'lia'
    assert dados['microfone'] is None
    salvar_persona({'saida': 3, 'personalidade': 'amigo'}, caminho)
    bruto = json.loads(caminho.read_text(encoding='utf-8'))
    assert bruto['futuro'] == 7 and bruto['saida'] == 3
    assert bruto['personagem'] == 'lia'
    assert carregar_persona(caminho)['saida'] == 3


def test_normalizar_dispositivo_aceita_formatos_antigos():
    assert normalizar_dispositivo(None) is None
    assert normalizar_dispositivo('nao-definido') is None
    assert normalizar_dispositivo('') is None
    assert normalizar_dispositivo('4') == 4
    assert normalizar_dispositivo(0) == 0
    assert normalizar_dispositivo(-1) is None
    assert normalizar_dispositivo(True) is None


def test_service_grava_antes_de_aplicar_e_nao_repete_gravacao(tmp_path):
    host = HostFalso()
    service = criar_service(tmp_path, host)
    persona = service.persona_path
    resultado = service.alterar('personagem', 'leda')
    assert resultado['salvo'] and resultado['aplicado']
    assert json.loads(persona.read_text(encoding='utf-8'))['personagem'] == 'leda'
    assert host.persona_atual['personagem'] == 'leda'
    tipo, chave, kwargs = host.chamadas[-1]
    assert (tipo, chave) == ('personagem', 'leda')
    assert kwargs['persistir'] is False

    antes = persona.stat().st_mtime_ns
    repetido = service.alterar('personagem', 'leda')
    assert repetido['inalterado'] and repetido['salvo']
    assert persona.stat().st_mtime_ns == antes
    assert len(host.chamadas) == 1


def test_service_distingue_salvo_de_aplicado(tmp_path):
    host = HostFalso(aplicado=False, erro='motor fechado')
    service = criar_service(tmp_path, host)
    resultado = service.alterar('saida', 2)
    assert resultado['salvo'] is True
    assert resultado['aplicado'] is False
    assert 'motor fechado' in resultado['erro']
    # A escolha ficou gravada mesmo com a aplicação ao vivo falhando.
    assert json.loads(service.persona_path.read_text(encoding='utf-8'))['saida'] == 2


def test_service_sem_motor_ainda_grava(tmp_path):
    service = criar_service(tmp_path, None)
    resultado = service.alterar('personalidade', 'amigo')
    assert resultado['salvo'] is True
    assert resultado['aplicado'] is False
    assert 'reabrir a NIA' in resultado['erro']
    assert json.loads(service.persona_path.read_text(encoding='utf-8'))[
        'personalidade'] == 'amigo'


# ── janela ──────────────────────────────────────────────────────────────────
def test_janela_le_valores_reais_e_preserva_dispositivo_indisponivel(app, tmp_path):
    janela, service, persona = criar_janela(app, tmp_path, host=HostFalso())
    try:
        persona.write_text(json.dumps(dict(ESCOLHA_PADRAO, personagem='sulafat',
                                           personalidade='amigo', microfone=42,
                                           saida=7)), encoding='utf-8')
        janela._aplicar_valores()
        assert janela.voice_combo.currentData() == 'sulafat'
        assert janela.personality_combo.currentData() == 'amigo'
        assert janela.mic_combo.currentData() == 42
        assert janela.saida_combo.currentData() == 7
        assert 'indispon' in janela.mic_combo.currentText().lower()

        # Atualizar a lista sem o aparelho salvo não troca a preferência.
        janela._microfones = [{'indice': 1, 'nome': 'Mic novo', 'api': 'WASAPI'}]
        janela._renderizar_microfones(service.carregar_persona())
        assert janela.mic_combo.currentData() == 42
        assert json.loads(persona.read_text(encoding='utf-8'))['microfone'] == 42
    finally:
        janela.close()


def test_janela_minima_mantem_sidebar_e_sem_rolagem_horizontal(
        app, tmp_path, apis_isoladas):
    janela, service, persona = criar_janela(app, tmp_path)
    janela.resize(700, 460)
    janela.show()
    app.processEvents()
    try:
        assert janela.width() == 700
        assert janela._sidebar.isVisible()
        assert janela._sidebar.geometry().right() < janela.width()
        for indice in (0, 1, 2):
            janela.activate_page(indice)
            app.processEvents()
            pagina = janela._scrolls[indice]
            assert pagina.horizontalScrollBar().maximum() == 0
        # Em janela estreita o cabeçalho encolhe em vez de empurrar o conteúdo.
        assert janela._modo_cabecalho == 'minimo'
        assert not janela._cabecalho_subtitulo.isVisible()
        assert not janela._pilula.isVisible()
        janela.resize(850, 520)
        app.processEvents()
        assert janela._modo_cabecalho == 'compacto'
        assert janela._pilula.isVisible()
        assert janela._pilula.text() == 'CONFIG.'
        janela.resize(1120, 720)
        app.processEvents()
        assert not janela._modo_compacto
        assert janela._cabecalho_subtitulo.isVisible()
        assert janela._pilula.text() == 'CONFIGURAÇÕES'
    finally:
        janela.close()


def test_troca_de_tema_preserva_pagina_foco_e_rolagem(app, tmp_path):
    janela, service, persona = criar_janela(app, tmp_path)
    janela.resize(760, 520)
    janela.show()
    app.processEvents()
    try:
        janela.activate_page('aparencia')
        app.processEvents()
        alvo = janela.theme_cards['claro']
        alvo.setFocus(Qt.FocusReason.OtherFocusReason)
        app.processEvents()
        barra = janela._pagina_aparencia.verticalScrollBar()
        barra.setValue(barra.maximum())
        antes = barra.value()
        assert janela.pagina_atual == 1

        assert janela.escolher_tema('claro') is True
        app.processEvents()
        QTest.qWait(30)
        app.processEvents()

        assert janela.tema == 'claro'
        assert janela.pagina_atual == 1
        assert janela._stack.currentIndex() == 1
        assert QApplication.focusWidget() is alvo
        assert janela._pagina_aparencia.verticalScrollBar().value() == antes
        assert janela.theme_cards['claro'].isChecked()
        assert not janela.theme_cards['escuro'].isChecked()
        assert janela._paleta == PALETAS['claro']
        salvo = json.loads((tmp_path / 'dashboard_config.json').read_text(encoding='utf-8'))
        assert salvo['tema'] == 'claro'
    finally:
        janela.close()


def test_alias_nao_grava_duas_vezes_entre_enter_e_foco(app, tmp_path):
    janela, service, persona = criar_janela(app, tmp_path, host=HostFalso())
    chamadas = []

    def alterar(tipo, chave, **kwargs):
        chamadas.append((tipo, chave))
        time.sleep(0.15)
        return {'salvo': True, 'aplicado': True}

    service.alterar = alterar
    try:
        janela.alias_edit.setText('Zzztestevalido')
        janela._salvar_alias()
        janela._salvar_alias()   # Enter + perda de foco antes da resposta
        QTest.qWait(300)
        app.processEvents()
        assert chamadas == [('apelido', ('sulafat', 'Zzztestevalido'))]
    finally:
        janela.close()


def test_navegacao_por_teclado_na_sidebar_e_nos_temas(app, tmp_path):
    janela, service, persona = criar_janela(app, tmp_path)
    janela.show()
    app.processEvents()
    try:
        primeiro = janela._nav_buttons[0]
        segundo = janela._nav_buttons[1]
        primeiro.setFocus(Qt.FocusReason.OtherFocusReason)
        QTest.keyClick(primeiro, Qt.Key.Key_Down)
        app.processEvents()
        assert janela.pagina_atual == 1
        assert QApplication.focusWidget() is segundo
        assert segundo.isChecked()

        janela.escolher_tema('claro')
        app.processEvents()
        card_claro = janela.theme_cards['claro']
        card_escuro = janela.theme_cards['escuro']
        card_claro.setFocus(Qt.FocusReason.OtherFocusReason)
        QTest.keyClick(card_claro, Qt.Key.Key_Left)
        app.processEvents()
        QTest.qWait(40)
        app.processEvents()
        assert janela.tema == 'escuro'
        assert card_escuro.isChecked()
        assert QApplication.focusWidget() is card_escuro
    finally:
        janela.close()


def test_idle_nao_deixa_animacao_nem_timer_rodando(app, tmp_path):
    janela, service, persona = criar_janela(app, tmp_path)
    janela.show()
    app.processEvents()
    QTest.qWait(250)
    app.processEvents()
    try:
        assert (janela._anim_indicador.state()
                == QAbstractAnimation.State.Stopped)
        assert not [t for t in janela.findChildren(QTimer) if t.isActive()]
    finally:
        janela.close()


def test_preferencias_sobrevivem_a_reabertura(app, tmp_path):
    host = HostFalso()
    janela, service, persona = criar_janela(app, tmp_path, host=host)
    try:
        assert service.alterar('personagem', 'leda')['salvo'] is True
        janela.escolher_tema('claro')
        assert janela.tema == 'claro'
    finally:
        janela.close()

    outra, outro_service, _ = criar_janela(app, tmp_path, host=HostFalso())
    try:
        assert outra.tema == 'claro'
        assert outra.voice_combo.currentData() == 'leda'
        dados = outro_service.carregar_persona()
        assert dados['personagem'] == 'leda'
    finally:
        outra.close()


def test_feedback_salvando_depois_salvo(app, tmp_path):
    host = HostFalso()
    janela, service, persona = criar_janela(app, tmp_path, host=host)
    try:
        janela._alterar('personagem', 'leda', janela.voice_status)
        assert janela.voice_status.text() == 'Salvando…'
        assert esperar(app, lambda: janela.voice_status.text() == 'Salvo')
        assert janela.voice_status.property('estado') == 'success'
    finally:
        janela.close()


def test_feedback_quando_gravou_mas_nao_aplicou(app, tmp_path):
    host = HostFalso(aplicado=False, erro='o motor não respondeu')
    janela, service, persona = criar_janela(app, tmp_path, host=host)
    try:
        janela._alterar('microfone', 1, janela.mic_status)
        assert esperar(app, lambda: 'Salvo, mas' in janela.mic_status.text())
        assert 'o motor não respondeu' in janela.mic_status.text()
        assert 'reabrir a NIA' in janela.mic_status.text()
        assert janela.mic_status.property('estado') == 'warning'
    finally:
        janela.close()


def test_feedback_de_falha_ao_gravar(app, tmp_path):
    janela, service, persona = criar_janela(app, tmp_path, host=HostFalso())
    # Caminho impossível de gravar: a pasta no lugar do arquivo.
    pasta = tmp_path / 'persona_dir'
    pasta.mkdir()
    service.persona_path = pasta
    try:
        janela._alterar('personagem', 'leda', janela.voice_status)
        assert esperar(app, lambda: 'Não foi possível salvar' in janela.voice_status.text())
        assert janela.voice_status.property('estado') == 'error'
        assert 'permissão' in janela.voice_status.text()
    finally:
        janela.close()


def test_resultado_atrasado_de_dispositivo_e_ignorado(app, tmp_path):
    janela, service, persona = criar_janela(app, tmp_path, host=HostFalso())

    def demorado(_indice):
        time.sleep(0.2)
        return {'ok': True, 'blocos': 9, 'nivel': 40.0}

    service.testar_microfone = demorado
    try:
        janela._testar_microfone()
        # Outra escolha/teste invalida a resposta que ainda está a caminho.
        janela._mic_teste_seq += 1
        QTest.qWait(350)
        app.processEvents()
        assert 'blocos' not in janela.mic_status.text()
    finally:
        janela.close()


def test_fechar_durante_trabalho_nao_entrega_resultado(app, tmp_path):
    janela, service, persona = criar_janela(app, tmp_path, host=HostFalso())
    entregues = []

    def demorado(_indice):
        time.sleep(0.2)
        return {'ok': True, 'blocos': 1, 'nivel': 1.0}

    service.testar_microfone = demorado
    janela._executar(lambda: service.testar_microfone(None),
                     lambda resultado: entregues.append(resultado))
    janela.close()
    QTest.qWait(350)
    app.processEvents()
    assert entregues == []


# ── entrada pela engrenagem clássica ───────────────────────────────────────
@pytest.fixture
def janela_principal(app, tmp_path, monkeypatch):
    import ui
    monkeypatch.setattr(ui, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(ui.MainWindow, '_check_config', lambda self: True)
    janela = ui.MainWindow('face.png')
    janela.resize(1100, 760)
    janela.show()
    app.processEvents()
    yield janela
    for timer in janela.findChildren(QTimer):
        timer.stop()
    janela.hide()
    janela.deleteLater()
    app.processEvents()


def test_engrenagem_abre_dashboard_sem_opcao_experimental(
        app, janela_principal, tmp_path, monkeypatch):
    import core.config_preferencias as preferencias
    monkeypatch.setattr(preferencias, 'PERSONA_PADRAO_PATH',
                        tmp_path / 'persona.json')
    monkeypatch.setattr(preferencias, 'DASHBOARD_PADRAO_PATH',
                        tmp_path / 'dashboard_config.json')
    monkeypatch.setattr(preferencias.ConfigService, 'listar_microfones',
                        lambda self: [])
    monkeypatch.setattr(preferencias.ConfigService, 'listar_saidas',
                        lambda self: [])
    botao = janela_principal._build_botao_config()
    assert 'configurações' in botao.toolTip().lower()
    assert 'experimental' not in botao.toolTip().lower()
    try:
        botao.click()
        app.processEvents()
        painel = janela_principal._dashboard_config
        assert painel is not None
        assert painel.pagina_atual == 0
    finally:
        if getattr(janela_principal, '_dashboard_config', None) is not None:
            janela_principal._dashboard_config.close()
        app.processEvents()


def test_engrenagem_abre_dashboard_reaproveita_e_fecha(
        app, janela_principal, tmp_path, monkeypatch):
    import core.config_preferencias as preferencias
    monkeypatch.setattr(preferencias, 'PERSONA_PADRAO_PATH',
                        tmp_path / 'persona.json')
    monkeypatch.setattr(preferencias, 'DASHBOARD_PADRAO_PATH',
                        tmp_path / 'dashboard_config.json')
    monkeypatch.setattr(preferencias.ConfigService, 'listar_microfones',
                        lambda self: [])
    monkeypatch.setattr(preferencias.ConfigService, 'listar_saidas',
                        lambda self: [])
    principal = janela_principal
    botao = principal._build_botao_config()
    assert botao.contextMenuPolicy() != Qt.ContextMenuPolicy.CustomContextMenu

    primeira = principal._abrir_dashboard_config('aparencia')
    try:
        assert primeira is not None
        assert primeira.pagina_atual == 1
        app.processEvents()
        assert principal._abrir_dashboard_config() is primeira
    finally:
        primeira.close()
        app.processEvents()
    assert principal._dashboard_config is None


# ── etapa 2: Provedores e modelos ───────────────────────────────────────────
@pytest.fixture
def apis_isoladas(tmp_path, monkeypatch):
    """Nenhum teste da etapa 2 toca o banco real nem faz rede verdadeira."""
    from core import db_chaves as db, llm_router as lr, llm_client as local
    from core import valida_chave
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'nia.db')
    monkeypatch.setattr(lr, 'CONFIG_PADRAO', tmp_path / 'routing.json')
    monkeypatch.setattr(lr, 'API_CONFIG_PATH', tmp_path / 'api_keys.json')
    monkeypatch.setattr(local, 'CONFIG_PATH', tmp_path / 'api_keys.json')
    monkeypatch.setattr(lr, '_router_global', None)
    monkeypatch.setattr(lr, '_assinatura_global', None)
    monkeypatch.setattr(local, '_MOTOR_CONVERSA', 'nenhuma chamada nesta sessão')
    monkeypatch.setattr(local.requests.sessions.Session, 'request',
                        Mock(side_effect=AssertionError('rede não simulada')))
    monkeypatch.setattr(valida_chave, '_get',
                        Mock(side_effect=AssertionError('rede não simulada')))
    return tmp_path


def test_pagina_provedores_e_sob_demanda_e_tema_preserva_painel(
        app, tmp_path, apis_isoladas):
    janela, _, _ = criar_janela(app, tmp_path)
    try:
        assert janela._painel_provedores is None
        assert 'carregar as APIs' in janela._provedores_placeholder.text()
        janela.activate_page('provedores')
        app.processEvents()
        painel = janela._painel_provedores
        assert painel is not None
        assert janela.pagina_atual == 2
        assert janela._stack.currentIndex() == 2
        assert janela._nav_buttons[2].isChecked()
        assert painel.area_atual == 'apis'
        assert 'APIs externas' in painel._botoes_area['apis'].text()
        assert 'Ollama' in painel._botoes_area['ollama'].text()
        assert janela._provedores_placeholder is None

        janela.activate_page('ollama')
        assert painel.area_atual == 'ollama'
        janela.activate_page('provedores')
        assert painel.area_atual == 'apis'

        assert janela.escolher_tema('claro') is True
        app.processEvents()
        QTest.qWait(30)
        app.processEvents()
        assert janela.tema == 'claro'
        assert janela.pagina_atual == 2
        assert janela._stack.currentWidget() is janela._scrolls[2]
        assert 'QLabel#ApiBadge' in janela.styleSheet()
        assert painel.mostrar_area('ollama') == 'ollama'
    finally:
        janela.close()
    assert painel._fechado is True


def test_pagina_provedores_gerencia_chaves_e_atualiza_roteador(
        app, tmp_path, apis_isoladas, monkeypatch):
    from core import db_chaves as db, llm_router as lr, valida_chave
    from PyQt6.QtWidgets import QLabel, QMessageBox

    janela, _, _ = criar_janela(app, tmp_path)
    janela.activate_page('provedores')
    painel = janela._painel_provedores
    monkeypatch.setattr(painel, '_executar', lambda f, cb: cb(f()))
    monkeypatch.setattr(painel, '_confirmar_indisponibilidade', lambda row: True)
    monkeypatch.setattr(QMessageBox, 'question',
                        lambda *a: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(valida_chave, 'testar', lambda *a: valida_chave.ResultadoValidacao(
        'verificada', 'ok', 200, modelos=('alpha', 'beta'), catalogo_completo=True))
    try:
        painel.provedor.setCurrentIndex(painel.provedor.findData('google'))
        painel.chave.setText('ficticia-segredo')
        painel.apelido.setText('principal')
        painel._salvar()
        linha = db.listar_chaves()[0]
        assert linha['key'] == 'ficticia-segredo'
        assert lr.resolver('gemini') == 'ficticia-segredo'
        textos = [l.text() for l in painel.findChildren(QLabel)]
        assert any('principal' in t for t in textos)
        assert not any('ficticia-segredo' in t for t in textos)

        painel._editar(linha)
        painel.apelido.setText('renomeada')
        painel.chave.clear()
        painel._metadados()
        assert db.listar_chaves()[0]['label'] == 'renomeada'
        assert db.listar_chaves()[0]['key'] == 'ficticia-segredo'

        painel._pausar(db.listar_chaves()[0])
        assert db.listar_chaves()[0]['enabled'] == 0
        painel._pausar(db.listar_chaves()[0])
        assert db.listar_chaves()[0]['enabled'] == 1

        painel._ver_modelos(db.listar_chaves()[0])
        painel.busca_modelos.setText('beta')
        assert painel.modelos_api.count() == 1
        painel._usar_modelo()
        painel._metadados()
        assert db.listar_chaves()[0]['modelo'] == 'beta'

        painel._excluir(db.listar_chaves()[0])
        assert not db.listar_chaves()
        assert lr.resolver('gemini') is None
    finally:
        janela.close()


def test_ollama_estados_distintos_e_preferencia_sobrevive_reabertura(
        app, tmp_path, apis_isoladas, monkeypatch):
    from core import llm_client as local
    import json as _json

    janela, _, _ = criar_janela(app, tmp_path)
    janela.activate_page('ollama')
    painel = janela._painel_provedores
    try:
        painel.url_local.setText('http://localhost:11434')
        local.CONFIG_PATH.write_text(_json.dumps(
            {'llm_model': 'm:8b', 'conversation_provider': 'legado',
             'opcao_antiga': 'preservada'}), encoding='utf-8')

        estados = [
            ({'estado': 'inacessivel', 'modelos': []}, 'inacessível', 'error'),
            ({'estado': 'sem_modelos', 'modelos': []}, 'Nenhum modelo instalado',
             'warning'),
            ({'estado': 'disponivel', 'modelos': ['outro:8b']},
             'não está instalado', 'warning'),
            ({'estado': 'disponivel', 'modelos': ['m:8b', 'outro:8b']},
             'Ollama disponível', 'success'),
        ]
        for estado, esperado, cor in estados:
            monkeypatch.setattr(painel, '_executar', lambda f, cb, e=estado: cb(e))
            painel._descobrir()
            assert esperado in painel.estado_local.text()
            assert painel.estado_local.property('estado') == cor

        local.CONFIG_PATH.write_text(_json.dumps(
            {'llm_model': 'sumido:8b', 'conversation_provider': 'legado',
             'opcao_antiga': 'preservada'}), encoding='utf-8')
        painel._atualizar_estado()
        assert 'Preferência gravada' in painel.preferencia_local.text()
        assert 'motor de conversa' in painel.em_uso_local.text().lower()

        painel.modelos.blockSignals(True)
        painel.modelos.clear()
        painel.modelos.addItem('m:8b')
        painel.modelos.setCurrentIndex(0)
        painel.modelos.blockSignals(False)
        monkeypatch.setattr(painel, '_executar', lambda f, cb: cb(
            {'estado': 'disponivel', 'modelos': ['m:8b']}))
        painel._ativar()
        gravado = _json.loads(local.CONFIG_PATH.read_text(encoding='utf-8'))
        assert gravado['llm_model'] == 'm:8b'
        assert gravado['conversation_provider'] == 'ollama'
        assert gravado['opcao_antiga'] == 'preservada'
        assert 'ativado' in painel.estado_local.text().lower()

        painel2 = type(painel)()
        try:
            painel2._atualizar_estado()
            assert 'm:8b' in painel2.preferencia_local.text()
            assert local.preferencia_conversa() == 'ollama'
        finally:
            painel2.encerrar()
    finally:
        janela.close()


def test_abertura_com_configuracao_legada_preservada(
        app, tmp_path, apis_isoladas):
    from core import llm_router as lr
    from PyQt6.QtWidgets import QLabel

    api = tmp_path / 'api_keys.json'
    api.write_text(json.dumps({
        'gemini_api_key': 'ficticia-legada',
        'conversation_provider': 'legado',
        'opcao_antiga': 7,
    }), encoding='utf-8')
    janela, _, _ = criar_janela(app, tmp_path)
    try:
        janela.activate_page('provedores')
        app.processEvents()
        assert lr.resolver('gemini') == 'ficticia-legada'
        assert janela._painel_provedores is not None
        assert not any('ficticia-legada' in rotulo.text()
                       for rotulo in janela._painel_provedores.findChildren(QLabel))
    finally:
        janela.close()
    assert json.loads(api.read_text(encoding='utf-8')) == {
        'gemini_api_key': 'ficticia-legada',
        'conversation_provider': 'legado',
        'opcao_antiga': 7}


def test_entrada_antiga_abre_pagina_compartilhada(
        app, janela_principal, tmp_path, apis_isoladas, monkeypatch):
    import core.config_preferencias as preferencias
    monkeypatch.setattr(preferencias, 'PERSONA_PADRAO_PATH',
                        tmp_path / 'persona.json')
    monkeypatch.setattr(preferencias, 'DASHBOARD_PADRAO_PATH',
                        tmp_path / 'dashboard_config.json')
    monkeypatch.setattr(preferencias.ConfigService, 'listar_microfones',
                        lambda self: [])
    monkeypatch.setattr(preferencias.ConfigService, 'listar_saidas',
                        lambda self: [])
    primeira = janela_principal._abrir_cadastro_chaves()
    try:
        assert primeira is not None
        assert primeira.pagina_atual == 2
        assert primeira._painel_provedores is not None
        assert primeira._painel_provedores.area_atual == 'apis'
        assert janela_principal._abrir_cadastro_chaves() is primeira
    finally:
        primeira.close()
        app.processEvents()
    assert janela_principal._dashboard_config is None


# ── etapa 3: Geral, Meu perfil, Aparência e Integrações ─────────────────────
def test_geral_grava_saudacao_e_reflete_inicializacao_real(
        app, tmp_path, config_isolada, monkeypatch):
    from core import iniciar_com_sistema as ini

    estado = {"ligado": False, "permissao": True, "motivo": ""}

    def ligar(querer):
        if not estado["permissao"]:
            return False, estado["motivo"] or "sem permissão"
        estado["ligado"] = bool(querer)
        return True, ""

    monkeypatch.setattr(ini, 'disponivel', lambda: True)
    monkeypatch.setattr(ini, 'esta_ligado', lambda: estado["ligado"])
    monkeypatch.setattr(ini, 'ligar', ligar)
    janela, service, _ = criar_janela(app, tmp_path)
    try:
        janela.activate_page('geral')
        assert esperar(app, lambda: 'DESLIGADO' in janela.inicio_botao.text())
        janela.inicio_botao.click()
        assert esperar(app, lambda: 'Salvo' in janela.inicio_status.text())
        assert 'LIGADO' in janela.inicio_botao.text()
        assert estado["ligado"] is True

        saudacao = service.carregar_persona()['saudacao']
        janela.saudacao_botao.click()
        assert esperar(app, lambda: service.carregar_persona()['saudacao'] != saudacao)
        assert 'Salvo' in janela.saudacao_status.text()
    finally:
        janela.close()

    estado["permissao"] = False
    estado["motivo"] = "sem permissão"
    estado["ligado"] = True
    outra, _, _ = criar_janela(app, tmp_path)
    try:
        outra.activate_page('geral')
        assert esperar(app, lambda: 'LIGADO' in outra.inicio_botao.text())
        outra.inicio_botao.click()
        assert esperar(app, lambda: 'Não foi possível' in outra.inicio_status.text())
        # O controle volta ao estadoefetivo consultado depois da falha.
        assert 'LIGADO' in outra.inicio_botao.text()
    finally:
        outra.close()


def test_meu_perfil_grava_enter_e_foco_sem_duplicar(
        app, tmp_path, config_isolada, monkeypatch):
    from core import dono
    chamadas = []
    salvar = dono.salvar

    def contado(dados):
        chamadas.append(dict(dados))
        return salvar(dados)

    monkeypatch.setattr(dono, 'salvar', contado)
    host = HostFalso()
    logs = []
    host.write_log = logs.append
    janela, service, _ = criar_janela(app, tmp_path, host=host)
    try:
        janela.activate_page('perfil')
        campo = janela._perfil_campos['como_chamar']
        campo.setText('Ana')
        QTest.keyClick(campo, Qt.Key.Key_Enter)
        assert esperar(app, lambda: chamadas == [{'como_chamar': 'Ana'}])
        assert esperar(app, lambda: janela._perfil_status['como_chamar'].text() == 'Salvo')
        campo.editingFinished.emit()
        app.processEvents()
        assert chamadas == [{'como_chamar': 'Ana'}]
        assert dono.carregar()['como_chamar'] == 'Ana'
        assert janela._perfil_status['como_chamar'].text() == 'Salvo'
        assert 'Ana' not in janela._perfil_status['como_chamar'].text()
        assert not any('Ana' in linha for linha in logs)
    finally:
        janela.close()


def test_aparencia_cores_nomes_dock_e_previa_sem_audio(
        app, tmp_path, config_isolada, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from core import llm_client, nomes_tela, tema
    from PyQt6.QtCore import QTimer

    host = HostFalso()
    host._win = SimpleNamespace(
        aplicar_tema=Mock(), aplicar_nomes=Mock(), hud=None)
    monkeypatch.setattr(llm_client, 'call_llm',
                        Mock(side_effect=AssertionError('modelo acionado')))
    janela, _, _ = criar_janela(app, tmp_path, host=host)
    try:
        janela.activate_page('aparencia')
        assert len(janela.theme_cards) == 2
        assert janela._previa_timer.isActive()
        janela._botoes_fases['ouvindo'].click()
        assert janela.nucleo_preview.fase == 'ouvindo'
        llm_client.call_llm.assert_not_called()

        janela.activate_page('geral')
        assert not janela._previa_timer.isActive()
        janela.activate_page('aparencia')
        assert janela._previa_timer.isActive()

        janela.cor_combo.setCurrentIndex(
            janela.cor_combo.findData('nucleo_pensando'))
        janela.cor_hex.setText('#123456')
        janela.cor_hex.editingFinished.emit()
        assert tema.escolhida('nucleo_pensando') == '#123456'
        assert host._win.aplicar_tema.call_count == 1

        chave = next(iter(janela._nomes_campos))
        janela._nomes_campos[chave].setText('Nome de teste')
        janela._nomes_campos[chave].editingFinished.emit()
        assert nomes_tela.carregar()[chave] == 'Nome de teste'
        assert host._win.aplicar_nomes.call_count >= 1

        janela.brilho.setValue(120)
        janela.brilho.sliderReleased.emit()
        gravado = json.loads((tmp_path / 'interface.json').read_text(encoding='utf-8'))
        assert gravado['appearance']['brightness'] == 120
        assert 'background_color' in gravado['appearance']

        janela.nucleo_combo.setCurrentIndex(
            janela.nucleo_combo.findData('hexagono'))
        assert json.loads((tmp_path / 'nucleo.json').read_text(encoding='utf-8'))[
            'nucleo'] == 'hexagono'
    finally:
        janela.close()
    assert not janela._previa_timer.isActive()


def test_integracoes_status_secretaria_e_revogacao(
        app, tmp_path, config_isolada, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QMessageBox
    import dashboard.server as server
    from actions import whatsapp_bridge

    principal = SimpleNamespace(
        _open_whatsapp=Mock(), _open_remote=Mock())
    host = HostFalso()
    host._win = principal
    host.on_revoke_devices = Mock(return_value=3)
    monkeypatch.setattr(whatsapp_bridge, 'get_status',
                        lambda: {'connected': True, 'session_saved': True})
    dispositivos = tmp_path / 'remote_devices.json'
    dispositivos.write_text(json.dumps({'devices': {'abc': {}}}), encoding='utf-8')
    monkeypatch.setattr(server, 'REMOTE_SESSIONS_FILE', dispositivos)
    monkeypatch.setattr(QMessageBox, 'question',
                        lambda *a: QMessageBox.StandardButton.Yes)

    janela, _, _ = criar_janela(app, tmp_path, host=host)
    try:
        janela.activate_page('integracoes')
        assert esperar(app, lambda: 'conectado' in janela.whatsapp_estado.text().lower())
        assert '1 dispositivo' in janela.remoto_estado.text()

        janela.whatsapp_botao.click()
        principal._open_whatsapp.assert_called_once()
        janela.remoto_botao.click()
        principal._open_remote.assert_called_once()

        assert janela.mostrar_integracao('secretaria') == 'secretaria'
        assert janela._secretaria_widget is not None
        timers = list(janela._secretaria_widget.findChildren(QTimer))
        assert any(t.isActive() for t in timers)
        janela.activate_page('geral')
        assert not any(t.isActive() for t in timers)

        janela.activate_page('integracoes')
        janela.revogar_botao.click()
        assert esperar(app, lambda: '3 acesso' in janela.integracoes_status.text())
        host.on_revoke_devices.assert_called_once()
    finally:
        janela.close()


def test_mais_opcoes_do_whatsapp_abre_secretaria_no_dashboard(
        app, tmp_path, config_isolada, monkeypatch, apis_isoladas):
    import ui
    import core.config_preferencias as preferencias
    monkeypatch.setattr(preferencias, 'PERSONA_PADRAO_PATH',
                        tmp_path / 'persona.json')
    monkeypatch.setattr(preferencias, 'DASHBOARD_PADRAO_PATH',
                        tmp_path / 'dashboard_config.json')
    monkeypatch.setattr(preferencias.ConfigService, 'listar_microfones',
                        lambda self: [])
    monkeypatch.setattr(preferencias.ConfigService, 'listar_saidas',
                        lambda self: [])
    janela = ui.MainWindow('face.png')
    janela.resize(1100, 760)
    janela.show()
    app.processEvents()
    try:
        from types import SimpleNamespace
        overlay = SimpleNamespace(window=lambda: janela)
        ui.WhatsAppQrOverlay._abrir_opcoes_secretaria(overlay)
        painel = janela._dashboard_config
        assert painel is not None
        assert painel.pagina_atual == 5
        assert painel.mostrar_integracao('secretaria') == 'secretaria'
    finally:
        if getattr(janela, "_dashboard_config", None) is not None:
            janela._dashboard_config.close()
        app.processEvents()
        janela.hide()
        janela.deleteLater()
        app.processEvents()


def test_busca_abre_secao_e_foca_controle(app, tmp_path, config_isolada,
                                          apis_isoladas):
    janela, _, _ = criar_janela(app, tmp_path)
    janela.show()
    app.processEvents()
    try:
        for termo, pagina, controle in (
                ('microfone', 0, 'mic_combo'),
                ('ollama', 2, '_painel_provedores.modelos'),
                ('dock', 1, 'dock_lista')):
            janela.busca_edit.setText(termo)
            janela.busca_edit.returnPressed.emit()
            app.processEvents()
            QTest.qWait(30)
            app.processEvents()
            assert janela.pagina_atual == pagina
            alvo = janela
            for parte in controle.split('.'):
                alvo = getattr(alvo, parte)
            assert alvo.hasFocus()
            assert 'Encontrado' in janela.busca_status.text()

        janela.busca_edit.setText('termo-inexistente')
        janela.busca_edit.returnPressed.emit()
        app.processEvents()
        assert 'Nenhum resultado' in janela.busca_status.text()

        # A navegação por teclado continua valendo depois da busca.
        janela._ir_para_pagina(0)
        primeiro = janela._nav_buttons[0]
        primeiro.setFocus(Qt.FocusReason.OtherFocusReason)
        QTest.keyClick(primeiro, Qt.Key.Key_Down)
        app.processEvents()
        assert janela.pagina_atual == 1
    finally:
        janela.close()


def test_f2_e_reconfiguracao_abrem_provedores_e_atualizam_prontidao(
        app, janela_principal, tmp_path, config_isolada, apis_isoladas,
        monkeypatch):
    import core.config_preferencias as preferencias
    monkeypatch.setattr(preferencias, 'PERSONA_PADRAO_PATH',
                        tmp_path / 'persona.json')
    monkeypatch.setattr(preferencias, 'DASHBOARD_PADRAO_PATH',
                        tmp_path / 'dashboard_config.json')
    monkeypatch.setattr(preferencias.ConfigService, 'listar_microfones',
                        lambda self: [])
    monkeypatch.setattr(preferencias.ConfigService, 'listar_saidas',
                        lambda self: [])
    principal = janela_principal
    principal._ready = True
    try:
        QTest.keyClick(principal, Qt.Key.Key_F2)
        app.processEvents()
        painel = principal._dashboard_config
        assert painel is not None and painel.pagina_atual == 2
        painel.close()
        app.processEvents()

        principal._ready = False
        principal._reconfig_sig.emit()
        app.processEvents()
        painel = principal._dashboard_config
        assert painel is not None and painel.pagina_atual == 2
        assert principal._aguardando_credencial is True
        painel.credencial_pronta.emit()
        app.processEvents()
        assert principal._ready is True
        assert principal._aguardando_credencial is False
    finally:
        if getattr(principal, '_dashboard_config', None) is not None:
            principal._dashboard_config.close()
        app.processEvents()


def test_abertura_e_fechamento_repetidos_nao_duplicam_conexoes(
        app, janela_principal, tmp_path, monkeypatch):
    import core.config_preferencias as preferencias
    monkeypatch.setattr(preferencias, 'PERSONA_PADRAO_PATH',
                        tmp_path / 'persona.json')
    monkeypatch.setattr(preferencias, 'DASHBOARD_PADRAO_PATH',
                        tmp_path / 'dashboard_config.json')
    monkeypatch.setattr(preferencias.ConfigService, 'listar_microfones',
                        lambda self: [])
    monkeypatch.setattr(preferencias.ConfigService, 'listar_saidas',
                        lambda self: [])
    principal = janela_principal
    try:
        for _ in range(3):
            janela = principal._abrir_dashboard_config('geral')
            assert janela.receivers(janela.fechada) == 1
            assert janela.receivers(janela.credencial_pronta) == 1
            assert principal._abrir_dashboard_config('geral') is janela
            janela.close()
            app.processEvents()
            assert principal._dashboard_config is None
    finally:
        if getattr(principal, '_dashboard_config', None) is not None:
            principal._dashboard_config.close()
        app.processEvents()


def test_primeira_execucao_com_config_invalida_continua_funcionando(
        app, janela_principal, tmp_path, monkeypatch):
    import ui
    api = tmp_path / 'api_keys.json'
    monkeypatch.setattr(ui, 'API_FILE', api)
    api.write_text('{invalido', encoding='utf-8')
    janela_principal._show_setup()
    app.processEvents()
    assert janela_principal._overlay is not None
    janela_principal._on_setup_done('', '', 'windows')
    app.processEvents()
    assert janela_principal._ready is True
    # JSON corrompido não impede a recuperação: os dados são reescritos.
    assert json.loads(api.read_text(encoding='utf-8'))['os_system'] == 'windows'


# ── etapa 5: regressões do fluxo normal ─────────────────────────────────────
def test_previa_pausa_ao_minimizar_e_volta_ao_restaurar(
        app, tmp_path, config_isolada, apis_isoladas):
    janela, _, _ = criar_janela(app, tmp_path)
    janela.show()
    app.processEvents()
    try:
        janela.activate_page('aparencia')
        assert janela._previa_timer.isActive()
        janela.showMinimized()
        app.processEvents()
        if janela.isMinimized():
            assert not janela._previa_timer.isActive()
        janela.showNormal()
        app.processEvents()
        assert janela._previa_timer.isActive()
    finally:
        janela.close()
    assert not janela._previa_timer.isActive()


def test_resultado_atrasado_de_inicializacao_e_descartado(
        app, tmp_path, config_isolada, monkeypatch):
    janela, _, _ = criar_janela(app, tmp_path)
    callbacks = []
    monkeypatch.setattr(janela, '_executar', lambda f, cb: callbacks.append(cb) or 1)
    try:
        janela.activate_page('geral')
        janela._consultar_inicio()
        janela._consultar_inicio()
        assert len(callbacks) >= 2
        callbacks[-2]({'disponivel': True, 'ligado': True, 'motivo': ''})
        assert 'LIGADO' not in janela.inicio_botao.text()
        callbacks[-1]({'disponivel': True, 'ligado': False, 'motivo': ''})
        assert 'DESLIGADO' in janela.inicio_botao.text()
    finally:
        janela.close()


def test_resultado_atrasado_de_integracoes_e_descartado_apos_fechar(
        app, tmp_path, config_isolada, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from actions import whatsapp_bridge
    monkeypatch.setattr(whatsapp_bridge, 'get_status', lambda: {'connected': False})

    host = HostFalso()
    host._win = SimpleNamespace()
    janela, _, _ = criar_janela(app, tmp_path, host=host)
    callbacks = []
    monkeypatch.setattr(janela, '_executar', lambda f, cb: callbacks.append(cb) or 1)
    janela.activate_page('integracoes')
    janela._consultar_conexoes()
    janela._consultar_conexoes()
    janela.close()
    app.processEvents()
    for cb in callbacks[-2:]:
        cb({'whatsapp': {'connected': True}, 'remoto': {'dispositivos': 9}})
    assert 'conectado' not in janela.whatsapp_estado.text().lower()


def test_falha_de_gravacao_do_perfil_nao_mostra_salvo(
        app, tmp_path, config_isolada, monkeypatch):
    from unittest.mock import Mock
    from core import dono
    monkeypatch.setattr(dono, 'salvar', Mock(side_effect=OSError('disco cheio')))
    janela, _, _ = criar_janela(app, tmp_path)
    try:
        janela.activate_page('perfil')
        campo = janela._perfil_campos['como_chamar']
        campo.setText('Nome de teste')
        campo.editingFinished.emit()
        status = janela._perfil_status['como_chamar']
        assert esperar(app, lambda: 'Não foi possível salvar' in status.text())
        assert 'Salvo' not in status.text()
    finally:
        janela.close()


def test_falha_ao_aplicar_dock_mantem_gravacao_e_avisa(
        app, tmp_path, config_isolada, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    host = HostFalso()
    host._win = SimpleNamespace(
        _right_panel=SimpleNamespace(
            preferences=SimpleNamespace(data={}),
            apply=Mock(side_effect=RuntimeError('dock fechado'))),
        centralWidget=Mock(side_effect=RuntimeError('janela fechada')))
    janela, _, _ = criar_janela(app, tmp_path, host=host)
    try:
        janela.activate_page('aparencia')
        janela.brilho.setValue(130)
        janela.brilho.sliderReleased.emit()
        texto = janela.interface_status.text()
        assert 'Salvo, mas não foi possível aplicar' in texto
        gravado = json.loads((tmp_path / 'interface.json').read_text(encoding='utf-8'))
        assert gravado['appearance']['brightness'] == 130
    finally:
        janela.close()


def test_secretaria_segue_padroes_visuais_do_dashboard(
        app, tmp_path, config_isolada, apis_isoladas, monkeypatch):
    from PyQt6.QtWidgets import QFrame, QPushButton, QScrollArea
    monkeypatch.setenv('NIA_SECRETARIA_CONFIG', str(tmp_path / 'secretaria.json'))
    janela, _, _ = criar_janela(app, tmp_path)
    try:
        janela.activate_page('integracoes')
        janela.mostrar_integracao('secretaria')
        app.processEvents()
        painel = janela._secretaria_widget
        cartoes = [f for f in painel.findChildren(QFrame)
                   if f.objectName() == 'GlassCard']
        assert len(cartoes) >= 6
        assert not painel.findChildren(QScrollArea)  # sem rolagem dupla
        assert any(b.objectName() == 'Toggle' for b in painel.findChildren(QPushButton))
        assert any(b.objectName() == 'Segment' and b.isCheckable()
                   for b in painel.findChildren(QPushButton))
        codigo = __import__('pathlib').Path('core/secretaria_tela.py').read_text(
            encoding='utf-8')
        inicio = codigo.index('def pagina(janela) -> QWidget:')
        fim = codigo.index('def secao_no_whatsapp', inicio)
        funcao = codigo[inicio:fim]
        assert 'setStyleSheet' not in funcao
        assert '_c(' not in funcao and '_fx(' not in funcao

        janela.escolher_tema('claro' if janela.tema == 'escuro' else 'escuro')
        app.processEvents()
        QTest.qWait(30)
        app.processEvents()
        assert janela.pagina_atual == 5
        assert janela._stack_integracoes.currentWidget() is janela._area_secretaria
    finally:
        janela.close()


def test_secretaria_mantem_acoes_apos_refatoracao_visual(
        app, tmp_path, config_isolada, apis_isoladas, monkeypatch):
    from PyQt6.QtWidgets import QPushButton
    import core.secretaria as SEC
    import core.secretaria_tela as sec_tela
    monkeypatch.setenv('NIA_SECRETARIA_CONFIG', str(tmp_path / 'secretaria.json'))
    monkeypatch.setattr(sec_tela, '_casca', None)
    janela, _, _ = criar_janela(app, tmp_path)
    try:
        janela.activate_page('integracoes')
        janela.mostrar_integracao('secretaria')
        app.processEvents()
        painel = janela._secretaria_widget
        liga = next(b for b in painel.findChildren(QPushButton)
                    if b.accessibleName() == 'Atender ligações')
        liga.click()
        assert SEC.carregar()['ligada'] is True
        assert liga.property('ligado') == 'true'
        liga.click()
        assert SEC.carregar()['ligada'] is False

        segmentos = [b for b in painel.findChildren(QPushButton)
                     if b.objectName() == 'Segment' and b.isCheckable()]
        assert segmentos
        segmentos[-1].click()
        app.processEvents()
        assert len({b.text() for b in segmentos}) > 1
    finally:
        janela.close()


# ── Skill 01: diagnóstico sob demanda ───────────────────────────────────────
def test_diagnostico_painel_abre_sem_rede_e_sem_iniciar_ollama(
        app, tmp_path, apis_isoladas, monkeypatch):
    from unittest.mock import Mock
    from core import llm_client, valida_chave
    monkeypatch.setattr(llm_client.requests.sessions.Session, 'request',
                        Mock(side_effect=AssertionError('rede nao simulada')))
    monkeypatch.setattr(valida_chave, '_get',
                        Mock(side_effect=AssertionError('rede nao simulada')))
    monkeypatch.setattr(llm_client, 'ensure_ollama_running',
                        Mock(side_effect=AssertionError('Ollama iniciado')))
    monkeypatch.setattr(llm_client, '_ULTIMA_RESPOSTA', None)
    janela, _, _ = criar_janela(app, tmp_path)
    try:
        janela.activate_page('provedores')
        painel = janela._painel_provedores
        assert 'Sem resposta registrada nesta sessão' in painel.efetivo.text()
        assert painel.diag_api_botao.isEnabled()
        assert painel.diag_local_botao.isEnabled()
    finally:
        janela.close()


def test_diagnostico_api_externa_com_ollama_ausente(
        app, tmp_path, apis_isoladas, monkeypatch):
    from unittest.mock import Mock
    from core import db_chaves as db, llm_client, valida_chave
    db.adicionar_chave('google', 'ficticia-segredo-1234', 'principal', modelo='m1')
    monkeypatch.setattr(llm_client, 'ensure_ollama_running',
                        Mock(side_effect=AssertionError('Ollama iniciado')))
    janela, _, _ = criar_janela(app, tmp_path)
    try:
        janela.activate_page('provedores')
        painel = janela._painel_provedores
        painel.provedor.setCurrentIndex(painel.provedor.findData('google'))
        monkeypatch.setattr(painel, '_executar', lambda f, cb: cb(f()))
        monkeypatch.setattr(valida_chave, 'testar', lambda *a:
                            valida_chave.ResultadoValidacao(
                                'verificada', 'ok', 200, modelos=('m1',),
                                catalogo_completo=True))
        painel.diag_api_botao.click()
        texto = painel.diag_api_status.text()
        assert 'Verificação concluída' in texto
        assert 'ficticia-segredo-1234' not in texto
        assert painel.diag_api_status.property('estado') == 'success'
        assert painel.diag_api_botao.isEnabled()
    finally:
        janela.close()


@pytest.mark.parametrize('resultado,trecho,estado', [
    (None, 'Verificação inconclusiva', 'warning'),
    (__import__('core.valida_chave', fromlist=['ResultadoValidacao'])
     .ResultadoValidacao('rede', 'rede'), 'Falha de conexão', 'error'),
    (__import__('core.valida_chave', fromlist=['ResultadoValidacao'])
     .ResultadoValidacao('recusada', 'recusada'), 'Credencial recusada', 'error'),
    (__import__('core.valida_chave', fromlist=['ResultadoValidacao'])
     .ResultadoValidacao('cota', 'cota'), 'Limite de requisições', 'warning'),
    (__import__('core.valida_chave', fromlist=['ResultadoValidacao'])
     .ResultadoValidacao('modelo', 'modelo', 404), 'Modelo indisponível', 'warning'),
])
def test_diagnostico_api_classifica_por_evidencia(
        app, tmp_path, apis_isoladas, monkeypatch, resultado, trecho, estado):
    from core import db_chaves as db, valida_chave
    db.adicionar_chave('google', 'ficticia-chave', 'conta', modelo='m1')
    janela, _, _ = criar_janela(app, tmp_path)
    try:
        janela.activate_page('provedores')
        painel = janela._painel_provedores
        painel.provedor.setCurrentIndex(painel.provedor.findData('google'))
        monkeypatch.setattr(painel, '_executar', lambda f, cb: cb(f()))
        monkeypatch.setattr(valida_chave, 'testar', lambda *a: resultado)
        painel.diag_api_botao.click()
        assert trecho in painel.diag_api_status.text()
        assert painel.diag_api_status.property('estado') == estado
        assert 'ficticia-chave' not in painel.diag_api_status.text()
    finally:
        janela.close()


def test_diagnostico_descarta_resultado_quando_alvo_muda(
        app, tmp_path, apis_isoladas, monkeypatch):
    from core import db_chaves as db, valida_chave
    db.adicionar_chave('google', 'ficticia-antiga', modelo='antigo')
    janela, _, _ = criar_janela(app, tmp_path)
    try:
        janela.activate_page('provedores')
        painel = janela._painel_provedores
        painel.provedor.setCurrentIndex(painel.provedor.findData('google'))
        callbacks = []
        monkeypatch.setattr(painel, '_executar',
                            lambda f, cb: callbacks.append(cb) or 1)
        painel.diag_api_botao.click()
        assert not painel.diag_api_botao.isEnabled()
        painel.provedor.setCurrentIndex(painel.provedor.findData('openai'))
        callbacks[0](valida_chave.ResultadoValidacao('verificada', 'ok'))
        app.processEvents()
        texto = painel.diag_api_status.text()
        assert 'descartado' in texto
        assert 'Verificação concluída' not in texto
        assert painel.diag_api_botao.isEnabled()
    finally:
        janela.close()


def test_diagnostico_ollama_estados_e_geracao_sem_iniciar_servico(
        app, tmp_path, apis_isoladas, monkeypatch):
    from unittest.mock import Mock
    from core import llm_client
    monkeypatch.setattr(llm_client, 'ensure_ollama_running',
                        Mock(side_effect=AssertionError('Ollama iniciado')))
    janela, _, _ = criar_janela(app, tmp_path)
    try:
        janela.activate_page('provedores')
        painel = janela._painel_provedores
        painel.mostrar_area('ollama')
        painel.modelos.addItem('m:8b')
        painel.modelos.setCurrentIndex(0)
        monkeypatch.setattr(painel, '_executar', lambda f, cb: cb(f()))
        cenarios = [
            ({'estado': 'inacessivel', 'modelos': []}, 'Serviço inacessível', 'error'),
            ({'estado': 'sem_modelos', 'modelos': []}, 'nenhum modelo', 'warning'),
            ({'estado': 'disponivel', 'modelos': ['outro:8b']}, 'não está instalado', 'warning'),
            ({'estado': 'disponivel', 'modelos': ['m:8b']}, 'encontrados', 'success'),
        ]
        for estado, esperado, cor in cenarios:
            monkeypatch.setattr(llm_client, 'descobrir_modelos', lambda url, e=estado: e)
            painel.diag_local_botao.click()
            assert esperado in painel.diag_local_status.text()
            assert painel.diag_local_status.property('estado') == cor

        monkeypatch.setattr(llm_client, 'testar_geracao_ollama',
                            lambda modelo, url: {'estado': 'ok', 'modelo': modelo})
        painel.diag_local_gerar.click()
        assert 'Geração concluída' in painel.diag_local_status.text()
        assert 'm:8b' in painel.diag_local_status.text()
    finally:
        janela.close()


def test_diagnostico_mostra_motivo_da_escolha(app, tmp_path, apis_isoladas,
                                              monkeypatch):
    from core import llm_client as local
    monkeypatch.setattr(local, '_ULTIMA_RESPOSTA', None)
    local.registrar_resposta_conversa(
        'gemini', 'modelo-real', 'Modelo configurado nas preferências')
    janela, _, _ = criar_janela(app, tmp_path)
    try:
        janela.activate_page('provedores')
        painel = janela._painel_provedores
        texto = painel.efetivo.text()
        assert 'Última resposta da conversa: gemini · modelo-real' in texto
        assert 'Motivo da escolha: Modelo configurado nas preferências' in texto
        assert 'Modelo configurado:' in texto
    finally:
        janela.close()


def test_diagnostico_manual_nao_substitui_ultima_resposta_da_conversa(
        app, tmp_path, apis_isoladas, monkeypatch):
    from core import db_chaves as db, llm_client, valida_chave
    monkeypatch.setattr(llm_client, '_ULTIMA_RESPOSTA', None)
    db.adicionar_chave('google', 'ficticia-chave', modelo='m1')
    janela, _, _ = criar_janela(app, tmp_path)
    try:
        janela.activate_page('provedores')
        painel = janela._painel_provedores
        painel.provedor.setCurrentIndex(painel.provedor.findData('google'))
        llm_client.registrar_resposta_conversa('gemini', 'modelo-real')
        painel._atualizar_estado()
        assert 'Última resposta da conversa: gemini · modelo-real' in painel.efetivo.text()

        monkeypatch.setattr(painel, '_executar', lambda f, cb: cb(f()))
        monkeypatch.setattr(valida_chave, 'testar', lambda *a:
                            valida_chave.ResultadoValidacao('verificada', 'ok'))
        painel.diag_api_botao.click()
        texto = painel.efetivo.text()
        assert 'modelo-real' in texto
        assert 'Diagnóstico manual:' in texto
        assert 'ficticia-chave' not in texto
    finally:
        janela.close()


def test_pagina_documentos_indexa_e_busca_sem_rede(
        app, tmp_path, config_isolada, apis_isoladas, monkeypatch):
    from unittest.mock import Mock
    from PyQt6.QtWidgets import QFileDialog
    from core import llm_client, valida_chave
    documentos = tmp_path / 'docs'
    documentos.mkdir()
    (documentos / 'info.TXT').write_text(
        'A secretária anotou um recado importante.', encoding='utf-8')
    monkeypatch.setenv('NIA_INDICE_DB', str(tmp_path / 'indice.db'))
    monkeypatch.setattr(llm_client.requests.sessions.Session, 'request',
                        Mock(side_effect=AssertionError('rede')))
    monkeypatch.setattr(valida_chave, '_get',
                        Mock(side_effect=AssertionError('rede')))
    monkeypatch.setattr(llm_client, 'ensure_ollama_running',
                        Mock(side_effect=AssertionError('Ollama iniciado')))
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory',
                        lambda *a, **k: str(documentos))

    janela, service, _ = criar_janela(app, tmp_path)
    try:
        janela.activate_page('documentos')
        assert janela.pagina_atual == 6
        assert '0 documento(s)' in janela.indice_contagem.text()
        janela._adicionar_fonte_indice()
        assert service.carregar_fontes_indice() == [str(documentos)]

        janela._executar = lambda f, cb: cb(f())
        janela.indice_atualizar.click()
        assert '1 atualizado(s)' in janela.indice_status.text()
        assert '1 documento(s)' in janela.indice_contagem.text()
        janela.busca_local_edit.setText('recado importante')
        janela.busca_local_botao.click()
        assert janela.busca_local_resultados.count() == 1
        assert 'info.txt' in janela.busca_local_resultados.item(0).text().lower()
        assert 'recado' in janela.busca_local_resultados.item(0).text().lower()
        llm_client.ensure_ollama_running.assert_not_called()
    finally:
        janela.close()


def test_rotinas_no_dashboard_persistem_e_executam(
        app, tmp_path, config_isolada, apis_isoladas, monkeypatch):
    from core import rotinas as R
    monkeypatch.setenv('NIA_ROTINAS_DB', str(tmp_path / 'rotinas.db'))
    notificacoes = []
    monkeypatch.setattr(R.Agendador, '_notificar',
                        lambda self, msg: (notificacoes.append(msg), (True, ''))[1])

    janela, _, _ = criar_janela(app, tmp_path)
    try:
        janela._executar = lambda f, cb: cb(f())
        janela.activate_page('geral')
        janela.rotina_titulo.setText('Beber água')
        janela.rotina_mensagem.setText('Hora de beber água')
        janela.rotina_repeticao.setCurrentIndex(
            janela.rotina_repeticao.findData('diaria'))
        janela.rotina_salvar.click()
        assert 'Salvo' in janela.rotinas_status.text()
        assert janela.rotinas_lista.count() == 1

        armazem = R.ArmazemRotinas(db_path=tmp_path / 'rotinas.db')
        itens = armazem.listar()
        assert itens[0]['titulo'] == 'Beber água'
        assert itens[0]['proxima_execucao']

        janela.rotinas_lista.setCurrentRow(0)
        janela.rotina_pausar.click()
        assert armazem.obter(itens[0]['id'])['estado'] == 'pausado'
        janela.rotina_pausar.click()
        assert armazem.obter(itens[0]['id'])['estado'] == 'ativo'

        janela.rotina_agora.click()
        assert notificacoes == ['Hora de beber água']
        assert janela.rotinas_historico.count() == 1
        assert 'ok' in janela.rotinas_historico.item(0).text()
    finally:
        janela.close()


def test_rotina_resumo_gera_e_atualiza_cartao(
        app, tmp_path, config_isolada, apis_isoladas, monkeypatch):
    from core import resumo_dia as RD
    from core import rotinas as R
    monkeypatch.setenv('NIA_ROTINAS_DB', str(tmp_path / 'rotinas.db'))
    chamadas = []
    monkeypatch.setattr(RD, 'gerar_e_salvar', lambda: chamadas.append(True) or {
        'ok': True, 'salvo': True, 'texto': 'Resumo local',
        'gerado_em': '2027-05-10T08:00:00+00:00'})

    host = HostFalso()
    host.atualizar_hoje = Mock()
    janela, _, _ = criar_janela(app, tmp_path, host=host)
    try:
        janela._executar = lambda f, cb: cb(f())
        janela.activate_page('geral')
        janela.rotina_titulo.setText('Resumo diário')
        janela.rotina_acao.setCurrentIndex(
            janela.rotina_acao.findData('resumo'))
        janela.rotina_repeticao.setCurrentIndex(
            janela.rotina_repeticao.findData('dias_uteis'))
        janela.rotina_salvar.click()
        armazem = R.ArmazemRotinas(db_path=tmp_path / 'rotinas.db')
        rotina = armazem.listar()[0]
        assert rotina['acao'] == 'resumo'
        assert rotina['repeticao'] == 'dias_uteis'

        janela.rotinas_lista.setCurrentRow(0)
        antes = rotina['proxima_execucao']
        janela.rotina_agora.click()
        assert chamadas == [True]
        assert armazem.obter(rotina['id'])['proxima_execucao'] == antes
        assert host.atualizar_hoje.called
    finally:
        janela.close()


def test_preferencia_do_cartao_hoje_usa_interface_json(tmp_path):
    servico = criar_service(tmp_path)
    assert servico.hoje_visivel() is True
    servico.salvar_hoje_visivel(False)
    dados = json.loads((tmp_path / 'interface.json').read_text(encoding='utf-8'))
    assert dados['cards']['hoje'] is False
    assert criar_service(tmp_path).hoje_visivel() is False


def test_pagina_habilidades_mostra_catalogo_e_aciona_executor_unico(
        app, tmp_path, monkeypatch):
    from core import catalogo_habilidades as CH
    from core.catalogo_habilidades import Disponibilidade
    monkeypatch.setattr(CH, 'disponibilidade',
                        lambda ident: Disponibilidade(True, 'Pronta para teste.'))
    chamadas = []
    monkeypatch.setattr(CH, '_EXECUTOR',
                        lambda ident, termo: chamadas.append((ident, termo)) or
                        (True, 'Ação concluída'))
    janela, _, _ = criar_janela(app, tmp_path)
    try:
        janela.activate_page('habilidades')
        app.processEvents()
        assert janela.pagina_atual == 7
        assert janela._nav_buttons[7].isChecked()
        assert 'habilidades' in janela._paginas_lazy
        textos = [l.text() for l in janela.habilidades_lista.findChildren(QLabel)]
        for habilidade in CH.todas():
            assert any(habilidade.nome in t for t in textos)
            assert any(habilidade.exemplo in t for t in textos)
            assert habilidade.id in janela.habilidades_botoes

        janela.habilidades_botoes['resumo_dia'].click()
        app.processEvents()
        assert chamadas == [('resumo_dia', '')]
        assert 'Ação concluída' in janela.habilidades_status['resumo_dia'].text()
    finally:
        janela.close()


def test_habilidade_indisponível_oferece_configuracao(
        app, tmp_path, monkeypatch):
    from core import catalogo_habilidades as CH
    from core.catalogo_habilidades import Disponibilidade
    monkeypatch.setattr(CH, 'disponibilidade', lambda ident: Disponibilidade(
        False, 'Configure as fontes em Configurações → Documentos.'))
    janela, _, _ = criar_janela(app, tmp_path)
    try:
        janela.activate_page('habilidades')
        app.processEvents()
        botao = janela.habilidades_botoes['buscar_arquivos']
        assert botao.text() == 'Abrir configuração'
        assert 'Configure as fontes' in janela.habilidades_status[
            'buscar_arquivos'].text()
    finally:
        janela.close()


def test_busca_e_teclado_alcancam_pagina_habilidades(app, tmp_path, monkeypatch):
    from core import catalogo_habilidades as CH
    from core.catalogo_habilidades import Disponibilidade
    monkeypatch.setattr(CH, 'disponibilidade',
                        lambda ident: Disponibilidade(True, 'Pronta.'))
    janela, _, _ = criar_janela(app, tmp_path)
    janela.show()
    app.processEvents()
    try:
        janela.activate_page('documentos')
        app.processEvents()
        janela._nav_buttons[6].setFocus(Qt.FocusReason.OtherFocusReason)
        QTest.keyClick(janela._nav_buttons[6], Qt.Key.Key_Down)
        app.processEvents()
        assert janela.pagina_atual == 7
        janela.busca_edit.setText('habilidades')
        janela.busca_edit.returnPressed.emit()
        app.processEvents()
        QTest.qWait(30)
        app.processEvents()
        assert janela.pagina_atual == 7
        assert 'Encontrado: Habilidades nativas' in janela.busca_status.text()
    finally:
        janela.close()


def test_abrir_habilidades_offline_sem_rede_inferencia_ou_indexacao(
        app, tmp_path, monkeypatch):
    import requests
    from core import catalogo_habilidades as CH
    from core import indice_local, llm_client, secretaria
    from core.config_preferencias import ConfigService

    def proibido(*args, **kwargs):
        pytest.fail('abrir o catálogo não deve acessar rede, modelo ou índice')

    monkeypatch.setattr(requests, 'get', proibido)
    monkeypatch.setattr(requests, 'post', proibido)
    monkeypatch.setattr(llm_client, 'call_llm', proibido)
    monkeypatch.setattr(llm_client, 'call_llm_stream', proibido)
    monkeypatch.setattr(indice_local.IndiceLocal, 'atualizar', proibido)
    monkeypatch.setattr(indice_local.IndiceLocal, 'reconstruir', proibido)
    monkeypatch.setattr(ConfigService, 'carregar_fontes_indice',
                        lambda self: [str(tmp_path)])
    monkeypatch.setattr(secretaria, 'carregar', lambda: {'ligada': True})

    janela, _, _ = criar_janela(app, tmp_path)
    try:
        janela.activate_page('habilidades')
        app.processEvents()
        for estado in janela.habilidades_status.values():
            assert estado.property('estado') == 'success'
        exemplo = CH.todas()[0].exemplo
        botao = next(b for b in janela.habilidades_lista.findChildren(QPushButton)
                     if b.accessibleName().startswith('Copiar exemplo'))
        botao.click()
        app.processEvents()
        assert QApplication.clipboard().text() == exemplo
    finally:
        janela.close()


def test_busca_por_secretaria_foca_controle_do_painel(
        app, tmp_path, config_isolada, apis_isoladas):
    janela, _, _ = criar_janela(app, tmp_path)
    janela.show()
    app.processEvents()
    try:
        janela.busca_edit.setText('secretaria')
        janela.busca_edit.returnPressed.emit()
        app.processEvents()
        QTest.qWait(30)
        app.processEvents()
        assert janela.pagina_atual == 5
        assert janela._secretaria_widget is not None
        foco = QApplication.focusWidget()
        assert foco is not None and janela._secretaria_widget.isAncestorOf(foco)
    finally:
        janela.close()
