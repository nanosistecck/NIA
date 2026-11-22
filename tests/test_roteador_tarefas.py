"""Política determinística de seleção por tarefa, sem IA para decidir."""
from types import SimpleNamespace

import pytest

from core import llm_client, llm_router, roteador_tarefas as RT


class _RouterFalso:
    def __init__(self, disponiveis):
        self.disponiveis = disponiveis
        self.cadeia = list(disponiveis)
        self.consultas = []

    def escolher(self, preferido=None):
        self.consultas.append(preferido)
        if preferido is not None:
            return (preferido, SimpleNamespace(modelo=self.disponiveis.get(preferido, ''))) \
                if preferido in self.disponiveis else None
        for nome in self.cadeia:
            if nome in self.disponiveis:
                return (nome, SimpleNamespace(modelo=self.disponiveis[nome]))
        return None


def _preferencia(monkeypatch, valor):
    monkeypatch.setattr(llm_client, 'preferencia_conversa', lambda: valor)


def test_operacao_local_nao_dispara_inferencia(monkeypatch):
    _preferencia(monkeypatch, 'legado')
    monkeypatch.setattr(llm_client, 'call_llm',
                        lambda *a, **k: pytest.fail('inferência indevida'))
    decisao = RT.decidir(RT.Requisitos(geracao=False))
    assert decisao.local and decisao.permitido
    assert 'sem inferência' in decisao.motivo


def test_conversa_comum_segue_preferencia_salva(monkeypatch):
    _preferencia(monkeypatch, 'legado')
    roteador = _RouterFalso({'gemini': 'gemini-2.5-flash'})
    decisao = RT.decidir(RT.Requisitos(origem='chat'), roteador=roteador)
    assert decisao.provedor == 'gemini'
    assert decisao.modelo == 'gemini-2.5-flash'
    assert 'preferência' in decisao.motivo.lower()


def test_ollama_selecionado_nao_consulta_provedores(monkeypatch):
    _preferencia(monkeypatch, 'ollama')
    monkeypatch.setattr(llm_client, 'get_llm_settings',
                        lambda: ('http://localhost:11434', 'qwen:8b'))
    roteador = _RouterFalso({'gemini': 'g'})

    def falha(*a, **k):
        pytest.fail('roteador externo não devia ser consultado')

    monkeypatch.setattr(roteador, 'escolher', falha)
    decisao = RT.decidir(RT.Requisitos(imagem=True), roteador=roteador)
    assert decisao.local and decisao.provedor == 'ollama'
    assert decisao.modelo == 'qwen:8b'
    assert 'não foi confirmada' in decisao.aviso


def test_imagem_prefere_provedor_compativel_conhecido(monkeypatch):
    _preferencia(monkeypatch, 'legado')
    roteador = _RouterFalso({'gemini': 'gemini-2.5-pro', 'openai': 'gpt-5'})
    decisao = RT.decidir(RT.Requisitos(imagem=True), roteador=roteador)
    assert decisao.provedor == 'gemini'
    assert 'imagens' in decisao.motivo.lower()
    assert roteador.consultas[0] == 'gemini'


def test_capacidade_nao_confirmada_preserva_comportamento(monkeypatch):
    _preferencia(monkeypatch, 'legado')
    roteador = _RouterFalso({'groq': 'llama-3.3-70b'})
    decisao = RT.decidir(RT.Requisitos(imagem=True), roteador=roteador)
    assert decisao.permitido
    assert decisao.provedor == 'groq'
    assert 'não confirmada' in decisao.aviso


def test_sem_candidato_ou_autorizacao_oferece_saida_local(monkeypatch):
    _preferencia(monkeypatch, 'legado')
    vazio = RT.decidir(RT.Requisitos(), roteador=_RouterFalso({}))
    assert not vazio.permitido
    assert 'recursos locais' in vazio.aviso

    nao_autorizado = RT.decidir(
        RT.Requisitos(documentos=True, autorizado=False),
        roteador=_RouterFalso({'gemini': 'g'}))
    assert not nao_autorizado.permitido
    assert 'trechos locais' in nao_autorizado.aviso


def test_ultima_decisao_fica_disponivel_para_diagnostico(monkeypatch):
    _preferencia(monkeypatch, 'legado')
    RT.decidir(RT.Requisitos(origem='voz'), roteador=_RouterFalso({'gemini': 'g'}))
    assert RT.ultima_decisao() is not None
    assert RT.ultima_decisao().provedor == 'gemini'


def test_destino_de_sintese_usa_o_mesmo_roteador(monkeypatch):
    from core import busca_fontes as BF
    _preferencia(monkeypatch, 'legado')
    monkeypatch.setattr(llm_router, 'carregar_router',
                        lambda: _RouterFalso({'gemini': 'gemini-2.5-pro'}))
    destino = BF.destino_atual()
    assert destino['provedor'] == 'gemini'
    assert destino['assinatura'] == 'gemini|gemini-2.5-pro'
    assert destino['motivo']
