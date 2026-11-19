"""Regressão offline: nunca abre dados reais nem consulta provedores."""
import ast
import asyncio
import json
import os
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
# Evita inclusive a migração automática de banco durante a importação.
os.environ['NIA_DB_PATH'] = str(Path(__file__).parent / 'nao_utilizado.db')
from core import db_chaves as db, llm_router as lr, llm_client as local, valida_chave as validacao
from core.cerebro_generico import CerebroGenerico
from core.cerebro_openrouter import CerebroOpenRouter


@pytest.fixture(autouse=True)
def isolado(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'nia.db')
    monkeypatch.setattr(lr, 'CONFIG_PADRAO', tmp_path / 'routing.json')
    monkeypatch.setattr(lr, 'API_CONFIG_PATH', tmp_path / 'api_keys.json')
    monkeypatch.setattr(local, 'CONFIG_PATH', tmp_path / 'api_keys.json')
    monkeypatch.setattr(lr, '_router_global', None)
    monkeypatch.setattr(lr, '_assinatura_global', None)
    monkeypatch.setattr(local, '_MOTOR_CONVERSA', 'nenhuma chamada nesta sessão')
    import core.cerebro_generico as cg
    monkeypatch.setattr(cg, '_FALHAS_MODELO', {})
    # Falha imediata se algum teste deixar escapar acesso à rede.
    monkeypatch.setattr(local.requests.sessions.Session, 'request', Mock(side_effect=AssertionError('rede não simulada')))
    monkeypatch.setattr(validacao, '_get', Mock(side_effect=RuntimeError('rede simulada fora')))
    yield


def config(**dados):
    local.CONFIG_PATH.write_text(json.dumps(dados), encoding='utf-8')


def registro(chave_id):
    return next(r for r in db.listar_chaves() if r['id'] == chave_id)


def test_alias_duplicata_preserva_metadados():
    i = db.adicionar_chave('google', 'ficticia-1', 'principal', 'modelo', 'https://a.invalid/v1')
    assert db.adicionar_chave('gemini', 'ficticia-1', 'outro') is None
    assert registro(i)['label'] == 'principal'
    assert len(db.listar_chaves('google')) == 1
    assert registro(i)['platform'] == 'gemini'


def test_migracao_aditiva_repetivel(tmp_path):
    with sqlite3.connect(db.DB_PATH) as con:
        con.execute('CREATE TABLE api_keys (id INTEGER PRIMARY KEY, platform TEXT, label TEXT, key TEXT, '
                    'status TEXT, enabled INTEGER, falhas INTEGER, sucessos INTEGER, uso_tokens INTEGER, '
                    'cooldown_ate REAL, created_at TEXT)')
        con.execute("INSERT INTO api_keys VALUES (17,'google','antiga','ficticia','ativo',1,2,3,40,0,'ontem')")
    a, b = db.listar_chaves(), db.listar_chaves()
    assert a == b
    assert a[0]['id'] == 17 and a[0]['uso_tokens'] == 40 and a[0]['label'] == 'antiga'
    assert lr.resolver('gemini') == 'ficticia'


def test_pausa_exclusao_reinicio_recadastro_bloqueiam_json():
    config(gemini_api_key='ficticia')
    lr.CONFIG_PADRAO.write_text(json.dumps({'router': {'provedores': {'google': {'chaves': ['ficticia']}}}}))
    i = db.adicionar_chave('google', 'ficticia')
    assert lr.resolver('gemini') == 'ficticia'
    assert db.atualizar_chave(i, 0, enabled=0)
    lr.recarregar()
    assert lr.resolver('gemini') is None
    assert not lr.carregar_router().escolher('google')
    assert db.atualizar_chave(i, 1, enabled=1)
    assert lr.resolver('gemini') == 'ficticia'
    db.remover_chave(i)
    lr._router_global = None
    assert lr.resolver('gemini') is None
    assert lr.proxima_chave('gemini') is None
    with sqlite3.connect(db.DB_PATH) as con:
        dados = con.execute('SELECT * FROM credenciais_bloqueadas').fetchall()
    assert dados and all('ficticia' not in str(r) for r in dados)
    assert db.adicionar_chave('gemini', 'ficticia')
    assert lr.resolver('gemini') == 'ficticia'


def test_provedor_desconhecido_nunca_recebe_gemini():
    config(gemini_api_key='ficticia-google')
    assert lr.resolver('groq') is None
    assert lr.resolver('openai') is None


def test_substituicao_atomica_e_resultado_atrasado():
    i = db.adicionar_chave('google', 'ficticia-antiga', 'apelido')
    assert db.atualizar_chave(i, 0, key='ficticia-nova', status='ativo')
    assert not db.atualizar_chave(i, 0, key='ficticia-atrasada')
    assert registro(i)['key'] == 'ficticia-nova'
    assert registro(i)['label'] == 'apelido'
    assert not db.fonte_legada_permitida('gemini', 'ficticia-antiga')
    db.remover_chave(i)
    assert not db.atualizar_chave(i, 1, status='ativo')


def test_falha_atrasada_nao_castiga_substituta():
    i = db.adicionar_chave('google', 'ficticia-antiga')
    antigo = lr.carregar_router().escolher('gemini')[1]
    db.atualizar_chave(i, 0, key='ficticia-nova', status='ativo')
    lr.KeyPool().registrar_falha(antigo, lr.T_QUOTA)
    assert registro(i)['status'] == 'ativo'
    assert lr.anotar_falha('gemini', '429', 'ficticia-antiga') is None


def test_cooldown_nao_vaza_para_copia_legada(monkeypatch):
    config(gemini_api_key='ficticia-a')
    db.adicionar_chave('google', 'ficticia-a')
    db.adicionar_chave('google', 'ficticia-b')
    lr.anotar_falha('gemini', '429', 'ficticia-a')
    assert lr.resolver('gemini') == 'ficticia-b'
    lr.anotar_falha('gemini', '429', 'ficticia-b')
    assert lr.resolver('gemini') is None


