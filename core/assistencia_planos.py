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
import math
import re
import unicodedata
from dataclasses import dataclass

from core.planos import STATUS_TAREFA, TIPOS_CARD, card_por_id

_CAMPOS_EDITAVEIS = {
    "titulo", "resumo", "descricao", "tipo", "status", "modelo", "estado",
    "valor", "acumulado", "restrito", "financeiro",
}
_TIPOS_OP = {"criar_card", "editar_campos", "alterar_progresso", "conectar",
            "anexar_texto", "mover_card", "desconectar", "excluir_card"}


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
    if " e desfaca" in n and re.search(r"marque|conclu", n):
        return "EDITAR"
    if re.search(r"desfaca|desfazer|reverta|volte.*(adicion|ultimo|lote)", n):
        return "DESFAZER"
    if re.search(r"que ideias|quais ideias|ideias posso|sugestoes de ideias", n):
        return "SUGERIR"
    if "dependem de" in n:
        return "DEPENDENCIAS"
    if re.search(r"marque|renomeie|renomear|mova|mover|exclua|excluir|desconecte|remova", n):
        return "EDITAR"
    if re.search(r"conecte|conecte este|ligue este", n):
        return "EDITAR"
    if re.search(r"adicion|adicione|crie|criar|transforme|reescreva|altere|mude|acrescente", n):
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


def intencao_para_lote(texto: str, contexto: dict) -> tuple[list[dict], list[str]]:
    """Converte um pedido em linguagem natural em operações estruturadas."""
    especiais, erros = pedido_estruturado(texto, contexto)
    if especiais is not None:
        return especiais, erros
    n = normalizar(texto)
    alvo = contexto.get("card_id")
    if not alvo:
        return [], ["Selecione um card ou me diga qual card você quer editar."]
    if re.search(r"acrescente.*(texto|descricao|ideias ao texto)|"
                 r"adicionar.*ideias.*(texto|descricao)", n):
        ideias = re.findall(r"([^,.;]+?)(?=,| e |;|\.|$)", n)
        ideias = [i.strip() for i in ideias
                  if i.strip() and not re.match(
                      r"^(acrescente|adicione|estas|duas|ideias|ao|texto|neste|card)$",
                      i.strip())]
        if not ideias:
            ideias = ["Ideia acrescentada pela NIA"]
        return [{"tipo": "anexar_texto", "card_id": alvo, "ideias": ideias}], []
    if re.search(r"reescreva.*resumo", n):
        atual = contexto.get("card") or {}
        origem = atual.get("descricao") or atual.get("titulo") or ""
        return [{"tipo": "editar_campos", "card_id": alvo,
                 "campos": {"resumo": _duas_frases(origem)}}], []
    if re.search(r"conecte|ligue", n):
        alvo_nome = None
        encontrado = re.search(r"(?:a|ao|com)\s+(publico-alvo|[^?]+)", n)
        if encontrado:
            alvo_nome = encontrado.group(1).strip(" .!?;:")
            alvo_nome = re.sub(r"\s+(?:ele|este card|card|no mapa).*$", "",
                               alvo_nome).strip()
        if not alvo_nome:
            return [], ["Qual é o card de destino da conexão?"]
        destinos = [c for c in contexto.get("cartoes", [])
                    if c.get("id") != alvo
                    and normalizar(c.get("titulo") or "") == alvo_nome]
        if not destinos:
            destinos = [c for c in contexto.get("cartoes", [])
                        if c.get("id") != alvo
                        and alvo_nome in normalizar(c.get("titulo") or "")]
        if len(destinos) > 1:
            return [], ["Encontrei vários destinos: "
                        + ", ".join(str(c.get("titulo")) for c in destinos)]
        if not destinos:
            return [], [f"Não encontrei o card {alvo_nome}."]
        return [{"tipo": "conectar", "origem": alvo,
                 "destino": destinos[0].get("id")}], []
    if re.search(r"(crie|criar|adicione|acrescente).*cards?.*(ligt|conectad)"
                 r"|(crie|criar) tres cards|monte um ramo", n):
        quantos = 3
        if re.search(r"(um|uma|1)\b", n):
            quantos = 1
        elif re.search(r"(dois|duas|2)\b", n):
            quantos = 2
        return _ramo(alvo, "ideia", "Divulgação gratuita", quantos), []
    return [], ["Não entendi a alteração pedida."]


def _validar_lote_base(operacoes: list[dict], plano_atual, contexto: dict) \
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
            if tipo == "anexar_texto":
                ideias = op.get("ideias")
                if not isinstance(ideias, list) or not ideias:
                    erros.append(f"operação {i}: sem ideias para anexar")
            elif tipo == "editar_campos":
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


