# -*- coding: utf-8 -*-
"""A chave que o dono colou e aceita pelo provedor? (18/11/2026)

POR QUE EXISTE
--------------
Em 18/11/2026 a voz do NIA estava muda com uma chave "cadastrada" no banco.
O roteador tinha um defeito (corrigido: `resolver()` nao lia o banco), mas
havia um SEGUNDO problema, este aqui: a chave guardada era um token de outro
tipo (`AQ.Ab8...`, de OAuth/CLI) e o Google respondia **401 API key not valid**
em toda chamada. A tela dizia "cadastrada"; a voz nao saia.

Nada aqui adivinha: faz UMA chamada de leitura no endpoint de modelos, que nao
gasta cota de geracao, e traduz a resposta para o dono.

REGRA DE OURO: chave nao se perde. Mesmo "invalida", ela fica no banco — quem
decide apagar e o dono. Este modulo so INFORMA.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from core.llm_router import provedor_canonico

_PRAZO_S = 6.0

# Como cada familia prova que a chave vale: uma leitura barata do catalogo.
_GEMINI = "https://generativelanguage.googleapis.com/v1beta/models"

# O QUE FAZER QUANDO O GOOGLE RECUSA (18/11/2026)
#
# O Google passou a emitir no AI Studio, desde 28/05/2026, chaves que comecam
# com `AQ.` (autorizacao) em vez das antigas `AIza`. Em algumas contas/versoes
# do endpoint essas chaves voltam **401 API key not valid / ACCESS_TOKEN_TYPE
# _UNSUPPORTED** mesmo estando boas no site. Nao ha o que configurar no NIA:
# quem precisa emitir outra chave e o dono. O recado abaixo diz exatamente isso.
_AJUDA_GEMINI = ("confira em https://aistudio.google.com/apikey se a chave esta "
                 "inteira (copiar de novo) e, se continuar recusada, gere uma "
                 "chave NOVA e cole aqui")


def _dica_gemini(chave: str) -> str:
    """Uma frase a mais quando a chave tem cara de `AQ.` (token de autorizacao)."""
    if chave.startswith("AQ."):
        return ("esta chave comeca com AQ. (formato novo do AI Studio) e o Google "
                f"a recusou neste endpoint; {_AJUDA_GEMINI}")
    return _AJUDA_GEMINI


def _get(url: str, cabecalho: dict) -> tuple[int, str]:
    pedido = urllib.request.Request(url, headers=cabecalho, method="GET")
    try:
        with urllib.request.urlopen(pedido, timeout=_PRAZO_S) as r:
            return int(getattr(r, "status", 200)), r.read(4000).decode("utf-8", "ignore")
    except urllib.error.HTTPError as exc:
        try:
            corpo = exc.read(4000).decode("utf-8", "ignore")
        except Exception:
            corpo = ""
        return int(exc.code), corpo
    except Exception as exc:
        raise RuntimeError(f"sem resposta do provedor ({type(exc).__name__})") from exc


def _mensagem_do_erro(corpo: str) -> str:
    """A frase util do JSON de erro, sem despejar o corpo inteiro na tela."""
    try:
        dados = json.loads(corpo)
    except Exception:
        return corpo.strip()[:120]
    erro = dados.get("error") if isinstance(dados, dict) else None
    if isinstance(erro, dict):
        return str(erro.get("message") or erro.get("status") or "")[:140]
    if isinstance(erro, str):
        return erro[:140]
    return str(dados)[:140]


def validar(provedor: str, chave: str, base_url: str = "") -> tuple[bool, str]:
    """``(ok, recado)``. ``ok=False`` so quando o provedor RECUSOU a chave.

    Rede fora, tempo esgotado ou provedor sem endpoint conhecido devolvem
    ``True`` com um aviso: nao da para condenar uma chave por causa da internet
    do momento.
    """
    chave = str(chave or "").strip()
    if not chave:
        return False, "chave vazia"
    nome = provedor_canonico(provedor)

    if nome.startswith("gemini") or nome == "google":
        try:
            status, corpo = _get(_GEMINI, {"x-goog-api-key": chave})
        except RuntimeError as exc:
            return True, str(exc)
        if 200 <= status < 300:
            return True, "chave aceita pelo Google"
        if status in (400, 401, 403):
            return False, (f"Google recusou a chave ({status}): "
                           f"{_mensagem_do_erro(corpo)} — {_dica_gemini(chave)}")
        if status == 429:
            return True, "chave valida, mas sem cota neste momento"
        return False, f"Google respondeu {status}: {_mensagem_do_erro(corpo)}"

    if nome == "openai":
        base = "https://api.openai.com/v1"
    else:
        from core.provedores import base_url_do_provedor  # noqa: PLC0415
        base = str(base_url or base_url_do_provedor(provedor) or "").rstrip("/")
    if not base:
        return True, "sem endpoint conhecido: chave guardada, nao verificada"
    if not base.endswith("/v1") and "/v1" not in base:
        base += "/v1"

    try:
        status, corpo = _get(base + "/models", {"Authorization": f"Bearer {chave}"})
    except RuntimeError as exc:
        return True, str(exc)
    if 200 <= status < 300:
        return True, "chave aceita pelo provedor"
    if status in (400, 401, 403):
        return False, f"provedor recusou a chave ({status}): {_mensagem_do_erro(corpo)}"
    if status == 429:
        return True, "chave valida, mas sem cota neste momento"
    if status == 404:
        return False, "endpoint de modelos nao existe nesta URL (confira a base_url)"
    return False, f"provedor respondeu {status}: {_mensagem_do_erro(corpo)}"


def recado_curto(provedor: str, chave: str, base_url: str = "") -> str:
    """Uma linha pronta para o log da interface."""
    ok, texto = validar(provedor, chave, base_url)
    return ("CHAVE: " if ok else "CHAVE RECUSADA: ") + texto
