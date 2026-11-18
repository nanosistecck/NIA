# -*- coding: utf-8 -*-
"""Banco local de chaves (SQLite) — portado do FreeLLMAPI.

Tudo fica só neste computador, em `config/jarvis.db`:

    api_keys: platform, label, key, modelo, base_url, status, enabled,
              falhas, sucessos, uso_tokens, cooldown_ate, created_at

O roteador (`core/llm_router.py`) carrega as chaves daqui; o cadastro de chaves
(`ui.py`) grava aqui. O JSON de config (`config/llm_routing.json`) continua com
estratégia, cadeia e o bloco dos provedores genéricos.

`modelo` e `base_url` são opcionais e existem para os provedores do catálogo que
não têm modelo conhecido (`core/provedores.py`) ou cujo endpoint o usuário quer
informar à mão — sem eles, a chave ficaria guardada sem nunca ser usada.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
import sqlite3
import time
from pathlib import Path

# Banco local; pode ser trocado por JARVIS_DB_PATH (teste/diagnóstico).
DB_PATH = Path(os.environ.get("JARVIS_DB_PATH")
               or (Path(__file__).resolve().parents[1] / "config" / "jarvis.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    platform     TEXT NOT NULL,
    label        TEXT NOT NULL DEFAULT '',
    key          TEXT NOT NULL,
    modelo       TEXT NOT NULL DEFAULT '',
    base_url     TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'ativo',
    enabled      INTEGER NOT NULL DEFAULT 1,
    falhas       INTEGER NOT NULL DEFAULT 0,
    sucessos     INTEGER NOT NULL DEFAULT 0,
    uso_tokens   INTEGER NOT NULL DEFAULT 0,
    cooldown_ate REAL NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# Colunas que entraram depois da primeira versão do banco.
_COLUNAS_NOVAS = (("modelo", "TEXT NOT NULL DEFAULT ''"),
                  ("base_url", "TEXT NOT NULL DEFAULT ''"))


@contextmanager
def _conexao():
    """Conexao curta: abre, entrega, commita e FECHA.

    Fechar importa: o roteador rele o banco quando ele muda de mtime, e sem o
    `close` cada leitura deixava um descritor aberto no processo (o Windows
    chega a travar o arquivo depois de algumas centenas).
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH), timeout=5.0)
    con.row_factory = sqlite3.Row
    try:
        con.execute(_SCHEMA)
        # Bancos criados antes de `modelo`/`base_url` recebem as colunas agora —
        # ninguém perde as chaves já cadastradas.
        existentes = {r["name"] for r in con.execute("PRAGMA table_info(api_keys)")}
        for nome, tipo in _COLUNAS_NOVAS:
            if nome not in existentes:
                con.execute(f"ALTER TABLE api_keys ADD COLUMN {nome} {tipo}")
                con.commit()
        with con:
            yield con
    finally:
        con.close()


def adicionar_chave(platform: str, key: str, label: str = "", modelo: str = "",
                    base_url: str = "") -> int | None:
    """Adiciona uma chave ao banco. Devolve o id (ou None se duplicada)."""
    key = str(key or "").strip()
    if not platform or not key:
        return None
    with _conexao() as con:
        ja = con.execute("SELECT id FROM api_keys WHERE platform=? AND key=?",
                         (platform, key)).fetchone()
        if ja is not None:
            return None
        cur = con.execute(
            "INSERT INTO api_keys (platform, label, key, modelo, base_url)"
            " VALUES (?, ?, ?, ?, ?)",
            (platform, str(label or ""), key, str(modelo or "").strip(),
             str(base_url or "").strip()))
        return int(cur.lastrowid)


def listar_chaves(platform: str | None = None) -> list[dict]:
    """Lista chaves (todas ou de um provedor), já como dict."""
    with _conexao() as con:
        if platform:
            rows = con.execute(
                "SELECT * FROM api_keys WHERE platform=? ORDER BY id", (platform,)
            ).fetchall()
        else:
            rows = con.execute("SELECT * FROM api_keys ORDER BY platform, id").fetchall()
        return [dict(r) for r in rows]


def remover_chave(chave_id: int) -> None:
    with _conexao() as con:
        con.execute("DELETE FROM api_keys WHERE id=?", (int(chave_id),))


def registrar_falha(chave_id: int, segundos: float = 60.0, status: str = "cooldown") -> None:
    with _conexao() as con:
        con.execute(
            "UPDATE api_keys SET status=?, cooldown_ate=?, falhas=falhas+1 WHERE id=?",
            (status, time.time() + float(segundos), int(chave_id)))


def registrar_sucesso(chave_id: int) -> None:
    with _conexao() as con:
        con.execute(
            "UPDATE api_keys SET status='ativo', cooldown_ate=0, falhas=0,"
            " sucessos=sucessos+1 WHERE id=?", (int(chave_id),))


def registrar_uso(chave_id: int, tokens: int) -> None:
    """Soma os tokens gastos (alimenta a estratégia `least-remaining`)."""
    if int(tokens or 0) <= 0:
        return
    with _conexao() as con:
        con.execute("UPDATE api_keys SET uso_tokens=uso_tokens+? WHERE id=?",
                    (int(tokens), int(chave_id)))


def limpar() -> None:
    """Apaga todas as chaves (uso de diagnóstico)."""
    with _conexao() as con:
        con.execute("DELETE FROM api_keys")
