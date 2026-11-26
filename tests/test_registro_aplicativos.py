# -*- coding: utf-8 -*-
"""Registro central: metadados válidos, dedupe, descoberta e carga sob demanda."""
import sys

import pytest

from core import registro_aplicativos as RA


@pytest.fixture(autouse=True)
def registro_isolado(monkeypatch):
    monkeypatch.setattr(RA, '_DESCRITORS', {})
    monkeypatch.setattr(RA, '_PROVEDOR_FERRAMENTAS', None)
    monkeypatch.setattr(RA, '_PROVEDOR_DISPONIBILIDADE', None)
    yield


def desc(id='app_teste', **kwargs):
    base = dict(id=id, nome='Aplicativo de Teste',
                descricao='Faz coisas úteis', categoria='produtividade',
                icone='system', cor='#00d4ff')
    base.update(kwargs)
    return RA.DescritorApp(**base)


def test_registro_valido_e_metadados_completos():
    RA.registrar(desc())
    item = RA.por_id('app_teste')
    assert item.nome == 'Aplicativo de Teste'
    dados = item.como_dict()
    for chave in ('id', 'nome', 'descricao', 'categoria', 'tipo', 'icone', 'cor',
                  'disponivel', 'possui_interface', 'executavel_por_nia',
                  'fixavel_no_dock', 'visivel_na_central',
                  'carregamento_sob_demanda', 'dominio_ferramenta', 'acoes',
                  'permissoes', 'palavras_chave'):
        assert chave in dados


def test_duplicado_e_metadados_invalidos():
    RA.registrar(desc())
    with pytest.raises(ValueError, match='duplicado'):
        RA.registrar(desc())
    RA.registrar(desc(), substituir=True)
    with pytest.raises(ValueError):
        RA.registrar(desc(id='MAIUSCULO'))
    with pytest.raises(ValueError):
        RA.registrar(desc(id='outra', categoria='inexistente'))
    with pytest.raises(ValueError):
        RA.registrar(desc(id='outra', cor='azul'))
    with pytest.raises(ValueError):
        RA.registrar(desc(id='outra', carregador='os:system'))
    with pytest.raises(TypeError):
        RA.registrar({'id': 'x'})


def test_desabilitado_sem_interface_e_ferramenta_temporaria():
    RA.registrar(desc(id='off', disponivel=False))
    RA.registrar(desc(id='skill', tipo='habilidade', possui_interface=False,
                      fixavel_no_dock=False, categoria='habilidades'))
    RA.registrar(desc(id='config', exigir_config=True, chave_config='api'))
    assert RA.disponibilidade('off').pronta is False
    assert 'desabilitado' in RA.disponibilidade('off').motivo
    assert RA.disponibilidade('skill').pronta is True
    assert RA.por_id('skill').possui_interface is False
    assert RA.por_id('config').exigir_config is True
    assert RA.disponibilidade('inexistente').pronta is False


def test_busca_local_ignora_acento_e_categoria():
    RA.registrar(desc(id='solar', nome='Pesquisa Solar',
                      descricao='Investiga energia solar', categoria='pesquisa',
                      palavras_chave=('energia', 'fotovoltaico')))
    RA.registrar(desc(id='outro', nome='Outro', categoria='sistema'))
    assert [i.id for i in RA.buscar('SOLAR')] == ['solar']
    assert [i.id for i in RA.buscar('solar', 'pesquisa')] == ['solar']
    assert [i.id for i in RA.buscar('solar', 'sistema')] == []
    assert [i.id for i in RA.buscar('energia')] == ['solar']
    assert [i.id for i in RA.buscar('', 'favoritos', favoritos={'solar'})] == ['solar']
    assert 'habilidades' not in RA.categorias()


def test_carga_sob_demanda_nao_importa_no_cadastro():
    RA.registrar(desc(id='preguicoso',
                      carregador='core.janelas_ferramentas:GerenciadorJanelas'))
    assert callable(RA.carregar(RA.por_id('preguicoso')))
    funcao = RA.carregar(RA.por_id('preguicoso'))
    assert callable(funcao)
    assert RA.carregar(desc()) is None


def test_sync_de_catalogo_e_declaracoes_sem_importar_main():
    total = RA.sincronizar_habilidades()
    assert total >= 3
    hab = RA.por_id('hab_secretaria')
    assert hab is not None and hab.tipo == 'habilidade' and hab.possui_interface is False
    RA.definir_provedor_ferramentas(lambda: [
        {'name': 'pesquisa', 'description': 'Pesquisa agrupada'},
        {'name': 'biblioteca', 'description': 'Biblioteca agrupada'},
    ])
    assert RA.sincronizar_ferramentas() == 2
    assert RA.por_id('tool_pesquisa').dominio_ferramenta == 'pesquisa'
    # Atalhos de modelo não poluem a bandeja da Central.
    assert RA.por_id('tool_pesquisa').visivel_na_central is False
    assert RA.por_id('tool_pesquisa').fixavel_no_dock is False
    assert 'tool_pesquisa' not in [i.id for i in RA.buscar()]
    assert RA.sincronizar_ferramentas() == 2  # idempotente (substitui)


def test_busca_inclui_fixavel_mesmo_oculto_da_central():
    RA.registrar(desc(id='oculto', nome='App Oculto',
                      visivel_na_central=False, fixavel_no_dock=True))
    RA.registrar(desc(id='habilidade', nome='Habilidade',
                      tipo='habilidade', fixavel_no_dock=False,
                      visivel_na_central=True))
    assert [i.id for i in RA.buscar()] == ['oculto']


def test_provedor_de_disponibilidade_e_respeitado():
    RA.registrar(desc(id='nuvem', exigir_config=True))
    RA.definir_provedor_disponibilidade(
        lambda d: RA.DisponibilidadeApp(False, 'Configure a nuvem'))
    estado = RA.disponibilidade('nuvem')
    assert estado.pronta is False and 'Configure' in estado.motivo
