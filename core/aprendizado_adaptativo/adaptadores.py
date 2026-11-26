# -*- coding: utf-8 -*-
"""Adaptadores para os serviços reais existentes (sem duplicar motores)."""
from __future__ import annotations

from typing import Callable

from core.aprendizado_adaptativo.avaliador import AvaliadorCapacidade


def buscador_web_real(consulta: str) -> list[dict]:
    """Adaptador sobre `actions.web_search` (rede real sujeita a política).

    Nunca é chamado automaticamente em repouso; o orquestrador decide quando
    uma lacuna autorizada justifica a chamada.
    """
    from actions import web_search as WS  # noqa: PLC0415
    from core.aprendizado_adaptativo import contratos as CT  # noqa: PLC0415
    try:
        texto = WS.web_search({'query': str(consulta), 'mode': 'research'})
    except Exception:
        return []
    if not isinstance(texto, str) or not texto or texto.startswith('Search failed'):
        return []
    import re  # noqa: PLC0415
    urls = re.findall(r'https?://[^\s)\]]+', texto)[:8]
    fontes = []
    for url in urls or ['']:
        fontes.append({'url': url, 'titulo': 'Pesquisa externa',
                       'trecho': texto[:4000], 'consultado_em': CT.agora()})
    return fontes


def construir_avaliador(*, aprendizado=None, evidencias: dict | None = None,
                        permitido: Callable[[str], bool] | None = None,
                        **opcoes) -> AvaliadorCapacidade:
    """Monta o avaliador sobre `core.aprendizado.Aprendizado`.

    A política real de execução continua em `capability_gateway` e
    `permissoes_ferramentas`; aqui apenas se avalia disponibilidade.
    """
    if aprendizado is None:
        from core import aprendizado as AP  # noqa: PLC0415
        aprendizado = AP.Aprendizado()

    def resolver(texto: str):
        try:
            return aprendizado.resolver(texto) or None
        except Exception:
            return None

    return AvaliadorCapacidade(
        resolver=resolver,
        evidencias=evidencias or {},
        permitido=permitido or (lambda capacidade: True),
        **opcoes)
