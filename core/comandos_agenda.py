# -*- coding: utf-8 -*-
"""Comandos da Agenda compartilhados por chat e voz.

Modulo puro: nao toca em Qt, arquivos ou rede. Devolve acoes para o NiaLive.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from core import agenda as AG
from core import assistencia_planos as AP


# Exige um termo de agenda (ou verbo de agendamento). Verbos como "exclua"
# sozinhos pertencem ao Canvas dos planos ("Exclua o card Validação").
_PEDIDO = re.compile(
    r"\b(?:agende|agendar|agenda|adicione|adicionar|crie|criar|marque|marcar|"
    r"programe|programar|compromissos?|reuni[aã]o|tarefas?|entrega|"
    r"viagem|anivers[aá]rio|consulta|revis[aã]o|pr[oó]ximo compromisso|"
    r"o que tenho|bom dia|boa tarde|boa noite|mostrar card da agenda|"
    r"preparo|prazo)\b", re.I)

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
    limpo = re.sub(r"^(?:na|\u00e0|a)\s+(?:minha\s+)?agenda\s+",
                   "", limpo, flags=re.I)
    limpo = re.sub(
        r"\s+(?:dia\s+\d{1,2}|amanh[aã]|hoje|depois de amanh[aã]|"
        r"em \d+ dias?|(?:na|no|[aà]s)\s+\d{1,2}(?::\d{2}|h\d{2})?)\b.*$",
        "", limpo, flags=re.I)
    limpo = re.sub(r"\s+(?:para|com)\s+(?:o |a )?(?:preparo|prazo).*$",
                   "", limpo, flags=re.I)
    limpo = re.sub(r"^(?:um|uma|o|a)\s+", "", limpo.strip(), flags=re.I)
    while True:
        anterior = limpo.strip()
        limpo = re.sub(r"\s+(?:para|de|da|do|no|na|com|a|o|as|os)$",
                       "", anterior, flags=re.I)
        if limpo == anterior:
            break
    return " ".join(limpo.strip(" .!?;:").split())[:120]


def _tem_data(texto: str) -> bool:
    n = _normalizar(texto)
    return bool(re.search(
        r"\b(?:amanh[aã]|hoje|depois de amanh[aã]|em \d+ dias?|"
        r"\d{1,2}\s*(?:h|:)\s*\d{0,2}|\d{1,2}/\d{1,2})\b", n))


_PALAVRAS_VAZIAS = {
    "para", "como", "com", "sobre", "mude", "mover", "conclua", "cancelar",
    "exclua", "excluir", "remova", "remover", "preparo", "minutos", "minuto",
    "alterar", "esta", "esse", "esse", "qual", "quais", "todos", "todas",
}


def _tokens(texto: str) -> set:
    return {p for p in re.split(r"\W+", _normalizar(texto))
            if len(p) >= 4 and p not in _PALAVRAS_VAZIAS}


def tem_referencia(texto: str) -> bool:
    """O dono citou titulo, data ou assunto? Evita cair no proximo as cegas."""
    n = _normalizar(texto)
    if re.search(r"\b(?:hoje|amanha|depois de amanha|\d{1,2}/\d{1,2}|\d{1,2}h)\b", n):
        return True
    tokens = _tokens(texto)
    for item in AG.listar():
        if _tokens(item.get("titulo") or "") & tokens:
            return True
    return bool(re.search(r"\b(?:de|da|do|com|sobre)\s+[a-z]{4,}\b", n))


def contar_casados(texto: str, itens: list) -> int:
    """Quantos itens casam com titulo/data ditos (para detectar ambiguidade)."""
    n = _normalizar(texto)
    if re.search(r"\b(?:hoje|amanha|depois de amanha|\d{1,2}/\d{1,2})\b", n):
        data = (date.today().isoformat() if "hoje" in n else
                (date.today() + timedelta(days=1)).isoformat()
                if "amanha" in n else "")
        if data:
            return sum(1 for i in itens
                       if str(i.get("inicio") or "").startswith(data))
    tokens = _tokens(texto)
    return sum(1 for i in itens if _tokens(i.get("titulo") or "") & tokens)


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
        tokens = _tokens(texto)
        for item in itens:
            titulo_tokens = _tokens(item.get("titulo") or "")
            if titulo_tokens and titulo_tokens & tokens:
                casados.append(item)
    if len(casados) == 1:
        return casados[0]
    if len(casados) > 1:
        return None
    if tem_referencia(texto):
        return None   # citou algo que nao existe: nao mexer em outro
    return proximo_item


def _periodo(texto: str) -> str | None:
    n = _normalizar(texto)
    if "proximo mes" in n:
        return "proximo_mes"
    if "amanha" in n:
        return "amanha"
    if "hoje" in n:
        return "hoje"
    if "proxima semana" in n or "próxima semana" in n:
        return "proxima_semana"
    if "semana" in n:
        return "semana"
    return None


def processar(texto: str, agora=None) -> dict:
    n = _normalizar(texto)
    # "Crie um card Entrega" e "Exclua o card Validação" pertencem ao Canvas
    # dos planos, mesmo contendo palavras que também são tipos de agenda.
    if re.search(r"\bcard\b", n) and not re.search(
            r"card (?:da|de) (?:agenda|compromisso)", n):
        return {"tratado": False}
    if not _PEDIDO.search(n):
        return {"tratado": False}

    if re.search(r"\bbom dia\b|\bboa tarde\b|\bboa noite\b", n):
        return {"tratado": True, "acao": "saudacao"}
    if re.search(r"mostrar card da agenda|mostre o card da agenda", n):
        return {"tratado": True, "acao": "mostrar_card"}
    if re.search(r"pr[oó]ximo compromisso|pr[oó]xima tarefa", n):
        return {"tratado": True, "acao": "proximo"}
    if re.search(r"o que tenho|quais compromissos|mostre (?:os |meus )?compromissos|"
                 r"liste (?:os |meus )?compromissos|minha agenda", n):
        return {"tratado": True, "acao": "listar",
                "periodo": _periodo(texto)}

    def valor_apos_para():
        encontrado = re.search(r"\bpara\s+(.+?)\s*[.!?]?$",
                               str(texto or ""), re.I)
        return encontrado.group(1).strip(' .!?;"“”') if encontrado else ""

    if re.search(r"\brenomeie|\brenomear|mude (?:o )?titulo|altere (?:o )?titulo", n):
        return {"tratado": True, "acao": "editar",
                "campos": {"titulo": valor_apos_para()}}

    if re.search(r"\b(?:mude|altere|defina)\s+(?:o\s+)?tipo\b", n):
        bruto = valor_apos_para()
        tipo = next((t for t in AG.TIPOS
                     if _normalizar(t) == _normalizar(bruto)), bruto)
        return {"tratado": True, "acao": "editar", "campos": {"tipo": tipo}}

    if re.search(r"\b(?:mude|altere|defina|acrescente)\s+(?:as\s+|a\s+)?"
                 r"(?:notas?|descricao)\b", n):
        return {"tratado": True, "acao": "editar",
                "campos": {"notas": valor_apos_para()}}

    if re.search(r"\breabra|\breabrir|volte a ser pendente", n):
        return {"tratado": True, "acao": "editar",
                "campos": {"estado": "pendente"}}

    if re.search(r"mude o preparo|altere o preparo|preparo.*para \d+", n):
        encontrado = re.search(r"(\d+)\s*(?:minutos?|min)\b", n)
        minutos = int(encontrado.group(1)) if encontrado else 30
        return {"tratado": True, "acao": "editar",
                "campos": {"preparo_minutos": minutos}}

    if re.search(r"\b(?:mude|mover|reagende|reagendar|adiar)\b", n) and _tem_data(n):
        inicio = AG.interpretar(texto, agora=agora)
        if inicio:
            return {"tratado": True, "acao": "mover", "inicio": inicio}

    if re.search(r"\b(?:exclua|excluir|remova|remover|apague)\b", n):
        return {"tratado": True, "acao": "excluir"}

    if re.search(r"\b(?:conclua|concluir|finalize|cancele|cancelar)\b", n):
        acao = "concluir" if re.search(r"conclua|concluir|finalize", n) else "cancelar"
        return {"tratado": True, "acao": acao}

    direto_na_agenda = bool(re.search(
        r"\b(?:agende|agendar|adicione|adicionar|crie|criar|programe|programar|"
        r"marque|marcar)\s+(?:na|\u00e0|a)\s+(?:minha\s+)?agenda\b", n))
    pedido_criar = bool(re.search(
        r"\b(?:agende|agendar|adicione|adicionar|crie|criar|programe|"
        r"programar|marque|marcar)\b", n) and re.search(
            r"\b(?:compromisso|reuni[aã]o|tarefa|entrega|viagem|"
            r"anivers[aá]rio|preparo|prazo)\b", n))
    if direto_na_agenda or pedido_criar:
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
