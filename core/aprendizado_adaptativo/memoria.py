# -*- coding: utf-8 -*-
"""Memória procedural persistente do aprendizado adaptativo (F02).

SQLite isolado em `~/.nia/` (fora do Git). Não substitui a memória de perfil
existente; guarda conhecimentos, procedimentos versionados, versões, etapas,
sessões, observações, experiências, documentos, tarefas e checkpoints.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
from datetime import datetime, timezone
import sqlite3
from typing import Any

_SCHEMA_VERSION = 1
_TABELAS = (
    'knowledge', 'procedures', 'versions', 'steps', 'sessions', 'observations',
    'experiences', 'workspaces', 'documents', 'items', 'tasks', 'checkpoints',
    'corrections', 'sources',
)
_JSON_COLS = {'payload', 'parametros', 'dados', 'ferramentas', 'evidencia'}
_SEGREDO = re.compile(
    r'(?i)\b(senha|password|passwd|token|api[_-]?key|secret|cvv|cartao)\b'
    r'\s*[:=]?\s*\S+')


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitizar(valor: Any) -> Any:
    """Redige credenciais antes de qualquer gravação."""
    if isinstance(valor, str):
        return _SEGREDO.sub(lambda m: f'{m.group(1)}: ***', valor)
    if isinstance(valor, dict):
        return {str(k): sanitizar(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [sanitizar(v) for v in valor]
    return valor


def _dumps(valor: Any) -> str:
    return json.dumps(sanitizar(valor), ensure_ascii=False, sort_keys=True)


def _loads(texto: Any) -> Any:
    if not isinstance(texto, str) or not texto:
        return None
    try:
        return json.loads(texto)
    except (ValueError, TypeError):
        return texto


class MemoriaProcedural:
    def __init__(self, db_path=None):
        self.caminho = Path(db_path) if db_path else (
            Path.home() / '.nia' / 'aprendizado_adaptativo.db')
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(str(self.caminho), check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.execute('PRAGMA foreign_keys=ON')
        self.ultima_migracao = self.migrar()

    # ── esquema ─────────────────────────────────────────────────────────────
    def migrar(self) -> dict:
        backup = False
        versao = int(self.con.execute('PRAGMA user_version').fetchone()[0] or 0)
        if (self.caminho.exists() and self.caminho.stat().st_size > 0
                and versao < _SCHEMA_VERSION):
            destino = self.caminho.with_name(
                f'{self.caminho.stem}.db.bak-{datetime.now().strftime("%Y%m%d%H%M%S")}')
            shutil.copy2(self.caminho, destino)
            backup = True
        ddl = '''
        CREATE TABLE IF NOT EXISTS knowledge (
            id TEXT PRIMARY KEY, tipo TEXT, titulo TEXT, conteudo TEXT,
            origem TEXT, escopo TEXT, estado TEXT, versao INTEGER DEFAULT 1,
            criado_em TEXT, validado_em TEXT, evidencia TEXT);
        CREATE TABLE IF NOT EXISTS procedures (
            id TEXT PRIMARY KEY, nome TEXT, objetivo TEXT, contexto TEXT,
            ferramentas TEXT, versao INTEGER DEFAULT 1, estado TEXT,
            origem TEXT, criado_em TEXT, atualizado_em TEXT);
        CREATE TABLE IF NOT EXISTS versions (
            id TEXT PRIMARY KEY, procedure_id TEXT NOT NULL, versao INTEGER NOT NULL,
            estado TEXT, payload TEXT, motivo TEXT, criado_em TEXT,
            FOREIGN KEY(procedure_id) REFERENCES procedures(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS steps (
            id TEXT PRIMARY KEY, procedure_id TEXT NOT NULL, ordem INTEGER,
            alvo TEXT, acao TEXT, parametros TEXT, precondicao TEXT,
            poscondicao TEXT, timeout REAL DEFAULT 0, retry INTEGER DEFAULT 0,
            FOREIGN KEY(procedure_id) REFERENCES procedures(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, objetivo TEXT, documento_id TEXT, janela TEXT,
            estado TEXT, proprietario TEXT, criado_em TEXT, atualizado_em TEXT);
        CREATE TABLE IF NOT EXISTS observations (
            id TEXT PRIMARY KEY, sessao_id TEXT, tipo TEXT, alvo TEXT, dados TEXT,
            ator TEXT, criado_em TEXT);
        CREATE TABLE IF NOT EXISTS experiences (
            id TEXT PRIMARY KEY, procedimento_id TEXT, resultado TEXT,
            evidencia TEXT, criado_em TEXT);
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY, titulo TEXT, estado TEXT, dados TEXT, criado_em TEXT);
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY, titulo TEXT, revisao INTEGER DEFAULT 0,
            conteudo TEXT, atualizado_em TEXT);
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY, documento_id TEXT, tipo TEXT, dados TEXT,
            revisao INTEGER DEFAULT 0, FOREIGN KEY(documento_id) REFERENCES documents(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, descricao TEXT, prioridade INTEGER DEFAULT 50,
            estado TEXT, cancel_generation INTEGER DEFAULT 0, criado_em TEXT);
        CREATE TABLE IF NOT EXISTS checkpoints (
            tarefa_id TEXT PRIMARY KEY, payload TEXT, criado_em TEXT);
        CREATE TABLE IF NOT EXISTS corrections (
            id TEXT PRIMARY KEY, procedure_id TEXT, descricao TEXT, aplicado_em TEXT);
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY, knowledge_id TEXT, url TEXT, titulo TEXT,
            consultado_em TEXT, evidencia TEXT);
        CREATE INDEX IF NOT EXISTS idx_steps_proc ON steps(procedure_id, ordem);
        CREATE INDEX IF NOT EXISTS idx_versions_proc ON versions(procedure_id, versao);
        CREATE INDEX IF NOT EXISTS idx_knowledge_tipo ON knowledge(tipo, estado);
        '''
        with self.con:
            self.con.executescript(ddl)
            self.con.execute(f'PRAGMA user_version={_SCHEMA_VERSION}')
        self.ultima_migracao = {'user_version': _SCHEMA_VERSION, 'backup': backup}
        return self.ultima_migracao

    # ── primitivas ──────────────────────────────────────────────────────────
    def _inserir(self, tabela: str, **campos) -> str:
        if tabela not in _TABELAS:
            raise ValueError('Tabela não autorizada: ' + str(tabela))
        campos = sanitizar(campos)
        colunas = ', '.join(campos)
        marcadores = ', '.join('?' for _ in campos)
        with self.con:
            self.con.execute(
                f'INSERT INTO {tabela} ({colunas}) VALUES ({marcadores})',
                tuple(_dumps(v) if isinstance(v, (dict, list, tuple))
                      else v for v in campos.values()))
        return str(campos.get('id', ''))

    def obter(self, tabela: str, identificador: str) -> dict | None:
        if tabela not in _TABELAS:
            raise ValueError('Tabela não autorizada: ' + str(tabela))
        linha = self.con.execute(
            f'SELECT * FROM {tabela} WHERE id=?', (str(identificador),)).fetchone()
        return self._linha(linha) if linha is not None else None

    def listar(self, tabela: str, limite: int = 100) -> tuple[dict, ...]:
        if tabela not in _TABELAS:
            raise ValueError('Tabela não autorizada: ' + str(tabela))
        colunas = {r['name'] for r in self.con.execute(
            f'PRAGMA table_info({tabela})').fetchall()}
        ordem = ('criado_em' if 'criado_em' in colunas else
                 'aplicado_em' if 'aplicado_em' in colunas else 'rowid')
        linhas = self.con.execute(
            f'SELECT * FROM {tabela} ORDER BY {ordem} DESC LIMIT ?',
            (int(limite),)).fetchall()
        return tuple(self._linha(l) for l in linhas)

    @staticmethod
    def _linha(linha: sqlite3.Row) -> dict:
        dados = dict(linha)
        for chave, valor in list(dados.items()):
            if chave in _JSON_COLS or isinstance(valor, str) and valor[:1] in '[{':
                dados[chave] = _loads(valor)
        return dados

    def fechar(self) -> None:
        try:
            self.con.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.fechar()

    # ── conhecimento e procedimentos ───────────────────────────────────────
    def registrar_conhecimento(self, titulo: str, conteudo: str, *,
                               origem: str = '', tipo: str = 'fato',
                               escopo: str = '', evidencia: dict | None = None,
                               identificador: str | None = None) -> str:
        from uuid import uuid4  # noqa: PLC0415
        kid = identificador or uuid4().hex
        self._inserir('knowledge', id=kid, tipo=tipo, titulo=titulo,
                      conteudo=conteudo, origem=origem, escopo=escopo,
                      estado='VALIDADO', versao=1, criado_em=_agora(),
                      validado_em=_agora(), evidencia=evidencia or {})
        return kid

    def registrar_procedimento(self, nome: str, *, objetivo: str = '',
                               contexto: dict | None = None,
                               ferramentas=(), origem: str = '',
                               identificador: str | None = None) -> str:
        from uuid import uuid4  # noqa: PLC0415
        pid = identificador or uuid4().hex
        self._inserir('procedures', id=pid, nome=nome, objetivo=objetivo,
                      contexto=contexto or {}, ferramentas=tuple(ferramentas),
                      versao=1, estado='EM_REVISAO', origem=origem,
                      criado_em=_agora(), atualizado_em=_agora())
        return pid

    def adicionar_etapa(self, procedimento_id: str, ordem: int, *, alvo: str = '',
                        acao: str = '', parametros: dict | None = None,
                        precondicao: str = '', poscondicao: str = '',
                        timeout: float = 0.0, retry: int = 0) -> str:
        from uuid import uuid4  # noqa: PLC0415
        if self.obter('procedures', procedimento_id) is None:
            raise ValueError('Procedimento inexistente')
        sid = uuid4().hex
        self._inserir('steps', id=sid, procedure_id=procedimento_id,
                      ordem=int(ordem), alvo=alvo, acao=acao,
                      parametros=parametros or {}, precondicao=precondicao,
                      poscondicao=poscondicao, timeout=float(timeout), retry=int(retry))
        return sid

    def registrar_versao(self, procedimento_id: str, *, versao: int = 1,
                         payload: dict | None = None, motivo: str = '',
                         estado: str = 'VALIDADO') -> str:
        from uuid import uuid4  # noqa: PLC0415
        if self.obter('procedures', procedimento_id) is None:
            raise ValueError('Procedimento inexistente')
        vid = uuid4().hex
        with self.con:
            self.con.execute(
                'INSERT INTO versions (id, procedure_id, versao, estado, payload, '
                'motivo, criado_em) VALUES (?,?,?,?,?,?,?)',
                (vid, procedimento_id, int(versao), estado, _dumps(payload or {}),
                 sanitizar(motivo), _agora()))
            self.con.execute(
                'UPDATE procedures SET versao=?, atualizado_em=? WHERE id=?',
                (int(versao), _agora(), procedimento_id))
        return vid

    def registrar_correcao(self, procedimento_id: str, descricao: str, *,
                           versao: int, payload: dict | None = None,
                           estado: str = 'VALIDADO') -> str:
        from uuid import uuid4  # noqa: PLC0415
        with self.con:
            self.con.execute(
                "UPDATE versions SET estado='OBSOLETO' WHERE procedure_id=? "
                'AND versao<?', (procedimento_id, int(versao)))
        vid = self.registrar_versao(
            procedimento_id, versao=versao, payload=payload or {},
            motivo=descricao, estado=estado)
        self._inserir('corrections', id=uuid4().hex,
                      procedure_id=procedimento_id, descricao=descricao,
                      aplicado_em=_agora())
        return vid

    def obter_procedimento(self, procedimento_id: str) -> dict | None:
        proc = self.obter('procedures', procedimento_id)
        if proc is None:
            return None
        etapas = self.con.execute(
            'SELECT * FROM steps WHERE procedure_id=? ORDER BY ordem',
            (procedimento_id,)).fetchall()
        proc['etapas'] = [self._linha(e) for e in etapas]
        return proc

    def obter_versoes(self, procedimento_id: str) -> tuple[dict, ...]:
        linhas = self.con.execute(
            'SELECT * FROM versions WHERE procedure_id=? ORDER BY versao',
            (procedimento_id,)).fetchall()
        return tuple(self._linha(l) for l in linhas)

    def excluir_procedimento(self, procedimento_id: str) -> bool:
        with self.con:
            cursor = self.con.execute(
                'DELETE FROM procedures WHERE id=?', (procedimento_id,))
        return cursor.rowcount > 0

    # ── checkpoints ─────────────────────────────────────────────────────────
    def registrar_checkpoint(self, tarefa_id: str, payload: dict) -> None:
        with self.con:
            self.con.execute(
                'INSERT OR REPLACE INTO checkpoints (tarefa_id, payload, criado_em) '
                'VALUES (?,?,?)', (tarefa_id, _dumps(payload), _agora()))

    def salvar_checkpoint(self, tarefa_id: str, payload: dict) -> None:
        self.registrar_checkpoint(tarefa_id, payload)

    def obter_checkpoint(self, tarefa_id: str) -> dict | None:
        linha = self.con.execute(
            'SELECT * FROM checkpoints WHERE tarefa_id=?', (tarefa_id,)).fetchone()
        if linha is None:
            return None
        return {'tarefa_id': tarefa_id, 'payload': _loads(linha['payload']),
                'criado_em': linha['criado_em']}