def _simular_lote(operacoes, plano):
    """Build the entire new state before touching scene or undo history."""
    from core.planos import novo_id, PlanoInvalido
    mapa = copy.deepcopy(plano.mapa)
    cards = {c['id']: c for c in mapa.get('cards', [])}
    ligs = list(mapa.get('conexoes', []))
    ids = {}
    def resolve(value):
        return ids.get(value, value)
    def card(ident):
        if ident not in cards:
            raise PlanoInvalido('Card alvo inexistente ou removido.')
        return cards[ident]
    def connect(origem, destino, rotulo=''):
        card(origem); card(destino)
        if origem == destino:
            raise PlanoInvalido('Conexão inválida.')
        if any(l['origem']==origem and l['destino']==destino for l in ligs):
            return
        ligs.append(dict(id=novo_id(), origem=origem, destino=destino, rotulo=str(rotulo)))
    refs = {op.get('destino_ref') for op in operacoes if op.get('tipo')=='conectar'}
    for op in operacoes:
        tipo = op['tipo']
        if tipo == 'criar_card':
            temp = op.get('temp_id')
            if temp and temp in ids:
                raise PlanoInvalido('Identificador temporário duplicado.')
            origem = resolve(op.get('origem'))
            base = card(origem) if origem else {}
            ident = novo_id()
            dados = dict(id=ident, titulo=str(op.get('titulo') or '').strip(),
                resumo=str(op.get('resumo') or ''), descricao=str(op.get('descricao') or ''),
                tipo=op.get('tipo_card', 'ideia'), status=op.get('status', ''),
                x=float(op.get('x', base.get('x',0)+270)), y=float(op.get('y',base.get('y',0)+110)))
            for field in ('modelo','estado','valor','acumulado','restrito','financeiro'):
                if field in op:
                    dados[field] = op[field]
            if not dados['titulo'] or dados['tipo'] not in TIPOS_CARD:
                raise PlanoInvalido('Título ou tipo de card inválido.')
            if dados['tipo']=='tarefa' and not dados['status']:
                dados['status']='pendente'
            cards[ident]=dados
            if temp:
                ids[temp]=ident
            if origem and temp not in refs:
                connect(origem,ident,op.get('rotulo',''))
        elif tipo == 'conectar':
            connect(resolve(op.get('origem')),resolve(op.get('destino') or op.get('destino_ref')),op.get('rotulo',''))
        elif tipo == 'desconectar':
            origem, destino = resolve(op.get('origem')), resolve(op.get('destino'))
            card(origem); card(destino)
            novas = [l for l in ligs if not (l['origem']==origem and l['destino']==destino)]
            if len(novas)==len(ligs):
                raise PlanoInvalido('A conexão indicada não existe.')
            ligs=novas
        else:
            ident=resolve(op.get('card_id')); dados=card(ident)
            if tipo=='editar_campos':
                campos=op.get('campos')
                if not isinstance(campos,dict) or not campos or set(campos)-_CAMPOS_EDITAVEIS:
                    raise PlanoInvalido('Campos inválidos.')
                dados.update(campos)
            elif tipo=='alterar_progresso':
                dados.update(tipo='tarefa', status=op.get('status'))
            elif tipo=='anexar_texto':
                ideias=op.get('ideias')
                if not isinstance(ideias,list) or not ideias:
                    raise PlanoInvalido('Sem ideias para anexar.')
                dados['descricao']=(str(dados.get('descricao') or '').rstrip()+'\n'+'\n'.join(map(str,ideias))).strip()
            elif tipo=='mover_card':
                dados.update(x=float(op['x']), y=float(op['y']))
            elif tipo=='excluir_card':
                if ident==mapa.get('raiz_id'):
                    raise PlanoInvalido('O card central não pode ser excluído.')
                del cards[ident]
                ligs=[l for l in ligs if ident not in (l['origem'],l['destino'])]
            else:
                raise PlanoInvalido('Tipo de operação desconhecido.')
    for dados in cards.values():
        if not math.isfinite(float(dados.get('x',0))) or not math.isfinite(float(dados.get('y',0))):
            raise PlanoInvalido('Posição inválida.')
        if not str(dados.get('titulo') or '').strip() or dados.get('tipo') not in TIPOS_CARD:
            raise PlanoInvalido('Título ou tipo inválido.')
        if dados.get('tipo')=='tarefa' and dados.get('status') not in STATUS_TAREFA:
            raise PlanoInvalido('Progresso inválido.')
    mapa.update(cards=list(cards.values()),conexoes=ligs)
    return mapa


def validar_lote(operacoes, plano_atual, contexto):
    if contexto.get('plano_id') != plano_atual.id:
        return [], ['O plano mudou desde o pedido; a resposta foi descartada.']
    antigas=[op for op in operacoes if op.get('tipo') not in ('mover_card','desconectar','excluir_card')]
    _, erros=_validar_lote_base(antigas,plano_atual,contexto)
    if erros:
        return [], erros
    from core.planos import PlanoInvalido
    try:
        _simular_lote(operacoes,plano_atual)
    except (ValueError,KeyError,TypeError,PlanoInvalido) as exc:
        return [], [str(exc)]
    return copy.deepcopy(operacoes), []


