"""Registro confiável passa pela ponte real, sem áudio, rede ou dados reais."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from core import catalogo_habilidades as CH
from main import NiaLive


@pytest.fixture(autouse=True)
def isolado(monkeypatch):
    monkeypatch.setattr(CH, '_MODULOS', {})
    monkeypatch.setattr(CH, '_EXECUTOR', None)


def manifesto(**extra):
    return CH.Habilidade('ficticia', 'Ferramenta fictícia', 'Somente teste',
                         'Teste fictício', 'teste', **extra)


def ponte():
    # Método real sem construir NiaLive, microfone ou serviços externos.
    nia = SimpleNamespace()
    real = NiaLive._executar_habilidade.__get__(nia, NiaLive)
    def executar(identificador, termo):
        # Simula somente a confirmação explícita da prévia, mantendo ponte real.
        from core import permissoes_ferramentas as PF
        h = CH.por_id(identificador)
        token = PF.confirmar(PF.preparar(identificador, {'termo': termo}, h.permissoes), confirmado=True)
        with PF.usar(token):
            return real(identificador, termo)
    CH.registrar_executor(executar)


def test_registro_sem_execucao_e_ponte_real_com_origem():
    chamadas = []
    h = manifesto(capacidades=('consulta',), permissoes=('dados_teste',))
    CH.registrar_modulo(h, lambda termo: chamadas.append((termo, CH.origem())) or CH.Resultado(True, 'Resposta real do callback'))
    assert chamadas == [] and CH.por_id(h.id) is h
    assert CH.todas()[:3] == CH.CATALOGO
    ponte()
    token = CH.definir_origem('voz')
    try:
        from core import permissoes_ferramentas as PF
        autorizacao = PF.confirmar(PF.preparar(h.id, {'termo': 'exemplo'}, h.permissoes), confirmado=True)
        with PF.usar(autorizacao):
            assert CH.executar(h.id, 'exemplo') == (True, 'Resposta real do callback')
    finally:
        CH.restaurar_origem(token)
    assert chamadas == [('exemplo', 'voz')]
    autorizacao = PF.confirmar(PF.preparar(h.id, {'termo': ''}, h.permissoes), confirmado=True)
    with PF.usar(autorizacao):
        assert CH.executar_resultado(h.id).ok


@pytest.mark.parametrize('extra', [{'api': 2}, {'api': True}, {'versao': 'antiga'}, {'permissoes': ['rede']}])
def test_manifesto_incompativel_nao_registra(extra):
    with pytest.raises(ValueError):
        CH.registrar_modulo(manifesto(**extra), lambda _: CH.Resultado(True, 'ok'))
    assert CH.por_id('ficticia') is None


def test_duplicacao_nativa_e_modular_rejeitada():
    CH.registrar_modulo(manifesto(), lambda _: CH.Resultado(True, 'ok'))
    for h in (manifesto(), replace(manifesto(), id='secretaria')):
        with pytest.raises(ValueError):
            CH.registrar_modulo(h, lambda _: CH.Resultado(True, 'indevido'))


def test_indisponibilidade_desativacao_e_ciclo_de_vida():
    eventos = []
    CH.registrar_modulo(manifesto(), lambda _: eventos.append('executou') or CH.Resultado(True, 'ok'),
                        disponibilidade=lambda: CH.Disponibilidade(False, 'Dependência opcional ausente'),
                        encerrar=lambda: eventos.append('encerrou'))
    ponte()
    assert not CH.disponibilidade('ficticia').pronta
    assert CH.executar('ficticia') == (False, 'Dependência opcional ausente')
    assert CH.ativar_modulo('ficticia', False)
    assert CH.executar_modulo('ficticia').codigo == 'desativado'
    assert CH.desregistrar_modulo('ficticia').ok
    assert CH.desregistrar_modulo('ficticia').codigo == 'ausente'
    assert eventos == ['encerrou']
    assert CH.por_id('secretaria') is not None


def test_acao_com_nome_nativo_nao_desvia_do_callback_registrado():
    CH.registrar_modulo(replace(manifesto(), acao='gerar_resumo'), lambda _: CH.Resultado(True, 'módulo'))
    ponte()
    assert CH.executar('ficticia') == (True, 'módulo')


def test_erros_nao_expoem_credenciais_e_nao_contaminam_ponte():
    def falhar(_):
        raise RuntimeError('segredo-ficticio-nao-exibir')
    CH.registrar_modulo(manifesto(), falhar)
    ponte()
    resultado = CH.executar_resultado('ficticia')
    assert not resultado.ok and 'segredo-ficticio' not in resultado.mensagem
    CH.desregistrar_modulo('ficticia')
    CH.registrar_modulo(manifesto(), lambda _: CH.Resultado(True, 'recuperou'))
    assert CH.executar_resultado('ficticia').ok


def test_ausencia_e_ponte_nao_inicializada():
    assert CH.executar_resultado('ausente').codigo == 'ausente'
    assert CH.executar_resultado('secretaria').codigo == 'nao_inicializado'
    assert CH.executar_modulo('ausente').codigo == 'ausente'


def test_contrato_invalido_nao_declara_sucesso():
    CH.registrar_modulo(manifesto(), lambda _: 'ok')
    ponte()
    assert not CH.executar_resultado('ficticia').ok


def test_falha_de_disponibilidade_e_fechamento_nao_vaza_segredos():
    def falhar():
        raise RuntimeError('segredo-ficticio')
    CH.registrar_modulo(manifesto(), lambda _: CH.Resultado(True, 'ok'), disponibilidade=falhar, encerrar=falhar)
    assert not CH.disponibilidade('ficticia').pronta
    assert CH.executar_modulo('ficticia').codigo == 'erro'
    assert CH.desregistrar_modulo('ficticia').codigo == 'erro_encerramento'
    assert CH.por_id('ficticia') is None
