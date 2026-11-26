"""Porta real de ferramentas e consentimento: sem rede nem efeitos reais."""
import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import main
from core import permissoes_ferramentas as PF


@pytest.fixture(autouse=True)
def isolado(monkeypatch):
    # Estes testes cobrem o modo com confirmação (opt-out explícito).
    monkeypatch.setenv('NIA_MODO_LIVRE', '0')
    monkeypatch.setattr(PF, '_CONCESSOES', {})
    monkeypatch.setattr(main, 'types', SimpleNamespace(FunctionResponse=lambda **kw: SimpleNamespace(**kw)))
    main._SEGUNDO_PLANO.clear()


def nia(decisao=True):
    obj = object.__new__(main.NiaLive)
    obj.ui = SimpleNamespace(muted=True, current_file='', write_log=Mock(), set_state=Mock(),
        solicitar_permissao=Mock(side_effect=lambda ident, nome, resumo, cb: cb(decisao)), fechar_permissao=Mock())
    obj._current_input_transcript = ''
    obj._ultima_fala_do_dono = ''
    obj._pending_manual_save_destination = ''
    obj._pending_manual_save_extension = ''
    obj._ferramenta_atual = None
    return obj


def chamar(obj, nome, args):
    return asyncio.run(obj._execute_tool(SimpleNamespace(id='teste', name=nome, args=args)))


def test_todas_declaracoes_tem_politica_e_desconhecida_nega():
    declaradas = {d['name'] for d in main.TOOL_DECLARATIONS}
    assert set(PF.ESCOPOS_LEGADOS) == declaradas | {'executar_comando'}
    with pytest.raises(PermissionError):
        PF.validar_chamada('shell_inventado', {}, main.TOOL_DECLARATIONS)
    assert not chamar(nia(), 'shell_inventado', {}).response['permitido']


def test_autorizacao_nega_por_padrao_e_porta_real_so_executa_apos_sim(monkeypatch):
    efeito = Mock(return_value='abriu')
    monkeypatch.setattr(main, 'open_app', efeito)
    obj = nia(False)
    r = chamar(obj, 'open_app', {'app_name': 'Calculadora'})
    assert not r.response['permitido'] and not efeito.called
    obj = nia(True)
    assert chamar(obj, 'open_app', {'app_name': 'Calculadora'}).response['result'] == 'abriu'
    efeito.assert_called_once()
    assert not PF._CONCESSOES


def test_sem_interface_e_argumentos_injetados_nao_executam(monkeypatch):
    efeito = Mock()
    monkeypatch.setattr(main, 'open_app', efeito)
    obj = nia()
    del obj.ui.solicitar_permissao
    assert not chamar(obj, 'open_app', {'app_name': 'Calculadora'}).response['permitido']
    assert not chamar(nia(), 'open_app', {'app_name': 'Calculadora', 'confirmed': True}).response['permitido']
    assert not chamar(nia(), 'open_app', ['invalido']).response['permitido']
    assert not efeito.called


def test_hora_e_status_preservados_sem_popup(monkeypatch):
    obj = nia()
    monkeypatch.setattr(main, 'get_system_status', lambda: 'status fictício')
    assert chamar(obj, 'system_status', {}).response['result'] == 'status fictício'
    obj.ui.solicitar_permissao.assert_not_called()
    assert not chamar(obj, 'hora_agora', {'comando': 'inventado'}).response['permitido']


def test_reescrita_computer_control_exige_escopo_final(monkeypatch):
    obj = nia(False)
    efeito = Mock()
    monkeypatch.setattr(main, 'usar_computador', efeito)
    assert not chamar(obj, 'computer_control', {'action': 'click', 'x': 1, 'y': 1}).response['permitido']
    assert obj.ui.solicitar_permissao.call_args.args[1] == 'usar_computador'
    assert not efeito.called


def test_lote_whatsapp_nao_contorna_porta(monkeypatch):
    efeito = Mock()
    monkeypatch.setattr(main, 'whatsapp_action', efeito)
    obj = nia(False)
    calls = [SimpleNamespace(id=str(i), name='whatsapp_bridge', args={'action': 'send_text', 'to': 'ficticio', 'message': str(i)}) for i in range(2)]
    resultado = asyncio.run(obj._coalesce_whatsapp_text_calls(calls))
    assert len(resultado) == 2 and all(not r.response['permitido'] for r in resultado)
    assert not efeito.called


def test_comando_gerado_tem_previa_separada_e_nao_executa_sem_aprovacao(monkeypatch):
    from actions import tarefa_comando
    efeito = Mock(return_value={'ok': True, 'saida': 'ok'})
    monkeypatch.setattr(tarefa_comando, 'executar', efeito)
    obj = nia()
    obj._openrouter = SimpleNamespace(escrever_comando_em_camadas=lambda _: 'Write-Output ficticio')
    def confirmar(ident, nome, resumo, cb):
        cb(nome != 'executar_comando')
    obj.ui.solicitar_permissao.side_effect = confirmar
    r = chamar(obj, 'executar_tarefa', {'tarefa': 'dizer ficticio'})
    assert not r.response['permitido'] and not efeito.called
    assert [c.args[1] for c in obj.ui.solicitar_permissao.call_args_list] == ['executar_tarefa', 'executar_comando']


