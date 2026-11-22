"""Controle real do Canvas por chat/voz, autorização e respostas atrasadas."""
import json
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

import main
import ui
from core import assistencia_planos as AP, planos as BP
from core import comandos_planos as CP
from core.controle_canvas import pedido_modo


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def sessao(app, tmp_path, monkeypatch):
    monkeypatch.setenv('NIA_PLANOS_DIR', str(tmp_path/'dados'))
    monkeypatch.setattr(ui, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(ui.MainWindow, '_check_config', lambda self: True)
    w = ui.MainWindow('face.png')
    w.resize(1280, 820)
    w.show()
    plano = BP.inicializar_mapa(BP.criar('Produto aberto', 'Validar o produto', 'Produto').id)
    w._abrir_canvas_do_plano(plano.id)
    app.processEvents()
    casca = object.__new__(ui.NiaUI)
    casca._win = w
    registros, falas = [], []
    casca.write_log = registros.append
    nia = object.__new__(main.NiaLive)
    nia.ui = casca
    nia._modo_local = True
    nia._sessao_planos = CP.SessaoComandosPlanos()
    nia._provedor_assistido = None
    nia._falar_resposta_comando = lambda mensagem, origem: falas.append((mensagem, origem))
    yield nia, w._canvas_editor, registros, falas
    for timer in w.findChildren(QTimer):
        timer.stop()
    w._canvas_editor.editor_internal.cena.itens_cards.clear()
    w._canvas_editor.editor_internal.cena.itens_conexoes.clear()
    w._canvas_editor.editor_internal.cena.clear()
    w.hide()
    w.deleteLater()
    app.processEvents()


def pedir(nia, app, texto, origem='texto'):
    assert nia._executar_frase_habilidade(texto, origem)
    app.processEvents()


@pytest.mark.parametrize('origem', ['texto', 'voz'])
def test_manual_pede_permissao_e_autorizacao_executa_pendente(sessao, app, origem):
    nia, overlay, registros, falas = sessao
    pedir(nia, app, 'Crie um card chamado Pesquisa', origem)
    assert len(overlay.editor_internal.plano_atual().mapa['cards']) == 1
    assert not overlay.modo_assistido
    assert 'pode ligar' in registros[-1]
    assert falas[-1][1] == origem
    pedir(nia, app, 'Pode ligar', origem)
    assert overlay.modo_assistido
    assert any(c['titulo'] == 'Pesquisa' for c in overlay.editor_internal.plano_atual().mapa['cards'])
    assert 'concluída' in registros[-1]


def test_consulta_plano_nao_exige_modo_nem_card(sessao, app):
    nia, overlay, registros, _ = sessao
    pedir(nia, app, 'Qual produto está aberto?', 'voz')
    assert 'Produto aberto' in registros[-1]
    assert 'Validar o produto' in registros[-1]
    assert not overlay.modo_assistido


def test_editar_dados_do_plano_salvar_desfazer_refazer(sessao, app):
    nia, overlay, registros, _ = sessao
    pedir(nia, app, 'Ative o modo NIA')
    pedir(nia, app, 'Renomeie o produto para Produto novo')
    assert overlay.editor_internal.plano_atual().titulo == 'Produto novo'
    assert 'Produto novo' in overlay.titulo.text()
    pedir(nia, app, 'Altere o objetivo do produto para Lançar em dezembro')
    pedir(nia, app, 'Salve o projeto')
    disco = BP.carregar(overlay.editor_internal._plano.id)
    assert disco.titulo == 'Produto novo' and disco.objetivo == 'Lançar em dezembro'
    pedir(nia, app, 'Desfaça a última edição')
    assert overlay.editor_internal.plano_atual().objetivo == 'Validar o produto'
    pedir(nia, app, 'Refaça a última edição')
    assert overlay.editor_internal.plano_atual().objetivo == 'Lançar em dezembro'


def test_cards_campos_conexoes_exclusao_e_zoom(sessao, app):
    nia, overlay, registros, _ = sessao
    pedir(nia, app, 'Ative o modo NIA')
    pedir(nia, app, 'Crie um card Pesquisa')
    pedir(nia, app, 'Crie um card Entrega')
    pedir(nia, app, 'Altere a descrição do card Pesquisa para Entrevistar clientes')
    pedir(nia, app, 'Marque o card Pesquisa como concluído')
    pedir(nia, app, 'Conecte o card Pesquisa ao card Entrega')
    mapa = overlay.editor_internal.plano_atual().mapa
    pesquisa = next(c for c in mapa['cards'] if c['titulo'] == 'Pesquisa')
    assert pesquisa['descricao'] == 'Entrevistar clientes'
    assert pesquisa['status'] == 'concluido'
    assert len(mapa['conexoes']) == 1
    pedir(nia, app, 'Desconecte o card Pesquisa do card Entrega')
    assert not overlay.editor_internal.plano_atual().mapa['conexoes']
    pedir(nia, app, 'Mova o card Pesquisa para 350, 200')
    pedir(nia, app, 'Zoom em 150%')
    assert overlay.editor_internal._camera['zoom'] == 1.5
    pedir(nia, app, 'Exclua o card Pesquisa')
    assert pesquisa['id'] not in overlay.editor_internal.cena.itens_cards


def test_revogar_modo_bloqueia_tambem_ponte_qt(sessao, app):
    nia, overlay, registros, _ = sessao
    pedir(nia, app, 'Ative o modo NIA')
    pedir(nia, app, 'Desligue o modo NIA')
    nia.ui.aplicar_lote_assistido([{'tipo':'criar_card','titulo':'Proibido'}], 'Teste')
    app.processEvents()
    assert not overlay.modo_assistido
    assert len(overlay.editor_internal.plano_atual().mapa['cards']) == 1


def test_provedor_sem_selecao_recebe_mapa_e_acoes_completas(sessao, app):
    nia, overlay, registros, _ = sessao
    pedir(nia, app, 'Ative o modo NIA')
    recebido = []
    def provedor(texto, contexto):
        recebido.append(contexto)
        return json.dumps({'operacoes':[
            {'tipo':'criar_card','titulo':'Planejamento','temp_id':'novo'},
            {'tipo':'editar_plano','campos':{'objetivo':'Novo objetivo'}},
            {'tipo':'zoom','valor':1.25}, {'tipo':'salvar'}]})
    nia._provedor_assistido = provedor
    pedir(nia, app, 'Organize o planejamento e crie as etapas necessárias')
    assert recebido and recebido[0]['titulo_plano'] == 'Produto aberto'
    assert recebido[0]['cartoes'] and 'plano' not in recebido[0]
    assert overlay.editor_internal.plano_atual().objetivo == 'Novo objetivo'
    assert overlay.editor_internal._camera['zoom'] == 1.25


@pytest.mark.parametrize('mudanca', ['modo', 'plano', 'reabrir'])
def test_resposta_atrasada_nao_altera_outro_estado(sessao, app, mudanca):
    nia, overlay, registros, _ = sessao
    pedir(nia, app, 'Ative o modo NIA')
    def provedor(texto, contexto):
        if mudanca == 'modo':
            overlay.definir_modo(False)
            overlay.definir_modo(True)
        else:
            plano = (BP.inicializar_mapa(BP.criar('Outro', 'Objetivo').id)
                     if mudanca == 'plano' else overlay.editor_internal.plano_atual())
            if mudanca == 'reabrir':
                overlay.window()._voltar_dos_planos()
            overlay.window()._abrir_canvas_do_plano(plano.id, assistido=True)
        return json.dumps({'operacoes':[{'tipo':'criar_card','titulo':'Tardia'}]})
    nia._provedor_assistido = provedor
    pedir(nia, app, 'Crie uma proposta detalhada para este produto')
    assert not any(c['titulo']=='Tardia' for c in overlay.editor_internal.plano_atual().mapa['cards'])


def test_autorizacao_pendente_nao_migra_para_outro_canvas(sessao, app):
    nia, overlay, registros, _ = sessao
    pedir(nia, app, 'Crie um card Pendente')
    outro = BP.inicializar_mapa(BP.criar('Outro', 'Objetivo').id)
    overlay.window()._abrir_canvas_do_plano(outro.id)
    app.processEvents()
    pedir(nia, app, 'Pode ligar')
    assert not overlay.modo_assistido
    assert len(overlay.editor_internal.plano_atual().mapa['cards']) == 1


@pytest.mark.parametrize('frase', ['não ligue o modo NIA', 'como ativar o modo NIA?',
                                  'e se eu ligar o modo NIA?', 'posso ativar o modo NIA?'])
def test_nao_confunde_pergunta_ou_negacao_com_autorizacao(frase):
    assert pedido_modo(frase) is None


def test_lote_invalido_nao_aplica_parte_valida(sessao, app):
    nia, overlay, registros, _ = sessao
    overlay.definir_modo(True)
    raiz = overlay.editor_internal.plano_atual().mapa['raiz_id']
    nia.ui.aplicar_lote_assistido([
        {'tipo':'editar_plano','campos':{'titulo':'Não aplicar'}},
        {'tipo':'excluir_card','card_id':raiz}], 'Lote inválido')
    assert overlay.editor_internal.plano_atual().titulo == 'Produto aberto'
    assert raiz in overlay.editor_internal.cena.itens_cards


def test_ativar_e_criar_salvar_no_mesmo_pedido(sessao, app):
    nia, overlay, registros, _ = sessao
    pedir(nia, app, 'Ative o modo NIA e crie um card Pesquisa e salve')
    plano = BP.carregar(overlay.editor_internal._plano.id)
    assert any(c['titulo']=='Pesquisa' for c in plano.mapa['cards'])
    assert not overlay.editor_internal.mudancas_pendentes


def test_pedido_composto_executa_todas_as_edicoes(sessao, app):
    nia, overlay, registros, _ = sessao
    pedir(nia, app, 'Ative o modo NIA')
    pedir(nia, app, 'Crie um card Pesquisa')
    pedir(nia, app, 'Renomeie o card Pesquisa para Pesquisa final e salve')
    plano = BP.carregar(overlay.editor_internal._plano.id)
    assert any(c['titulo']=='Pesquisa final' for c in plano.mapa['cards'])
    assert not any('salve' in c['titulo'] for c in plano.mapa['cards'])


def test_contexto_completo_nao_vaza_card_restrito_por_outro_campo(sessao):
    nia, overlay, _, _ = sessao
    plano = overlay.editor_internal.plano_atual()
    raiz = plano.mapa['cards'][0]
    raiz['restrito'] = True
    raiz['descricao'] = 'Segredo confidencial'
    contexto = AP.montar_contexto(plano, raiz['id'])
    contexto['plano'] = plano
    externo = AP.filtrar_contexto(contexto, AP.Destino(local=False))
    assert 'Segredo confidencial' not in json.dumps(externo, ensure_ascii=False)
    assert 'plano' not in externo


def test_chat_ou_voz_em_thread_externa_aplica_na_fila_qt(sessao, app):
    import threading
    nia, overlay, registros, _ = sessao
    erros = []
    def executar():
        try:
            assert nia._executar_frase_habilidade('Ative o modo NIA e crie um card Da voz', 'voz')
        except Exception as exc:
            erros.append(exc)
    worker = threading.Thread(target=executar)
    worker.start()
    worker.join(timeout=5)
    assert not worker.is_alive() and not erros
    app.processEvents()
    assert overlay.modo_assistido
    assert any(c['titulo']=='Da voz' for c in overlay.editor_internal.plano_atual().mapa['cards'])


def test_falha_ao_salvar_nao_anuncia_sucesso(sessao, app, monkeypatch):
    nia, overlay, registros, _ = sessao
    pedir(nia, app, 'Ative o modo NIA')
    def falhar(*args, **kwargs):
        raise OSError('disco indisponível')
    monkeypatch.setattr('core.interface_mapa.atualizar', falhar)
    pedir(nia, app, 'Crie um card Em memória e salve')
    assert 'Não foi possível' in registros[-1]
    assert any(c['titulo']=='Em memória' for c in overlay.editor_internal.plano_atual().mapa['cards'])
    assert overlay.editor_internal.mudancas_pendentes


@pytest.mark.parametrize('frase', [
    'Qual plano eu abrir?', 'Qual plano eu abri?', 'Qual projeto eu abri agora?',
    'Qual o nome do plano que eu abrir?', 'Que plano está aberto?'])
def test_pergunta_do_usuario_consulta_canvas_em_vez_de_buscar_nome(sessao, app, frase):
    nia, overlay, registros, falas = sessao
    pedir(nia, app, frase)
    assert 'Produto aberto' in registros[-1]
    assert 'Não encontrei' not in registros[-1]
    assert falas[-1][0] in registros[-1] and falas[-1][1] == 'texto'


def test_abrir_pelo_nome_sem_canvas_e_trocar_preservando_edicoes(sessao, app):
    nia, overlay, registros, falas = sessao
    w = overlay.window()
    w._voltar_dos_planos()
    novo = BP.inicializar_mapa(BP.criar('Campanha de novembro', 'Publicar').id)
    pedir(nia, app, 'Abra o plano Campanha de novembro')
    assert nia.ui.contexto_canvas()['plano_id'] == novo.id
    overlay.editor_internal.criar_card('Não perder')
    proximo = BP.inicializar_mapa(BP.criar('Produto seguinte', 'Construir', 'Produto').id)
    pedir(nia, app, 'Feche o plano atual e abra o produto Produto seguinte')
    assert nia.ui.contexto_canvas()['plano_id'] == proximo.id
    assert any(c['titulo']=='Não perder' for c in BP.carregar(novo.id).mapa['cards'])
    assert 'Abrindo' in registros[-1]
    assert falas[-1][1] == 'texto'


@pytest.mark.parametrize('frase', ['Mostre a janela NIA Planos', 'Abra o Gerenciador de Planos',
                                  'Mostre meus planos', 'Abra a janela de planos'])
def test_mostrar_gerenciador_a_partir_do_canvas(sessao, app, frase):
    nia, overlay, registros, _ = sessao
    plano_id = nia.ui.contexto_canvas()['plano_id']
    pedir(nia, app, frase)
    assert overlay.window()._planos_window.isVisible()
    assert nia.ui.contexto_canvas()['plano_id'] == plano_id


def test_fechar_canvas_e_consultar_sem_plano_aberto(sessao, app):
    nia, overlay, registros, falas = sessao
    pedir(nia, app, 'Feche o plano aberto')
    assert not overlay.isVisible()
    assert nia.ui.contexto_canvas()['plano'] is None
    pedir(nia, app, 'Qual plano eu abrir?')
    assert 'Nenhum plano' in registros[-1]
    assert falas[-1][1] == 'texto'


def test_troca_cancelada_nao_anuncia_que_abriu_outro_plano(sessao, app, monkeypatch):
    nia, overlay, registros, falas = sessao
    anterior = overlay.editor_internal._plano.id
    outro = BP.inicializar_mapa(BP.criar('Outro plano', 'Objetivo').id)
    overlay.editor_internal.criar_card('Pendente')
    monkeypatch.setattr(overlay, 'fechar_com_seguranca', lambda: False)
    monkeypatch.setattr(ui, '_perguntar_salvar_mapa', lambda *args: ui._SB_CANCELAR)
    pedir(nia, app, 'Abra o plano Outro plano')
    assert nia.ui.contexto_canvas()['plano_id'] == anterior
    assert 'Não foi possível' in registros[-1]
    assert 'Abrindo' not in registros[-1]


@pytest.mark.parametrize('origem', ['texto', 'voz'])
def test_resposta_local_aciona_audio_tambem_no_chat(sessao, origem):
    import threading
    nia, _, _, _ = sessao
    evento = threading.Event()
    textos = []
    def falar(texto):
        textos.append(texto)
        evento.set()
    nia._falar_local = falar
    main.NiaLive._falar_resposta_comando(nia, 'O plano aberto é Produto aberto.', origem)
    assert evento.wait(2)
    assert textos == ['O plano aberto é Produto aberto.']


def test_abrir_plano_que_ja_esta_aberto_nao_descarta_edicoes(sessao, app):
    nia, overlay, _, _ = sessao
    overlay.editor_internal.criar_card('Edição em memória')
    sessao_anterior = overlay._sessao_id
    pedir(nia, app, 'Abra o produto Produto aberto')
    assert overlay._sessao_id == sessao_anterior
    assert any(c['titulo']=='Edição em memória' for c in overlay.editor_internal.plano_atual().mapa['cards'])


PEDIDO_SUBSTITUIR = 'vc consegue apagar todos os cards e criar cards sobre o seu funcionamento e já pensando em evolução?'


def test_pedido_exato_substitui_mapa_em_um_unico_undo(sessao, app):
    nia, overlay, registros, _ = sessao
    overlay.definir_modo(True)
    editor = overlay.editor_internal
    raiz = editor.plano_atual().mapa['raiz_id']
    antigo = editor.criar_card('Antigo')
    editor.conectar(raiz, antigo)
    editor.selecionar(antigo)
    antes = editor.plano_atual().mapa
    contagem = editor.pilha.count()
    operacoes = [
        {'tipo':'limpar_mapa'},
        {'tipo':'editar_campos','card_id':raiz,'campos':{'titulo':'Funcionamento e evolução da NIA'}},
        {'tipo':'criar_card','titulo':'Funcionamento','descricao':'Chat, voz e Canvas.','temp_id':'func'},
        {'tipo':'criar_card','titulo':'Evoluções propostas','descricao':'Melhorias futuras a validar.','temp_id':'evol'},
        {'tipo':'conectar','origem':raiz,'destino_ref':'func'},
        {'tipo':'conectar','origem':'func','destino_ref':'evol'},
    ]
    nia._provedor_assistido = lambda *args: 'Segue o planejamento:\n```json\n'+json.dumps({'operacoes':operacoes})+'\n```'
    pedir(nia, app, PEDIDO_SUBSTITUIR)
    mapa = editor.plano_atual().mapa
    assert antigo not in editor.cena.itens_cards
    assert len(mapa['cards']) == 3 and len(mapa['conexoes']) == 2
    assert editor.pilha.count() == contagem+1
    editor.pilha.undo()
    assert editor.plano_atual().mapa == antes


def test_json_invalido_e_corrigido_uma_vez_sem_aplicar_parcial(sessao, app):
    nia, overlay, registros, _ = sessao
    overlay.definir_modo(True)
    editor = overlay.editor_internal
    antigo = editor.criar_card('Preservar até terminar')
    chamadas = []
    def provedor(pedido, contexto):
        chamadas.append(pedido)
        assert antigo in editor.cena.itens_cards
        if len(chamadas) == 1:
            return 'Sim, vou apagar os cards e montar os novos.'
        return json.dumps({'operacoes':[{'tipo':'criar_card','titulo':'Funcionamento'},
                                      {'tipo':'criar_card','titulo':'Evolução proposta'}]})
    nia._provedor_assistido = provedor
    pedir(nia, app, PEDIDO_SUBSTITUIR)
    assert len(chamadas) == 2
    assert antigo not in editor.cena.itens_cards
    assert any(c['titulo']=='Funcionamento' for c in editor.plano_atual().mapa['cards'])


@pytest.mark.parametrize('resposta', ['Não é JSON', '{"operacoes":[{"tipo":"limpar_mapa"}]}'])
def test_duas_respostas_invalidas_ou_so_exclusao_preservam_tudo(sessao, app, resposta):
    nia, overlay, registros, falas = sessao
    overlay.definir_modo(True)
    editor = overlay.editor_internal
    editor.criar_card('Não apagar')
    antes = editor.plano_atual().mapa
    chamadas = []
    nia._provedor_assistido = lambda *args: chamadas.append(args) or resposta
    pedir(nia, app, PEDIDO_SUBSTITUIR)
    assert len(chamadas) == 2
    assert editor.plano_atual().mapa == antes
    assert 'Nenhum card foi alterado' in registros[-1]


def test_apagar_todos_requer_modo_e_apagar_cards_nomeados_nao_limpa_mapa(sessao, app):
    from core.controle_canvas import pede_limpar_mapa
    nia, overlay, registros, _ = sessao
    chamadas = []
    nia._provedor_assistido = lambda *args: chamadas.append(args) or '{}'
    pedir(nia, app, PEDIDO_SUBSTITUIR)
    assert not chamadas and 'pode ligar' in registros[-1]
    assert not pede_limpar_mapa('apagar os cards Pesquisa e Entrega')


# Pedido real do dono (22/11/2026): a NIA tratou "cards" como arquivos do
# Windows, rodou um Get-ChildItem e respondeu "sucesso" sem tocar no Canvas.
PEDIDO_OUTROS = ('agora apaga os outros cards, e modifique para como seu sistema '
                 'funciona e um plano de evolução')


def test_apaga_os_outros_cards_e_reconhecido_como_edicao():
    from core.assistencia_planos import reconhecer_intencao
    from core.controle_canvas import pede_limpar_mapa, pede_substituir_mapa
    assert reconhecer_intencao(PEDIDO_OUTROS) == 'EDITAR'
    assert reconhecer_intencao('modifique os cards para explicar o sistema') == 'EDITAR'
    assert pede_limpar_mapa(PEDIDO_OUTROS)
    assert pede_substituir_mapa(PEDIDO_OUTROS)
    # Nomear cards continua sem limpar o mapa inteiro.
    assert not pede_limpar_mapa('apagar os cards Pesquisa e Entrega')


def test_apaga_os_outros_cards_pede_autorizacao_antes_de_apagar(sessao, app):
    nia, overlay, registros, _ = sessao
    chamadas = []
    nia._provedor_assistido = lambda *args: chamadas.append(args) or '{}'
    pedir(nia, app, PEDIDO_OUTROS)
    assert not chamadas
    assert 'pode ligar' in registros[-1]
    assert overlay.editor_internal.plano_atual().mapa['cards']


def test_apaga_os_outros_cards_e_recria_o_plano_em_um_lote(sessao, app):
    nia, overlay, registros, _ = sessao
    overlay.definir_modo(True)
    editor = overlay.editor_internal
    raiz = editor.plano_atual().mapa['raiz_id']
    antigo = editor.criar_card('Antigo')
    editor.conectar(raiz, antigo)
    editor.selecionar(antigo)
    operacoes = [
        {'tipo': 'editar_campos', 'card_id': raiz,
         'campos': {'titulo': 'Como a NIA funciona'}},
        {'tipo': 'criar_card', 'titulo': 'Funcionamento',
         'descricao': 'Chat, voz e Canvas.', 'temp_id': 'func'},
        {'tipo': 'criar_card', 'titulo': 'Plano de evolução',
         'descricao': 'Melhorias futuras a validar.', 'temp_id': 'evo'},
        {'tipo': 'conectar', 'origem': raiz, 'destino_ref': 'func'},
        {'tipo': 'conectar', 'origem': 'func', 'destino_ref': 'evo'},
    ]
    nia._provedor_assistido = lambda *args: json.dumps({'operacoes': operacoes})
    pedir(nia, app, PEDIDO_OUTROS)
    mapa = editor.plano_atual().mapa
    assert antigo not in editor.cena.itens_cards
    titulos = {c['titulo'] for c in mapa['cards']}
    assert {'Funcionamento', 'Plano de evolução'} <= titulos
    assert 'concluída' in registros[-1] or 'concluido' in registros[-1]
