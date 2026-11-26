# -*- coding: utf-8 -*-
"""Gerenciador de plugins locais (Fase 06).

Instalação, ativação, reparo e remoção usam somente pacotes já inspecionados
por ``core.niateck``. Nenhum módulo é importado, nenhum processo é iniciado e
nenhuma dependência é instalada. Dados, versões e ambientes virtuais ficam em
diretórios distintos do código do produto.
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


class GerenciadorPlugins:
    def __init__(self, raiz):
        self.raiz = Path(raiz)
        self.raiz.mkdir(parents=True, exist_ok=True)
        for nome in ('staging', 'instalados', 'removidos', 'versoes', 'venvs'):
            (self.raiz / nome).mkdir(parents=True, exist_ok=True)
        self.caminho_estado = self.raiz / 'estado.json'
        self._estado = self._carregar()

    def _carregar(self) -> dict:
        if not self.caminho_estado.is_file():
            return {'plugins': {}}
        try:
            dados = json.loads(self.caminho_estado.read_text(encoding='utf-8'))
            if isinstance(dados.get('plugins'), dict):
                return dados
        except (ValueError, OSError):
            pass
        return {'plugins': {}}

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

    def _hash(self, caminho: Path) -> str:
        return hashlib.sha256(caminho.read_bytes()).hexdigest()

    def preparar(self, pacote):
        pacote = Path(pacote)
        relatorio = NT.inspecionar(pacote)
        if not relatorio.ok:
            raise ValueError('Pacote recusado: ' + '; '.join(relatorio.motivos))
        identificador = relatorio.manifest['id']
        destino = self.raiz / 'staging' / identificador
        if destino.exists():
            shutil.rmtree(destino)
        destino.mkdir(parents=True)
        shutil.copy2(pacote, destino / 'pacote.niateck')
        metadados = {
            'id': identificador,
            'versao': relatorio.manifest['versao'],
            'origem': str(relatorio.upstream.get('origem', 'desconhecida')),
            'hash': self._hash(destino / 'pacote.niateck'),
        }
        (destino / 'manifesto.json').write_text(
            json.dumps(metadados, ensure_ascii=False, indent=2), encoding='utf-8')
        return metadados

    def instalar(self, pacote):
        metadados = self.preparar(pacote)
        identificador = metadados['id']
        if identificador in self._estado['plugins']:
            raise ValueError('Plugin já registrado: ' + identificador)
        origem = self.raiz / 'staging' / identificador
        destino = self.raiz / 'instalados' / identificador
        if destino.exists():
            shutil.rmtree(destino)
        shutil.move(str(origem), str(destino))
        registro = {
            'estado': 'instalado', 'ativo': False,
            'versao': metadados['versao'], 'origem': metadados['origem'],
            'carregador': '', 'hash': metadados['hash'],
        }
        self._estado['plugins'][identificador] = registro
        self._salvar()
        return {'id': identificador, **registro}

    def _alterar_ativo(self, identificador: str, ativo: bool) -> bool:
        registro = self._estado['plugins'].get(identificador)
        if registro is None or registro.get('estado') != 'instalado':
            return False
        registro['ativo'] = ativo
        self._salvar()
        return True

    def ativar(self, identificador: str) -> bool:
        return self._alterar_ativo(identificador, True)

    def desativar(self, identificador: str) -> bool:
        return self._alterar_ativo(identificador, False)

    def remover(self, identificador: str) -> bool:
        registro = self._estado['plugins'].get(identificador)
        if registro is None:
            return False
        origem = self.raiz / 'instalados' / identificador
        if origem.exists():
            selo = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
            shutil.move(str(origem), str(self.raiz / 'removidos' / f'{identificador}-{selo}'))
        self._estado['plugins'].pop(identificador, None)
        self._salvar()
        return True

    def reparar(self, identificador: str) -> bool:
        registro = self._estado['plugins'].get(identificador)
        if registro is None:
            return False
        pacote = self.raiz / 'instalados' / identificador / 'pacote.niateck'
        relatorio = NT.inspecionar(pacote)
        if not relatorio.ok:
            registro['estado'] = 'corrompido'
            registro['ativo'] = False
            self._salvar()
            return False
        registro['estado'] = 'instalado'
        registro['hash'] = self._hash(pacote)
        self._salvar()
        return True

    def recuperar(self) -> int:
        total = 0
        for pasta in sorted((self.raiz / 'staging').iterdir()):
            manifesto = pasta / 'manifesto.json'
            pacote = pasta / 'pacote.niateck'
            if not pasta.is_dir() or not manifesto.is_file() or not pacote.is_file():
                continue
            try:
                metadados = json.loads(manifesto.read_text(encoding='utf-8'))
                identificador = metadados['id']
            except (ValueError, KeyError, OSError):
                continue
            relatorio = NT.inspecionar(pacote)
            if not relatorio.ok:
                continue
            destino = self.raiz / 'instalados' / identificador
            if destino.exists():
                shutil.rmtree(destino)
            shutil.move(str(pasta), str(destino))
            self._estado['plugins'][identificador] = {
                'estado': 'instalado', 'ativo': False,
                'versao': metadados.get('versao', '1.0.0'),
                'origem': metadados.get('origem', 'desconhecida'),
                'carregador': '',
                'hash': self._hash(destino / 'pacote.niateck'),
            }
            total += 1
        for identificador, registro in self._estado['plugins'].items():
            pacote = self.raiz / 'instalados' / identificador / 'pacote.niateck'
            if not pacote.is_file() and registro.get('estado') == 'instalado':
                registro['estado'] = 'corrompido'
                registro['ativo'] = False
        self._salvar()
        return total

    def inventario(self) -> tuple:
        itens = []
        for identificador, registro in sorted(self._estado['plugins'].items()):
            itens.append({
                'id': identificador,
                'estado': registro.get('estado', 'desconhecido'),
                'ativo': bool(registro.get('ativo', False)),
                'versao': registro.get('versao', ''),
                'origem': registro.get('origem', ''),
                'carregador': '',
            })
        return tuple(itens)
