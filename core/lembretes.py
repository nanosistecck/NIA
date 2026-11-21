# -*- coding: utf-8 -*-
"""Lembretes locais dos planos do Canvas (Prompt 06).

Persistidos no mesmo JSON versionado do plano, usando `core.planos.atualizar`
(revisão, gravação atômica). Nenhuma rede, API externa ou Ollama.
"""
from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from core import planos as BP

ESTADOS = ("pendente", "concluido", "cancelado", "suspenso")


def novo_id() -> str:
    return uuid.uuid4().hex


def normalizar(texto: str) -> str:
    bruto = unicodedata.normalize("NFKD", str(texto or "")).casefold()
    return "".join(c for c in bruto if not unicodedata.combining(c)).strip()


def interpretar(texto: str, fuso: str = "America/Sao_Paulo",
                agora: datetime | None = None) -> tuple[str | None, str]:
    """Converte linguagem natural em UTC ISO; sem data/hora, pede a falta."""
    agora = agora or datetime.now(timezone.utc)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=timezone.utc)
    n = normalizar(texto)
    try:
        zona = ZoneInfo(fuso)
    except Exception:
        zona = timezone.utc
        fuso = "UTC"
    local = agora.astimezone(zona)
    if "amanha" in n:
        dia = local.date() + timedelta(days=1)
    elif "hoje" in n:
        dia = local.date()
    else:
        encontrado = re.search(r"em\s+(\d+)\s+dia", n)
        if encontrado:
            dia = local.date() + timedelta(days=int(encontrado.group(1)))
        else:
            dia = None
    hora = re.search(r"\bas\s*(\d{1,2})(?::(\d{2})|h(\d{2}))?", n)
    if not hora:
        hora = re.search(r"\b(\d{1,2})h(\d{2})?\b", n)
    if dia is None or not hora:
        return None, "Informe a data e a hora do lembrete (ex.: amanhã às 19h)."
    horas = int(hora.group(1))
    minutos = int(hora.group(2) or hora.group(3) or 0)
    if horas > 23 or minutos > 59:
        return None, "Horário inválido. Informe a data e a hora novamente."
    momento = datetime.combine(dia, time(horas, minutos), tzinfo=zona)
    horario = momento.astimezone(timezone.utc).isoformat()
    return horario, (f"Lembrete salvo para {momento.strftime('%d/%m às %H:%M')} "
                     f"({fuso}).")


def _plano(plano_id: str):
    plano = BP.carregar(plano_id)
    if plano is None:
        raise BP.PlanoInvalido("plano inexistente")
    return plano


def _salvar(plano, lembretes: list[dict]):
    return BP.atualizar(plano.id, {"lembretes": lembretes}, plano.revisao)


def criar(plano_id: str, assunto: str, horario: str, fuso: str,
          card_id: str | None = None) -> dict:
    if not str(assunto or "").strip():
        raise BP.PlanoInvalido("assunto obrigatório")
    try:
        datetime.fromisoformat(str(horario).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise BP.PlanoInvalido("horário inválido")
    plano = _plano(plano_id)
    lembrete = {
        "id": novo_id(), "plano_id": plano.id, "card_id": card_id or None,
        "assunto": str(assunto).strip(), "horario": str(horario),
        "fuso": str(fuso or "America/Sao_Paulo"), "estado": "pendente",
        "avisos": [], "criado_em": BP.agora_iso(),
    }
    _salvar(plano, [*plano.lembretes, lembrete])
    return lembrete


def listar(plano_id: str) -> list[dict]:
    return _plano(plano_id).lembretes


def listar_todos() -> list[dict]:
    planos, _avisos = BP.listar()
    todos = []
    for plano in planos:
        todos.extend(plano.lembretes)
    return todos


def carregar(lembrete_id: str) -> dict | None:
    return next((x for x in listar_todos() if x.get("id") == lembrete_id), None)


def _alterar(lembrete_id: str, **mudancas) -> dict:
    planos, _avisos = BP.listar()
    for plano in planos:
        for item in plano.lembretes:
            if item.get("id") == lembrete_id:
                item.update(mudancas)
                _salvar(plano, plano.lembretes)
                return item
    raise BP.PlanoInvalido("lembrete inexistente")


def adiar(lembrete_id: str, horario: str) -> dict:
    try:
        datetime.fromisoformat(str(horario).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise BP.PlanoInvalido("horário inválido")
    return _alterar(lembrete_id, horario=str(horario), estado="pendente", avisos=[])


def concluir(lembrete_id: str) -> dict:
    return _alterar(lembrete_id, estado="concluido")


def cancelar(lembrete_id: str) -> dict:
    return _alterar(lembrete_id, estado="cancelado")


def suspender_por_card(plano_id: str, card_id: str) -> None:
    plano = _plano(plano_id)
    for item in plano.lembretes:
        if item.get("card_id") == card_id and item.get("estado") == "pendente":
            item["estado"] = "suspenso"
    _salvar(plano, plano.lembretes)


def restaurar_por_card(plano_id: str, card_id: str) -> None:
    plano = _plano(plano_id)
    for item in plano.lembretes:
        if item.get("card_id") == card_id and item.get("estado") == "suspenso":
            item["estado"] = "pendente"
    _salvar(plano, plano.lembretes)


def suspender_por_plano(plano_id: str) -> None:
    plano = _plano(plano_id)
    for item in plano.lembretes:
        if item.get("estado") == "pendente":
            item["estado"] = "suspenso"
    _salvar(plano, plano.lembretes)


def restaurar_por_plano(plano_id: str) -> None:
    plano = _plano(plano_id)
    for item in plano.lembretes:
        if item.get("estado") == "suspenso":
            item["estado"] = "pendente"
    _salvar(plano, plano.lembretes)


def vencidos(agora: datetime | None = None) -> list[dict]:
    agora = agora or datetime.now(timezone.utc)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=timezone.utc)
    resultado = []
    for item in listar_todos():
        if item.get("estado") != "pendente":
            continue
        try:
            quando = datetime.fromisoformat(
                str(item.get("horario")).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if quando <= agora and quando.isoformat() not in item.get("avisos", []):
            resultado.append(item)
    return resultado


def registrar_aviso(lembrete_id: str, ocorrencia: str) -> dict:
    item = carregar(lembrete_id)
    avisos = list(item.get("avisos") or []) if item else []
    if ocorrencia not in avisos:
        avisos.append(ocorrencia)
    return _alterar(lembrete_id, avisos=avisos)


def proximo(agora: datetime | None = None) -> dict | None:
    agora = agora or datetime.now(timezone.utc)
    candidatos = []
    for item in listar_todos():
        if item.get("estado") != "pendente":
            continue
        try:
            quando = datetime.fromisoformat(
                str(item.get("horario")).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if quando > agora:
            candidatos.append((quando, item))
    return min(candidatos, key=lambda par: par[0])[1] if candidatos else None


def alvo(lembrete: dict) -> dict:
    """Destino da notificação: card quando houver, senão o plano."""
    return {"plano_id": lembrete.get("plano_id"),
            "card_id": lembrete.get("card_id")}