def test_erro_modelo_nao_condena_chave():
    db.adicionar_chave('google', 'ficticia')
    assert lr.anotar_falha('gemini', '404 model not found', 'ficticia') == lr.T_MODELO
    assert lr.resolver('gemini') == 'ficticia'


@pytest.mark.parametrize('status,estado', [(401,'recusada'), (403,'permissao'), (429,'cota'),
                                          (404,'endpoint'), (503,'indisponivel'), (408,'timeout')])
def test_validacao_estruturada(status, estado, monkeypatch):
    monkeypatch.setattr(validacao, '_get', lambda *args: (status, 'ficticia-segredo'))
    r = validacao.testar('google', 'ficticia-segredo')
    assert r.estado == estado and not r.apta
    assert 'ficticia-segredo' not in r.mensagem


def test_validacao_rede_e_catalogo_publico(monkeypatch):
    assert validacao.testar('google', 'ficticia').estado == 'rede'
    monkeypatch.setattr(validacao, '_get', lambda *args: (200, '{"data":[]}'))
    assert not validacao.testar('nvidia', 'ficticia').apta
    assert validacao.testar('nvidia', 'ficticia').estado == 'conectividade'


def test_validacao_sucesso_verificavel_e_adapter(monkeypatch):
    get = Mock(return_value=(200, '{"models":[]}'))
    monkeypatch.setattr(validacao, '_get', get)
    assert validacao.testar('google', 'ficticia').apta
    assert get.call_args.args[1] == {'x-goog-api-key': 'ficticia'}
    get.side_effect = [(200, '{"data":[]}'), (401, '{}')]
    assert validacao.testar('groq', 'ficticia', 'https://a.invalid/v1').apta


def test_conexao_url_modelo_e_chave_juntos(monkeypatch):
    db.adicionar_chave('custom', 'ficticia-a', modelo='modelo-a', base_url='https://a.invalid/v1')
    db.adicionar_chave('custom', 'ficticia-b', modelo='modelo-b', base_url='https://b.invalid/v1')
    cerebro = CerebroGenerico('custom')
    postar = Mock(return_value={'choices': [{'message': {'content': 'ok'}}]})
    monkeypatch.setattr(cerebro, '_postar', postar)
    assert cerebro.escrever_longo('sistema', 'pedido') == 'ok'
    assert (cerebro.chave, cerebro.url, postar.call_args.args[0]['model']) == ('ficticia-a', 'https://a.invalid/v1', 'modelo-a')
    lr.anotar_falha('custom', '429', 'ficticia-a')
    cerebro.escrever_longo('sistema', 'pedido')
    assert (cerebro.chave, cerebro.url, postar.call_args.args[0]['model']) == ('ficticia-b', 'https://b.invalid/v1', 'modelo-b')


def test_chave_endpoint_custom_nao_enviada_a_consumidor_nativo():
    db.adicionar_chave('google', 'ficticia', base_url='https://custom.invalid/v1')
    assert lr.resolver('gemini') is None
    assert lr.resolver_conexao('gemini').chave == 'ficticia'


def test_transporte_bloqueia_redirecionamento_e_filtra_segredo(monkeypatch):
    import core.cerebro_generico as cg
    from core.http_seguranca import SemRedirect
    assert SemRedirect().redirect_request(None, None, 302, '', {}, 'https://outro.invalid') is None
    c = CerebroGenerico('custom', chave='ficticia-segredo', modelo='m', base_url='https://a.invalid/v1')
    sessao = SimpleNamespace(post=Mock(return_value=SimpleNamespace(status_code=401,
        json=lambda: {'error': {'message': 'ficticia-segredo recusada'}})))
    monkeypatch.setattr(cg, '_sessao', lambda: sessao)
    with pytest.raises(RuntimeError) as exc:
        c._postar({}, 1)
    assert 'ficticia-segredo' not in str(exc.value)
    assert sessao.post.call_args.kwargs['allow_redirects'] is False


def resposta(modelos):
    return SimpleNamespace(status_code=200, raise_for_status=lambda: None,
                           json=lambda: {'models': [{'name': m} for m in modelos]})


def test_ollama_ativacao_preserva_legado_e_ultima_valida(monkeypatch):
    config(gemini_api_key='ficticia-legada', outra_opcao={'a': 1})
    monkeypatch.setattr(local.requests, 'get', lambda *a, **k: resposta(['m:latest', 'm:8b']))
    local.ativar_modelo('m:8b')
    anterior = local.CONFIG_PATH.read_bytes()
    with pytest.raises(ValueError):
        local.ativar_modelo('m:70b')
    assert local.CONFIG_PATH.read_bytes() == anterior
    dados = json.loads(anterior)
    assert dados['gemini_api_key'] == 'ficticia-legada' and dados['outra_opcao'] == {'a': 1}
    assert local.preferencia_conversa() == 'ollama'
    assert local.check_model_available()


def test_ollama_servico_parado_sem_modelos_e_modelo_exato(monkeypatch):
    assert local.descobrir_modelos()['estado'] == 'inacessivel'
    assert not local.check_model_available()
    monkeypatch.setattr(local.requests, 'get', lambda *a, **k: resposta([]))
    assert local.descobrir_modelos()['estado'] == 'sem_modelos'
    assert not local._modelo_instalado('m:8b', ['m:70b'])
    assert not local._modelo_instalado('m', ['m:8b'])
    assert local._modelo_instalado('m', ['m:latest'])


def test_config_corrompida_nao_sobrescrita():
    local.CONFIG_PATH.write_text('{invalido')
    with pytest.raises(ValueError):
        local.salvar_config_local({'llm_model': 'novo'})
    assert local.CONFIG_PATH.read_text() == '{invalido'


