# -*- coding: utf-8 -*-
"""Motor de conhecimento local (Fase 10).

Registra pesquisas com fontes verificáveis, conclusões, lacunas e revisões.
Reaproveita ``indice_local``/``busca_fontes`` quando injetado, mas nunca faz
rede nem indexa fonte fora da lista autorizada. A integração com Canvas é por
ID, sem importar ``ui``.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import os
import tempfile
from uuid import uuid4


class MotorConhecimento:
    def __init__(self, caminho=None, indice=None, fts5=None, autorizadas=()):
        self.caminho = Path(caminho) if caminho else Path.home() / '.nia' / 'conhecimento.json'
        self.indice = indice
        if fts5 is None:
            try:
                from core import indice_local  # importação local e leve
                fts5 = indice_local.fts5_disponivel()
            except Exception:
                fts5 = False
        self.fts5 = bool(fts5)
        self.autorizadas = frozenset(str(f) for f in (autorizadas or ()))
        self._dados = self._carregar()

    def _carregar(self) -> dict:
        if not self.caminho.is_file():
            return {'pesquisas': {}, 'canvas': []}
        try:
            dados = json.loads(self.caminho.read_text(encoding='utf-8'))
            if isinstance(dados.get('pesquisas'), dict):
                return dados
        except (ValueError, OSError):
            pass
        return {'pesquisas': {}, 'canvas': []}

    def _salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        fd, temporario = tempfile.mkstemp(prefix='conhecimento-', suffix='.json',
                                          dir=str(self.caminho.parent))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as arquivo:
                json.dump(self._dados, arquivo, ensure_ascii=False, indent=2)
                arquivo.write('\n')
                arquivo.flush()
                os.fsync(arquivo.fileno())
            os.replace(temporario, self.caminho)
        finally:
            if os.path.exists(temporario):
                os.unlink(temporario)

    def registrar(self, pergunta, fontes, conclusao, lacunas=()) -> str:
        identificador = uuid4().hex
        self._dados['pesquisas'][identificador] = {
            'pergunta': str(pergunta),
            'fontes': [str(f) for f in (fontes or ())],
            'conclusao': str(conclusao),
            'lacunas': [str(x) for x in (lacunas or ())],
            'criado_em': datetime.now(timezone.utc).isoformat(),
            'revisoes': 0,
            'historico': [],
        }
        self._salvar()
        return identificador

    def obter(self, identificador: str) -> dict | None:
        return self._dados['pesquisas'].get(str(identificador))

    def revisar(self, identificador: str, conclusao: str) -> bool:
        registro = self.obter(identificador)
        if registro is None:
            return False
        registro['historico'].append({
            'conclusao_anterior': registro['conclusao'],
            'revisado_em': datetime.now(timezone.utc).isoformat(),
        })
        registro['conclusao'] = str(conclusao)
        registro['revisoes'] = int(registro.get('revisoes', 0)) + 1
        self._salvar()
        return True

    def integrar_canvas(self, identificador: str) -> dict:
        if self.obter(identificador) is None:
            raise ValueError('Pesquisa não registrada.')
        cartao = {'pesquisa_id': identificador, 'card_id': 'canvas-' + identificador[:8]}
        if cartao not in self._dados['canvas']:
            self._dados['canvas'].append(cartao)
            self._salvar()
        return cartao

    def referencias_canvas(self) -> tuple:
        return tuple(self._dados['canvas'])

    def excluir(self, identificador: str) -> bool:
        if self._dados['pesquisas'].pop(str(identificador), None) is None:
            return False
        self._dados['canvas'] = [c for c in self._dados['canvas']
                                 if c['pesquisa_id'] != identificador]
        self._salvar()
        return True

    def buscar(self, termo: str, limite: int = 10) -> tuple:
        if (self.indice is None or not self.autorizadas
                or not isinstance(termo, str) or not termo.strip()):
            return ()
        brutos = self.indice.buscar(termo.strip(), int(limite)) or ()
        resultados = []
        for trecho in brutos:
            if not isinstance(trecho, dict) or str(trecho.get('fonte', '')) not in self.autorizadas:
                continue
            resultados.append({
                'fonte': str(trecho['fonte']),
                'texto': str(trecho.get('texto', '')),
                'posicao': trecho.get('posicao', 0),
            })
        return tuple(resultados)
