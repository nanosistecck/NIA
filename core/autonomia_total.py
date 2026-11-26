# -*- coding: utf-8 -*-
"""Modo de autonomia total da NIA.

Quando ativo (padrão, por decisão do dono), nenhuma ferramenta pede
confirmação interativa. Validação de esquema, política e escopo continua
sendo aplicada — apenas o prompt ao usuário é eliminado.

Opt-out: definir `NIA_MODO_LIVRE=0` no ambiente.
"""
from __future__ import annotations

import os

from core import permissoes_ferramentas as PF

_DESLIGADO = frozenset(('0', 'false', 'no', 'nao', 'off'))


def ativado() -> bool:
    return str(os.environ.get('NIA_MODO_LIVRE', '1')).strip().lower() not in _DESLIGADO


def autorizar(nome: str, argumentos: dict, escopos: tuple) -> str:
    """Emite consentimento interno sem exibir prévia ou dialogar."""
    previa = PF.preparar(nome, argumentos, escopos)
    return PF.confirmar(previa, confirmado=True)