def test_conversa_real_ollama_sem_fallback_externo(monkeypatch):
    config(conversation_provider='ollama', llm_model='m:8b')
    cerebro = object.__new__(CerebroOpenRouter)
    cerebro._ferramentas_para = lambda m: []
    cerebro._pensar_com_codex = Mock(side_effect=AssertionError('fallback externo'))
    chamar = Mock(return_value={'content': 'local', 'tool_calls': []})
    monkeypatch.setattr(local, 'call_llm', chamar)
    assert cerebro._pensar([{'role': 'user', 'content': 'oi'}])['texto'] == 'local'
    assert cerebro.ultimo_cerebro == 'ollama'
    chamar.side_effect = RuntimeError('Ollama fora')
    with pytest.raises(RuntimeError, match='Ollama fora'):
        cerebro._pensar([])
    cerebro._pensar_com_codex.assert_not_called()


def test_escada_legada_preservada():
    cerebro = object.__new__(CerebroOpenRouter)
    cerebro._genericos_preferidos = lambda: False
    cerebro._pensar_com_codex = Mock(return_value={'texto': 'legado'})
    assert cerebro._pensar([]) == {'texto': 'legado'}


def test_geracao_e_stream_usam_modelo_ativado(monkeypatch):
    config(llm_model='selecionado:8b', llm_provider='ollama', llm_url='http://localhost:11434')
    class Resp:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def raise_for_status(self): pass
        def json(self): return {'message': {'content': 'ok'}}
        def iter_lines(self):
            yield b'{"message":{"content":"ok"},"done":true}'
    post = Mock(return_value=Resp())
    monkeypatch.setattr(local.requests, 'post', post)
    assert local.call_llm([])['content'] == 'ok'
    assert list(local.call_llm_stream([]))[-1]['content'] == 'ok'
    assert all(c.kwargs['json']['model'] == 'selecionado:8b' for c in post.call_args_list)


@pytest.fixture
def dialogo():
    """O antigo diálogo virou o painel compartilhado do dashboard."""
    from PyQt6.QtWidgets import QApplication
    from core.config_apis_ui import ConfigAPIsPanel
    app = QApplication.instance() or QApplication([])
    dlg = ConfigAPIsPanel()
    yield dlg
    dlg.encerrar()
    app.processEvents()


def escolher(dlg, provedor='google'):
    dlg.provedor.setCurrentIndex(dlg.provedor.findData(provedor))


def test_ui_nova_sem_rede_fica_pendente(dialogo, monkeypatch):
    escolher(dialogo)
    dialogo.chave.setText('ficticia')
    monkeypatch.setattr(dialogo, '_executar', lambda f, cb: cb(f()))
    dialogo._salvar()
    assert db.listar_chaves()[0]['status'] == 'pendente'
    assert lr.resolver('gemini') is None


def test_ui_substituicao_recusada_preserva_anterior(dialogo, monkeypatch):
    i = db.adicionar_chave('google', 'ficticia-antiga')
    dialogo._editar(registro(i))
    dialogo.chave.setText('ficticia-nova')
    monkeypatch.setattr(validacao, '_get', lambda *a: (401, '{}'))
    monkeypatch.setattr(dialogo, '_executar', lambda f, cb: cb(f()))
    dialogo._salvar()
    assert registro(i)['key'] == 'ficticia-antiga' and registro(i)['status'] == 'ativo'


@pytest.mark.parametrize('acao', ['editar', 'pausar', 'excluir'])
def test_ui_teste_atrasado_nao_sobrescreve(dialogo, monkeypatch, acao):
    i = db.adicionar_chave('google', 'ficticia')
    dialogo._editar(registro(i))
    callbacks = []
    monkeypatch.setattr(dialogo, '_executar', lambda f, cb: callbacks.append(cb))
    dialogo._salvar()
    if acao == 'editar':
        dialogo.chave.setText('edicao-em-curso')
    elif acao == 'pausar':
        db.atualizar_chave(i, 0, enabled=0)
    else:
        db.remover_chave(i)
    callbacks[0](validacao.ResultadoValidacao('verificada', 'ok'))
    if acao == 'excluir':
        assert not db.listar_chaves()
    elif acao == 'pausar':
        assert not registro(i)['enabled']
    else:
        assert dialogo.chave.text() == 'edicao-em-curso'
        assert registro(i)['revision'] == 0


def test_ui_ativacao_local_atrasada_ignorada(dialogo, monkeypatch):
    config(llm_model='anterior', conversation_provider='legado')
    dialogo.modelos.addItems(['m:8b', 'outro:8b'])
    callbacks = []
    monkeypatch.setattr(dialogo, '_executar', lambda f, cb: callbacks.append(cb))
    dialogo._ativar()
    dialogo.modelos.setCurrentIndex(1)
    callbacks[0]({'estado': 'disponivel', 'modelos': ['m:8b']})
    assert local.preferencia_conversa() == 'legado'
    assert local.get_llm_settings()[1] == 'anterior'


def test_ui_worker_real_responsivo(dialogo, monkeypatch):
    from PyQt6.QtCore import QThread
    from PyQt6.QtWidgets import QApplication
    import threading
    principal = threading.get_ident()
    capturados = []
    dialogo._executar(lambda: threading.get_ident(), lambda valor: capturados.append((valor, threading.get_ident())))
    limite = time.monotonic() + 4
    while not capturados and time.monotonic() < limite:
        QApplication.processEvents()
        QThread.msleep(2)
    assert capturados and capturados[0][0] != principal and capturados[0][1] == principal


def metodo_isolado(arquivo, classe, nome, globais):
    """Executa o método real de voz sem carregar drivers de áudio no teste."""
    arvore = ast.parse(Path(arquivo).read_text(encoding='utf-8'))
    cls = next(n for n in arvore.body if isinstance(n, ast.ClassDef) and n.name == classe)
    funcao = next(n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nome)
    codigo = ast.Module(body=[funcao], type_ignores=[])
    ns = dict(globais)
    exec(compile(codigo, arquivo, 'exec'), ns)
    return ns[nome]


