# -*- coding: utf-8 -*-
"""Base local dos planos da NIA (Etapa 1 do Canvas Infinito).

Um JSON UTF-8 por plano, na área de dados do usuário (fora da árvore de
trabalho). ``formato`` é a versão do formato; ``revisao`` é a revisão do
conteúdo. Toda gravação é atômica (``.tmp`` + ``os.replace``) e devolve um
novo ``Plano`` com a revisão incrementada — quem grava sempre reatribui o
objeto devolvido antes de outra gravação.

Sem PyQt, sem rede, sem serviços externos.
"""
from __future__ import annotations

import json
import os
import platform
import re
import unicodedata
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FORMATO = 1
TIPOS = ("Geral", "Produto", "Projeto", "Conteúdo", "Estudos", "Finanças")
STATUS = ("ativo", "arquivado")
_CHAVE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Alias de módulo: os testes isolam falhas de gravação substituindo este nome.
_replace = os.replace


class ErroPlano(Exception):
    """Falha de domínio da base de planos."""


class PlanoInvalido(ErroPlano):
    """Dados inválidos na leitura ou antes de gravar."""


class ConflitoDeRevisao(ErroPlano):
    """O arquivo no disco mudou desde a leitura; nada foi sobrescrito."""

    def __init__(self, revisao_local: int, revisao_disco: int):
        self.revisao_local = revisao_local
        self.revisao_disco = revisao_disco
        super().__init__(
            f"revisão local {revisao_local} != revisão no disco {revisao_disco}")


def _raiz_do_repo() -> Path:
    return Path(__file__).resolve().parents[1]


def _base_plataforma() -> Path:
    sistema = platform.system()
    if sistema == "Windows":
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        return base / "NIA-CyberBot"
    if sistema == "Darwin":
        return Path.home() / "Library" / "Application Support" / "NIA-CyberBot"
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "NIA-CyberBot"


def base_dados_usuario() -> Path:
    """Base adotada pela NIA. ``NIA_PLANOS_DIR`` tem precedência (testes)."""
    override = os.environ.get("NIA_PLANOS_DIR")
    if override and str(override).strip():
        return Path(override).expanduser().resolve()
    base = _base_plataforma().expanduser().resolve()
    try:
        base.relative_to(_raiz_do_repo())
    except ValueError:
        return base
    # Configuração apontando para dentro da árvore de trabalho: usar a
    # localização por usuário compatível com a plataforma.
    return _base_plataforma().expanduser().resolve()


def pasta_planos() -> Path:
    caminho = base_dados_usuario() / "planos"
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def novo_id() -> str:
    return uuid.uuid4().hex


def agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalizar(texto: str) -> str:
    bruto = unicodedata.normalize("NFKD", str(texto or "")).casefold()
    return "".join(c for c in bruto if not unicodedata.combining(c)).strip()


@dataclass
class Plano:
    id: str
    titulo: str
    objetivo: str
    tipo: str = "Geral"
    status: str = "ativo"
    criado_em: str = ""
    atualizado_em: str = ""
    formato: int = FORMATO
    revisao: int = 0
    extras: dict[str, Any] = field(default_factory=dict)
    mapa: dict[str, Any] = field(default_factory=dict)

    def para_json(self) -> dict:
        dados = dict(self.extras)
        dados.update({
            "id": self.id,
            "titulo": self.titulo,
            "objetivo": self.objetivo,
            "tipo": self.tipo,
            "status": self.status,
            "criado_em": self.criado_em,
            "atualizado_em": self.atualizado_em,
            "formato": self.formato,
            "revisao": self.revisao,
        })
        if self.mapa:
            dados["mapa"] = self.mapa
        return dados

    @classmethod
    def de_json(cls, dados: dict) -> "Plano":
        if not isinstance(dados, dict):
            raise PlanoInvalido("plano não é um objeto JSON")
        ident = dados.get("id")
        titulo = dados.get("titulo")
        objetivo = dados.get("objetivo")
        if not isinstance(ident, str) or not _CHAVE_ID.fullmatch(ident):
            raise PlanoInvalido("identificador do plano inválido")
        if not isinstance(titulo, str) or not titulo.strip():
            raise PlanoInvalido("título do plano inválido")
        if not isinstance(objetivo, str):
            raise PlanoInvalido("objetivo do plano inválido")
        formato = dados.get("formato", FORMATO)
        if isinstance(formato, bool) or not isinstance(formato, int):
            raise PlanoInvalido("formato do plano inválido")
        if formato > FORMATO or formato < 1:
            raise PlanoInvalido(f"versão de formato desconhecida: {formato}")
        revisao = dados.get("revisao", 0)
        if isinstance(revisao, bool) or not isinstance(revisao, int) or revisao < 0:
            revisao = 0
        tipo = dados.get("tipo", "Geral")
        if tipo not in TIPOS:
            tipo = "Geral"
        status = dados.get("status", "ativo")
        if status not in STATUS:
            status = "ativo"
        mapa = dados.get("mapa")
        if not isinstance(mapa, dict):
            mapa = {}
        conhecidas = {
            "id", "titulo", "objetivo", "tipo", "status", "criado_em",
            "atualizado_em", "formato", "revisao", "mapa",
        }
        extras = {k: v for k, v in dados.items() if k not in conhecidas}
        return cls(
            id=ident,
            titulo=titulo,
            objetivo=objetivo,
            tipo=tipo,
            status=status,
            criado_em=str(dados.get("criado_em") or ""),
            atualizado_em=str(dados.get("atualizado_em") or ""),
            formato=formato,
            revisao=revisao,
            extras=extras,
            mapa=mapa,
        )


