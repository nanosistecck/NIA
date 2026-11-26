# -*- coding: utf-8 -*-
"""Outbox de notificações (Fase 14).

Registra criado/enviado/confirmado/falhou com canais injetados. Nenhum canal
real é chamado por este módulo: o host decide quais adaptadores fornecer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import os
import tempfile
from uuid import uuid4


@dataclass(frozen=True)
class Mensagem:
    canal: str
    destino: str
    texto: str
    id: str = field(default_factory=lambda: uuid4().hex)
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def dedupe(self) -> tuple:
        return (self.canal, self.destino, self.texto)


class Outbox:
    def __init__(self, caminho=None, canais=None, max_tentativas: int = 3):
        self.caminho = Path(caminho) if caminho else Path.home() / '.nia' / 'outbox.json'
        self.canais = dict(canais or {})
        self.max_tentativas = max(1, int(max_tentativas))
        self._dados = self._carregar()
        self._vistos = {tuple(m['dedupe']) for m in self._dados['mensagens']
                        if isinstance(m.get('dedupe'), list)}

    def _carregar(self) -> dict:
        if not self.caminho.is_file():
            return {'mensagens': []}
        try:
            dados = json.loads(self.caminho.read_text(encoding='utf-8'))
            if isinstance(dados.get('mensagens'), list):
                return dados
        except (ValueError, OSError):
            pass
        return {'mensagens': []}

    def _salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        fd, temporario = tempfile.mkstemp(prefix='outbox-', suffix='.json',
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

    def _entregar(self, registro: dict) -> dict:
        canal = self.canais.get(registro['canal'])
        if canal is None:
            registro['estado'] = 'falhou'
        else:
            try:
                resposta = canal(registro['texto'])
            except Exception:
                resposta = False
            if isinstance(resposta, dict) and resposta.get('confirmado') is True:
                registro['estado'] = 'confirmado'
                registro['confirmacao'] = str(resposta.get('id', ''))
            elif resposta is True:
                registro['estado'] = 'enviado'
            elif isinstance(resposta, (dict, str)) and resposta:
                registro['estado'] = 'enviado'
            else:
                registro['estado'] = 'falhou'
        if registro['estado'] == 'falhou':
            registro['tentativas'] = int(registro.get('tentativas', 0)) + 1
        return registro

    def enviar(self, mensagem: Mensagem) -> dict:
        if not isinstance(mensagem, Mensagem):
            raise TypeError('Mensagem inválida.')
        chave = tuple(mensagem.dedupe())
        if chave in self._vistos:
            return {'estado': 'duplicada'}
        registro = {
            'id': mensagem.id, 'canal': mensagem.canal, 'destino': mensagem.destino,
            'texto': mensagem.texto, 'criado_em': mensagem.criado_em,
            'estado': 'criado', 'tentativas': 0, 'confirmacao': '',
            'dedupe': list(chave),
        }
        self._vistos.add(chave)
        self._dados['mensagens'].append(registro)
        self._entregar(registro)
        self._salvar()
        return dict(registro)

    def reenviar_pendentes(self) -> tuple:
        atualizados = []
        for registro in self._dados['mensagens']:
            if (registro['estado'] != 'falhou'
                    or int(registro.get('tentativas', 0)) >= self.max_tentativas):
                continue
            self._entregar(registro)
            atualizados.append(dict(registro))
        if atualizados:
            self._salvar()
        return tuple(atualizados)

    def listar(self) -> tuple:
        return tuple(dict(m) for m in self._dados['mensagens'])
