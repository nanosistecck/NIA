# -*- coding: utf-8 -*-
"""Modelos locais de planejamento para o Canvas Infinito (Prompt 05).

Cada modelo é uma estrutura inicial de cards e conexões, gerada no aplicativo
sem rede. A aplicação usa o mesmo fluxo de operações estruturadas da edição
assistida: um lote validado, uma única operação de desfazer/refazer e a
gravação atômica já existente.
"""
from __future__ import annotations

import copy
import unicodedata
from typing import Any

from core.planos import STATUS_TAREFA, novo_id

TIPOS_MODELO = ("Produto", "Projeto", "Conteúdo", "Estudos", "Finanças")
ESTADOS_PUBLICACAO = ("rascunho", "revisao", "pronto", "publicado")

# (título, resumo, tipo de card, estado de publicação)
_TEMPLATES: dict[str, tuple[tuple[str, str, str, str], ...]] = {
    "Produto": (
        ("O que vender?", "Compare físico, digital, serviço e SaaS", "ideia", ""),
        ("Pergunta: tempo disponível?", "Defina antes de escolher", "ideia", ""),
        ("Pergunta: orçamento?", "Defina antes de escolher", "ideia", ""),
        ("Pergunta: acesso ao público?", "Defina antes de escolher", "ideia", ""),
        ("Público", "Quem tem o problema", "ideia", ""),
        ("Problema", "O que dói hoje", "ideia", ""),
        ("Oferta", "O que será entregue", "ideia", ""),
        ("Hipótese de validação", "O que se acredita", "tarefa", ""),
        ("Teste de validação", "Como verificar", "tarefa", ""),
        ("Critério de sucesso", "Quando aceitar", "tarefa", ""),
        ("Preço", "Como cobrar", "ideia", ""),
        ("Onde vender", "Canal de transação", "ideia", ""),
        ("Onde divulgar", "Canal de alcance", "ideia", ""),
        ("Lançamento", "Primeira entrega", "tarefa", ""),
        ("Métricas", "Como acompanhar", "ideia", ""),
    ),
    "Projeto": (
        ("Objetivo", "Resultado esperado", "ideia", ""),
        ("Usuários", "Quem usa", "ideia", ""),
        ("Escopo", "O que entra e o que fica de fora", "ideia", ""),
        ("Entregas", "O que será entregue", "ideia", ""),
        ("Tarefas", "Trabalho necessário", "tarefa", ""),
        ("Dependências", "O que bloqueia o avanço", "tarefa", ""),
        ("Critérios de conclusão", "Como saber que terminou", "tarefa", ""),
    ),
    "Conteúdo": (
        ("Objetivo", "O que o material deve conseguir", "ideia", ""),
        ("Público", "Para quem é", "ideia", ""),
        ("Mensagem", "Ideia central", "ideia", ""),
        ("Formato", "Post, vídeo, newsletter...", "ideia", ""),
        ("Rascunho", "Primeira versão", "ideia", "rascunho"),
        ("Chamada para ação", "O que o leitor faz depois", "ideia", ""),
        ("Revisão", "Ajustes finais", "ideia", "revisao"),
        ("Calendário", "Quando publicar", "ideia", ""),
        ("Variações por canal", "Adaptações", "ideia", ""),
        ("Métricas", "Como medir", "ideia", ""),
    ),
    "Estudos": (
        ("Objetivo", "O que quer aprender", "ideia", ""),
        ("Nível atual", "De onde parte", "ideia", ""),
        ("Pré-requisitos", "O que precisa saber antes", "ideia", ""),
        ("Tópico 1", "Primeiro passo", "tarefa", ""),
        ("Tópico 2", "Segundo passo", "tarefa", ""),
        ("Exemplos", "Casos para estudar", "ideia", ""),
        ("Exercício", "Prática do tópico", "tarefa", ""),
        ("Revisão", "Revisar e consolidar", "tarefa", ""),
    ),
    "Finanças": (
        ("Receitas", "O que entra", "ideia", ""),
        ("Despesas", "O que sai", "ideia", ""),
        ("Dívidas", "O que deve", "ideia", ""),
        ("Meta", "Objetivo com valor e acumulado", "ideia", ""),
        ("Revisão mensal", "Conferir números", "tarefa", ""),
    ),
}


def normalizar(texto: str) -> str:
    bruto = unicodedata.normalize("NFKD", str(texto or "")).casefold()
    return "".join(c for c in bruto if not unicodedata.combining(c)).strip()


def reconhecer_tipo(texto: str) -> str:
    """Infere o modelo a partir de tema/intenção já presentes no pedido."""
    n = normalizar(texto)
    if any(p in n for p in ("financ", "orcamento", "meta de", "divida")):
        return "Finanças"
    if any(p in n for p in ("post", "conteudo", "campanha", "noticia", "video")):
        return "Conteúdo"
    if any(p in n for p in ("estudar", "estudo", "aprender", "curso", "do zero",
                            "fotografia")):
        return "Estudos"
    if any(p in n for p in ("saas", "aplicativo", "app ", "projeto", "ferramenta",
                            "sistema")):
        return "Projeto"
    if any(p in n for p in ("vender", "produto", "lojista", "oferta", "negocio")):
        return "Produto"
    return ""


def cards_financeiros(titulo: str, valor: str | None,
                      acumulado: str | None) -> list[dict]:
    """Fábrica de meta financeira com centavos exatos/valor em branco."""
    return [{"titulo": str(titulo or "Meta"), "valor": valor,
             "acumulado": acumulado}]


