# -*- coding: utf-8 -*-
"""Edição assistida do Canvas Infinito (Prompt 04).

Toda decisão estrutural acontece no aplicativo: o provedor (quando usado)
apenas devolve dados. Antes de qualquer chamada externa, ``filtrar_contexto``
aplica a política de saída com base no destino. Nenhuma chamada de rede
acontece neste módulo.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass

from core.planos import STATUS_TAREFA, TIPOS_CARD, card_por_id

_CAMPOS_EDITAVEIS = {
    "titulo", "resumo", "descricao", "tipo", "status", "modelo", "estado",
    "valor", "acumulado", "restrito", "financeiro",
}
_TIPOS_OP = {"criar_card", "editar_campos", "alterar_progresso", "conectar"}


@dataclass(frozen=True)
class Destino:
    local: bool
    provedor: str = ""
    assinatura: str = ""


def normalizar(texto: str) -> str:
    bruto = unicodedata.normalize("NFKD", str(texto or "")).casefold()
    return "".join(c for c in bruto if not unicodedata.combining(c)).strip()


def fingerprint(plano) -> str:
    """Identifica o estado do mapa, inclusive edições ainda não salvas."""
    bruto = json.dumps(plano.mapa, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def montar_contexto(plano, card_id: str | None) -> dict:
    """Contexto semântico mínimo: plano, card indicado e vizinhos diretos."""
    cartoes = plano.mapa.get("cards", [])
    ligacoes = plano.mapa.get("conexoes", [])
    card = copy.deepcopy(card_por_id(plano, card_id)) if card_id else None
    vizinhos = []
    for lig in ligacoes:
        if card_id and card_id in (lig.get("origem"), lig.get("destino")):
            outro = lig.get("destino") if lig.get("origem") == card_id else lig.get("origem")
            outro_card = next((c for c in cartoes if c.get("id") == outro), None)
            if outro_card is not None:
                vizinhos.append(copy.deepcopy(outro_card))
    return {
        "plano_id": plano.id,
        "revisao": plano.revisao,
        "fingerprint": fingerprint(plano),
        "objetivo": plano.objetivo,
        "titulo_plano": plano.titulo,
        "raiz_id": str(plano.mapa.get("raiz_id") or ""),
        "card_id": card_id,
        "card": card,
        "vizinhos": vizinhos,
        "trechos": [],
    }


def filtrar_contexto(contexto: dict, destino: Destino) -> dict:
    """Aplica a política de saída ANTES de montar a chamada externa."""
    filtrado = copy.deepcopy(contexto)
    if destino.local:
        filtrado["destino_local"] = True
        return filtrado
    removidos = 0
    card = filtrado.get("card")
    if isinstance(card, dict) and (card.get("restrito") or card.get("financeiro")):
        filtrado["card"] = None
        removidos += 1
    vizinhos = []
    for viz in filtrado.get("vizinhos", []):
        if isinstance(viz, dict) and (viz.get("restrito") or viz.get("financeiro")):
            removidos += 1
        else:
            vizinhos.append(viz)
    filtrado["vizinhos"] = vizinhos
    trechos = []
    for trecho in filtrado.get("trechos", []):
        if isinstance(trecho, dict) and trecho.get("restrito"):
            removidos += 1
        else:
            trechos.append(trecho)
    filtrado["trechos"] = trechos
    filtrado["removidos"] = removidos
    filtrado["destino_local"] = False
    filtrado["provedor"] = destino.provedor
    filtrado["assinatura"] = destino.assinatura
    return filtrado


def reconhecer_intencao(texto: str) -> str:
    """EXPLICAR | SUGERIR | EDITAR | DESFAZER | NENHUMA."""
    n = normalizar(texto)
    if re.search(r"desfaca|desfazer|reverta|volte.*(adicion|ultimo|lote)", n):
        return "DESFAZER"
    if re.search(r"adicion|adicione|crie|criar|transforme|reescreva|altere|mude", n):
        return "EDITAR"
    if re.search(r"que solucoes|alternativas|sugestoes|opcoes", n):
        return "SUGERIR"
    if re.search(r"com quais cards|conectad|ligad|vinculad", n):
        return "CONEXOES_CARD"
    if re.search(r"quais cards|liste os cards|lista de cards|cards existem", n):
        return "LISTAR_CARDS"
    if re.search(r"escrevi|escrito neste card|leia o que|leia este card|"
                 r"texto deste card|conteudo deste card", n):
        return "LER_CARD"
    if re.search(r"como (ele |isso )?se liga|ligad|vinculad", n) \
            and re.search(r"explique|explica", n):
        return "EXPLICAR_CARD"
    if re.search(r"me explica|explique|explica este card|o que e este card", n):
        return "EXPLICAR"
    return "NENHUMA"


def _duas_frases(texto: str) -> str:
    partes = [p.strip() for p in re.findall(r"[^.]+(?:\.|$)", str(texto or ""))]
    return " ".join(p for p in partes if p)[:400]


def pedido_local(texto: str, contexto: dict) -> tuple[list[dict], list[str]]:
    """Operações determinísticas que não precisam de provedor."""
    n = normalizar(texto)
    alvo = contexto.get("card_id")
    card = contexto.get("card") or {}
    if not alvo or not card:
        return [], ["Selecione um card antes de pedir a edição."]
    if re.search(r"reescreva.*resumo", n):
        origem = card.get("descricao") or card.get("resumo") or card.get("titulo") or ""
        return [{"tipo": "editar_campos", "card_id": alvo,
                 "campos": {"resumo": _duas_frases(origem)}}], []
    if re.search(r"transforme.*tarefa", n):
        return _ramo(alvo, "tarefa", "Tarefa", 3), []
    if re.search(r"adicion|adicione|crie|criar", n) and re.search(r"soluc", n):
        quantos = 3
        if re.search(r"(um|uma|1)\b", n):
            quantos = 1
        elif re.search(r"(dois|duas|2)\b", n):
            quantos = 2
        elif re.search(r"(quatro|4)\b", n):
            quantos = 4
        return _ramo(alvo, "ideia", "Solução", quantos), []
    return [], ["Não há uma operação local segura para esse pedido."]


def _ramo(origem: str, tipo: str, rotulo: str, quantos: int) -> list[dict]:
    ops: list[dict] = []
    for i in range(max(1, min(6, quantos))):
        temp = f"tmp{i}"
        ops.append({
            "tipo": "criar_card", "titulo": f"{rotulo} {i + 1}",
            "tipo_card": tipo,
            "status": "pendente" if tipo == "tarefa" else "",
            "origem": origem, "temp_id": temp,
        })
        ops.append({"tipo": "conectar", "origem": origem, "destino_ref": temp})
    return ops


def parse_resposta(bruto: str, contexto: dict) -> tuple[list[dict], list[str]]:
    """Converte a resposta do provedor em operações; conteúdo é dado, não ordem."""
    try:
        dados = json.loads(str(bruto or ""))
    except (TypeError, ValueError):
        return [], ["Resposta do provedor não é JSON válido."]
    brutos = dados.get("operacoes") if isinstance(dados, dict) else None
    if not isinstance(brutos, list):
        return [], ["Resposta do provedor não trouxe operações."]
    ops: list[dict] = []
    for i, item in enumerate(brutos):
        if not isinstance(item, dict) or item.get("tipo") not in _TIPOS_OP:
            return [], [f"operação {i} inválida"]
        op = dict(item)
        if op["tipo"] == "criar_card" and "temp_id" not in op:
            op["temp_id"] = f"prov{i}"
        ops.append(op)
    return ops, []


def validar_lote(operacoes: list[dict], plano_atual, contexto: dict) \
        -> tuple[list[dict], list[str]]:
    """Valida o lote inteiro contra o estado ATUAL do editor, antes de aplicar."""
    erros: list[str] = []
    if contexto.get("plano_id") != plano_atual.id:
        return [], ["O plano mudou desde o pedido; a resposta foi descartada."]
    cartoes = {c.get("id"): c for c in plano_atual.mapa.get("cards", [])}
    ligacoes = plano_atual.mapa.get("conexoes", [])
    base = contexto.get("card") or {}
    temporarios: set[str] = set()
    for i, op in enumerate(operacoes):
        tipo = op.get("tipo")
        if tipo not in _TIPOS_OP:
            erros.append(f"operação {i}: tipo desconhecido")
            continue
        if tipo == "criar_card":
            if not str(op.get("titulo") or "").strip():
                erros.append(f"operação {i}: título vazio")
            if op.get("origem") and op["origem"] not in cartoes:
                erros.append(f"operação {i}: card de origem removido")
            if op.get("tipo_card", "ideia") not in TIPOS_CARD:
                erros.append(f"operação {i}: tipo de card inválido")
            if op.get("temp_id"):
                temporarios.add(op["temp_id"])
        elif tipo == "conectar":
            origem = op.get("origem")
            destino = op.get("destino")
            ref = op.get("destino_ref")
            if origem not in cartoes and origem not in temporarios:
                erros.append(f"operação {i}: origem inexistente")
            if destino is None and ref not in temporarios:
                erros.append(f"operação {i}: destino inexistente")
            elif destino is not None and destino not in cartoes:
                erros.append(f"operação {i}: destino inexistente")
            if origem == destino:
                erros.append(f"operação {i}: conexão consigo mesmo")
        else:
            ident = op.get("card_id")
            if ident not in cartoes:
                erros.append(f"operação {i}: card alvo removido")
                continue
            if tipo == "editar_campos":
                campos = op.get("campos")
                if not isinstance(campos, dict) or not campos:
                    erros.append(f"operação {i}: campos vazios")
                else:
                    for chave, valor in campos.items():
                        if chave not in _CAMPOS_EDITAVEIS:
                            erros.append(f"operação {i}: campo não permitido")
                        elif ident == contexto.get("card_id") \
                                and base.get(chave) != cartoes[ident].get(chave):
                            erros.append(
                                f"operação {i}: '{chave}' foi editado manualmente")
            elif tipo == "alterar_progresso":
                if op.get("status") not in STATUS_TAREFA:
                    erros.append(f"operação {i}: progresso inválido")
    if erros:
        return [], erros
    return copy.deepcopy(operacoes), []


def aplicar_lote(editor, operacoes: list[dict], rotulo: str) -> bool:
    """Aplica o lote em UMA operação de desfazer, na thread da interface."""
    ids: dict[str, str] = {}
    refs = {op.get("destino_ref") for op in operacoes
            if op.get("tipo") == "conectar"}
    editor.pilha.beginMacro(f"Assistido: {rotulo}")
    try:
        for op in operacoes:
            tipo = op["tipo"]
            if tipo == "criar_card":
                card_id = editor.criar_card(
                    str(op.get("titulo") or "Novo card"),
                    str(op.get("resumo") or ""),
                    str(op.get("descricao") or ""),
                    str(op.get("tipo_card") or "ideia"),
                    str(op.get("status") or ""),
                    float(op.get("x") or 0.0), float(op.get("y") or 0.0),
                    modelo=str(op.get("modelo") or ""),
                    estado=str(op.get("estado") or ""),
                    valor=op.get("valor"), acumulado=op.get("acumulado"),
                    restrito=bool(op.get("restrito") or False),
                    financeiro=bool(op.get("financeiro") or False))
                if op.get("temp_id"):
                    ids[op["temp_id"]] = card_id
                if (op.get("temp_id") not in refs
                        and op.get("origem") in editor.cena.itens_cards):
                    editor.conectar(op["origem"], card_id,
                                    str(op.get("rotulo") or ""))
            elif tipo == "conectar":
                destino = op.get("destino") or ids.get(op.get("destino_ref"))
                origem = ids.get(op.get("origem"), op.get("origem"))
                if destino and origem in editor.cena.itens_cards:
                    editor.conectar(origem, destino, str(op.get("rotulo") or ""))
            elif tipo == "editar_campos":
                editor.editar_card(op["card_id"], dict(op.get("campos") or {}))
            elif tipo == "alterar_progresso":
                editor.definir_progresso(op["card_id"], str(op.get("status") or ""))
    finally:
        editor.pilha.endMacro()
    return True


def desfazer_lote(editor) -> bool:
    """Reverte o lote assistido somente se ele for a última operação."""
    indice = editor.pilha.index() - 1
    if indice < 0:
        return False
    comando = editor.pilha.command(indice)
    if comando is None or not comando.text().startswith("Assistido:"):
        return False
    editor.desfazer()
    return True
