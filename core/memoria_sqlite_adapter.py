# -*- coding: utf-8 -*-
"""Adaptador SQLite compatível com memory_manager/diario (Fase 08 finalizada).

Mantém as mesmas operações usadas pelo restante da NIA, mas sobre o banco
migrado. A migração é idempotente e os arquivos JSON/JSONL originais não são
alterados. Nenhuma função é ligada automaticamente ao produto: a ativação é
explícita pelo host.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4

from core import memoria_sqlite as MS


class MemoriaSQLite:
    def __init__(self, db_path, perfil='padrao', memoria_json=None, diario_jsonl=None):
        self.db_path = Path(db_path)
        self.perfil = str(perfil or 'padrao')
        self._migrador = MS.MigradorMemoria(
            memoria_json or self.db_path.parent / 'memory.json',
            diario_jsonl or self.db_path.parent / 'diario.jsonl',
            self.db_path, self.perfil)
        if memoria_json is not None or diario_jsonl is not None:
            self._migrador.migrar()
        with closing(self._conectar()) as conexao:
            pass

    def _conectar(self):
        conexao = self._migrador._conectar()
        conexao.row_factory = sqlite3.Row
        return conexao

    def _agora(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _memoria(self) -> dict:
        with closing(self._conectar()) as conexao:
            linhas = conexao.execute(
                'SELECT chave, valor FROM memoria WHERE perfil=? ORDER BY rowid',
                (self.perfil,)).fetchall()
        return {linha['chave']: linha['valor'] for linha in linhas}

    def load_memory(self) -> dict:
        return self._memoria()

    def _gravar(self, chave: str, valor) -> None:
        with closing(self._conectar()) as conexao:
            conexao.execute(
                'INSERT INTO memoria (id, perfil, chave, valor, origem, criado_em) '
                'VALUES (?,?,?,?,?,?)',
                (uuid4().hex, self.perfil, str(chave), str(valor),
                 'adaptador', self._agora()))
            conexao.commit()

    def update_memory(self, mudancas: dict) -> None:
        atual = self._memoria()
        for chave, valor in (mudancas or {}).items():
            if (isinstance(valor, dict) and isinstance(atual.get(chave), dict)):
                novo = dict(atual[chave])
                novo.update(valor)
                atual[chave] = novo
            else:
                atual[chave] = valor
        with closing(self._conectar()) as conexao:
            conexao.execute('DELETE FROM memoria WHERE perfil=?', (self.perfil,))
            for chave, valor in atual.items():
                conexao.execute(
                    'INSERT INTO memoria (id, perfil, chave, valor, origem, criado_em) '
                    'VALUES (?,?,?,?,?,?)',
                    (uuid4().hex, self.perfil, str(chave), str(valor),
                     'adaptador', self._agora()))
            conexao.commit()

    def remember(self, chave: str, valor) -> None:
        self._gravar(chave, valor)

    def forget(self, chave: str) -> bool:
        with closing(self._conectar()) as conexao:
            cursor = conexao.execute(
                'DELETE FROM memoria WHERE perfil=? AND chave=?',
                (self.perfil, str(chave)))
            conexao.commit()
        return cursor.rowcount > 0

    def format_memory_for_prompt(self) -> str:
        return '\n'.join(f'{chave}: {valor}'
                         for chave, valor in self._memoria().items())

    def anotar(self, texto: str, sessao: str = 'atual') -> None:
        with closing(self._conectar()) as conexao:
            conexao.execute(
                'INSERT INTO diario (id, perfil, texto, origem, criado_em, sessao) '
                'VALUES (?,?,?,?,?,?)',
                (uuid4().hex, self.perfil, str(texto or ''),
                 'adaptador', self._agora(), sessao))
            conexao.commit()

    def _linhas(self) -> list:
        with closing(self._conectar()) as conexao:
            return [linha['texto'] for linha in conexao.execute(
                'SELECT texto FROM diario WHERE perfil=? ORDER BY rowid',
                (self.perfil,)).fetchall()]

    def ler(self, limite: int = 50) -> list:
        return self._linhas()[-max(0, int(limite)):]

    def procurar(self, termo: str) -> list:
        alvo = str(termo or '').casefold()
        return [linha for linha in self._linhas() if alvo in linha.casefold()]

    def resumo_para_o_cerebro(self) -> str:
        return '\n'.join(self.ler(20))

    def excluir(self, chave: str) -> bool:
        valor = self._memoria().get(str(chave))
        if valor is None:
            return False
        with closing(self._conectar()) as conexao:
            conexao.execute(
                'DELETE FROM memoria WHERE perfil=? AND chave=?',
                (self.perfil, str(chave)))
            conexao.execute(
                'DELETE FROM diario WHERE perfil=? AND texto LIKE ?',
                (self.perfil, '%' + str(valor) + '%'))
            conexao.commit()
        return True