def test_voz_openai_cache_revalida_pausa():
    i = db.adicionar_chave('openai', 'ficticia')
    funcao = metodo_isolado('core/voz_openai.py', 'VozOpenAI', '_cabecalho', {})
    voz = SimpleNamespace(_chave_gerenciada=True, chave='ficticia', _chave_do_config=lambda: lr.resolver('openai') or '')
    assert funcao(voz)['Authorization'] == 'Bearer ficticia'
    db.atualizar_chave(i, 0, enabled=0)
    with pytest.raises(RuntimeError):
        funcao(voz)


def test_voz_gemini_fecha_sessao_apos_exclusao():
    i = db.adicionar_chave('google', 'ficticia')
    fechadas = []
    async def fechar(): fechadas.append(True)
    funcao = metodo_isolado('core/gemini_voice.py', 'GeminiCharonVoice', '_atualizar_credencial', {})
    voz = SimpleNamespace(_chave='ficticia', _reset_persistent_session=fechar)
    db.remover_chave(i)
    with pytest.raises(RuntimeError):
        asyncio.run(funcao(voz))
    assert fechadas


def test_validacao_timeout_e_catalogo_grande(monkeypatch):
    monkeypatch.setattr(validacao, '_get', Mock(side_effect=TimeoutError))
    assert validacao.testar('google', 'ficticia').estado == 'timeout'
    corpo = json.dumps({'models': [{'name': 'modelo' * 100}] * 30})
    class Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self, limite): return corpo.encode()[:limite]
    monkeypatch.setattr(validacao, 'abrir', lambda *a, **k: Resp())
    # Usa o transporte real com uma resposta em memória.
    with monkeypatch.context() as m:
        m.setattr(validacao, '_get', _GET_ORIGINAL)
        assert validacao.testar('google', 'ficticia').apta


_GET_ORIGINAL = validacao._get


def test_nativo_openai_renova_chave_endpoint_e_preserva_modelo(monkeypatch):
    import core.cerebro_openai as ca
    i = db.adicionar_chave('openai', 'ficticia-a', modelo='preferencia-preservada', base_url='https://a.invalid/v1')
    c = ca.CerebroOpenAI()
    post = Mock(return_value={'output': []})
    monkeypatch.setattr(ca, '_postar', post)
    c._chamar([], [], False, 1)
    assert post.call_args.args[0] == 'ficticia-a'
    assert post.call_args.args[3] == 'https://a.invalid/v1/responses'
    assert post.call_args.args[1]['model'] == ca.MODELO
    db.atualizar_chave(i, 0, key='ficticia-b', base_url='https://b.invalid/v1', status='ativo')
    c._chamar([], [], False, 1)
    assert post.call_args.args[0] == 'ficticia-b'
    assert post.call_args.args[3] == 'https://b.invalid/v1/responses'
    db.atualizar_chave(i, 1, enabled=0)
    with pytest.raises(RuntimeError):
        c._chamar([], [], False, 1)


def test_nativo_gemini_renova_cliente_apos_substituicao(monkeypatch):
    import core.cerebro_gemini as cg
    client = Mock(return_value=SimpleNamespace())
    monkeypatch.setattr(cg, 'genai', SimpleNamespace(Client=client))
    i = db.adicionar_chave('google', 'ficticia-a')
    c = cg.CerebroGemini()
    assert client.call_args.kwargs['api_key'] == 'ficticia-a'
    db.atualizar_chave(i, 0, key='ficticia-b', status='ativo')
    c._atualizar_conexao()
    assert client.call_args.kwargs['api_key'] == 'ficticia-b'
    db.remover_chave(i)
    with pytest.raises(RuntimeError):
        c._atualizar_conexao()


def test_erro_modelo_em_operacao_nao_bloqueia_outra(monkeypatch):
    c = CerebroGenerico('custom', chave='ficticia', modelo='m', base_url='https://a.invalid/v1')
    post = Mock(side_effect=RuntimeError('404 model not found'))
    monkeypatch.setattr(c, '_postar', post)
    with pytest.raises(RuntimeError):
        c._chamar([], [], False, 1, 700)
    with pytest.raises(RuntimeError):
        c._chamar([], [], False, 1, 700)
    assert post.call_count == 1
    post.side_effect = None
    post.return_value = {'choices': []}
    c._chamar([], [], False, 1, 700, operacao='texto')
    assert post.call_count == 2


def test_alias_legado_duplicado_pausado_nao_retorna():
    i = db.adicionar_chave('google', 'ficticia')
    with db._conexao() as con:
        con.execute("INSERT INTO api_keys(platform,key) VALUES ('google','ficticia')")
    assert len(db.listar_chaves()) == 2
    db.atualizar_chave(i, 0, enabled=0)
    assert lr.resolver('gemini') is None
    assert not lr.carregar_router().escolher('gemini')


def test_fallback_nao_repete_modelo_invalido_na_mesma_operacao():
    r = lr.Router(estrategia='priority', cadeia=['gemini'])
    r.registrar('google', 'ficticia-a')
    r.registrar('google', 'ficticia-b')
    gerar = Mock(side_effect=[(False, None, '404 model not found'), (True, 'ok', '')])
    assert r.executar_fallback(gerar)[1] == 'ok'
    assert gerar.call_count == 2
    assert gerar.call_args_list[0].args[1].chave == 'ficticia-a'
    assert gerar.call_args_list[1].args[1].chave == 'ficticia-b'
    assert r.pool.obter('gemini').chave == 'ficticia-a'


