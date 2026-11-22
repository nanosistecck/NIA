# -*- coding: utf-8 -*-
"""Comandos de planejamento em português natural, sem IA e sem rede.

O reconhecedor cobre frases claras, negações, perguntas informativas e
pedidos hipotéticos. A sessão guarda perguntas pendentes, opções numeradas,
contexto de plano/card e dedup de eventos — o mesmo processar() atende chat e
transcrição final de voz.
"""
from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from core import modelos_planos as MP
from core import planos as BP
from core.planos import TIPOS, buscar, resumo_progresso

_PALAVRA_TIPO = (
    ("produto", "Produto"), ("projeto", "Projeto"), ("estudo", "Estudos"),
    ("conteudo", "Conteúdo"), ("financas", "Finanças"),
)

_TEMA = re.compile(
    r"(?:para|sobre|de|do|da|no|na)\s+(.+?)\s*(?:[?.!]|$)")

# O objeto direto precisa ser card; "criar um projeto com cards" continua sendo
# criacao de plano. Esta distincao evita que "criar um novo card" pergunte
# "qual plano?" (defeito real de 22/11/2026).
_CRIACAO_DE_CARD = re.compile(
    r"\b(?:criar|crie|cria|criem|adicionar|adicione|adiciona|adicionem|"
    r"acrescentar|acrescente|acrescenta|incluir|inclua|inclui|gerar|gere)\b"
    r"(?:\s+(?:um|uma|o|a|os|as|novo|nova|novos|novas|mais|dois|duas|tres|"
    r"quatro|cinco|seis|[2-9]))*\s+"
    r"(?:card|cartao|cartoes|cards)\b")
_QUERO_CARD = re.compile(
    r"\b(?:quero|preciso de|me (?:de|da)|faca)\s+(?:um|uma|o|a)?\s*"
    r"(?:card|cartao)\b")


def normalizar(texto: str) -> str:
    bruto = unicodedata.normalize("NFKD", str(texto or "")).casefold()
    return "".join(c for c in bruto if not unicodedata.combining(c)).strip()


def consulta_plano_atual(texto: str) -> bool:
    n = normalizar(texto)
    return bool(re.search(
        r"\b(?:qual|que)\b.*\b(?:plano|projeto|produto|canvas)\b.*"
        r"\b(?:abri|abrir|abriu|aberto|aberta|atual|estamos|estou|trabalhando)\b|"
        r"\b(?:em qual|onde) estamos\b|\bqual.*nome.*(?:plano|projeto|produto)\b", n))


@dataclass
class Intencao:
    tipo: str
    dados: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResultadoComando:
    tratado: bool
    resposta: str = ""
    acoes: list[dict] = field(default_factory=list)
    opcoes: list[dict] = field(default_factory=list)
    pendente: bool = False


def _extrair(texto: str) -> dict:
    n = normalizar(texto)
    tipo = "Geral"
    for chave, valor in _PALAVRA_TIPO:
        if chave in n:
            tipo = valor
            break
    tema = ""
    encontrado = _TEMA.search(n)
    if encontrado:
        tema = encontrado.group(1).strip(" .!?;:")
        tema = re.sub(r"^(plano|projeto|produto|estudo)\s+", "", tema).strip()
    titulo = f"{tipo} para {tema}" if tema and tipo != "Geral" else ""
    explicito = re.search(
        r"\b(?:chamado|chamada|denominad[oa]|com\s+(?:o\s+)?t[ií]tulo)\s+(.+)$",
        str(texto or ''), re.I)
    if explicito:
        titulo = explicito.group(1).strip(' .!?;:"“”')
    return {"tipo": tipo, "tema": tema, "titulo": titulo,
            "original": str(texto or "").strip()}