def _caminho(plano_id: str) -> Path:
    if not isinstance(plano_id, str) or not _CHAVE_ID.fullmatch(plano_id):
        raise PlanoInvalido("identificador do plano inválido")
    return pasta_planos() / f"{plano_id}.json"


def _gravar(plano: Plano) -> None:
    caminho = _caminho(plano.id)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".tmp")
    try:
        temporario.write_text(
            json.dumps(plano.para_json(), ensure_ascii=False, indent=2),
            encoding="utf-8")
        _replace(temporario, caminho)
    finally:
        try:
            temporario.unlink(missing_ok=True)
        except OSError:
            pass


def _carregar_ou_erro(plano_id: str) -> Plano:
    caminho = _caminho(plano_id)
    if not caminho.is_file():
        raise PlanoInvalido("plano inexistente")
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise PlanoInvalido(f"arquivo ilegível ({type(exc).__name__})") from exc
    return Plano.de_json(dados)


def carregar(plano_id: str) -> Plano | None:
    """Plano salvo ou ``None`` se ausente/corrompido (sem expor conteúdo)."""
    try:
        return _carregar_ou_erro(plano_id)
    except ErroPlano:
        return None


def listar() -> tuple[list[Plano], list[str]]:
    """Carrega o catálogo uma vez; falhas por arquivo não impedem os demais."""
    planos: list[Plano] = []
    avisos: list[str] = []
    for caminho in sorted(pasta_planos().glob("*.json")):
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            planos.append(Plano.de_json(dados))
        except (OSError, ValueError, TypeError, ErroPlano) as exc:
            # Aviso sem conteúdo: nem título nem trecho do JSON entram no log.
            avisos.append(f"plano {caminho.stem}: {type(exc).__name__}")
    planos.sort(key=lambda p: (p.atualizado_em, p.revisao), reverse=True)
    return planos, avisos


def _validar_campos(mudancas: dict) -> dict:
    if not isinstance(mudancas, dict):
        raise PlanoInvalido("mudanças precisam ser um dicionário")
    permitidas = {"titulo", "objetivo", "tipo", "status", "mapa"}
    limpas = {k: v for k, v in mudancas.items() if k in permitidas}
    if "titulo" in limpas:
        if not isinstance(limpas["titulo"], str) or not limpas["titulo"].strip():
            raise PlanoInvalido("título obrigatório")
        limpas["titulo"] = limpas["titulo"].strip()
    if "objetivo" in limpas:
        if not isinstance(limpas["objetivo"], str) or not limpas["objetivo"].strip():
            raise PlanoInvalido("objetivo obrigatório")
        limpas["objetivo"] = limpas["objetivo"].strip()
    if "tipo" in limpas and limpas["tipo"] not in TIPOS:
        raise PlanoInvalido("tipo desconhecido")
    if "status" in limpas and limpas["status"] not in STATUS:
        raise PlanoInvalido("status desconhecido")
    if "mapa" in limpas and not isinstance(limpas["mapa"], dict):
        raise PlanoInvalido("mapa inválido")
    return limpas


def criar(titulo: str, objetivo: str, tipo: str = "Geral") -> Plano:
    limpas = _validar_campos({"titulo": titulo, "objetivo": objetivo, "tipo": tipo})
    agora = agora_iso()
    plano = Plano(
        id=novo_id(),
        titulo=limpas["titulo"],
        objetivo=limpas["objetivo"],
        tipo=limpas["tipo"],
        criado_em=agora,
        atualizado_em=agora,
        formato=FORMATO,
        revisao=0,
    )
    _gravar(plano)
    return plano


def atualizar(plano_id: str, mudancas: dict, revisao_esperada: int) -> Plano:
    limpas = _validar_campos(mudancas)
    atual = _carregar_ou_erro(plano_id)
    if atual.revisao != revisao_esperada:
        raise ConflitoDeRevisao(revisao_esperada, atual.revisao)
    novo = replace(atual, **limpas,
                   revisao=atual.revisao + 1,
                   atualizado_em=agora_iso())
    _gravar(novo)
    return novo


def arquivar(plano_id: str, revisao_esperada: int) -> Plano:
    return atualizar(plano_id, {"status": "arquivado"}, revisao_esperada)


def restaurar(plano_id: str, revisao_esperada: int) -> Plano:
    return atualizar(plano_id, {"status": "ativo"}, revisao_esperada)


def buscar(planos: list[Plano], termo: str = "", tipo: str = "",
           status: str = "") -> list[Plano]:
    """Busca por título ou objetivo, tolerante a caixa e acentos."""
    alvo = _normalizar(termo)
    resultados = []
    for plano in planos:
        if tipo and plano.tipo != tipo:
            continue
        if status and plano.status != status:
            continue
        if alvo and alvo not in _normalizar(plano.titulo) \
                and alvo not in _normalizar(plano.objetivo):
            continue
        resultados.append(plano)
    return resultados


__all__ = [
    "FORMATO", "TIPOS", "STATUS", "ErroPlano", "PlanoInvalido",
    "ConflitoDeRevisao", "Plano", "base_dados_usuario", "pasta_planos",
    "novo_id", "agora_iso", "carregar", "listar", "criar", "atualizar",
    "arquivar", "restaurar", "buscar",
]
