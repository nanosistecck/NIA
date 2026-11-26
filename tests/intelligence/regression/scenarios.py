# -*- coding: utf-8 -*-
"""IDs de cenários que já falharam e devem voltar sempre na regressão."""
from __future__ import annotations

REGRESSAO: tuple[str, ...] = ()


def registrar(identificador: str) -> None:
    if identificador not in REGRESSAO:
        REGRESSAO += (identificador,)