def reconhecer(texto: str, contexto: dict | None = None) -> Intencao:
    """Classifica apenas intenções claras; o resto segue o fluxo normal."""
    n = normalizar(texto)
    dados = _extrair(texto)
    if re.match(r"^(ainda\s+)?nao quero|^(nao|não)\s|desistir|deixa para depois",
                n):
        return Intencao("NEGAR", dados)
    if consulta_plano_atual(texto):
        return Intencao('PLANO_ATUAL', dados)
    if re.match(r'^(?:nia[, ]+)?(?:como|me explique|me explica|explique)\b', n):
        return Intencao('EXPLICAR', dados)
    if re.search(r"\b(?:abra|abre|abrir|mostre|mostrar|exiba|exibir|gerenciar)\b.*"
                 r"\b(?:(?:gerenciador|janela|janelas|lista|tela|painel)(?: d[aeo]s?)?(?: nia)?(?: d[eo]s?)? planos|(?:meus |os )?planos)\b", n):
        return Intencao('GERENCIADOR', dados)
    if re.search(r"\b(?:quais|que|quantos)\b.*\bplanos\b|"
                 r"\b(?:liste|listar|listagem)\b.*\bplanos\b|"
                 r"\bmeus planos\b", n) and not re.search(
                     r"\b(?:abra|abre|abrir|mostre|mostrar|exiba|exibir|gerenciar)\b", n):
        return Intencao('LISTAR_PLANOS', dados)
    # Trocar de plano usa a própria abertura, que só sai do atual após salvar.
    abertura = re.search(r"\b(?:abra|abre|abrir|troque para|mude para)\s+"
                        r"(?:(?:o|um|outro|esse|este)\s+)?(?:plano|projeto|produto)\b(.*)$", n)
    if abertura:
        alvo = abertura[1].strip(' .!?;:')
        alvo = re.sub(r'^(?:chamado|de nome)\s+', '', alvo)
        dados['tema'] = alvo.strip('"“”')
        return Intencao('ABRIR', dados)
    if re.search(r"\b(?:feche|fecha|fechar|encerre|encerrar|saia|sair)\b.*"
                 r"\b(?:plano|projeto|produto|canvas)\b", n):
        return Intencao('FECHAR', dados)
    if re.search(r"me explica|explique|como (planejar|criar)|o que e", n):
        return Intencao("EXPLICAR", dados)
    if re.search(r"titulo (desse|do|deste) card|titulo do card", n):
        return Intencao("CARD_TITULO", dados)
    if re.search(r"o que falta|tarefas pendentes|progresso do", n):
        return Intencao("PROGRESSO", dados)
    if re.search(r"objetivo (no|do|da|de)|qual era meu objetivo", n):
        return Intencao("OBJETIVO", dados)
    if re.search(r"continuar meus estudos|continua meu estudo|retomar", n):
        dados["tipo"] = "Estudos"
        return Intencao("RETOMAR", dados)
    if re.search(r"vamos planejar|quero criar|criar (um|uma|o|a|estudo)|comecar|iniciar", n) \
            and not _CRIACAO_DE_CARD.search(n) and not _QUERO_CARD.search(n):
        return Intencao("CRIAR", dados)
    if re.search(r"^(?:nia[, ]+)?(?:abra|abre|abrir|continua|continue|retoma|retome)\b", n):
        return Intencao("ABRIR", dados)
    return Intencao("NENHUMA", dados)


