# -*- coding: utf-8 -*-
"""Comandos de lembrete compartilhados por chat e voz (Prompt 06)."""
from __future__ import annotations

import re
from datetime import datetime

from core import assistencia_planos as AP
from core import lembretes as L

_PEDIDO = re.compile(
    r"lembr|me avise|me avisar|revisar|adiar|concluir lembrete|cancelar lembrete")


def assunto_de(texto: str, titulo_card: str = "") -> str:
    n = AP.normalizar(texto)
    limpo = re.sub(
        r"^(?:me lembra de|me lembre de|lembrete de|lembrete para|lembra de|"
        r"crie um lembrete para|criar lembrete para|me avise de|me avise sobre)\s*",
        "", n)
    limpo = re.sub(
        r"^(?:amanha|hoje|em \d+ dias?)\s*(?:as \d{1,2}(?::\d{2}|h\d{2})?)?\s*",
        "", limpo)
    limpo = re.sub(r"\s+(?:me lembra|lembra|lembrete|por favor)\b.*$", "", limpo)
    limpo = limpo.strip(" .!?;:")
    return limpo or titulo_card or "Revisar"


def processar(texto: str, origem: str, contexto: dict,
              agora: datetime | None = None,
              fuso: str = "America/Sao_Paulo") -> dict:
    """Reconhece o pedido e devolve a ação; não toca em arquivos nem Qt."""
    n = AP.normalizar(texto)
    if not _PEDIDO.search(n):
        return {"tratado": False}
    plano_id = contexto.get("plano_id")
    card_id = contexto.get("card_id")
    titulo_card = str((contexto.get("card") or {}).get("titulo") or "")
    if "cancelar lembrete" in n or "cancelar o lembrete" in n:
        return {"tratado": True, "acao": "cancelar"}
    if "concluir lembrete" in n or "concluir o lembrete" in n:
        return {"tratado": True, "acao": "concluir"}
    if "adiar" in n:
        horario, mensagem = L.interpretar(texto, fuso=fuso, agora=agora)
        return {"tratado": True, "acao": "adiar", "horario": horario,
                "resposta": mensagem}
    if not re.search(r"me lembra|me lembre|lembrete|me avise|me avisar|revisar", n):
        return {"tratado": False}
    if not plano_id:
        return {"tratado": True, "acao": "sem_plano",
                "resposta": "Abra um plano para definir um lembrete."}
    if not card_id and re.search(r"este|esse|this", n):
        return {"tratado": True, "acao": "sem_card",
                "resposta": "Indique o card ou plano do lembrete."}
    horario, mensagem = L.interpretar(texto, fuso=fuso, agora=agora)
    if horario is None:
        return {"tratado": True, "acao": "pendente", "resposta": mensagem,
                "plano_id": plano_id, "card_id": card_id,
                "assunto": assunto_de(texto, titulo_card)}
    return {"tratado": True, "acao": "criar", "horario": horario,
            "plano_id": plano_id, "card_id": card_id,
            "assunto": assunto_de(texto, titulo_card), "resposta": mensagem}
