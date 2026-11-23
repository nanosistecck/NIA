# -*- coding: utf-8 -*-
"""Proteção de saída para publicação de conteúdo do Canvas (Prompt 06).

A política roda no aplicativo, antes de qualquer envio. Não há publicação real
conectada ao Canvas nesta etapa: destinos fora da lista de simulados são
bloqueados. Nenhum conteúdo privado entra em log.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re

_SEGREDO = re.compile(r"sk-[A-Za-z0-9_-]{10,}|api[_-]?key\s*[:=]", re.I)
_DESTINOS_SIMULADOS = ("github", "rascunho-local")
_CONFIRMACOES: dict[str, dict] = {}


class BloqueioPublicacao(Exception):
    """Conteúdo ou destino não autorizado para envio."""


def interno(caminho: str) -> bool:
    texto = str(caminho or "").replace("\\", "/")
    if not texto:
        return False
    partes = {p.lower() for p in texto.split("/")}
    if any(p in (".git", "__pycache__", ".venv-apis", "config") for p in partes):
        return True
    return os.path.basename(texto).lower() in {
        "api_keys.json", "nia.db", "jarvis.db", "credenciais.json"
    }


def tem_segredo(texto: str) -> bool:
    return bool(_SEGREDO.search(str(texto or "")))


def _hash(dados: dict) -> str:
    bruto = {k: v for k, v in dados.items() if k != "previa"}
    texto = json.dumps(bruto, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def preparar_conteudo(plano, card_ids, anexos=(), mensagem: str = "",
                      resumo_de: str | None = None) -> dict:
    """Cópia explícita dos cards escolhidos; nada é lido fora da seleção."""
    cartoes = {c.get("id"): c for c in plano.mapa.get("cards", [])}
    cards = []
    for ident in card_ids:
        cartao = cartoes.get(ident)
        if cartao is None:
            continue
        cards.append({
            "id": ident,
            "titulo": cartao.get("titulo"),
            "resumo": cartao.get("resumo"),
            "descricao": cartao.get("descricao"),
            "estado": cartao.get("estado"),
            "restrito": bool(cartao.get("restrito")),
            "financeiro": bool(cartao.get("financeiro")),
        })
    derivado = cartoes.get(resumo_de) if resumo_de else None
    payload = {
        "plano_id": plano.id,
        "cards": cards,
        "anexos": [str(a) for a in (anexos or [])],
        "mensagem": str(mensagem or ""),
        "resumo_de": resumo_de,
        "resumo_restrito": bool(derivado and
                                (derivado.get("restrito") or
                                 derivado.get("financeiro"))),
    }
    payload["previa"] = _hash(payload)
    return payload


def calcular_previa(payload: dict) -> str:
    return _hash(payload)


def validar(payload: dict, destino: str = "github") -> list[str]:
    """Devolve motivos de bloqueio, sem incluir o conteúdo bloqueado."""
    motivos: list[str] = []
    if destino not in _DESTINOS_SIMULADOS:
        motivos.append("destino de publicação não conectado ao Canvas")
    for cartao in payload.get("cards", []):
        if cartao.get("restrito") or cartao.get("financeiro"):
            motivos.append(f"card {cartao.get('id')} é restrito")
    if payload.get("resumo_restrito"):
        motivos.append("resumo derivado de card restrito")
    for anexo in payload.get("anexos", []):
        if interno(anexo):
            motivos.append("anexo interno do aplicativo")
    if tem_segredo(payload.get("mensagem", "")):
        motivos.append("segredo detectado na mensagem")
    for cartao in payload.get("cards", []):
        if tem_segredo(" ".join(str(cartao.get(k) or "")
                                for k in ("titulo", "resumo", "descricao"))):
            motivos.append("segredo detectado em card selecionado")
    return motivos


def confirmar(previa: str) -> dict:
    token = {"previa": str(previa)}
    _CONFIRMACOES[token["previa"]] = token
    return token


def publicar(payload: dict, token: dict | None, destino: str,
             enviar) -> dict:
    """Revalida tudo no envio e em cada reenvio."""
    motivos = validar(payload, destino)
    if motivos:
        raise BloqueioPublicacao("; ".join(sorted(set(motivos))))
    if not token or token.get("previa") != payload.get("previa"):
        raise BloqueioPublicacao("prévia alterada: confirme novamente")
    if calcular_previa(payload) != payload.get("previa"):
        raise BloqueioPublicacao("conteúdo alterado depois da confirmação")
    copia = copy.deepcopy(payload)
    copia.pop("previa", None)
    copia.pop("resumo_restrito", None)
    enviar(copia)
    return {"ok": True, "motivos": []}
