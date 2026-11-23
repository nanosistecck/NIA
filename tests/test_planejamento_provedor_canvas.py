"""O planejamento usa conteúdo longo/cru, não o caminho curto de conversa."""
import json
import sys
from types import SimpleNamespace

import pytest

from core import busca_fontes as BF, controle_canvas as CC, llm_client, llm_router


@pytest.mark.parametrize('provedor,modulo,nome', [
    ('openai', 'core.cerebro_openai', 'CerebroOpenAI'),
    ('gemini', 'core.cerebro_gemini', 'CerebroGemini'),
    ('groq', 'core.cerebro_generico', 'CerebroGenerico')])
def test_provedores_externos_usam_geracao_longa(monkeypatch, provedor, modulo, nome):
    chamadas = []
    class Cerebro:
        def __init__(self, *args, **kwargs):
            pass
        def escrever_longo(self, instrucao, pedido, **kwargs):
            chamadas.append((instrucao, pedido, kwargs))
            return '{"operacoes":[{"tipo":"limpar_mapa"}]}'
    monkeypatch.setitem(sys.modules, modulo, SimpleNamespace(**{nome:Cerebro}))
    monkeypatch.setattr(BF, 'destino_atual', lambda: {'provedor':provedor,'local':False,'permitido':True})
    monkeypatch.setattr(llm_router, 'carregar_router', lambda: {})
    resultado = CC.gerar_operacoes('Monte os novos cards', {'raiz_id':'raiz'})
    assert json.loads(resultado)['operacoes']
    instrucao, pedido, kwargs = chamadas[0]
    assert kwargs['max_tokens'] == 8000
    assert 'limpar_mapa' in instrucao and 'destino_ref' in instrucao
    assert json.loads(pedido)['contexto']['raiz_id'] == 'raiz'


def test_codex_usa_modo_cru_e_contrato_completo_no_conteudo(monkeypatch):
    chamadas = []
    class Cerebro:
        def escrever(self, instrucao, pedido, cru=False):
            chamadas.append((instrucao, pedido, cru))
            return '{"operacoes":[]}'
    monkeypatch.setitem(sys.modules, 'core.cerebro_codex', SimpleNamespace(CerebroCodex=Cerebro))
    monkeypatch.setattr(BF, 'destino_atual', lambda: {'provedor':'codex','local':False,'permitido':True})
    CC.gerar_operacoes('Crie cards sobre evolução', {'raiz_id':'raiz'})
    instrucao, pedido, cru = chamadas[0]
    assert cru and len(instrucao) < 800
    assert json.loads(pedido)['contrato'] == CC.instrucoes_operacoes()


def test_local_recebe_limite_para_lote_completo_e_sem_ferramentas(monkeypatch):
    chamadas = []
    monkeypatch.setattr(BF, 'destino_atual', lambda: {'local':True,'permitido':True})
    monkeypatch.setattr(llm_client, 'call_llm', lambda *args, **kwargs:
                        chamadas.append((args, kwargs)) or {'content':'{"operacoes":[]}'})
    CC.gerar_operacoes('Criar vários cards', {})
    args, kwargs = chamadas[0]
    assert kwargs['max_tokens'] == 8000 and kwargs['tools'] is None
    assert [m['role'] for m in args[0]] == ['system','user']


@pytest.mark.parametrize('provedor', ['openai','ollama'])
@pytest.mark.parametrize('limite', [None, 8000])
def test_cliente_preserva_limite_padrao_e_permite_lote_longo(monkeypatch, provedor, limite):
    chamadas = []
    monkeypatch.setattr(llm_client, 'get_llm_settings', lambda: ('http://127.0.0.1:11434','modelo'))
    monkeypatch.setattr(llm_client, 'get_llm_provider', lambda: provedor)
    monkeypatch.setattr(llm_client, 'registrar_resposta_conversa', lambda *args: None)
    resposta = {'choices':[{'message':{'content':'{}'}}]} if provedor == 'openai' else {'message':{'content':'{}'}}
    monkeypatch.setattr(llm_client.requests, 'post', lambda *args, **kwargs:
                        chamadas.append(kwargs['json']) or SimpleNamespace(
                            raise_for_status=lambda: None, json=lambda: resposta))
    llm_client.call_llm([{'role':'user','content':'teste'}], **({'max_tokens':limite} if limite else {}))
    payload = chamadas[0]
    import inspect
    padrao = inspect.signature(llm_client.call_llm).parameters['max_tokens'].default
    assert (payload['max_tokens'] if provedor == 'openai' else payload['options']['num_predict']) == (limite or padrao)


def test_destino_bloqueado_nao_e_chamado(monkeypatch):
    monkeypatch.setattr(BF, 'destino_atual', lambda: {'local':True,'permitido':False})
    monkeypatch.setattr(llm_client, 'call_llm', lambda *a, **k: pytest.fail('Não deve chamar'))
    with pytest.raises(RuntimeError):
        CC.gerar_operacoes('Criar cards', {})