def aplicar_lote(editor, operacoes, rotulo):
    """Validate and publish one snapshot; a failure cannot leave half a branch."""
    plano=editor.plano_atual()
    contexto=montar_contexto(plano,editor.card_selecionado_id)
    validas,erros=validar_lote(operacoes,plano,contexto)
    if erros:
        raise ValueError(erros[0])
    mapa=_simular_lote(validas,plano)
    if mapa == plano.mapa:
        return False
    editor.aplicar_mapa(mapa, 'Assistido: '+rotulo)
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


def resolver_card(nome, contexto):
    nome=re.sub(r'^(?:o |ao |a |do |este )?(?:card )?', '', nome.strip(' .?!"“”'), flags=re.I)
    if normalizar(nome) in ('este','este card','selecionado','deste card'):
        nome=contexto.get('card_id')
    cards=contexto.get('cartoes') or (contexto.get('plano').mapa.get('cards',[]) if contexto.get('plano') else [])
    encontrados=[c for c in cards if c.get('id')==nome or normalizar(c.get('titulo'))==normalizar(nome)]
    if len(encontrados)>1:
        selecionado=[c for c in encontrados if c.get('id')==contexto.get('card_id')]
        if selecionado:
            return selecionado[0]
        raise ValueError('Há cards com o mesmo título. Selecione o card desejado.')
    if not encontrados:
        raise ValueError(f'Não encontrei o card {nome}.')
    return encontrados[0]


def pedido_estruturado(texto, contexto):
    """Named edits shared by chat and voice; returns None for legacy grammar."""
    n=normalizar(texto)
    try:
        m=re.search(r'(?:crie|criar) (?:um )?card (.+?) e conecte (?:ao|a|com) (?:o )?(?:card )?(.+?)[.!?]?$',texto,re.I)
        if m:
            base=resolver_card(m[2],contexto)
            return [dict(tipo='criar_card',titulo=m[1].strip(),temp_id='novo',x=base.get('x',0)+270,y=base.get('y',0)+120),
                    dict(tipo='conectar',origem=base['id'],destino_ref='novo')],[]
        m=re.search(r'marque (?:o )?(?:card )?(.+?) como (conclu[ií]do|pendente|bloqueado|em andamento)',texto,re.I)
        if m:
            alvo=resolver_card(m[1],contexto)
            status=normalizar(m[2]).replace(' ','_')
            return [dict(tipo='alterar_progresso',card_id=alvo['id'],status=status)],[]
        m=re.search(r'renomeie (?:o )?(?:card )?(.+?) para (.+)',texto,re.I)
        if m:
            alvo=resolver_card(m[1],contexto)
            return [dict(tipo='editar_campos',card_id=alvo['id'],campos=dict(titulo=m[2].strip(' .')))],[]
        m=re.search(r'(?:adicione|adicionar) (tr[eê]s|duas|dois|uma|um|[1-6]) ideias? (?:[àa] descri[cç][aã]o|ao texto) d[oe] (?:card )?([^:]+)(?::(.*))?$',texto,re.I)
        if m:
            alvo=resolver_card(m[2],contexto)
            quantidade={'tres':3,'duas':2,'dois':2,'uma':1,'um':1}.get(normalizar(m[1]), int(m[1]) if m[1].isdigit() else 3)
            ideias=[v.strip() for v in re.split(r';|\n',m[3] or '') if v.strip()]
            if not ideias:
                ideias=[f'Explorar um conceito de {alvo["titulo"]}.',f'Registrar exemplos práticos de {alvo["titulo"]}.',f'Anotar dúvidas e próximos passos de {alvo["titulo"]}.']
            return [dict(tipo='anexar_texto',card_id=alvo['id'],ideias=ideias[:quantidade])],[]
        m=re.search(r'mova (?:o )?(?:card )?(.+?) para (-?[0-9.]+)\s*,\s*(-?[0-9.]+)',texto,re.I)
        if m:
            alvo=resolver_card(m[1],contexto)
            return [dict(tipo='mover_card',card_id=alvo['id'],x=float(m[2]),y=float(m[3]))],[]
        m=re.search(r'(conecte|desconecte) (?:o )?card (.+?) (?:ao|a|de|do) (?:o )?card (.+?)[.!?]?$',texto,re.I)
        if m:
            a,b=resolver_card(m[2],contexto),resolver_card(m[3],contexto)
            return [dict(tipo='conectar' if normalizar(m[1])=='conecte' else 'desconectar',origem=a['id'],destino=b['id'])],[]
        m=re.search(r'(?:exclua|remova) (?:o )?card (.+?)[.!?]?$',texto,re.I)
        if m:
            alvo=resolver_card(m[1],contexto)
            return [dict(tipo='excluir_card',card_id=alvo['id'])],[]
    except ValueError as exc:
        return [],[str(exc)]
    return None,[]