def test_preferencia_local_nao_pode_acionar_backend_externo(monkeypatch):
    config(conversation_provider='ollama', llm_provider='openai', llm_url='https://externo.invalid')
    c = object.__new__(CerebroOpenRouter)
    chamar = Mock(side_effect=AssertionError('envio indevido'))
    monkeypatch.setattr(local, 'call_llm', chamar)
    with pytest.raises(RuntimeError, match='backend Ollama'):
        c._pensar([])
    chamar.assert_not_called()


def test_entrada_perguntar_usa_local_e_preserva_historico(monkeypatch):
    config(conversation_provider='ollama', llm_model='m:8b')
    c = CerebroOpenRouter(sistema='teste isolado')
    c._prompt_da_personalidade = lambda: 'teste isolado'
    c._lembrete_do_jeito = lambda: ''
    c._voz_interpreta = lambda: False
    c._ferramentas_para = lambda mensagens: []
    c._pensar_com_codex = Mock(side_effect=AssertionError('envio externo'))
    monkeypatch.setattr(local, 'call_llm', lambda *a, **k: {'content': 'Olá.', 'tool_calls': []})
    assert c.perguntar('oi') == 'Olá.'
    assert c.historico[-1]['content'] == 'Olá.'
    assert local.motor_conversa_em_uso() == 'ollama'


def test_credencial_corrigida_reabilita_reserva_sem_alterar_preferencia():
    c = object.__new__(CerebroOpenRouter)
    c.usar_gemini = False  # decisão do usuário permanece
    c._sincronizar_credenciais()
    c._openai_bloqueada = True
    c._gemini_bloqueada = True
    c._gemini_ate = time.time() + 1000
    db.adicionar_chave('openai', 'ficticia')
    c._sincronizar_credenciais()
    assert not c._openai_bloqueada and not c._gemini_bloqueada
    assert c._gemini_ate == 0
    assert c.usar_gemini is False


def test_ui_editar_preserva_formulario_e_apelido(dialogo):
    i = db.adicionar_chave('google', 'ficticia', 'antigo', modelo='m', base_url='https://a.invalid/v1')
    dialogo._editar(registro(i))
    dialogo.apelido.setText('novo apelido')
    dialogo.chave.setText('edicao-nao-confirmada')
    dialogo._metadados()
    assert registro(i)['label'] == 'novo apelido'
    assert registro(i)['modelo'] == 'm'
    assert registro(i)['base_url'] == 'https://a.invalid/v1'
    assert registro(i)['key'] == 'ficticia'
    assert dialogo.chave.text() == 'edicao-nao-confirmada'


def test_ui_reteste_recupera_recusada_mas_preserva_pausa(dialogo, monkeypatch):
    i = db.adicionar_chave('google', 'ficticia', status='invalida')
    db.atualizar_chave(i, 0, enabled=0)
    monkeypatch.setattr(validacao, '_get', lambda *a: (200, '{"models":[]}'))
    monkeypatch.setattr(dialogo, '_executar', lambda f, cb: cb(f()))
    dialogo._retestar(registro(i))
    assert registro(i)['status'] == 'ativo'
    assert registro(i)['enabled'] == 0
    assert lr.resolver('gemini') is None


def test_ui_setup_legado_pendente_ate_resultado(monkeypatch, dialogo):
    from core.config_apis_ui import testar_configuracao_legada
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QThread
    monkeypatch.setattr(validacao, '_get', lambda *a: (200, '{"models":[]}'))
    feedback = []
    testar_configuracao_legada(dialogo, 'google', 'ficticia', feedback.append)
    assert db.listar_chaves()[0]['status'] == 'pendente'
    limite = time.monotonic() + 4
    while not feedback and time.monotonic() < limite:
        QApplication.processEvents()
        QThread.msleep(2)
    assert feedback
    assert lr.resolver('gemini') == 'ficticia'


def test_catalogo_reconhece_alias_canonico():
    from core.provedores import nome_do_provedor, modelos_do_provedor, base_url_do_provedor
    assert nome_do_provedor('gemini') == nome_do_provedor('google')
    assert nome_do_provedor('provedor-inexistente') == 'PROVEDOR-INEXISTENTE'
    assert modelos_do_provedor('gemini') == modelos_do_provedor('google')
    assert base_url_do_provedor('gemini') == base_url_do_provedor('google')


def test_classificacao_preserva_diagnosticos_e_repr_sem_segredo():
    assert lr.classificar_erro('401 unauthorized') == lr.T_INVALIDA
    assert lr.classificar_erro('403 permission_denied') == lr.T_PERMISSAO
    assert lr.classificar_erro('credit_balance billing') == lr.T_QUOTA
    assert 'ficticia-segredo' not in repr(lr.Chave('google', 'ficticia-segredo'))


def test_texto_backend_compativel_preservado(monkeypatch):
    config(llm_provider='openai', llm_model='manual', llm_url='http://localhost:1234')
    post = Mock(return_value=SimpleNamespace(raise_for_status=lambda: None,
        json=lambda: {'choices': [{'message': {'content': 'compatível'}}]}))
    monkeypatch.setattr(local.requests, 'post', post)
    assert local.call_llm_text('oi') == 'compatível'
    assert post.call_args.args[0] == 'http://localhost:1234/v1/chat/completions'
    assert post.call_args.kwargs['json']['model'] == 'manual'


def test_ui_falha_f2_preserva_copia_legada(monkeypatch, dialogo):
    from core.config_apis_ui import testar_configuracao_legada
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QThread
    config(gemini_api_key='ficticia-anterior', preferencia_legada=123)
    monkeypatch.setattr(validacao, '_get', lambda *a: (401, '{}'))
    feedback = []
    testar_configuracao_legada(dialogo, 'google', 'ficticia-nova', feedback.append)
    limite = time.monotonic() + 4
    while not feedback and time.monotonic() < limite:
        QApplication.processEvents()
        QThread.msleep(2)
    assert feedback
    assert json.loads(local.CONFIG_PATH.read_text())['gemini_api_key'] == 'ficticia-anterior'
    assert lr.resolver('gemini') == 'ficticia-anterior'