class SessaoComandosPlanos:
    """Estado conversacional local; uma instância por sessão da NIA."""

    def __init__(self, armazenamento=None):
        self.armazenamento = armazenamento or BP
        self.pendente: dict | None = None
        self.opcoes: list[dict] = []
        self._vistos: dict[str, float] = {}

    # ── API principal ───────────────────────────────────────────────────
    def processar(self, texto: str, origem: str = "texto",
                  contexto: dict | None = None,
                  armazenamento=None) -> ResultadoComando:
        contexto = contexto or {}
        storage = armazenamento or self.armazenamento
        agora = time.time()
        chave = f"{origem}:{contexto.get('sessao_id') or contexto.get('plano_id', '')}:{normalizar(texto)}"
        if agora - self._vistos.get(chave, 0.0) < 4.0:
            return ResultadoComando(True, "")
        self._vistos[chave] = agora
        if len(self._vistos) > 200:
            self._vistos = {k: v for k, v in self._vistos.items()
                            if agora - v < 60.0}

        if self.pendente and agora - self.pendente.get("em", 0.0) > 180.0:
            self.pendente = None
            self.opcoes = []
        intencao = reconhecer(texto, contexto)
        if intencao.tipo in ('PLANO_ATUAL', 'GERENCIADOR', 'FECHAR', 'ABRIR',
                             'LISTAR_PLANOS'):
            # Navegação/consulta explícita substitui uma escolha antiga, sem
            # consumir a consulta como nome de um plano em criação.
            if intencao.tipo != 'PLANO_ATUAL':
                self.pendente = None
                self.opcoes = []
            return self._executar(intencao, contexto, storage)
        if self.pendente:
            return self._responder_pendente(texto, contexto, storage)

        intencao = reconhecer(texto, contexto)
        if intencao.tipo == "EXPLICAR" or intencao.tipo == "NENHUMA":
            return ResultadoComando(False)
        if intencao.tipo == "NEGAR":
            return ResultadoComando(True, "")
        return self._executar(intencao, contexto, storage)

    # ── respostas pendentes ─────────────────────────────────────────────
    def _responder_pendente(self, texto: str, contexto: dict, storage) -> ResultadoComando:
        n = normalizar(texto)
        if any(p in n for p in ("cancelar", "desistir", "esquece")):
            self.pendente = None
            self.opcoes = []
            return ResultadoComando(True, "Cancelado.")
        pendente = self.pendente or {}
        if pendente.get("tipo") == "criar":
            return self._criar(texto, pendente.get("dados", {}), storage)
        if pendente.get("tipo") == "escolha":
            indice = self._ordinal(n)
            if indice is None or indice >= len(self.opcoes):
                return ResultadoComando(True, self._listar_opcoes(), pendente=True)
            opcao = self.opcoes[indice]
            self.pendente = None
            self.opcoes = []
            return self._acao_da_opcao(opcao, contexto, storage)
        self.pendente = None
        return ResultadoComando(False)

    @staticmethod
    def _ordinal(n: str) -> int | None:
        numeros = {"primeiro": 0, "segundo": 1, "terceiro": 2,
                   "quarto": 3, "quinto": 4}
        encontrado = re.search(r"^(?:o |a )?(primeir[oa]|segund[oa]|terceir[oa]|quart[oa]|quint[oa])$", n)
        if encontrado:
            chave = encontrado.group(1)
            for nome, indice in numeros.items():
                if chave.startswith(nome[:6]):
                    return indice
        if re.match(r"^(?:o |a )?[1-9]$", n):
            return int(n[-1]) - 1
        return None

    def _acao_da_opcao(self, opcao: dict, contexto: dict, storage) -> ResultadoComando:
        acao = opcao.get("acao", "abrir")
        plano_id = opcao.get("plano_id")
        if acao == "criar":
            dados = {"tipo": opcao.get("tipo", "Geral"),
                     "original": "", "titulo": "", "tema": ""}
            self.pendente = {"tipo": "criar", "dados": dados,
                             "em": time.time()}
            return ResultadoComando(True, "Qual é o título do novo plano?", pendente=True)
        if acao == "restaurar":
            plano = storage.carregar(plano_id)
            if plano is None:
                return ResultadoComando(True, "Essa opção não está mais disponível.")
            storage.restaurar(plano.id, plano.revisao)
            return ResultadoComando(True, f"Plano restaurado: {plano.titulo}.",
                                    [{"tipo": "abrir_canvas", "plano_id": plano.id}])
        if acao == "visualizar":
            return ResultadoComando(True, "Visualizando o plano arquivado.",
                                    [{"tipo": "abrir_manager"}])
        return ResultadoComando(True, f"Abrindo {opcao.get('titulo', 'o plano')}.",
                                [{"tipo": "abrir_canvas", "plano_id": plano_id}])

    # ── execução das intenções ──────────────────────────────────────────
    def _executar(self, intencao: Intencao, contexto: dict, storage) -> ResultadoComando:
        tipo = intencao.tipo
        dados = intencao.dados
        if tipo == 'PLANO_ATUAL':
            plano = contexto.get('plano')
            return ResultadoComando(True, (
                f'O plano aberto é {plano.titulo} ({plano.tipo}). Objetivo: {plano.objetivo}.'
                if plano is not None else 'Nenhum plano está aberto no Canvas agora.'))
        if tipo == 'GERENCIADOR':
            return ResultadoComando(True, 'Mostrando a janela NIA Planos.', [{'tipo':'abrir_manager'}])
        if tipo == 'LISTAR_PLANOS':
            return self._listar_planos(storage)
        if tipo == 'FECHAR':
            if contexto.get('plano') is None:
                return ResultadoComando(True, 'Nenhum plano está aberto no Canvas agora.')
            return ResultadoComando(True, 'Plano fechado. Mostrando NIA Planos.', [{'tipo':'fechar_canvas'}])
        if tipo == "CRIAR":
            return self._criar(None, dados, storage)
        if tipo in ("RETOMAR", "ABRIR"):
            return self._localizar(dados, storage)
        if tipo == "OBJETIVO":
            return self._objetivo(dados, contexto, storage)
        if tipo == "PROGRESSO":
            return self._progresso(contexto, storage)
        if tipo == "CARD_TITULO":
            return self._titulo_card(contexto)
        return ResultadoComando(False)

    def _listar_planos(self, storage) -> ResultadoComando:
        """Consulta local de planos, sem abrir o gerenciador nem criar nada."""
        planos, _avisos = storage.listar()
        if not planos:
            return ResultadoComando(True, 'Nenhum plano cadastrado ainda.')
        ativos = [p for p in planos if p.status == 'ativo']
        arquivados = [p for p in planos if p.status != 'ativo']
        if ativos:
            titulos = [p.titulo for p in ativos]
            visiveis = ', '.join(titulos[:10])
            if len(titulos) > 10:
                visiveis += f' (e mais {len(titulos) - 10})'
            mensagem = f'Planos ativos ({len(ativos)}): {visiveis}.'
        else:
            mensagem = 'Nenhum plano ativo.'
        if arquivados:
            mensagem += f' Há {len(arquivados)} plano(s) arquivado(s).'
        return ResultadoComando(True, mensagem)

    def _criar(self, resposta: str | None, dados: dict, storage) -> ResultadoComando:
        self.pendente = None
        self.opcoes = []
        tipo = dados.get("tipo", "Geral")
        if tipo not in TIPOS:
            tipo = "Geral"
        titulo = dados.get("titulo") or ""
        original = str(dados.get("original") or "")
        if resposta is not None:
            titulo = str(resposta or "").strip()
            objetivo = original or titulo
        else:
            objetivo = original or titulo
        if not titulo or not objetivo:
            pergunta = {
                "Produto": "Qual é o produto?", "Projeto": "Qual é o projeto?",
                "Estudos": "Qual é o estudo?", "Conteúdo": "Qual é o conteúdo?",
                "Finanças": "Qual é o plano financeiro?",
            }.get(tipo, "Qual é o plano?")
            self.pendente = {"tipo": "criar", "dados": {**dados, "tipo": tipo},
                             "em": time.time()}
            return ResultadoComando(True, pergunta, pendente=True)
        try:
            plano = storage.criar(titulo, objetivo, tipo)
            if tipo in MP.TIPOS_MODELO and storage is BP:
                plano = BP.inicializar_mapa(plano.id)
                mapa = MP.aplicar_estrutura_no_mapa(
                    plano.mapa,
                    MP.estrutura_modelo(tipo, titulo, objetivo),
                    plano.mapa.get("raiz_id"))
                plano = BP.atualizar(plano.id, {"mapa": mapa}, plano.revisao)
        except Exception as exc:
            return ResultadoComando(
                True, f"Não foi possível criar o plano ({type(exc).__name__}). "
                      "Os dados ficaram guardados para nova tentativa.")
        return ResultadoComando(
            True, f"Plano criado: {plano.titulo}. Abrindo o Canvas.",
            [{"tipo": "abrir_canvas", "plano_id": plano.id}])

    def _localizar(self, dados: dict, storage) -> ResultadoComando:
        termo = str(dados.get("tema") or "")
        tipo = dados.get("tipo", "Geral")
        planos, _ = storage.listar()
        # Prefira o título completo; não remova preposições que fazem parte
        # dele. A forma “abra o projeto do ...” é um fallback de linguagem.
        exatos = [p for p in planos if normalizar(p.titulo) == normalizar(termo)] if termo else []
        if termo and not exatos:
            termo = re.sub(r'^(?:do|da|de)\s+', '', termo)
        ativos = [p for p in planos if p.status == "ativo"]
        candidatos = [p for p in exatos if p.status == 'ativo'] or (storage.buscar(ativos, termo) if termo else ativos)
        if tipo != "Geral":
            filtrados = [p for p in candidatos if p.tipo == tipo]
            if filtrados:
                candidatos = filtrados
        if not candidatos:
            todos = storage.buscar(planos, termo) if termo else planos
            if todos and all(p.status == "arquivado" for p in todos):
                return self._oferecer_opcoes(
                    todos, "Esse plano está arquivado. O que deseja fazer?",
                    acoes=("visualizar", "restaurar"))
            return ResultadoComando(
                True, "Não encontrei um plano com esse nome. Posso abrir o "
                      "Gerenciador ou criar um novo — você escolhe.")
        if len(candidatos) > 1:
            return self._oferecer_opcoes(candidatos, "Encontrei vários planos:")
        plano = candidatos[0]
        return ResultadoComando(True, f"Abrindo {plano.titulo}.",
                                [{"tipo": "abrir_canvas", "plano_id": plano.id}])

    def _oferecer_opcoes(self, planos: list, mensagem: str,
                         acoes: tuple[str, ...] = ("abrir",)) -> ResultadoComando:
        self.opcoes = []
        linhas = [mensagem]
        for i, plano in enumerate(planos):
            rotulo = plano.titulo
            self.opcoes.append({"plano_id": plano.id, "titulo": rotulo,
                                "acao": acoes[0], "tipo": plano.tipo})
            linhas.append(f"{i + 1}) {rotulo} — {plano.tipo} — {plano.status}")
        if acoes == ("abrir",):
            linhas.append(f"{len(planos) + 1}) Criar novo plano")
        else:
            for acao in acoes[1:]:
                self.opcoes.append({"plano_id": planos[0].id,
                                    "titulo": planos[0].titulo,
                                    "acao": acao, "tipo": planos[0].tipo})
                linhas.append(acao.capitalize())
        self.pendente = {"tipo": "escolha", "em": time.time()}
        return ResultadoComando(True, " ".join(linhas), opcoes=list(self.opcoes),
                                pendente=True)

    def _listar_opcoes(self) -> str:
        return " ".join(
            f"{i + 1}) {o.get('titulo', 'opção')}" for i, o in enumerate(self.opcoes))

    def _plano_por_referencia(self, dados: dict, contexto: dict, storage):
        plano = contexto.get("plano") if contexto.get("plano_id") else None
        if plano is not None:
            return plano
        termo = str(dados.get("tema") or "")
        if not termo:
            return None
        planos, _ = storage.listar()
        encontrados = storage.buscar(planos, termo)
        return encontrados[0] if len(encontrados) == 1 else None

    def _objetivo(self, dados: dict, contexto: dict, storage) -> ResultadoComando:
        plano = self._plano_por_referencia(dados, contexto, storage)
        if plano is None:
            return ResultadoComando(True, "Qual plano você quer consultar?")
        acoes = [{"tipo": "abrir_canvas", "plano_id": plano.id}]
        return ResultadoComando(
            True, f"O objetivo de {plano.titulo} é: {plano.objetivo}", acoes=acoes)

    def _progresso(self, contexto: dict, storage) -> ResultadoComando:
        plano = contexto.get("plano") if contexto.get("plano_id") else None
        if plano is None:
            return ResultadoComando(True, "Qual plano você quer consultar?")
        r = resumo_progresso(plano)
        if r["sem_tarefas"]:
            return ResultadoComando(True, "Esse plano ainda não tem tarefas cadastradas.")
        pendente = r["pendente"]
        andamento = r["em_andamento"]
        bloqueado = r["bloqueado"]
        partes = [f"{pendente} pendente(s)", f"{andamento} em andamento",
                  f"{bloqueado} bloqueada(s)"]
        return ResultadoComando(True, "Progresso: " + ", ".join(partes) + ".")

    def _titulo_card(self, contexto: dict) -> ResultadoComando:
        card_id = contexto.get("card_id")
        plano = contexto.get("plano")
        if not card_id or plano is None:
            return ResultadoComando(
                True, "Nenhum card selecionado. Selecione um card ou me diga qual.")
        card = BP.card_por_id(plano, card_id)
        if card is None:
            return ResultadoComando(True, "Esse card não existe mais no mapa.")
        return ResultadoComando(True, f"O título do card é {card.get('titulo')}.")
