"""Skill 08: validação integrada com clientes simulados e perfis temporários."""
import json
import os
import queue
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

import main
from core import busca_fontes as BF
from core import llm_client


@pytest.fixture(scope='module')
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _falsa(**extras):
    base = dict(
        ui=SimpleNamespace(muted=False, write_log=Mock(), set_state=Mock()),
        _interrupted=False, _turno_seq=1, _is_speaking=False,
        _speaking_lock=threading.Lock(), _GUARDA_POS_FALA_S=0.2,
        _mic_fechado_ate=0.0, _turn_done_event=Mock(),
        audio_in_queue=queue.Queue(), _falar_local=Mock(return_value=True),
        _voz_local=SimpleNamespace(voz='__gemini__'),
    )
    base.update(extras)
    nia = SimpleNamespace(**base)
    for nome in ('_falar_resumo', 'set_speaking', 'interrupt',
                 '_oferecer_sintese', '_tratar_confirmacao_sintese',
                 '_on_text_command', '_fala_para_servicos_locais'):
        setattr(nia, nome, getattr(main.NiaLive, nome).__get__(nia, main.NiaLive))
    return nia


# ── perfis novo e antigo ───────────────────────────────────────────────────
def test_perfil_antigo_e_novo_preservam_preferencias(tmp_path, monkeypatch):
    antigo = tmp_path / 'antigo'
    antigo.mkdir()
    (antigo / 'api_keys.json').write_text(json.dumps({
        'llm_provider': 'ollama', 'llm_url': 'http://localhost:11434',
        'llm_model': 'llama3.2', 'conversation_provider': 'ollama',
        'campo_futuro': 'preservado',
    }), encoding='utf-8')
    monkeypatch.setattr(llm_client, 'CONFIG_PATH', antigo / 'api_keys.json')
    assert llm_client.preferencia_conversa() == 'ollama'
    assert llm_client.get_llm_settings() == ('http://localhost:11434', 'llama3.2')

    novo = tmp_path / 'novo'
    novo.mkdir()
    (novo / 'api_keys.json').write_text('{}', encoding='utf-8')
    monkeypatch.setattr(llm_client, 'CONFIG_PATH', novo / 'api_keys.json')
    assert llm_client.preferencia_conversa() == 'legado'
    llm_client.salvar_config_local({'conversation_provider': 'legado'})
    dados = json.loads((novo / 'api_keys.json').read_text(encoding='utf-8'))
    assert dados['conversation_provider'] == 'legado'

    from core.config_preferencias import ConfigService
    servico = ConfigService(
        dashboard_path=antigo / 'dashboard.json',
        interface_path=antigo / 'interface.json',
        persona_path=antigo / 'persona.json')
    (antigo / 'dashboard.json').write_text(json.dumps({
        'tema': 'claro', 'indice_fontes': ['documentos'],
    }), encoding='utf-8')
    servico.salvar_hoje_visivel(False)
    preservado = json.loads((antigo / 'dashboard.json').read_text(encoding='utf-8'))
    assert preservado['tema'] == 'claro'
    assert preservado['indice_fontes'] == ['documentos']
    assert servico.carregar_tema() == 'claro'
    assert servico.hoje_visivel() is False


def test_interface_responde_com_trabalho_lento(app, tmp_path):
    from core.config_dashboard import TaskRunner
    runner = TaskRunner()
    liberar = threading.Event()
    recebido = []
    runner.bridge.terminou.connect(lambda token, valor: recebido.append((token, valor)))
    try:
        def lento():
            liberar.wait(2)
            return 'concluido'
        runner.executar(lento)
        assert not recebido
        app.processEvents()
        assert not recebido
        liberar.set()
        fim = time.monotonic() + 2
        while time.monotonic() < fim and not recebido:
            app.processEvents()
            time.sleep(0.01)
        assert recebido and recebido[0][1] == 'concluido'
    finally:
        liberar.set()
        runner.encerrar()


# ── regressões de integração encontradas na auditoria final ────────────────
def test_sim_apos_avanco_de_turno_nao_perde_a_sintese(monkeypatch):
    nia = _falsa()
    nia._turno_seq = 1
    nia._pendente_sintese = {
        'pergunta': 'garantia', 'fontes': [], 'destino': {'assinatura': 'x'},
        'assinatura': 'x', 'seq': 1, 'origem': 'texto', 'em': time.time(),
    }
    monkeypatch.setattr(main, '_SEGUNDO_PLANO', threading.Event())
    monkeypatch.setattr(BF, 'destino_atual', lambda: {'assinatura': 'x'})
    execucao = Mock()
    monkeypatch.setattr(nia, '_executar_sintese', execucao, raising=False)

    nia._on_text_command('sim')
    assert execucao.called
    assert execucao.call_args.args[0]['seq'] == nia._turno_seq == 2
    assert nia._pendente_sintese is None


def test_porta_de_ativacao_vale_para_servicos_locais():
    nia = _falsa()
    nia._passa_pelo_nome = lambda texto: (False, texto)
    assert nia._fala_para_servicos_locais('abra a Secretaria')[0] is False
    nia._passa_pelo_nome = lambda texto: (True, '')
    assert nia._fala_para_servicos_locais('NIA.')[0] is False
    nia._passa_pelo_nome = lambda texto: (True, 'abra a Secretaria')
    assert nia._fala_para_servicos_locais('NIA, abra a Secretaria') == (
        True, 'abra a Secretaria')


