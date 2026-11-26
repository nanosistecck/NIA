# -*- coding: utf-8 -*-
"""Integração com catálogo, dock e SDK sem criar executor paralelo (F11)."""
from __future__ import annotations

CAPACIDADES = (
    'aprendizado.avaliar',
    'aprendizado.pesquisar',
    'aprendizado.demonstrar',
    'aprendizado.colaborar',
    'aprendizado.corrigir',
    'aprendizado.executar',
    'aprendizado.consultar',
)


def registrar_no_catalogo() -> None:
    """Registra capacidades declarativas no catálogo único da NIA."""
    from core import catalogo_habilidades as CH  # noqa: PLC0415

    if CH.por_id('aprendizado_adaptativo') is not None:
        return

    def executar(termo: str) -> CH.Resultado:
        # A abertura da janela acontece pelo GerenciadorJanelas do dock.
        return CH.Resultado(True, 'Central de Aprendizado registrada: ' + str(termo)[:60])

    hab = CH.Habilidade(
        id='aprendizado_adaptativo',
        nome='Aprendizado Adaptativo',
        descricao='Avalia lacunas, aprende e reutiliza procedimentos declarativos.',
        exemplo='abrir central de aprendizado',
        acao='abrir_aprendizado',
        versao='1.0.0',
        api=1,
        capacidades=CAPACIDADES,
        permissoes=('aprendizado:ler',),
        agendavel=False,
        aliases=('central de aprendizado', 'aprendizado adaptativo'))
    CH.registrar_modulo(hab, executar)


def manifesto() -> dict:
    """Manifesto compatível com `core.plugin_sdk` (somente metadados)."""
    from core import plugin_sdk as PS  # noqa: PLC0415
    dados = PS.manifesto_padrao()
    dados.update({'id': 'aprendizado_adaptativo',
                  'nome': 'Motor de Aprendizado Adaptativo',
                  'imports': [],
                  'capacidades': list(CAPACIDADES)})
    return dados
