# -*- coding: utf-8 -*-
"""Descritores estáticos dos aplicativos nativos da NIA (etapa 02 da Central).

Somente metadados: nenhum módulo é importado, nenhum serviço iniciado e
nenhuma credencial lida. Fontes dinâmicas (habilidades e declarações) entram
pelas funções de sincronização do registro central.
"""
from __future__ import annotations

from core import registro_aplicativos as RA


# Chave = id do botão em ui.py::_build_dock. A ponte da Central usa essa
# coincidência para chamar exatamente o mesmo botão do dock.
_DOCK = (
    ('mute', 'Microfone ativo', 'Liga ou desliga o microfone da NIA.',
     'mute', '#00d4ff'),
    ('so_nome', 'Sempre ouvindo', 'Ativa a palavra de chamada da NIA.',
     'so_nome', '#00d4ff'),
    ('interrupt', 'Interromper', 'Interrompe a fala e a ação atual (Esc).',
     'interrupt', '#ff6b6b'),
    ('whatsapp', 'Conectar WhatsApp', 'Abre a ponte com o WhatsApp.',
     'whatsapp', '#00ff88'),
    ('remote', 'Controle remoto', 'Abre o controle remoto da NIA.',
     'remote', '#00d4ff'),
    ('webcam', 'Webcam', 'Liga ou desliga a câmera.',
     'webcam', '#00d4ff'),
    ('cowork', 'Cowork', 'Abre o programador da NIA (Cowork).',
     'cowork', '#ffb84d'),
    ('computer_use', 'Computer use', 'A NIA usa o computador sob comando.',
     'computer_use', '#00d4ff'),
    ('segundo_plano', 'Segundo plano',
     'Esconde a NIA no ícone da bandeja do sistema.',
     'segundo_plano', '#94a3b8'),
    ('central', 'Central de Aplicativos', 'Mostra ou esconde esta bandeja.',
     'menu', '#00d4ff'),
    ('system', 'Sistema e visão', 'Abre o painel de sistema e visão.',
     'system', '#94a3b8'),
    ('skill_secretaria', 'Consultar a Secretaria',
     'Abre a Secretaria ou a área para ativá-la.',
     'secretaria', '#00ff88'),
    ('skill_buscar_arquivos', 'Buscar nos arquivos',
     'Busca com fontes verificáveis nos seus arquivos.',
     'buscar_arquivos', '#00d4ff'),
    ('skill_resumo_dia', 'Preparar resumo do dia',
     'Gera o resumo local do Hoje.',
     'resumo', '#00ff88'),
)


def registrar_nativos(*, substituir=True) -> int:
    itens = [
        # Aplicativos com interface própria (janelas já existentes).
        RA.DescritorApp(id='planos', nome='Planos',
            descricao='Gerenciador local de planos e tarefas.', categoria='produtividade',
            icone='planos', cor='#00d4ff', possui_interface=True,
            janela='planos', dominio_ferramenta='planejamento'),
        RA.DescritorApp(id='agenda', nome='Agenda',
            descricao='Compromissos, tarefas e prazos.', categoria='produtividade',
            icone='agenda', cor='#00ff88', possui_interface=True,
            janela='agenda', dominio_ferramenta='agenda'),
        RA.DescritorApp(id='config', nome='Configurações',
            descricao='Aparência, voz, provedores e integrações.', categoria='sistema',
            icone='config', cor='#94a3b8', possui_interface=True,
            janela='config', dominio_ferramenta='configuracoes'),
        RA.DescritorApp(id='globo', nome='Globo',
            descricao='Terra 3D com ruas e mapas (janela própria).', categoria='conhecimento',
            icone='globo', cor='#00d4ff', possui_interface=True,
            janela='globo', dominio_ferramenta='globo'),
    ]
    # Canvas Infinito não entra: a janela é a mesma de Planos.
    for chave, nome, descricao, icone, cor in _DOCK:
        habilidade = chave.startswith('skill_')
        itens.append(RA.DescritorApp(
            id=chave, nome=nome, descricao=descricao,
            categoria='habilidades' if habilidade else 'sistema',
            tipo='habilidade' if habilidade else 'aplicativo',
            icone=icone, cor=cor, possui_interface=False,
            fixavel_no_dock=True, dominio_ferramenta='dock',
            origem='dock'))
    total = 0
    for descritor in itens:
        RA.registrar(descritor, substituir=substituir)
        total += 1
    total += RA.sincronizar_habilidades()
    total += RA.sincronizar_ferramentas()
    return total