def test_conversa_local_executa_ferramentas_existentes(monkeypatch):
    config(conversation_provider='ollama')
    c = object.__new__(CerebroOpenRouter)
    c._ferramentas_para = lambda m: [{'type': 'function', 'function': {'name': 'consulta'}}]
    c.executor = Mock(return_value='resultado local')
    chamar = Mock(side_effect=[
        {'content': '', 'tool_calls': [{'function': {'name': 'consulta', 'arguments': {'a': 1}}}]},
        {'content': 'Concluído.', 'tool_calls': []},
    ])
    monkeypatch.setattr(local, 'call_llm', chamar)
    r = c._pensar([{'role': 'user', 'content': 'consulte'}])
    assert r == {'texto': 'Concluído.', 'chamou_ferramenta': True}
    c.executor.assert_called_once_with('consulta', {'a': 1})
    assert chamar.call_args.args[0][-1]['content'] == 'resultado local'


def test_ui_nova_chave_verificada_selecionavel(dialogo, monkeypatch):
    escolher(dialogo)
    dialogo.chave.setText('ficticia')
    monkeypatch.setattr(validacao, '_get', lambda *a: (200, '{"models":[]}'))
    monkeypatch.setattr(dialogo, '_executar', lambda f, cb: cb(f()))
    dialogo._salvar()
    assert db.listar_chaves()[0]['status'] == 'ativo'
    assert lr.resolver('gemini') == 'ficticia'


def test_ui_substituicao_conclusiva_preserva_id_e_metadados(dialogo, monkeypatch):
    i = db.adicionar_chave('google', 'ficticia-antiga', 'apelido')
    dialogo._editar(registro(i))
    dialogo.chave.setText('ficticia-nova')
    monkeypatch.setattr(validacao, '_get', lambda *a: (200, '{"models":[]}'))
    monkeypatch.setattr(dialogo, '_executar', lambda f, cb: cb(f()))
    dialogo._salvar()
    assert registro(i)['key'] == 'ficticia-nova'
    assert registro(i)['label'] == 'apelido'
    assert lr.resolver('gemini') == 'ficticia-nova'


@pytest.mark.parametrize('fonte', ['api', 'routing'])
def test_falha_concreta_de_legada_sobrevive_reinicio(fonte):
    if fonte == 'api':
        config(gemini_api_key='ficticia-legada')
    else:
        lr.CONFIG_PADRAO.write_text(json.dumps({'router': {'provedores': {'google': {'chaves': ['ficticia-legada']}}}}))
    assert lr.resolver('gemini') == 'ficticia-legada'
    assert lr.anotar_falha('gemini', '401 unauthorized', 'ficticia-legada') == lr.T_INVALIDA
    lr._router_global = None
    assert lr.resolver('gemini') is None
    assert len(db.listar_chaves()) == 1
    assert db.listar_chaves()[0]['status'] == 'invalida'


def test_falha_atrasada_de_legada_nao_recadastra_excluida():
    c = lr.Chave('gemini', 'ficticia-legada')
    i = db.adicionar_chave('google', 'ficticia-legada')
    db.remover_chave(i)
    lr.KeyPool().registrar_falha(c, lr.T_QUOTA)
    assert not db.listar_chaves()


def test_ui_ativacao_reutiliza_descoberta_sem_rede_na_thread_qt(dialogo, monkeypatch):
    config(opcao_legada='preservada')
    dialogo.modelos.addItem('m:8b')
    monkeypatch.setattr(dialogo, '_executar', lambda f, cb: cb(
        {'estado': 'disponivel', 'modelos': ['m:8b']}))
    rede = Mock(side_effect=AssertionError('não repetir rede na thread Qt'))
    monkeypatch.setattr(local.requests, 'get', rede)
    dialogo._ativar()
    assert local.preferencia_conversa() == 'ollama'
    assert local.get_llm_settings()[1] == 'm:8b'
    assert json.loads(local.CONFIG_PATH.read_text())['opcao_legada'] == 'preservada'
    rede.assert_not_called()


@pytest.mark.parametrize('http,corpo,estado', [
    (401, '{}', 'invalido'), (402, '{}', 'esgotado'),
    (429, '{"error":{"code":"insufficient_quota"}}', 'esgotado'),
    (429, '{"error":{"code":"rate_limit_exceeded"}}', 'limitado'),
    (403, '{"error":{"code":"API_KEY_INVALID"}}', 'invalido'),
    (403, '{"error":{"code":"permission_denied"}}', 'inconclusivo'),
    (200, '{"error":{"type":"invalid_api_key"}}', 'invalido'),
    (503, '{}', 'inconclusivo'), (200, '{"data":[]}', 'validado'),
])
def test_status_http_e_codigo_do_provedor(http, corpo, estado):
    assert validacao.interpretar_resposta(http, corpo).status_exibicao == estado


def test_modelo_cujo_nome_parece_erro_nao_invalida_catalogo():
    r = validacao.interpretar_resposta(200, '{"data":[{"id":"credit_balance-model"}]}')
    assert r.apta


def test_gemini_descobre_todas_as_paginas_sem_alterar_preferencia(monkeypatch):
    i = db.adicionar_chave('google', 'ficticia-chave', modelo='manual-legado')
    get = Mock(side_effect=[
        (200, '{"models":[{"name":"models/a"}],"nextPageToken":"pagina 2"}'),
        (200, '{"models":[{"name":"models/a"},{"name":"models/b"}]}'),
    ])
    monkeypatch.setattr(validacao, '_get', get)
    r = validacao.testar('google', 'ficticia-chave')
    assert r.modelos == ('a', 'b') and r.catalogo_completo
    assert 'pageToken=pagina+2' in get.call_args.args[0]
    assert db.aplicar_validacao(i, 0, r)
    assert json.loads(registro(i)['modelos_json']) == ['a', 'b']
    assert registro(i)['modelo'] == 'manual-legado'
    assert registro(i)['validacao_estado'] == 'validado'