def _slug(tipo: str) -> str:
    return normalizar(tipo).replace("ç", "c")


def _op_coordenada(i: int, origem: dict | None) -> tuple[float, float]:
    base_x = float((origem or {}).get("x") or 0.0)
    base_y = float((origem or {}).get("y") or 0.0)
    return base_x + 260.0 + (i % 3) * 220.0, base_y + (i // 3) * 120.0


def estrutura_modelo(tipo: str, titulo: str = "", objetivo: str = "",
                     tema: str = "", Origem: dict | None = None) -> list[dict]:
    """Operações do modelo; `Origem` é o card de origem quando for um ramo."""
    if tipo not in TIPOS_MODELO:
        return []
    modelo = _slug(tipo)
    origem = Origem or {}
    ops: list[dict] = []
    anterior: str | None = None
    for i, (rotulo, resumo, card_tipo, estado) in enumerate(_TEMPLATES[tipo]):
        temp = f"{modelo}{i}"
        x, y = _op_coordenada(i, origem)
        op: dict[str, Any] = {
            "tipo": "criar_card",
            "titulo": rotulo,
            "resumo": resumo,
            "descricao": "",
            "tipo_card": card_tipo,
            "status": "pendente" if card_tipo == "tarefa" else "",
            "modelo": modelo,
            "estado": estado,
            "x": x, "y": y,
            "temp_id": temp,
        }
        if tipo == "Finanças" and i == 3:
            meta = cards_financeiros(tema or titulo or "Meta", None, None)[0]
            op["valor"] = meta["valor"]
            op["acumulado"] = meta["acumulado"]
        ops.append(op)
        primeiro = origem.get("id") if i == 0 else None
        if primeiro:
            ops.append({"tipo": "conectar", "origem": primeiro,
                        "destino_ref": temp, "modelo": modelo})
        elif anterior:
            ops.append({"tipo": "conectar", "origem": anterior,
                        "destino_ref": temp, "modelo": modelo})
        anterior = temp
    return ops


def ramo_modelo(tipo: str, origem_id: str, posicao: dict | None = None) -> list[dict]:
    """Estrutura conectada ao card escolhido, sem mover cards existentes."""
    return estrutura_modelo(tipo, Origem={**(posicao or {}), "id": origem_id})


def aplicar_estrutura_no_mapa(mapa: dict, ops: list[dict],
                              origem_id: str | None = None) -> dict:
    """Versão pura (sem Qt) para criar plano com modelo no gerenciador."""
    resultado = copy.deepcopy(mapa)
    ids: dict[str, str] = {}
    anterior = origem_id
    for op in ops:
        if op.get("tipo") != "criar_card":
            continue
        ident = novo_id()
        if op.get("temp_id"):
            ids[op["temp_id"]] = ident
        cartao = {
            "id": ident, "tipo": op.get("tipo_card", "ideia"),
            "titulo": str(op.get("titulo") or ""),
            "resumo": str(op.get("resumo") or ""),
            "descricao": str(op.get("descricao") or ""),
            "status": str(op.get("status") or ""),
            "x": float(op.get("x") or 0.0), "y": float(op.get("y") or 0.0),
            "restrito": bool(op.get("restrito") or False),
            "financeiro": bool(op.get("financeiro") or False),
            "modelo": str(op.get("modelo") or ""),
            "estado": str(op.get("estado") or ""),
            "valor": op.get("valor"), "acumulado": op.get("acumulado"),
        }
        resultado.setdefault("cards", []).append(cartao)
        origem = op.get("origem") or anterior
        if origem:
            resultado.setdefault("conexoes", []).append({
                "id": novo_id(), "origem": origem, "destino": ident,
                "rotulo": "",
            })
        anterior = ident
    return resultado


def calculo_financeiro(plano) -> dict:
    """Soma em centavos inteiros; campo vazio permanece ``None``."""
    metas = []
    total = 0
    for card in plano.mapa.get("cards", []):
        valor = card.get("valor")
        if valor is None or str(valor).strip() == "" or card.get("modelo") != "financas":
            continue
        try:
            alvo = int(valor)
            bruto = card.get("acumulado")
            atual = None if bruto is None or str(bruto).strip() == "" else int(bruto)
        except (TypeError, ValueError):
            continue
        total += atual or 0
        metas.append({
            "id": card.get("id"), "titulo": card.get("titulo"),
            "valor": alvo, "acumulado": atual,
            "restante": max(0, alvo - (atual or 0)),
        })
    return {"metas": metas, "total_acumulado": total}


def progresso_por_ramo(plano) -> dict:
    """Progresso agrupado por ramo, preservando status/estados já registrados."""
    ramos: dict[str, dict] = {}
    for card in plano.mapa.get("cards", []):
        modelo = str(card.get("modelo") or "")
        if not modelo:
            continue
        ramo = ramos.setdefault(modelo, {
            "total": 0, "concluido": 0, "pendente": 0,
            "em_andamento": 0, "bloqueado": 0,
            "rascunho": 0, "revisao": 0, "pronto": 0, "publicado": 0,
            "topico": 0,
        })
        ramo["total"] += 1
        status = str(card.get("status") or "")
        if status in STATUS_TAREFA:
            ramo[status] += 1
        estado = str(card.get("estado") or "")
        if estado:
            ramo[estado] = ramo.get(estado, 0) + 1
        if modelo == "estudos" and str(card.get("titulo") or "").startswith("Tópico"):
            ramo["topico"] += 1
    if "financas" in ramos:
        ramos["financas"].update(calculo_financeiro(plano))
    return ramos
