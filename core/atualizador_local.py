# -*- coding: utf-8 -*-
"""Atualizador local sem rede (Fase 19).

Prepara um candidato em diretório separado, valida o pacote com o inspetor
`.niateck`, aplica por troca atômica com backup e permite rollback. Nunca
executa `git pull`, não baixa arquivos e não importa código do candidato.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import os
import shutil
import tempfile

from core import niateck as NT


class Atualizador:
    def __init__(self, raiz, aplicador=None):
        self.raiz = Path(raiz)
        self.aplicador = aplicador
        for nome in ('atual', 'candidatos', 'backups', 'staging'):
            (self.raiz / nome).mkdir(parents=True, exist_ok=True)
        self.caminho_estado = self.raiz / 'estado.json'
        self._estado = self._carregar()

    def _carregar(self) -> dict:
        if not self.caminho_estado.is_file():
            return {'estado': 'sem_candidato', 'id': '', 'hash': '', 'backup': ''}
        try:
            dados = json.loads(self.caminho_estado.read_text(encoding='utf-8'))
            if isinstance(dados.get('estado'), str):
                return dados
        except (ValueError, OSError):
            pass
        return {'estado': 'sem_candidato', 'id': '', 'hash': '', 'backup': ''}

    def _salvar(self) -> None:
        fd, temporario = tempfile.mkstemp(prefix='estado-', suffix='.json',
                                          dir=str(self.raiz))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as arquivo:
                json.dump(self._estado, arquivo, ensure_ascii=False, indent=2)
                arquivo.write('\n')
                arquivo.flush()
                os.fsync(arquivo.fileno())
            os.replace(temporario, self.caminho_estado)
        finally:
            if os.path.exists(temporario):
                os.unlink(temporario)

    def estado(self) -> dict:
        return dict(self._estado)

    def preparar(self, pacote) -> dict:
        pacote = Path(pacote)
        relatorio = NT.inspecionar(pacote)
        if not relatorio.ok:
            return {'ok': False, 'motivos': relatorio.motivos}
        identificador = relatorio.manifest['id']
        destino = self.raiz / 'candidatos' / (identificador + '.niateck')
        shutil.copy2(pacote, destino)
        self._estado = {
            'estado': 'preparado', 'id': identificador,
            'hash': hashlib.sha256(destino.read_bytes()).hexdigest(),
            'backup': '',
        }
        self._salvar()
        return {'ok': True, 'id': identificador, 'pacote': str(destino)}

    def aplicar(self, migracao_irreversivel: bool = False) -> bool:
        if migracao_irreversivel is True:
            return False
        if self._estado.get('estado') not in ('preparado', 'aplicando'):
            return False
        identificador = self._estado['id']
        pacote = self.raiz / 'candidatos' / (identificador + '.niateck')
        atual = self.raiz / 'atual'
        selo = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        backup = self.raiz / 'backups' / selo
        staging = self.raiz / 'staging' / identificador
        self._estado['estado'] = 'aplicando'
        self._salvar()
        try:
            shutil.copytree(atual, backup)
            if staging.exists():
                shutil.rmtree(staging)
            shutil.copytree(atual, staging)
            if self.aplicador is not None and self.aplicador(staging, pacote) is not True:
                shutil.rmtree(staging, ignore_errors=True)
                self._estado['estado'] = 'falhou'
                self._salvar()
                return False
            shutil.rmtree(atual)
            os.replace(staging, atual)
        except (OSError, shutil.Error):
            self._estado['estado'] = 'falhou'
            self._salvar()
            return False
        self._estado['estado'] = 'aplicado'
        self._estado['backup'] = str(backup)
        self._salvar()
        return True

    def rollback(self) -> bool:
        backups = sorted((self.raiz / 'backups').iterdir())
        if not backups:
            return False
        origem = backups[-1]
        atual = self.raiz / 'atual'
        try:
            shutil.rmtree(atual)
            shutil.copytree(origem, atual)
        except (OSError, shutil.Error):
            return False
        self._estado['estado'] = 'revertido'
        self._salvar()
        return True

    def recuperar(self) -> bool:
        if self._estado.get('estado') == 'aplicando':
            return self.aplicar()
        return self._estado.get('estado') == 'aplicado'
