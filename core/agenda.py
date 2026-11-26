# -*- coding: utf-8 -*-
"""Agenda da NIA: compromissos com data, hora e preparo.

Persistencia propria, atômica e isolada por perfil, fora do repositorio.
Nenhuma rede, API externa ou dependencia de planos/lembretes do Canvas.
"""
from __future__ import annotations

import json
import os
import re
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
        raise ValueError("tipo de compromisso invalido")
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
        if chave not in permitidas:
            continue
        if chave == "titulo" and not str(valor or "").strip():
            raise ValueError("titulo obrigatorio")
        if chave in ("inicio", "fim") and valor is not None:
            try:
                datetime.fromisoformat(str(valor))
            except (TypeError, ValueError):
                raise ValueError("data e hora invalidas")
        if chave == "tipo" and str(valor or "").strip().lower() not in TIPOS:
            raise ValueError("tipo de compromisso invalido")
        if chave == "estado" and valor not in ESTADOS:
            raise ValueError("estado invalido")
        item[chave] = (valor.strip() if chave in ("titulo", "notas") and valor is not None
                       else str(valor).strip().lower() if chave == "tipo" else valor)
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


def reabrir(item_id: str) -> dict:
    return editar(item_id, {"estado": "pendente"})


def excluir(item_id: str) -> None:
    """Remove o compromisso do perfil atual, sem tocar nos demais."""
    itens = [i for i in carregar()["itens"] if i.get("id") != item_id]
    salvar(itens)


def filtrar_por_periodo(itens: list, periodo: str | None, agora=None) -> list:
    """Filtra por hoje/amanha/proximo mes; None devolve todos."""
    if not periodo:
        return list(itens or [])
    referencia = _agora(agora)
    if hasattr(referencia, "astimezone"):
        try:
            referencia = referencia.astimezone(ZoneInfo("America/Sao_Paulo"))
        except Exception:
            pass
    selecionados = []
    for item in itens or []:
        try:
            inicio = _agora(item.get("inicio"))
            if hasattr(inicio, "astimezone"):
                inicio = inicio.astimezone(ZoneInfo("America/Sao_Paulo"))
        except (TypeError, ValueError):
            continue
        if periodo == "hoje" and inicio.date() == referencia.date():
            selecionados.append(item)
        elif periodo == "amanha" and inicio.date() == referencia.date() + timedelta(days=1):
            selecionados.append(item)
        elif periodo == "proximo_mes" and (inicio.year, inicio.month) == (
                (referencia.year + (referencia.month // 12),
                 referencia.month % 12 + 1)):
            selecionados.append(item)
        elif periodo == "semana" and 0 <= (inicio.date() - referencia.date()).days <= 7:
            selecionados.append(item)
        elif periodo == "proxima_semana":
            proxima_segunda = referencia.date() + timedelta(
                days=7 - referencia.weekday())
            fim = proxima_segunda + timedelta(days=6)
            if proxima_segunda <= inicio.date() <= fim:
                selecionados.append(item)
    return selecionados


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
    n = normalizar(texto)
    dia_dito = re.search(r"\bdia\s+(\d{1,2})\b", n)
    if dia_dito and "amanha" not in n and "hoje" not in n:
        hora_dita = re.search(r"\bas\s+(\d{1,2})(?::(\d{2})|h(\d{2}))?\b", n)
        if not hora_dita:
            hora_dita = re.search(r"\b(\d{1,2})h(\d{2})?\b", n)
        if not hora_dita:
            return None
        referencia = _agora(agora)
        dia = int(dia_dito.group(1))
        horas = int(hora_dita.group(1))
        minutos = 0
        for grupo in hora_dita.groups()[1:]:
            if grupo:
                minutos = int(grupo)
                break
        if not 1 <= dia <= 31 or horas > 23 or minutos > 59:
            return None
        ano, mes = referencia.year, referencia.month
        if dia < referencia.day:
            mes += 1
            if mes > 12:
                mes, ano = 1, ano + 1
        try:
            zona = ZoneInfo(fuso)
            momento = datetime(ano, mes, dia, horas, minutos, tzinfo=zona)
            return momento.isoformat()
        except Exception:
            return None
    horario, _mensagem = L.interpretar(texto, fuso=fuso, agora=_agora(agora))
    if not horario:
        # Hora sem data: hoje se ainda vai acontecer, amanha se ja passou.
        hora = re.search(r"\b(?:as\s+)?(\d{1,2})(?::(\d{2})|h(\d{2}))\b", n)
        if not hora:
            return None
        referencia = _agora(agora)
        horas = int(hora.group(1))
        minutos = int(hora.group(2) or hora.group(3) or 0)
        if horas > 23 or minutos > 59:
            return None
        try:
            zona = ZoneInfo(fuso)
        except Exception:
            return None
        local = referencia.astimezone(zona)
        dia = local.date()
        momento = datetime(dia.year, dia.month, dia.day, horas, minutos, tzinfo=zona)
        if momento <= local:
            dia = dia + timedelta(days=1)
            momento = datetime(dia.year, dia.month, dia.day, horas, minutos, tzinfo=zona)
        return momento.isoformat()
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
