# -*- coding: utf-8 -*-
"""Migração opcional de memória e diário para SQLite (Fase 08).

Os arquivos JSON/JSONL originais nunca são alterados ou apagados: cópias de
segurança são feitas antes da leitura. A migração é transacional, idempotente
e isolada por perfil. Este módulo não é chamado automaticamente pelo produto.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
from uuid import uuid4


class MigradorMemoria:
    def __init__(self, memoria_json, diario_jsonl, db_path, perfil):
        self.memoria = Path(memoria_json)
        self.diario = Path(diario_jsonl)
        self.db = Path(db_path)
        self.perfil = str(perfil or 'padrao')
        self._agora = datetime.now(timezone.utc).isoformat()

    def _backup(self) -> None:
        selo = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        for caminho in (self.memoria, self.diario):
            if caminho.is_file():
                shutil.copy2(caminho, caminho.with_name(
                    caminho.name + '.bak-' + selo))

    def _fontes(self):
        dados = {}
        if self.memoria.is_file():
            bruto = json.loads(self.memoria.read_text(encoding='utf-8'))
            if not isinstance(bruto, dict):
                raise ValueError('Memória não é um objeto JSON.')
            dados = bruto
        linhas = []
        if self.diario.is_file():
            for linha in self.diario.read_text(encoding='utf-8').splitlines():
                if not linha.strip():
                    continue
                item = json.loads(linha)
                if isinstance(item, dict):
                    linhas.append({
                        'texto': str(item.get('texto', '')),
                        'sessao': 'atual' if item.get('sessao') == 'atual' else 'antiga',
                    })
                else:
                    linhas.append({'texto': str(item), 'sessao': 'antiga'})
        return dados, linhas

    def _conectar(self):
        conexao = sqlite3.connect(str(self.db))
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS memoria (
                id TEXT PRIMARY KEY, perfil TEXT, chave TEXT, valor TEXT,
                origem TEXT, criado_em TEXT)
        """)
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS diario (
                id TEXT PRIMARY KEY, perfil TEXT, texto TEXT, origem TEXT,
                criado_em TEXT, sessao TEXT)
        """)
        return conexao

    def contar(self) -> dict:
        if not self.db.is_file():
            return {'memoria': 0, 'diario': 0}
        with closing(self._conectar()) as conexao:
            memoria = conexao.execute(
                'SELECT COUNT(*) FROM memoria WHERE perfil=?', (self.perfil,)).fetchone()[0]
            diario = conexao.execute(
                'SELECT COUNT(*) FROM diario WHERE perfil=?', (self.perfil,)).fetchone()[0]
        return {'memoria': memoria, 'diario': diario}

    def migrar(self) -> dict:
        self._backup()
        try:
            dados, linhas = self._fontes()
        except (ValueError, OSError, UnicodeDecodeError) as exc:
            return {'ok': False, 'motivo': 'fonte_invalida:' + type(exc).__name__}
        fontes = {'memoria': len(dados), 'diario': len(linhas)}
        if self.db.is_file():
            atuais = self.contar()
            if atuais == fontes:
                return {'ok': True, 'ja_migrado': True, **fontes}
            vazio = {'memoria': 0, 'diario': 0}
            if atuais != vazio:
                return {'ok': False, 'motivo': 'banco_divergente', **atuais}
        self.db.parent.mkdir(parents=True, exist_ok=True)
        conexao = self._conectar()
        try:
            with conexao:
                for chave, valor in dados.items():
                    conexao.execute(
                        'INSERT INTO memoria (id, perfil, chave, valor, origem, criado_em) '
                        'VALUES (?, ?, ?, ?, ?, ?)',
                        (uuid4().hex, self.perfil, str(chave), str(valor),
                         'memory.json', self._agora))
                for item in linhas:
                    conexao.execute(
                        'INSERT INTO diario (id, perfil, texto, origem, criado_em, sessao) '
                        'VALUES (?, ?, ?, ?, ?, ?)',
                        (uuid4().hex, self.perfil, item['texto'],
                         'diario.jsonl', self._agora, item['sessao']))
            finale = self.contar()
            if finale != fontes:
                conexao.close()
                self.db.unlink(missing_ok=True)
                return {'ok': False, 'motivo': 'contagem_divergente', **finale}
        except sqlite3.Error as exc:
            conexao.close()
            self.db.unlink(missing_ok=True)
            return {'ok': False, 'motivo': 'sqlite:' + type(exc).__name__}
        conexao.close()
        return {'ok': True, 'ja_migrado': False, **finale}

    def historico(self) -> tuple:
        if not self.db.is_file():
            return ()
        with closing(self._conectar()) as conexao:
            linhas = conexao.execute(
                'SELECT texto, perfil, origem, sessao FROM diario '
                'WHERE perfil=? ORDER BY rowid', (self.perfil,)).fetchall()
        return tuple(linhas)

    def sessao_atual(self) -> str:
        for texto, _perfil, _origem, sessao in self.historico():
            if sessao == 'atual':
                return texto
        return ''

    def contexto(self, limite: int = 2000) -> str:
        partes = []
        if self.db.is_file():
            with closing(self._conectar()) as conexao:
                for chave, valor in conexao.execute(
                        'SELECT chave, valor FROM memoria WHERE perfil=? ORDER BY rowid',
                        (self.perfil,)):
                    partes.append(f'memoria:{chave}={valor}')
                for (texto,) in conexao.execute(
                        'SELECT texto FROM diario WHERE perfil=? ORDER BY rowid',
                        (self.perfil,)):
                    partes.append('diario:' + texto)
        texto = '; '.join(partes)
        return texto[:max(0, int(limite))]
