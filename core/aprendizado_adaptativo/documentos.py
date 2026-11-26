# -*- coding: utf-8 -*-
"""Documentos universais com blocos tipados e revisão otimista (F07)."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
from uuid import uuid4


class ConflitoRevisao(RuntimeError):
    """A revisão informada é mais antiga que a revisão atual."""


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


class DocumentoInteligente:
    def __init__(self, *, titulo: str = '', memoria=None, identificador=None,
                 revisao: int = 0, blocos=None):
        self.id = str(identificador or uuid4().hex)
        self.titulo = str(titulo or '')
        self.memoria = memoria
        self.revisao = int(revisao)
        self.blocos: list[dict] = list(blocos or [])
        self._undo: list[dict] = []
        self._redo: list[dict] = []

    @classmethod
    def carregar(cls, identificador: str, *, memoria) -> "DocumentoInteligente":
        dato = memoria.obter('documents', str(identificador))
        if dato is None:
            raise KeyError('Documento inexistente')
        conteudo = dato.get('conteudo') or {}
        if isinstance(conteudo, str):
            conteudo = json.loads(conteudo)
        return cls(titulo=dato.get('titulo', ''), memoria=memoria,
                   identificador=identificador, revisao=int(dato.get('revisao', 0)),
                   blocos=conteudo.get('blocos', ()))

    def _snapshot(self) -> None:
        self._undo.append({'revisao': self.revisao,
                           'blocos': copy.deepcopy(self.blocos)})
        self._redo.clear()

    def adicionar_bloco(self, tipo: str, dados: dict) -> str:
        self._snapshot()
        bid = uuid4().hex
        self.blocos.append({'id': bid, 'tipo': str(tipo),
                            'dados': copy.deepcopy(dict(dados or {})),
                            'revisao': self.revisao + 1})
        self.revisao += 1
        return bid

    def editar_bloco(self, bloco_id: str, dados: dict, *, revisao: int) -> None:
        if int(revisao) != int(self.revisao):
            raise ConflitoRevisao('revisão divergente')
        bloco = next((b for b in self.blocos if b['id'] == bloco_id), None)
        if bloco is None:
            raise KeyError('Bloco inexistente')
        self._snapshot()
        bloco['dados'] = copy.deepcopy(dict(dados or {}))
        bloco['revisao'] = self.revisao + 1
        self.revisao += 1

    def desfazer(self) -> bool:
        if not self._undo:
            return False
        self._redo.append({'revisao': self.revisao,
                           'blocos': copy.deepcopy(self.blocos)})
        anterior = self._undo.pop()
        self.revisao = anterior['revisao']
        self.blocos = anterior['blocos']
        return True

    def refazer(self) -> bool:
        if not self._redo:
            return False
        self._undo.append({'revisao': self.revisao,
                           'blocos': copy.deepcopy(self.blocos)})
        posterior = self._redo.pop()
        self.revisao = posterior['revisao']
        self.blocos = posterior['blocos']
        return True

    def exportar_markdown(self) -> str:
        linhas = [f'# {self.titulo}', '']
        for bloco in self.blocos:
            dados = bloco.get('dados') or {}
            tipo = bloco.get('tipo')
            if tipo == 'titulo':
                linhas += [f"## {dados.get('texto', '')}", '']
            elif tipo == 'texto':
                linhas += [str(dados.get('texto', '')), '']
            elif tipo == 'checklist':
                linhas += [f"- [ ] {item}" for item in dados.get('itens', ())]
            elif tipo == 'lista':
                linhas += [f"- {item}" for item in dados.get('itens', ())]
            elif tipo == 'links':
                linhas += [f"[{d.get('titulo', '')}]({d.get('url', '')})"
                           for d in dados.get('itens', ()) if isinstance(d, dict)]
            elif tipo == 'tabela':
                for linha in dados.get('linhas', ()):
                    if isinstance(linha, (list, tuple)):
                        linhas.append('| ' + ' | '.join(str(x) for x in linha) + ' |')
            elif tipo == 'notas':
                linhas += [f"> {dados.get('texto', '')}", '']
        return '\n'.join(linhas).rstrip() + '\n'

    def salvar(self) -> str:
        if self.memoria is None:
            return self.id
        with self.memoria.con:
            self.memoria.con.execute(
                'INSERT OR REPLACE INTO documents '
                '(id, titulo, revisao, conteudo, atualizado_em) VALUES (?,?,?,?,?)',
                (self.id, self.titulo, self.revisao,
                 json.dumps({'blocos': self.blocos}, ensure_ascii=False),
                 _agora()))
            self.memoria.con.execute('DELETE FROM items WHERE documento_id=?',
                                     (self.id,))
            for bloco in self.blocos:
                self.memoria.con.execute(
                    'INSERT INTO items (id, documento_id, tipo, dados, revisao) '
                    'VALUES (?,?,?,?,?)',
                    (bloco['id'], self.id, bloco['tipo'],
                     json.dumps(bloco['dados'], ensure_ascii=False),
                     int(bloco.get('revisao', self.revisao))))
        return self.id
