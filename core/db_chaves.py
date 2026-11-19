# -*- coding: utf-8 -*-
"""Banco local de chaves (SQLite) — portado do FreeLLMAPI.

Tudo fica só neste computador, em `config/nia.db`:

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
import hashlib
import json
import sqlite3
import time
from pathlib import Path

# Banco local; pode ser trocado por NIA_DB_PATH (teste/diagnóstico).
# O nome antigo da variável continua valendo: quem já tinha script apontando
# para um banco de teste não perde o caminho na troca de nome do produto.
_RAIZ = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("NIA_DB_PATH")
               or os.environ.get("JARVIS_DB_PATH")
               or (_RAIZ / "config" / "nia.db"))

# DADOS DE ANTES DA TROCA DE NOME (18/11/2026). O banco nasceu como
# `config/jarvis.db` e é lá que estão as chaves de quem já usa o programa.
# Na primeira abertura com o nome novo copiamos o antigo — sem apagar nada.
# Um banco de teste apontado por variável de ambiente nunca entra nesta conta.
_LEGADO = _RAIZ / "config" / "jarvis.db"
if (DB_PATH.name == "nia.db" and not DB_PATH.exists()
        and not os.environ.get("NIA_DB_PATH") and not os.environ.get("JARVIS_DB_PATH")
        and _LEGADO.is_file()):
    try:
        import shutil  # noqa: PLC0415

        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_LEGADO, DB_PATH)
    except OSError:
        pass

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
                  ("base_url", "TEXT NOT NULL DEFAULT ''"),
                  ("revision", "INTEGER NOT NULL DEFAULT 0"),
                  ('validacao_estado', "TEXT NOT NULL DEFAULT 'nao_verificada'"),
                  ('validacao_mensagem', "TEXT NOT NULL DEFAULT ''"),
                  ('validacao_http', 'INTEGER NOT NULL DEFAULT 0'),
                  ('validacao_codigo', "TEXT NOT NULL DEFAULT ''"),
                  ('validacao_em', 'REAL NOT NULL DEFAULT 0'),
                  ('modelos_json', "TEXT NOT NULL DEFAULT '[]'"),
                  ('modelos_em', 'REAL NOT NULL DEFAULT 0'),
                  ('modelos_completo', 'INTEGER NOT NULL DEFAULT 0'),
                  ('modelos_publico', 'INTEGER NOT NULL DEFAULT 0'),
                  ('modelos_mensagem', "TEXT NOT NULL DEFAULT ''"))


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
        con.execute("CREATE TABLE IF NOT EXISTS credenciais_bloqueadas "
                    "(platform TEXT, identidade TEXT, PRIMARY KEY(platform, identidade))")
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
                    base_url: str = "", status: str = "ativo", explicita: bool = True) -> int | None:
    """Adiciona uma chave ao banco. Devolve o id (ou None se duplicada)."""
    key = str(key or "").strip()
    platform = _canonico(platform)
    if not platform or not key:
        return None
    with _conexao() as con:
        con.execute("BEGIN IMMEDIATE")
        if not explicita and con.execute(
                'SELECT 1 FROM credenciais_bloqueadas WHERE platform=? AND identidade=?',
                (platform, _identidade(key))).fetchone():
            return None
        if any(_canonico(r['platform']) == platform and r['key'] == key
               for r in con.execute("SELECT platform, key FROM api_keys")):
            return None
        con.execute("DELETE FROM credenciais_bloqueadas WHERE platform=? AND identidade=?",
                    (platform, _identidade(key)))
        cur = con.execute(
            "INSERT INTO api_keys (platform, label, key, modelo, base_url, status)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (platform, str(label or ""), key, str(modelo or "").strip(),
             str(base_url or "").strip(), status))
        return int(cur.lastrowid)


def listar_chaves(platform: str | None = None) -> list[dict]:
    """Lista chaves (todas ou de um provedor), já como dict."""
    with _conexao() as con:
        rows = con.execute("SELECT * FROM api_keys ORDER BY id").fetchall()
        return [dict(r) for r in rows if not platform
                or _canonico(r['platform']) == _canonico(platform)]


def remover_chave(chave_id: int) -> None:
    with _conexao() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute("SELECT * FROM api_keys WHERE id=?", (int(chave_id),)).fetchone()
        if row:
            _bloquear(con, row['platform'], row['key'])
        con.execute("DELETE FROM api_keys WHERE id=?", (int(chave_id),))


def _canonico(platform):
    from core.llm_router import provedor_canonico
    return provedor_canonico(platform)


def _identidade(key):
    return hashlib.sha256(str(key).encode('utf-8')).hexdigest()


def _bloquear(con, platform, key):
    con.execute("INSERT OR IGNORE INTO credenciais_bloqueadas VALUES (?, ?)",
                (_canonico(platform), _identidade(key)))


def fonte_legada_permitida(platform, key):
    """Uma cópia antiga nunca vence uma decisão sobre a conexão gerenciada."""
    with _conexao() as con:
        if con.execute("SELECT 1 FROM credenciais_bloqueadas WHERE platform=? AND identidade=?",
                       (_canonico(platform), _identidade(key))).fetchone():
            return False
        return not any(_canonico(r['platform']) == _canonico(platform) and r['key'] == key
                       for r in con.execute("SELECT platform, key FROM api_keys"))


def identidade_bloqueada(platform, key):
    with _conexao() as con:
        return bool(con.execute('SELECT 1 FROM credenciais_bloqueadas WHERE platform=? AND identidade=?',
                                (_canonico(platform), _identidade(key))).fetchone())


def atualizar_chave(chave_id, revision, **campos):
    """Compare-and-swap: resultados atrasados não recriam nem alteram registros."""
    permitidos = {'label', 'modelo', 'base_url', 'key', 'enabled', 'status', 'cooldown_ate'} | {
        nome for nome, _ in _COLUNAS_NOVAS if nome.startswith(('validacao_', 'modelos_'))}
    if not campos or not set(campos) <= permitidos:
        raise ValueError('campos de credencial inválidos')
    with _conexao() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM api_keys WHERE id=? AND revision=?",
                          (chave_id, revision)).fetchone()
        if not row:
            return False
        nova = str(campos.get('key', row['key'])).strip()
        if not nova:
            raise ValueError('chave vazia')
        if nova != row['key'] and any(r['id'] != chave_id and _canonico(r['platform']) == _canonico(row['platform'])
               and r['key'] == nova for r in con.execute("SELECT * FROM api_keys")):
            raise ValueError('chave já cadastrada; edite ou teste a entrada existente')
        if nova != row['key']:
            _bloquear(con, row['platform'], row['key'])
            campos['key'] = nova
        if nova != row['key'] or campos.get('base_url', row['base_url']) != row['base_url']:
            # Um catálogo/diagnóstico pertence ao segredo e endpoint testados.
            for nome, valor in campos_validacao_vazia().items():
                campos.setdefault(nome, valor)
        atribuicoes = ', '.join(f'{k}=?' for k in campos)
        if campos.get('status') == 'ativo':
            atribuicoes += ', cooldown_ate=0, falhas=0'
            con.execute('DELETE FROM credenciais_bloqueadas WHERE platform=? AND identidade=?',
                        (_canonico(row['platform']), _identidade(nova)))
        con.execute(f"UPDATE api_keys SET {atribuicoes}, revision=revision+1 WHERE id=?",
                    (*campos.values(), chave_id))
        return True


def registrar_falha(chave_id: int, segundos: float = 60.0, status: str = "cooldown", revision=None) -> None:
    with _conexao() as con:
        guarda = ' AND revision=?' if revision is not None else ''
        con.execute(
            "UPDATE api_keys SET status=?, cooldown_ate=?, falhas=falhas+1,"
            " validacao_estado=CASE WHEN ?='invalida' THEN 'invalido' WHEN ?='esgotada' THEN 'esgotado'"
            " ELSE validacao_estado END WHERE id=?" + guarda,
            (status, time.time() + float(segundos), status, status, int(chave_id), *((revision,) if revision is not None else ())))


def registrar_sucesso(chave_id: int, revision=None) -> None:
    with _conexao() as con:
        guarda = ' AND revision=?' if revision is not None else ''
        con.execute(
            "UPDATE api_keys SET status='ativo', cooldown_ate=0, falhas=0,"
            " sucessos=sucessos+1, validacao_estado='validado',"
            " validacao_mensagem='Chamada autenticada concluída.', validacao_em=? WHERE id=?" + guarda,
            (time.time(), int(chave_id), *((revision,) if revision is not None else ())))


def campos_validacao_vazia():
    return {'validacao_estado': 'nao_verificada', 'validacao_mensagem': '', 'validacao_http': 0,
            'validacao_codigo': '', 'validacao_em': 0, 'modelos_json': '[]', 'modelos_em': 0,
            'modelos_completo': 0, 'modelos_publico': 0, 'modelos_mensagem': ''}


def aplicar_validacao(chave_id, revision, resultado, **alteracoes):
    """Persiste o resultado da conexão testada sem alterar pausa ou preferências."""
    campos = dict(alteracoes)
    campos.update(validacao_estado=resultado.status_exibicao, validacao_mensagem=resultado.mensagem,
                  validacao_http=resultado.http_status, validacao_codigo=resultado.codigo,
                  validacao_em=time.time())
    if resultado.estado == 'modelo':
        campos.pop('validacao_estado')  # erro do modelo não desfaz a autenticação já comprovada
    if resultado.apta:
        campos['status'] = 'ativo'
    elif resultado.estado == 'recusada':
        campos['status'] = 'invalida'
    elif resultado.estado == 'cota':
        campos['status'] = 'esgotada'
        campos['cooldown_ate'] = time.time() + 60
    if resultado.catalogo_completo or resultado.modelos:
        campos.update(modelos_json=json.dumps(resultado.modelos, ensure_ascii=False), modelos_em=time.time(),
                      modelos_completo=int(resultado.catalogo_completo), modelos_publico=int(resultado.catalogo_publico))
    campos['modelos_mensagem'] = resultado.catalogo_mensagem
    return atualizar_chave(chave_id, revision, **campos)


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