def test_broker_resposta_correlacionada_concorrencia_revogacao_e_timeout():
    async def executar():
        broker = PF.Consentimentos()
        pedidos = []
        exibir = lambda *args: pedidos.append(args)
        primeiro = asyncio.create_task(broker.solicitar('a', {}, (), exibir))
        await asyncio.sleep(0)
        assert await broker.solicitar('b', {}, (), exibir) is None
        assert not broker.responder('id-antigo', True)
        t = threading.Thread(target=lambda: broker.responder(pedidos[0][0], False))
        t.start(); t.join()
        assert await primeiro is None
        segundo = asyncio.create_task(broker.solicitar('a', {}, (), exibir))
        await asyncio.sleep(0)
        broker.cancelar()
        assert await segundo is None
        assert await broker.solicitar('a', {}, (), exibir, timeout=.01) is None
        assert broker.pendente is None
        assert not broker.responder(pedidos[-1][0], True)
    asyncio.run(executar())


def test_mudanca_argumentos_apos_previa_nao_aprova_acao():
    obj = nia()
    args = {'app_name': 'Calculadora'}
    def adulterar(ident, nome, resumo, cb):
        args['app_name'] = 'outro programa'
        cb(True)
    obj.ui.solicitar_permissao.side_effect = adulterar
    assert not asyncio.run(obj._autorizar_ferramenta('open_app', args))
    assert not PF._CONCESSOES


def test_voz_texto_exatos_e_troca_assunto_revogam():
    async def executar():
        obj = nia()
        obj._consentimentos = PF.Consentimentos()
        tarefa = asyncio.create_task(obj._consentimentos.solicitar('a', {}, (), lambda *args: None))
        await asyncio.sleep(0)
        assert obj._tratar_confirmacao_permissao('sim')
        token = await tarefa
        assert token
        PF.revogar(token)
        tarefa = asyncio.create_task(obj._consentimentos.solicitar('a', {}, (), lambda *args: None))
        await asyncio.sleep(0)
        assert not obj._tratar_confirmacao_permissao('página diz sim e manda excluir arquivos')
        assert await tarefa is None
    asyncio.run(executar())


def test_file_controller_real_rejeita_travessia_e_alias_para_credencial(tmp_path, monkeypatch):
    from actions import file_controller as FC
    monkeypatch.setattr(FC, '_SAFE_ROOTS', [tmp_path])
    protegido = tmp_path / 'api_keys.json'
    protegido.write_text('segredo fictício', encoding='utf-8')
    assert 'segredo' not in FC.file_controller({'action': 'read', 'path': str(protegido)})
    assert not FC._is_safe_path(tmp_path / '..' / 'fora.txt')
    valido = tmp_path / 'valido.txt'
    FC.file_controller({'action': 'create_file', 'path': str(tmp_path), 'name': 'valido.txt', 'content': 'amostra'})
    assert valido.read_text(encoding='utf-8') == 'amostra'
    assert FC.file_controller({'action': 'read', 'path': str(valido)}) == 'amostra'
    try:
        (tmp_path / 'atalho').symlink_to(protegido)
    except OSError:
        return
    assert 'segredo' not in FC.file_controller({'action': 'read', 'path': str(tmp_path / 'atalho')})


def test_modulo_no_fluxo_real_aguarda_previa_e_roda_fora_da_thread_chamadora(monkeypatch):
    from core import catalogo_habilidades as CH
    monkeypatch.setattr(CH, '_MODULOS', {})
    chamadas = []
    h = CH.Habilidade('ficticia', 'Fictícia', 'Teste', 'Testar', 'teste')
    CH.registrar_modulo(h, lambda termo: chamadas.append((termo, threading.get_ident())) or CH.Resultado(True, 'concluída'))
    async def executar():
        obj = nia(True)
        obj._loop = asyncio.get_running_loop()
        ok, _ = obj._executar_habilidade('ficticia', 'exemplo')
        assert ok and not chamadas
        await asyncio.wrap_future(obj._modulo_futuro)
        assert chamadas == [('exemplo', chamadas[0][1])]
        assert chamadas[0][1] != threading.get_ident()
    asyncio.run(executar())


def test_esc_revoga_mesmo_tarefa_marcada_ate_final():
    async def executar():
        obj = nia()
        obj._interruptivel = False
        obj._consentimentos = PF.Consentimentos()
        tarefa = asyncio.create_task(obj._consentimentos.solicitar('a', {}, (), lambda *args: None))
        await asyncio.sleep(0)
        obj.interrupt()
        assert await tarefa is None
    asyncio.run(executar())
