# -*- coding: utf-8 -*-
"""Descritores estáticos dos aplicativos nativos da NIA (etapa 02 da Central).

Somente metadados: nenhum módulo é importado, nenhum serviço iniciado e
nenhuma credencial lida. Fontes dinâmicas (habilidades e declarações) entram
pelas funções de sincronização do registro central.
"""
from __future__ import annotations

from core import registro_aplicativos as RA


def registrar_nativos(*, substituir=True) -> int:
    itens = [
        # Aplicativos com interface própria (janelas já existentes).
        RA.DescritorApp(id='canvas', nome='Canvas Infinito',
            descricao='Mapas, planos e diagramas no Canvas.', categoria='criacao',
            icone='canvas', cor='#00d4ff', possui_interface=True,
            janela='planos', dominio_ferramenta='planejamento'),
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
        # Controles do dock (microfone/interromper) NÃO entram na Central:
        # são ações de contexto, já acessíveis no dock e nas configurações.
    ]
    total = 0
    for descritor in itens:
        RA.registrar(descritor, substituir=substituir)
        total += 1
    total += RA.sincronizar_habilidades()
    total += RA.sincronizar_ferramentas()
    return total
