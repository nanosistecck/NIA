# -*- coding: utf-8 -*-
"""Comandos da Agenda compartilhados por chat e voz.

Modulo puro: nao toca em Qt, arquivos ou rede. Devolve acoes para o NiaLive.
"""
from __future__ import annotations

import re
from datetime import datetime

from core import agenda as AG
from core import assistencia_planos as AP


_PEDIDO = re.compile(
    r"\b(?:agende|agendar|agenda|adicione|adicionar|crie|criar|marque|marcar|"
    r"programe|programar|compromisso|compromissos|reuni[aã]o|tarefa|entrega|"
    r"viagem|anivers[aá]rio|pr[oó]ximo compromisso|o que tenho|bom dia|"
    r"mostrar card da agenda|conclua|cancele|mude|alterar|preparo)\b", re.I)

_VERBOS_CRIAR = re.compile(
    r"^\s*(?:nia[, ]+)?(?:agende|agendar|adicione|adicionar|crie|criar|"
    r"programe|programar|marque|marcar)\s+", re.I)

_TIPOS = (
    ("reunião|reuniao|encontro", "reuniao"),
    ("chamada|liga[cç][aã]o|call", "chamada"),
    ("tarefa", "tarefa"),
    ("entrega|prazo", "entrega"),
    ("viagem|passagem|voo", "viagem"),
    ("anivers[aá]rio", "aniversario"),
)


def _normalizar(texto: str) -> str:
    return AP.normalizar(texto)


def _tipo(texto: str) -> str:
    n = _normalizar(texto)
    for padrao, tipo in _TIPOS:
        if re.search(padrao, n):
            return tipo
    return "outro"


def _titulo(texto: str) -> str:
    limpo = _VERBOS_CRIAR.sub("", str(texto or "").strip())
    limpo = re.sub(
        r"\s+(?:amanh[aã]|hoje|depois de amanh[aã]|em \d+ dias?|"
        r"(?:na|no|[aà]s)\s+\d{1,2}(?::\d{2}|h\d{2})?)\b.*$",
        "", limpo, flags=re.I)
    limpo = re.sub(r"\s+(?:para|com)\s+(?:o |a )?(?:preparo|prazo).*$",
                   "", limpo, flags=re.I)
    limpo = re.sub(r"^(?:um|uma|o|a)\s+", "", limpo.strip(), flags=re.I)
    return " ".join(limpo.strip(" .!?;:").split())[:120]


def _tem_data(texto: str) -> bool:
    n = _normalizar(texto)
    return bool(re.search(
        r"\b(?:amanh[aã]|hoje|depois de amanh[aã]|em \d+ dias?|"
        r"\d{1,2}\s*(?:h|:)\s*\d{0,2}|\d{1,2}/\d{1,2})\b", n))


def resolver_alvo(texto: str, itens: list, proximo_item: dict | None,
                  agora=None) -> dict | None:
    """Titulo/data ditos; senao proximo; se ambiguo, None (Perguntar)."""
    n = _normalizar(texto)
    if not itens:
        return None
    casados = []
    if re.search(r"\b(?:amanh[aã]|hoje|depois de amanh[aã])\b", n):
        try:
            referencia = AG._agora(agora)
            alvo_data = (referencia.date().strftime("%Y-%m-%d") if "hoje" in n
                         else None)
            if alvo_data is None and "amanha" in n:
                from datetime import timedelta
                alvo_data = (referencia.date() + timedelta(days=1)).isoformat()
            if alvo_data:
                casados = [i for i in itens
                           if str(i.get("inicio") or "").startswith(alvo_data)]
        except Exception:
            casados = []
    if not casados:
        for item in itens:
            titulo = _normalizar(item.get("titulo") or "")
            if len(titulo) >= 4 and titulo in n:
                casados.append(item)
    if len(casados) == 1:
        return casados[0]
    if len(casados) > 1:
        return None
    return proximo_item


def processar(texto: str, agora=None) -> dict:
    n = _normalizar(texto)
    if not _PEDIDO.search(n):
        return {"tratado": False}

    if re.search(r"\bbom dia\b", n):
        return {"tratado": True, "acao": "saudacao"}
    if re.search(r"mostrar card da agenda|mostre o card da agenda", n):
        return {"tratado": True, "acao": "mostrar_card"}
    if re.search(r"pr[oó]ximo compromisso|pr[oó]xima tarefa", n):
        return {"tratado": True, "acao": "proximo"}
    if re.search(r"o que tenho|quais compromissos|mostre (?:os |meus )?compromissos|"
                 r"liste (?:os |meus )?compromissos|minha agenda", n):
        return {"tratado": True, "acao": "listar"}

    if re.search(r"mude o preparo|altere o preparo|preparo.*para \d+", n):
        encontrado = re.search(r"(\d+)\s*(?:minutos?|min)\b", n)
        minutos = int(encontrado.group(1)) if encontrado else 30
        return {"tratado": True, "acao": "editar",
                "campos": {"preparo_minutos": minutos}}

    if re.search(r"\b(?:mude|mover|reagende|reagendar|adiar)\b", n) and _tem_data(n):
        inicio = AG.interpretar(texto, agora=agora)
        if inicio:
            return {"tratado": True, "acao": "mover", "inicio": inicio}

    if re.search(r"\b(?:conclua|concluir|finalize|cancele|cancelar)\b", n):
        acao = "concluir" if re.search(r"conclua|concluir|finalize", n) else "cancelar"
        return {"tratado": True, "acao": acao}

    if re.search(r"\b(?:agende|agendar|adicione|adicionar|crie|criar|programe|"
                 r"programar|marque|marcar)\b", n) and re.search(
                     r"\b(?:compromisso|reuni[aã]o|tarefa|entrega|viagem|"
                     r"anivers[aá]rio|preparo|prazo)\b", n):
        if not _tem_data(n):
            return {"tratado": True, "acao": "pendente",
                    "resposta": "Informe a data e a hora do compromisso."}
        inicio = AG.interpretar(texto, agora=agora)
        if not inicio:
            return {"tratado": True, "acao": "pendente",
                    "resposta": "Informe a data e a hora do compromisso."}
        return {"tratado": True, "acao": "criar", "titulo": _titulo(texto),
                "inicio": inicio, "tipo": _tipo(texto)}

    return {"tratado": False}
