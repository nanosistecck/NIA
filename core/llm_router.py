# -*- coding: utf-8 -*-
"""Pool de credenciais e roteamento com estratégias e failover limitado.

O roteador do processo combina SQLite e fontes JSON legadas, preserva sua
identidade nas recargas e aplica cooldowns por credencial. Consumidores de endpoint
fixo usam resolver(); clientes configuráveis recebem resolver_conexao().
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import time

# Status possiveis de uma chave do pool.
CHAVE_ATIVA = "ativo"          # pronta para ser usada
CHAVE_COOLDOWN = "cooldown"    # em pausa ate `cooldown_ate`
CHAVE_INVALIDA = "invalida"    # a chave recusou (proxima tenta outra)
CHAVE_ESGOTADA = "esgotada"    # cota esgotada (proxima tenta outra)

# Classes de falha (adaptação do error-classify do FreeLLMAPI).
T_INVALIDA = "chave_invalida"
T_QUOTA = "quota"
T_MODELO = "modelo_indisponivel"
T_SERVIDOR = "servidor"
T_TIMEOUT = "timeout"
T_DESCONHECIDA = "desconhecida"
T_PERMISSAO = 'permissao'

# Esperas das falhas de credencial. Modelos têm controle por operação no cliente;
# credenciais recusadas só retornam após reteste ou substituição explícita.
_SEGUNDOS = {
    T_INVALIDA: 12 * 3600.0,
    T_QUOTA: 60.0,
    T_SERVIDOR: 30.0,
    T_TIMEOUT: 20.0,
    T_DESCONHECIDA: 30.0,
    T_PERMISSAO: 60.0,
}

# CAMINHOS SEMPRE ABSOLUTOS (18/11/2026). O NIA roda de pastas diferentes
# (atalho do Windows, teste, dashboard) e um caminho relativo errado devolvia
# "config vazio" em silencio — o roteador ficava sem chave e ninguem via o erro.
_RAIZ = Path(__file__).resolve().parents[1]
CONFIG_PADRAO = _RAIZ / "config" / "llm_routing.json"
API_CONFIG_PATH = _RAIZ / 'config' / 'api_keys.json'

# APELIDOS DE PROVEDOR (18/11/2026) — o achado que travava a voz de vez.
#
# O catalogo (`core/provedores.py`) chama a Gemini de **"google"**, mas a cadeia
# do roteador e TODO o codigo de voz falam **"gemini"**. Resultado medido nesta
# maquina: uma chave da Gemini cadastrada na tela ficava no pool como "google",
# `resolver("gemini")` nao a encontrava e o NIA continuava mudo — com a chave
# certa, valida, guardada no banco.
_APELIDOS = {
    "google": "gemini",
    "google gemini": "gemini",
    "google ai": "gemini",
    "google ai studio": "gemini",
    "chatgpt": "openai",
    "open ai": "openai",
}


def provedor_canonico(nome: str) -> str:
    """Nome interno do provedor (``google`` -> ``gemini``, ``chatgpt`` -> ``openai``)."""
    baixo = str(nome or "").strip().lower()
    return _APELIDOS.get(baixo, baixo)


@dataclass
class Chave:
    """Estado de UMA chave dentro do pool."""

    provedor: str
    chave: str = field(repr=False)
    rotulo: str = ""
    status: str = CHAVE_ATIVA
    cooldown_ate: float = 0.0
    erro: str = ""
    falhas: int = 0
    sucessos: int = 0
    uso_tokens: int = 0
    # Vindos do banco (`config/nia.db`): id para gravar estado de volta e os
    # dois campos que o provedor genérico precisa (modelo e endpoint).
    id: int = 0
    modelo: str = ""
    base_url: str = ""
    revision: int = 0
    validacao_estado: str = 'nao_verificada'


class KeyPool:
    """Gerencia chaves por provedor, cada uma com estado proprio."""

    def __init__(self) -> None:
        self._por_provedor: dict[str, list[Chave]] = {}

    def adicionar(self, provedor: str, chave: str, rotulo: str = "") -> Chave:
        """Registra uma chave no pool (nao duplica entradas iguais)."""
        for c in self._por_provedor.get(provedor, []):
            if c.chave == chave:
                return c
        nova = Chave(provedor=provedor, chave=chave, rotulo=rotulo)
        self._por_provedor.setdefault(provedor, []).append(nova)
        return nova

    def disponiveis(self, provedor: str) -> list[Chave]:
        """Chaves prontas para uso agora, nesta ordem.

        Falhas transitórias e cota voltam após o cooldown. Credenciais recusadas
        exigem reteste ou substituição; a espera não as reativa.

        A ORDEM E' A DO CADASTRO. Uma chave recem-colada so' assume depois que
        a anterior falha (e ai a falha a poe em castigo) — trocar a ordem faria
        uma chave nova "roubar" a vez de uma que ja' estava funcionando.
        """
        agora = time.time()
        prontas: list[Chave] = []
        for c in self._por_provedor.get(provedor, []):
            if c.status in (CHAVE_COOLDOWN, CHAVE_ESGOTADA) and c.cooldown_ate and agora >= c.cooldown_ate:
                c.status = CHAVE_ATIVA
                c.cooldown_ate = 0.0
            if c.status == CHAVE_ATIVA and agora >= c.cooldown_ate:
                prontas.append(c)
        return prontas

    def obter(self, provedor: str) -> Chave | None:
        """Melhor chave disponivel do provedor (ou None)."""
        disp = self.disponiveis(provedor)
        return disp[0] if disp else None

    def provedores(self) -> list[str]:
        """Ids de todos os provedores que tem alguma chave registrada."""
        return list(self._por_provedor)


    def registrar_falha(self, chave: Chave, motivo: str, segundos: float = 0.0) -> None:
        """Marca a chave como problematica e agenda o cooldown de recuperacao."""
        if motivo == T_MODELO:
            return  # erro da operação/modelo não condena a credencial inteira
        if not chave.id:
            # Evidência concreta de falha também deve valer para fontes JSON
            # após reinício. Importação aditiva não desfaz exclusão explícita.
            from core.db_chaves import adicionar_chave
            chave.id = adicionar_chave(chave.provedor, chave.chave, chave.rotulo,
                chave.modelo, chave.base_url, explicita=False) or 0
        chave.falhas += 1
        chave.erro = motivo
        segs = segundos or _SEGUNDOS.get(motivo, 30.0)
        if motivo == T_INVALIDA:
            chave.status = CHAVE_INVALIDA
        elif motivo == T_QUOTA:
            chave.status = CHAVE_ESGOTADA
        else:
            chave.status = CHAVE_COOLDOWN
        chave.cooldown_ate = time.time() + segs
        # Estado gravado no banco: o cooldown sobrevive a fechar e abrir o NIA.
        try:
            if chave.id > 0:
                from core.db_chaves import registrar_falha as _gravar  # noqa: PLC0415
                _gravar(chave.id, segs, chave.status, revision=chave.revision)
        except Exception:
            pass

    def registrar_sucesso(self, chave: Chave) -> None:
        """Chamada apos resposta boa: chave volta a ficar ativa."""
        chave.status = CHAVE_ATIVA
        chave.validacao_estado = 'validado'
        chave.erro = ""
        chave.sucessos += 1
        # FALHAS SAO CONSECUTIVAS (18/11/2026): sem zerar, uma chave que foi
        # recusada uma vez e depois corrigida carregava a mancha para sempre e
        # perdia a vez para uma chave nunca usada na estrategia `auto`.
        chave.falhas = 0
        chave.cooldown_ate = 0.0
        try:
            if chave.id > 0:
                from core.db_chaves import registrar_sucesso as _gravar  # noqa: PLC0415
                _gravar(chave.id, revision=chave.revision)
        except Exception:
            pass


def classificar_erro(texto: str) -> str:
    """Traduz a mensagem de erro do provedor para a classe de falha."""
    baixo = str(texto or "").lower()
    if any(s in baixo for s in ("api key not valid", "api_key_invalid", '401', 'unauthorized',
                               "api key expired", "invalid_api_key")):
        return T_INVALIDA
    if any(s in baixo for s in ('403', 'permission_denied', 'permission denied')):
        return T_PERMISSAO
    if any(s in baixo for s in ("429", "resource_exhausted", "quota", "rate limit", "too many requests", 'billing', 'credit_balance')):
        return T_QUOTA
    if "404" in baixo or "not_found" in baixo or "no longer available" in baixo:
        return T_MODELO
    if any(s in baixo for s in ("500", "internal", "503", "overloaded")):
        return T_SERVIDOR
    if any(s in baixo for s in ("timeout", "timed out", "deadline")):
        return T_TIMEOUT
    return T_DESCONHECIDA


class Router:
    """Roteador com failover automatico sobre o pool de chaves.

    Estrategias (adaptacao do scoring do FreeLLMAPI):
      - ``auto``            -> composto padrao (balanced) na cadeia (padrao).
      - ``priority``        -> ordem explicita da cadeia.
      - ``balanced``        -> composto: inteligencia + velocidade + confiabilidade.
      - ``smartest``        -> maior rank de inteligencia.
      - ``fastest``         -> maior rank de velocidade.
      - ``reliable``        -> maior taxa de acerto da chave.
      - ``custom``          -> pesos do config (pesos).
      - ``least-remaining`` -> chave com menos uso (mais folga).
      - ``decision``        -> reserva para escolha por modelo (hoje = balanced).
    """

    CADEIA_PADRAO = ["gemini", "openai", "codex"]
    ESTRATEGIAS = ("auto", "priority", "balanced", "smartest", "fastest",
                   "reliable", "custom", "decision", "least-remaining")

    def __init__(self, estrategia: str = "auto", cadeia: list[str] | None = None) -> None:
        self.estrategia = estrategia if estrategia in self.ESTRATEGIAS else "auto"
        self.cadeia: list[str] = list(cadeia) if cadeia else list(self.CADEIA_PADRAO)
        self.pool = KeyPool()
        self.ranks: dict[str, dict] = {}
        self.pesos_custom: dict[str, float] = {}
        # Provedores OpenAI-compat do catalogo (core/provedores.py). "reserva"
        # = ultimo degrau da escada; "preferido" = antes do Codex da VPS.
        self.genericos: dict = {"ativo": True, "prioridade": "reserva", "max": 3}

    def registrar(self, provedor: str, chave: str, rotulo: str = "") -> Chave:
        """Adiciona uma chave ao pool, sob o nome CANONICO do provedor."""
        return self.pool.adicionar(provedor_canonico(provedor), chave, rotulo)

    def carregar_do_banco(self) -> int:
        """Carrega as chaves do banco local (`config/nia.db`).

        O estado de cada chave (status, cooldown, falhas, sucessos, uso) vem do
        banco. Devolve quantas chaves foram carregadas.
        """
        try:
            from core.db_chaves import listar_chaves, identidade_bloqueada
        except Exception:
            return 0
        n = 0
        rows = listar_chaves()
        pausadas = {(provedor_canonico(r['platform']), r['key']) for r in rows if not r.get('enabled')}
        for row in rows:
            identidade = (provedor_canonico(row['platform']), row['key'])
            if identidade in pausadas or identidade_bloqueada(*identidade):
                continue
            c = self.registrar(str(row.get("platform")), str(row.get("key") or ""),
                               str(row.get("label") or ""))
            if c.id:
                continue  # duplicatas legadas preservam a prioridade do primeiro ID
            c.falhas = int(row.get("falhas") or 0)
            c.sucessos = int(row.get("sucessos") or 0)
            c.uso_tokens = int(row.get("uso_tokens") or 0)
            c.status = str(row.get("status") or "ativo")
            c.cooldown_ate = float(row.get("cooldown_ate") or 0.0)
            c.id = int(row.get("id") or 0)
            c.modelo = str(row.get("modelo") or "")
            c.base_url = str(row.get("base_url") or "")
            c.revision = int(row.get('revision') or 0)
            c.validacao_estado = row.get('validacao_estado', 'nao_verificada')
            n += 1
        return n

    def definir_estrategia(self, estrategia: str) -> None:
        self.estrategia = estrategia if estrategia in self.ESTRATEGIAS else "auto"

    @classmethod
    def a_partir_config(cls, caminho: str | Path | None = None) -> "Router":
        """Carrega o Router de uma configuracao INDEPENDENTE (FASE 3).

        Sem `caminho`, usa ``config/llm_routing.json`` em caminho ABSOLUTO. O
        banco de chaves e sempre lido antes, entao mesmo sem o arquivo o
        roteador ja sobe com o que foi cadastrado na tela.
        Qualquer erro de leitura devolve um Router padrao — nada quebra por causa do config.
        """
        roteador = cls()
        roteador.carregar_do_banco()
        try:
            dados = json.loads(Path(caminho or CONFIG_PADRAO).read_text(encoding="utf-8"))
        except Exception:
            return roteador
        cfg = dados.get("router") or {} if isinstance(dados, dict) else {}
        roteador.definir_estrategia(str(cfg.get("estrategia") or "auto"))
        cadeia = cfg.get("cadeia") or cls.CADEIA_PADRAO
        roteador.cadeia = list(cadeia) if isinstance(cadeia, list) else list(cls.CADEIA_PADRAO)
        provedores = cfg.get("provedores") or {}
        if isinstance(provedores, dict):
            for nome, spec in provedores.items():
                if not isinstance(spec, dict):
                    continue
                chaves = spec.get("chaves") or spec.get("api_keys") or []
                if isinstance(chaves, list):
                    for k in chaves:
                        if k:
                            from core.db_chaves import fonte_legada_permitida
                            if fonte_legada_permitida(str(nome), str(k)):
                                c = roteador.registrar(str(nome), str(k), str(spec.get("rotulo") or ""))
                                c.modelo = str(spec.get('modelo') or '')
                                c.base_url = str(spec.get('base_url') or '')
        # Ranks por provedor (inteligencia/velocidade) para as estrategias.
        ranks: dict[str, dict] = {}
        for nome, spec in (provedores.items() if isinstance(provedores, dict) else {}):
            if not isinstance(spec, dict):
                continue
            if isinstance(spec.get("ranks"), dict):
                ranks[str(nome)] = spec["ranks"]
            elif any(k in spec for k in ("inteligencia", "velocidade")):
                ranks[str(nome)] = {"inteligencia": spec.get("inteligencia"),
                                    "velocidade": spec.get("velocidade")}
        roteador.ranks = ranks
        pesos = cfg.get("pesos") or {}
        if isinstance(pesos, dict):
            roteador.pesos_custom = {str(k): float(v) for k, v in pesos.items()
                                     if isinstance(v, (int, float))}
        # Provedores genericos (OpenAI-compat): como e quando entram na escada.
        gen = cfg.get("genericos")
        if isinstance(gen, dict):
            roteador.genericos = {
                "ativo": bool(gen.get("ativo", True)),
                "prioridade": str(gen.get("prioridade") or "reserva").lower(),
                "max": int(gen.get("max") or 3),
            }
        return roteador

    def _confiabilidade(self, chave: Chave) -> float:
        """Taxa de acerto da chave (0 a 1); sem historico = 1.0."""
        total = int(chave.sucessos) + int(chave.falhas)
        if total <= 0:
            return 1.0
        return int(chave.sucessos) / total

    def pontuar(self, provedor: str, chave: Chave) -> float:
        """Pontuacao do par (provedor, chave) para a estrategia ativa."""
        ranks = self.ranks.get(provedor) or {}
        intel = float(ranks.get("inteligencia") or 50.0)
        vel = float(ranks.get("velocidade") or 50.0)
        confi = self._confiabilidade(chave) * 100.0
        if self.estrategia == "smartest":
            return intel
        if self.estrategia == "fastest":
            return vel
        if self.estrategia == "reliable":
            return confi
        if self.estrategia == "custom":
            pesos = self.pesos_custom or {"inteligencia": 1.0, "velocidade": 1.0,
                                          "confiabilidade": 1.0}
            return (float(pesos.get("inteligencia", 1.0)) * intel
                    + float(pesos.get("velocidade", 1.0)) * vel
                    + float(pesos.get("confiabilidade", 1.0)) * confi)
        # balanced / auto / decision
        return 0.4 * intel + 0.3 * vel + 0.3 * confi

    def _proximo(self, preferido: str | None = None, excluir=None) -> tuple[str, Chave] | None:
        ordem = [preferido] if preferido else list(self.cadeia)
        candidatos: list[tuple[str, Chave]] = []
        for provedor in ordem:
            provedor = provedor_canonico(provedor)
            for c in self.pool.disponiveis(provedor):
                if not excluir or id(c) not in excluir:
                    candidatos.append((provedor, c))
        if not candidatos:
            return None
        if self.estrategia == "priority":
            return candidatos[0]
        if self.estrategia == "least-remaining":
            return min(candidatos, key=lambda pc: pc[1].uso_tokens)
        if self.estrategia in ("balanced", "smartest", "fastest", "reliable",
                               "custom", "auto", "decision"):
            return max(candidatos, key=lambda pc: self.pontuar(pc[0], pc[1]))
        return candidatos[0]

    def escolher(self, preferido: str | None = None) -> tuple[str, Chave] | None:
        """Retorna o primeiro (provedor, chave) disponivel da cadeia."""
        return self._proximo(preferido)

    def provedores_disponiveis(self) -> list[str]:
        """Provedores com pelo menos uma chave pronta para uso agora."""
        return [p for p in self.pool.provedores() if self.pool.obter(p) is not None]

    def chave_ativa(self, provedor: str = "gemini") -> str | None:
        """Chave ativa para o provedor: pool (config independente) ou chave do usuario."""
        provedor = provedor_canonico(provedor)
        from core.provedores import base_url_do_provedor
        padrao = base_url_do_provedor('google' if provedor == 'gemini' else provedor).rstrip('/')
        for c in self.pool.disponiveis(provedor):
            # Consumidores que pedem só o segredo usam endpoint nativo fixo.
            # Conexões personalizadas exigem resolver_conexao().
            if not c.base_url or c.base_url.rstrip('/') == padrao:
                return c.chave
        return _chave_do_usuario(provedor)

    def executar_fallback(self, gerar, contexto: dict | None = None) -> tuple[bool, object, str]:
        """Tenta a cadeia ate achar uma resposta util.

        ``gerar(provedor: str, chave: Chave, **contexto) -> tuple[bool, object, str]``
        deve devolver ``(True, resultado, "")`` em sucesso ou ``(False, None, motivo)``
        em falha — e e essa falha que alimenta cooldown/fallback automatico.
        """
        contexto = contexto or {}
        max_tentativas = max(4, len(self.cadeia) * 4)
        ultimo_erro = ""
        tentativas = 0
        tentadas = set()
        while tentativas < max_tentativas:
            par = self._proximo(excluir=tentadas)
            if par is None:
                break
            provedor, chave = par
            tentadas.add(id(chave))
            ok, resultado, erro = gerar(provedor, chave, **contexto)
            tentativas += 1
            if ok:
                self.pool.registrar_sucesso(chave)
                return True, resultado, ""
            ultimo_erro = erro
            tipo = classificar_erro(erro)
            self.pool.registrar_falha(chave, tipo)
        return False, None, ultimo_erro


def _caminho_do_banco() -> Path:
    """Caminho do SQLite de chaves (o mesmo que `core/db_chaves.py` usa)."""
    try:
        from core.db_chaves import DB_PATH  # noqa: PLC0415
        return Path(DB_PATH)
    except Exception:
        novo = _RAIZ / "config" / "nia.db"
        antigo = _RAIZ / "config" / "jarvis.db"   # banco de antes da troca de nome
        return novo if novo.exists() or not antigo.exists() else antigo


def _assinatura() -> tuple:
    """Impressao digital barata das fontes do roteador (config + banco).

    Cadastrar/remover chave mexe no banco; editar a cadeia mexe no config. Com
    isto o roteador se refaz sozinho na proxima pergunta, sem reiniciar o NIA
    e sem ler o banco a cada chamada.
    """
    marcas = []
    for caminho in (CONFIG_PADRAO, _caminho_do_banco()):
        try:
            st = caminho.stat()
            marcas.append((str(caminho), st.st_mtime_ns, st.st_size))
        except OSError:
            marcas.append((str(caminho), 0, 0))
    return tuple(marcas)


_router_global: "Router | None" = None
_assinatura_global: tuple | None = None


def _reaproveitar(roteador: Router, caminho: str | Path) -> Router:
    """Recarrega o conteudo SEM trocar o objeto.

    A IDENTIDADE IMPORTA (18/11/2026): o `main` guarda o roteador num global e o
    `CerebroOpenRouter` guarda a referencia. Se cada recarga devolvesse um
    objeto novo, quem ja tinha o antigo continuaria com as chaves velhas e
    cadastrar chave so valeria para quem consultasse `resolver()` — metade do
    programa. Aqui o mesmo objeto passa a apontar para o pool novo.
    """
    novo = Router.a_partir_config(caminho)
    roteador.estrategia = novo.estrategia
    roteador.cadeia = novo.cadeia
    roteador.ranks = novo.ranks
    roteador.pesos_custom = novo.pesos_custom
    roteador.genericos = novo.genericos
    roteador.pool = novo.pool
    return roteador


def _global() -> Router:
    """O roteador UNICO do processo, refeito quando o banco/config mudam."""
    global _router_global, _assinatura_global
    assinatura = _assinatura()
    if _router_global is None:
        _router_global = Router.a_partir_config(CONFIG_PADRAO)
    elif assinatura != _assinatura_global:
        _reaproveitar(_router_global, CONFIG_PADRAO)
    _assinatura_global = assinatura
    return _router_global


def recarregar() -> Router:
    """Forca releitura do banco/config (a tela de chaves chama apos salvar)."""
    global _router_global, _assinatura_global
    if _router_global is None:
        _router_global = Router.a_partir_config(CONFIG_PADRAO)
    else:
        _reaproveitar(_router_global, CONFIG_PADRAO)
    _assinatura_global = _assinatura()
    return _router_global


def _achar_chave(roteador: Router, provedor: str, chave: str | None) -> Chave | None:
    """A chave citada (ou a ativa do provedor, quando nao vem qual foi)."""
    provedor = provedor_canonico(provedor)
    alvo = str(chave or "").strip()
    if alvo:
        for c in roteador.pool._por_provedor.get(provedor, []):  # noqa: SLF001
            if c.chave == alvo:
                return c
        return None
    return roteador.pool.obter(provedor)


def anotar_falha(provedor: str, erro: str, chave: str | None = None) -> str | None:
    """Registra que a chave falhou e devolve a CLASSE da falha.

    A voz usa isto para saber se adianta trocar de chave (cota/chave recusada)
    ou se o problema e outro (mudez, modelo fora). Nunca levanta excecao: o
    caminho da fala nao pode quebrar por causa de contabilidade.
    """
    try:
        roteador = _global()
        alvo = _achar_chave(roteador, provedor, chave)
        if alvo is None:
            legado = _chave_do_usuario(provedor)
            if legado and (not chave or chave == legado):
                alvo = Chave(provedor_canonico(provedor), legado, 'legada')
        if alvo is None:
            return None
        tipo = classificar_erro(erro)
        roteador.pool.registrar_falha(alvo, tipo)
        return tipo
    except Exception:
        return None


def anotar_sucesso(provedor: str, chave: str | None = None) -> None:
    """A chave respondeu: limpa cooldown/erro. So grava se havia o que limpar."""
    try:
        roteador = _global()
        alvo = _achar_chave(roteador, provedor, chave)
        if alvo is None:
            return
        if alvo.status == CHAVE_ATIVA and not alvo.cooldown_ate and alvo.falhas == 0 and alvo.validacao_estado == 'validado':
            return
        roteador.pool.registrar_sucesso(alvo)
    except Exception:
        pass


def proxima_chave(provedor: str, atual: str | None = None) -> str | None:
    """Outra chave pronta do provedor, diferente da que acabou de falhar.

    Devolve ``None`` quando nao ha substituta — quem chamou decide o que fazer
    (a voz, por exemplo, fica calada em vez de repetir a chave que estourou).
    """
    try:
        roteador = _global()
        provedor = provedor_canonico(provedor)
        for c in roteador.pool.disponiveis(provedor):
            from core.provedores import base_url_do_provedor
            padrao = base_url_do_provedor('google' if provedor == 'gemini' else provedor).rstrip('/')
            if c.chave != atual and (not c.base_url or c.base_url.rstrip('/') == padrao):
                return c.chave
        do_usuario = _chave_do_usuario(provedor)
        if do_usuario and do_usuario != atual:
            return do_usuario
        return None
    except Exception:
        return None


def carregar_router(caminho: str | Path | None = None) -> Router:
    """O roteador do processo (ou um novo, quando pedem um config especifico)."""
    if caminho is None:
        return _global()
    caminho = Path(caminho)
    try:
        padrao = caminho.resolve() == CONFIG_PADRAO.resolve()
    except Exception:
        padrao = False
    return _global() if padrao else Router.a_partir_config(caminho)


def _chave_do_usuario(provedor: str) -> str | None:
    """Chave unica do usuario (config/api_keys.json) — fallback do pool."""
    campos = {
        "gemini": ("gemini_api_key", "GEMINI_API_KEY", "google_api_key"),
        "openai": ("openai_api_key",),
        "openrouter": ("openrouter_api_key",),
    }.get(provedor_canonico(provedor), ())
    try:
        dados = json.loads(
            API_CONFIG_PATH
            .read_text(encoding="utf-8"))
        for campo in campos:
            valor = str(dados.get(campo) or "").strip()
            if valor:
                from core.db_chaves import fonte_legada_permitida
                if fonte_legada_permitida(provedor, valor):
                    return valor
    except Exception:
        pass
    return None


def resolver(provedor: str = "gemini") -> str | None:
    """Chave ativa para o provedor — banco (`nia.db`) primeiro, JSON depois.

    E A PORTA DA VOZ: `GeminiCharonVoice`, `GeminiConversa`, `GeminiCharonTTS` e
    `VozOpenAI` nascem chamando isto. Enquanto esta funcao criava um `Router()`
    vazio, chave cadastrada na tela nao chegava na fala e o NIA emudecia.
    """
    try:
        return _global().chave_ativa(provedor)
    except Exception:
        return _chave_do_usuario(provedor)


def resolver_conexao(provedor, router=None):
    """Resolve segredo, modelo e endpoint como uma única conexão."""
    provedor = provedor_canonico(provedor)
    # Atualiza também quem mantém referência ao roteador global.
    atual = _global()
    roteador = router if router is not None else atual
    escolhido = roteador.escolher(provedor)
    if escolhido:
        return escolhido[1]
    chave = _chave_do_usuario(provedor)
    return Chave(provedor, chave) if chave else None