def test_paginacao_nao_envia_chave_para_outro_host(monkeypatch):
    get = Mock(return_value=(200, '{"models":[{"name":"models/a"}],"next":"https://outro.invalid/models"}'))
    monkeypatch.setattr(validacao, '_get', get)
    r = validacao.testar('google', 'ficticia-chave')
    assert r.modelos == ('a',) and not r.catalogo_completo
    assert get.call_count == 1


def test_catalogo_publico_lista_modelos_sem_afirmar_chave_valida(monkeypatch):
    get = Mock(return_value=(200, '{"data":[{"id":"modelo-publico"}]}'))
    monkeypatch.setattr(validacao, '_get', get)
    r = validacao.testar('nvidia', 'ficticia-chave')
    assert r.status_exibicao == 'inconclusivo' and r.catalogo_publico
    assert r.modelos == ('modelo-publico',)
    assert get.call_args.args[1] == {}


def test_openrouter_autentica_chave_separadamente_do_catalogo(monkeypatch):
    get = Mock(side_effect=[(200, '{"data":{"limit_remaining":10}}'),
                            (200, '{"data":[{"id":"org/modelo"}]}')])
    monkeypatch.setattr(validacao, '_get', get)
    r = validacao.testar('openrouter', 'ficticia-chave')
    assert r.apta and r.modelos == ('org/modelo',)
    assert get.call_args_list[0].args[0].endswith('/key')


def test_erro_catalogo_nao_invalida_chave_openrouter_confirmada(monkeypatch):
    get = Mock(side_effect=[(200, '{"data":{"limit_remaining":10}}'), (404, '{}')])
    monkeypatch.setattr(validacao, '_get', get)
    r = validacao.testar('openrouter', 'ficticia-chave')
    assert r.apta and not r.catalogo_completo
    assert r.catalogo_mensagem


def test_saldo_pago_zerado_nao_bloqueia_gratuitos(monkeypatch):
    get = Mock(side_effect=[(200, '{"data":{"limit_remaining":0,"free_model_daily_requests":{"remaining":5}}}'),
                            (200, '{"data":[]}')])
    monkeypatch.setattr(validacao, '_get', get)
    assert validacao.testar('openrouter', 'ficticia-chave').apta


def test_resultado_de_cota_persiste_sem_retomar_chave_pausada():
    i = db.adicionar_chave('google', 'ficticia-chave', modelo='preferido')
    db.atualizar_chave(i, 0, enabled=0)
    r = validacao.interpretar_resposta(402, '{}')
    assert db.aplicar_validacao(i, 1, r)
    row = registro(i)
    assert row['validacao_estado'] == 'esgotado' and row['status'] == 'esgotada'
    assert row['cooldown_ate'] > time.time() and row['enabled'] == 0
    assert row['modelo'] == 'preferido'


def test_falha_rede_preserva_uso_legado_e_catalogo_anterior():
    i = db.adicionar_chave('google', 'ficticia-chave')
    r = validacao.ResultadoValidacao('verificada', 'ok', 200, modelos=('a',), catalogo_completo=True)
    assert db.aplicar_validacao(i, 0, r)
    assert db.aplicar_validacao(i, 1, validacao.ResultadoValidacao('rede', 'Rede indisponível.'))
    row = registro(i)
    assert row['status'] == 'ativo' and row['validacao_estado'] == 'inconclusivo'
    assert json.loads(row['modelos_json']) == ['a']


def test_substituicao_invalida_cache_de_modelos_e_validacao():
    i = db.adicionar_chave('google', 'ficticia-chave')
    db.aplicar_validacao(i, 0, validacao.ResultadoValidacao('verificada', 'ok', modelos=('a',), catalogo_completo=True))
    assert db.atualizar_chave(i, 1, key='outra-chave', base_url='https://b.invalid/v1')
    row = registro(i)
    assert row['validacao_estado'] == 'nao_verificada'
    assert json.loads(row['modelos_json']) == []


def test_validacao_antiga_nao_sobrescreve_substituicao():
    i = db.adicionar_chave('google', 'ficticia-chave')
    db.atualizar_chave(i, 0, key='outra-chave', status='ativo')
    assert not db.aplicar_validacao(i, 0, validacao.ResultadoValidacao('recusada', 'inválida'))
    assert registro(i)['key'] == 'outra-chave' and registro(i)['status'] == 'ativo'


def test_ui_valida_todas_sem_trocar_modelos_ou_pausas(dialogo, monkeypatch):
    i = db.adicionar_chave('google', 'ficticia-a', modelo='manual')
    j = db.adicionar_chave('groq', 'ficticia-b')
    db.atualizar_chave(j, 0, enabled=0)
    monkeypatch.setattr(validacao, 'testar', lambda *a: validacao.ResultadoValidacao(
        'verificada', 'ok', 200, modelos=('a', 'b'), catalogo_completo=True))
    monkeypatch.setattr(dialogo, '_executar', lambda f, cb: cb(f()))
    dialogo._validar_todas()
    assert all(r['validacao_estado'] == 'validado' for r in db.listar_chaves())
    assert registro(i)['modelo'] == 'manual' and registro(j)['enabled'] == 0
    assert dialogo.progresso.value() == 2 and dialogo.validar_todas.isEnabled()


def test_ui_cancelamento_lote_ignora_resultado(dialogo, monkeypatch):
    i = db.adicionar_chave('google', 'ficticia-a')
    callbacks = []
    monkeypatch.setattr(dialogo, '_executar', lambda f, cb: callbacks.append(cb))
    dialogo._validar_todas()
    dialogo._cancelar_validacao()
    callbacks[0](validacao.ResultadoValidacao('recusada', 'inválida'))
    assert registro(i)['status'] == 'ativo' and registro(i)['revision'] == 0


