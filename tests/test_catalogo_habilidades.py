"""Skill 07: catálogo único de habilidades nativas, sem inferência."""
import pytest
import requests

from core import catalogo_habilidades as CH


@pytest.fixture
def executor_falso(monkeypatch):
    chamadas = []

    def executar(identificador, termo):
        chamadas.append((identificador, termo, CH.origem()))
        return True, 'ok'

    monkeypatch.setattr(CH, '_EXECUTOR', executar)
    return chamadas


def test_catalogo_tem_as_tres_habilidades_com_definicao_unica():
    ids = [h.id for h in CH.todas()]
    assert ids == ['secretaria', 'buscar_arquivos', 'resumo_dia']
    assert len(ids) == len(set(ids))
    for habilidade in CH.todas():
        assert habilidade.nome and habilidade.descricao
        assert habilidade.exemplo and habilidade.acao
        assert CH.por_id(habilidade.id) is habilidade


@pytest.mark.parametrize('frase,esperado,termo', [
    ('NIA, abra a Secretaria.', 'secretaria', ''),
    ('abra a Secretaria', 'secretaria', ''),
    ('NIA, procure nos meus arquivos por garantia.', 'buscar_arquivos', 'garantia'),
    ('procure nos meus documentos por garantia', 'buscar_arquivos', 'garantia'),
    ('NIA, prepare o resumo do dia.', 'resumo_dia', ''),
])
def test_exemplos_sao_reconhecidos_sem_modelo(frase, esperado, termo):
    habilidade, extraido = CH.reconhecer(frase)
    assert habilidade is not None and habilidade.id == esperado
    assert extraido == termo


def test_conversa_comum_e_sintese_nao_catalogadas():
    for frase in ('Olá, como vai?',
                  'Resuma o que meus arquivos dizem sobre garantia',
                  'abra minha pasta de downloads'):
        assert CH.reconhecer(frase)[0] is None


def test_executor_unico_registra_origem(executor_falso):
    assert CH.executar('secretaria') == (True, 'ok')
    token = CH.definir_origem('voz')
    try:
        CH.executar('buscar_arquivos', 'garantia')
    finally:
        CH.restaurar_origem(token)
    CH.executar('resumo_dia')
    assert executor_falso == [
        ('secretaria', '', 'catalogo'),
        ('buscar_arquivos', 'garantia', 'voz'),
        ('resumo_dia', '', 'catalogo'),
    ]
    assert CH.executar('inexistente')[0] is False


def test_disponibilidade_usa_apenas_estado_local(monkeypatch):
    from core import indice_local, secretaria
    from core.config_preferencias import ConfigService

    monkeypatch.setattr(secretaria, 'carregar', lambda: {'ligada': False})
    monkeypatch.setattr(indice_local, 'fts5_disponivel', lambda: True)
    monkeypatch.setattr(ConfigService, 'carregar_fontes_indice', lambda self: [])

    def sem_rede(*args, **kwargs):
        pytest.fail('catálogo não deve acessar rede')

    monkeypatch.setattr(requests, 'get', sem_rede)
    monkeypatch.setattr(requests, 'post', sem_rede)

    assert not CH.disponibilidade('secretaria').pronta
    assert 'Configurações' in CH.disponibilidade('secretaria').motivo
    assert not CH.disponibilidade('buscar_arquivos').pronta
    assert 'Documentos' in CH.disponibilidade('buscar_arquivos').motivo
    assert CH.disponibilidade('resumo_dia').pronta