# ── voz do resumo e cancelamento ───────────────────────────────────────────
def test_leitura_do_resumo_respeita_autorizacao_e_mantem_texto(monkeypatch):
    from core.config_preferencias import ConfigService
    nia = _falsa()
    monkeypatch.setattr(ConfigService, 'resumo_voz_externa', lambda self: False)
    assert nia._falar_resumo('Resumo local') is False
    assert not nia._falar_local.called
    assert any('resumo disponível no card' in c.args[0]
               for c in nia.ui.write_log.call_args_list)

    monkeypatch.setattr(ConfigService, 'resumo_voz_externa', lambda self: True)
    assert nia._falar_resumo('Resumo local') is True
    nia._falar_local.assert_called_once_with('Resumo local')

    nia._falar_local.side_effect = RuntimeError('sem áudio')
    assert nia._falar_resumo('Resumo local') is False
    assert any('voz indisponível' in c.args[0]
               for c in nia.ui.write_log.call_args_list)


def test_interromper_drena_audio_e_invalida_turno():
    nia = _falsa()
    for _ in range(3):
        nia.audio_in_queue.put(b'chunk')
    nia._is_speaking = True
    nia._mic_fechado_ate = 999.0
    before = nia._turno_seq
    nia.interrupt()
    assert nia.audio_in_queue.empty()
    assert nia._interrupted is True
    assert nia._turno_seq == before + 1
    assert nia._mic_fechado_ate == 0.0
    assert nia._is_speaking is False
    nia._turn_done_event.clear.assert_called_once_with()


# ── streaming e recuperação de transporte ──────────────────────────────────
class _RespStream:
    def __init__(self, linhas):
        self._linhas = linhas

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        return None

    def iter_lines(self):
        yield from self._linhas


def _linhas_stream():
    for texto in ('Bom dia. ', 'Tudo pronto.'):
        yield json.dumps({'message': {'content': texto}}).encode()
    yield json.dumps({'message': {'content': ''}, 'done': True}).encode()


def test_stream_emite_frases_e_nao_reinicia_ollama_sem_falha(monkeypatch):
    monkeypatch.setattr(llm_client, 'get_llm_provider', lambda: 'ollama')
    monkeypatch.setattr(llm_client, 'get_llm_settings',
                        lambda: ('http://localhost:11434', 'modelo'))
    posta = Mock(return_value=_RespStream(_linhas_stream()))
    monkeypatch.setattr(llm_client.requests, 'post', posta)
    reiniciar = Mock(return_value=False)
    monkeypatch.setattr(llm_client, 'ensure_ollama_running', reiniciar)

    eventos = list(llm_client.call_llm_stream([{'role': 'user', 'content': 'oi'}]))
    frases = [e['text'] for e in eventos if e['type'] == 'sentence']
    assert frases == ['Bom dia.', 'Tudo pronto.']
    assert eventos[-1]['type'] == 'done'
    assert posta.call_count == 1
    assert not reiniciar.called


def test_call_llm_reinicia_uma_vez_e_registra_modelo_que_respondeu(monkeypatch):
    monkeypatch.setattr(llm_client, 'get_llm_provider', lambda: 'ollama')
    monkeypatch.setattr(llm_client, 'get_llm_settings',
                        lambda: ('http://localhost:11434', 'modelo-local'))
    resposta = Mock()
    resposta.raise_for_status.return_value = None
    resposta.json.return_value = {'message': {'content': 'pronto'}}
    posta = Mock(side_effect=[llm_client.requests.exceptions.ConnectionError(), resposta])
    monkeypatch.setattr(llm_client.requests, 'post', posta)
    reiniciar = Mock(return_value=True)
    monkeypatch.setattr(llm_client, 'ensure_ollama_running', reiniciar)
    monkeypatch.setattr(llm_client, '_ULTIMA_RESPOSTA', None)

    resultado = llm_client.call_llm([{'role': 'user', 'content': 'oi'}])
    assert resultado['content'] == 'pronto'
    assert posta.call_count == 2
    reiniciar.assert_called_once_with()
    real = llm_client.ultima_resposta_conversa()
    assert real['provedor'] == 'ollama' and real['modelo'] == 'modelo-local'


# ── autorização de síntese e resultados atrasados ──────────────────────────
def test_autorizacao_de_sintese_expira_e_local_nao_pede_sim(monkeypatch):
    nia = _falsa()
    nia._pendente_sintese = {'em': time.time() - 181, 'assinatura': 'x'}
    monkeypatch.setattr(BF, 'destino_atual', lambda: {'assinatura': 'x'})
    sintetizar = Mock()
    monkeypatch.setattr(BF, 'sintetizar', sintetizar)
    assert nia._tratar_confirmacao_sintese('sim') is False
    assert nia._pendente_sintese is None
    assert not sintetizar.called

    monkeypatch.setattr(BF, 'destino_atual',
                        lambda: {'local': True, 'assinatura': 'local'})
    monkeypatch.setattr(BF, 'contexto_minimo', lambda *a, **k: 'DADOS')
    execucao = Mock()
    monkeypatch.setattr(nia, '_executar_sintese', execucao, raising=False)
    nia._oferecer_sintese(SimpleNamespace(consulta='garantia'), [], 1, 'texto')
    assert nia._pendente_sintese is None
    execucao.assert_called_once()
    assert not any('Responda SIM' in c.args[0]
                   for c in nia.ui.write_log.call_args_list)