def test_ui_modelos_filtraveis_com_selecao_explicita(dialogo):
    i = db.adicionar_chave('google', 'ficticia-a', modelo='manual')
    db.aplicar_validacao(i, 0, validacao.ResultadoValidacao('verificada', 'ok', modelos=('alpha', 'beta'), catalogo_completo=True))
    dialogo._editar(registro(i))
    dialogo.busca_modelos.setText('beta')
    assert dialogo.modelos_api.count() == 1
    assert dialogo.modelo.text() == 'manual'
    dialogo._usar_modelo()
    assert dialogo.modelo.text() == 'beta' and registro(i)['modelo'] == 'manual'
    dialogo._metadados()
    assert registro(i)['modelo'] == 'beta'


def test_ui_teste_individual_nao_descarta_formulario(dialogo, monkeypatch):
    i = db.adicionar_chave('google', 'ficticia-a')
    dialogo._editar(registro(i))
    dialogo.apelido.setText('edição em curso')
    monkeypatch.setattr(validacao, 'testar', lambda *a: validacao.ResultadoValidacao('verificada', 'ok'))
    monkeypatch.setattr(dialogo, '_executar', lambda f, cb: cb(f()))
    dialogo._retestar(registro(i))
    assert dialogo.apelido.text() == 'edição em curso'
    assert registro(i)['label'] == ''


def test_teste_uso_tem_prompt_fixo_sem_historico(monkeypatch):
    http = Mock(return_value=(200, '{"choices":[{"message":{"content":"OK"}}]}'))
    monkeypatch.setattr(validacao, '_http', http)
    r = validacao.testar_geracao('nvidia', 'ficticia-chave', 'modelo-a')
    assert r.apta
    pedido = http.call_args.args[0]
    payload = json.loads(pedido.data)
    assert payload['messages'] == [{'role': 'user', 'content': 'Responda apenas OK.'}]
    assert payload['max_tokens'] == 8
    assert pedido.full_url == 'https://integrate.api.nvidia.com/v1/chat/completions'


@pytest.mark.parametrize('status,esperado', [(401,'invalido'), (402,'esgotado'), (429,'limitado'), (404,'inconclusivo')])
def test_teste_uso_classifica_sem_confundir_modelo_com_chave(monkeypatch, status, esperado):
    monkeypatch.setattr(validacao, '_http', Mock(return_value=(status, '{}')))
    r = validacao.testar_geracao('nvidia', 'ficticia-chave', 'modelo-a')
    assert r.status_exibicao == esperado


def test_ui_teste_de_uso_exige_confirmacao(dialogo, monkeypatch):
    from core.config_apis_ui import QMessageBox
    i = db.adicionar_chave('nvidia', 'ficticia-chave')
    db.aplicar_validacao(i, 0, validacao.ResultadoValidacao('conectividade', 'público', modelos=('modelo-a',), catalogo_completo=True))
    dialogo._ver_modelos(registro(i))
    executar = Mock()
    monkeypatch.setattr(dialogo, '_executar', executar)
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.No)
    dialogo._testar_uso()
    executar.assert_not_called()


def test_http403_de_bloqueio_nao_rotula_credencial_invalida():
    r = validacao.interpretar_resposta(403, '<html>Cloudflare access denied</html>')
    assert r.status_exibicao == 'inconclusivo' and r.codigo == 'bloqueio_acesso'


def test_pagina_recusada_nao_deixa_chave_marcada_validada(monkeypatch):
    get = Mock(side_effect=[(200, '{"models":[{"name":"models/a"}],"nextPageToken":"b"}'), (401, '{}')])
    monkeypatch.setattr(validacao, '_get', get)
    r = validacao.testar('google', 'ficticia-chave')
    assert r.status_exibicao == 'invalido' and r.modelos == ('a',)
    assert not r.catalogo_completo


def test_erro_de_modelo_preserva_autenticacao_comprovada():
    i = db.adicionar_chave('google', 'ficticia-chave')
    db.aplicar_validacao(i, 0, validacao.ResultadoValidacao('verificada', 'ok'))
    db.aplicar_validacao(i, 1, validacao.ResultadoValidacao('modelo', 'Modelo indisponível.', 404))
    assert registro(i)['validacao_estado'] == 'validado'
    assert registro(i)['status'] == 'ativo'


def test_diagnostico_voz_nao_confunde_rede_com_chave_invalida(monkeypatch, capsys):
    arvore = ast.parse(Path('verificar_voz.py').read_text(encoding='utf-8'))
    funcao = next(n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == '_ver_provedor')
    ns = {'llm_router': SimpleNamespace(resolver=lambda nome: 'ficticia-chave'),
          'valida_chave': validacao, '_marca': lambda segredo: 'oculta'}
    exec(compile(ast.Module(body=[funcao], type_ignores=[]), 'verificar_voz.py', 'exec'), ns)
    monkeypatch.setattr(validacao, 'testar', lambda *a: validacao.ResultadoValidacao('rede', 'Sem resposta.'))
    assert ns['_ver_provedor']('gemini', 'Voz') is False
    saida = capsys.readouterr().out
    assert 'Inconclusivo' in saida and 'RECUSOU' not in saida and 'gere outra' not in saida


def test_ui_filtra_apis_por_status_sem_alterar_registros(dialogo):
    i = db.adicionar_chave('google', 'ficticia-a')
    j = db.adicionar_chave('groq', 'ficticia-b')
    db.aplicar_validacao(i, 0, validacao.ResultadoValidacao('verificada', 'ok'))
    db.aplicar_validacao(j, 0, validacao.ResultadoValidacao('recusada', 'inválida'))
    dialogo._atualizar()
    assert dialogo.linhas.count() == 3
    dialogo.filtro_status.setCurrentIndex(dialogo.filtro_status.findData('invalido'))
    assert dialogo.linhas.count() == 2
    assert len(db.listar_chaves()) == 2
