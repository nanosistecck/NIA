# -*- coding: utf-8 -*-
"""Agenda da NIA: compromissos com data, hora e preparo.

Persistencia propria, atômica e isolada por perfil, fora do repositorio.
Nenhuma rede, API externa ou dependencia de planos/lembretes do Canvas.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from core import lembretes as L

ESTADOS = ("pendente", "concluido", "cancelado")
TIPOS = ("reuniao", "chamada", "tarefa", "entrega", "viagem", "aniversario", "outro")

PREPARO_PADRAO = {
    "reuniao": 15, "chamada": 15, "tarefa": 30, "entrega": 30,
    "viagem": 60, "aniversario": 120, "outro": 30,
}

_TRAVA = threading.RLock()


def caminho_padrao() -> Path:
    externo = os.environ.get("NIA_AGENDA")
    if externo:
        return Path(externo).expanduser()
    return Path.home() / ".nia" / "agenda.json"


def perfil_atual() -> str:
    return str(os.environ.get("NIA_PERFIL") or "principal")


def novo_id() -> str:
    return uuid.uuid4().hex


def normalizar(texto: str) -> str:
    import unicodedata
    bruto = unicodedata.normalize("NFKD", str(texto or "")).casefold()
    return "".join(c for c in bruto if not unicodedata.combining(c)).strip()


def sugerir_preparo(tipo: str) -> int:
    return PREPARO_PADRAO.get(str(tipo or "").strip().lower(), 30)


def _carregar_todos() -> dict:
    try:
        dados = json.loads(caminho_padrao().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def carregar(perfil: str | None = None) -> dict:
    atual = _carregar_todos().get(perfil or perfil_atual())
    if isinstance(atual, dict) and isinstance(atual.get("itens"), list):
        return atual
    return {"itens": []}


def salvar(itens: list, perfil: str | None = None) -> None:
    with _TRAVA:
        caminho = caminho_padrao()
        dados = _carregar_todos()
        dados[perfil or perfil_atual()] = {"itens": list(itens or [])}
        caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = caminho.with_suffix(".tmp")
        temporario.write_text(
            json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        temporario.replace(caminho)


def _agora(agora=None) -> datetime:
    if agora is None:
        return datetime.now(timezone.utc)
    if isinstance(agora, datetime):
        valor = agora
    else:
        valor = datetime.fromisoformat(str(agora))
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    return valor


def _encontrar(item_id: str) -> dict:
    for item in carregar()["itens"]:
        if item.get("id") == item_id:
            return item
    raise ValueError("compromisso inexistente")


def _gravar_item(item: dict) -> None:
    itens = carregar()["itens"]
    for posicao, atual in enumerate(itens):
        if atual.get("id") == item["id"]:
            itens[posicao] = item
            break
    salvar(itens)


def criar(titulo: str, inicio: str, tipo: str = "outro",
          preparo_minutos: int | None = None, fim: str | None = None,
          notas: str = "") -> dict:
    titulo = str(titulo or "").strip()
    if not titulo:
        raise ValueError("titulo obrigatorio")
    try:
        datetime.fromisoformat(str(inicio))
    except (TypeError, ValueError):
        raise ValueError("data e hora invalidas")
    tipo = str(tipo or "outro").strip().lower()
    if tipo not in TIPOS:
        tipo = "outro"
    try:
        preparo = int(preparo_minutos) if preparo_minutos is not None else sugerir_preparo(tipo)
    except (TypeError, ValueError):
        preparo = sugerir_preparo(tipo)
    agora = datetime.now(timezone.utc).isoformat()
    item = {
        "id": novo_id(), "titulo": titulo, "inicio": str(inicio),
        "fim": str(fim) if fim else None, "tipo": tipo,
        "preparo_minutos": max(0, preparo), "estado": "pendente",
        "notas": str(notas or ""), "criado_em": agora, "atualizado_em": agora,
    }
    salvar(carregar()["itens"] + [item])
    return item


def editar(item_id: str, mudancas: dict) -> dict:
    item = _encontrar(item_id)
    permitidas = {"titulo", "inicio", "fim", "tipo", "preparo_minutos", "notas", "estado"}
    for chave, valor in (mudancas or {}).items():
        if chave in permitidas:
            item[chave] = valor
    if item.get("estado") not in ESTADOS:
        item["estado"] = "pendente"
    item["atualizado_em"] = datetime.now(timezone.utc).isoformat()
    _gravar_item(item)
    return item


def mover(item_id: str, inicio: str) -> dict:
    return editar(item_id, {"inicio": inicio})


def concluir(item_id: str) -> dict:
    return editar(item_id, {"estado": "concluido"})


def cancelar(item_id: str) -> dict:
    return editar(item_id, {"estado": "cancelado"})


def listar() -> list:
    return list(carregar()["itens"])


def proximo(agora=None) -> dict | None:
    referencia = _agora(agora)
    candidatos = []
    for item in listar():
        if item.get("estado") != "pendente":
            continue
        try:
            inicio = _agora(item.get("inicio"))
        except (TypeError, ValueError):
            continue
        if inicio >= referencia:
            candidatos.append((inicio, item))
    return min(candidatos, key=lambda par: par[0])[1] if candidatos else None


def interpretar(texto: str, agora=None, fuso: str = "America/Sao_Paulo") -> str | None:
    horario, _mensagem = L.interpretar(texto, fuso=fuso, agora=_agora(agora))
    if not horario:
        return None
    try:
        # O parser de lembretes devolve UTC; a Agenda guarda e fala no fuso
        # local do dono, senao "15h" viraria "18h" no card e na voz.
        local = datetime.fromisoformat(horario).astimezone(ZoneInfo(fuso))
        return local.isoformat()
    except Exception:
        return horario


def resumo_proximo(agora=None) -> str:
    item = proximo(agora)
    if item is None:
        return "Nenhum compromisso próximo."
    inicio = _agora(item["inicio"])
    preparo = inicio - timedelta(minutes=int(item.get("preparo_minutos") or 0))
    return (f'Próximo compromisso: {item["titulo"]} às '
            f'{inicio:%H:%M}. Preparar às {preparo:%H:%M}.')
