# -*- coding: utf-8 -*-
"""Factory local de pacotes .niateck (Fase 18).

Constrói pacotes apenas a partir de uma fixture local já presente em disco.
Não baixa nada, não importa adapter, não executa código e não altera upstream.
O ZIP é determinístico: nomes ordenados e timestamp fixo.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import zipfile

DATA_FIXA = (1980, 1, 1, 0, 0, 0)
_ID = re.compile(r'^[a-z][a-z0-9_]{0,63}$')
_VERSAO = re.compile(r'^\d+\.\d+\.\d+$')


def _arquivos(origem: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(origem.iterdir()) if p.is_file()}


def construir(origem, destino, manifesto: dict, upstream: dict) -> dict:
    origem, destino = Path(origem), Path(destino)
    motivos: list[str] = []
    if not origem.is_dir():
        return {'ok': False, 'motivos': ['fixture ausente']}
    if (not isinstance(manifesto, dict) or type(manifesto.get('api')) is not int
            or manifesto['api'] != 1):
        motivos.append('API do manifesto incompatível.')
    if (not isinstance(manifesto.get('versao'), str)
            or not _VERSAO.fullmatch(manifesto.get('versao', ''))):
        motivos.append('Versão do manifesto inválida.')
    if (not isinstance(manifesto.get('id'), str)
            or not _ID.fullmatch(manifesto.get('id', ''))):
        motivos.append('Identificador inválido.')
    if not isinstance(manifesto.get('nome'), str) or not manifesto['nome'].strip():
        motivos.append('Nome ausente.')
    if not isinstance(manifesto.get('licenca'), str) or not manifesto['licenca'].strip():
        motivos.append('Licença ausente.')
    if not isinstance(upstream, dict):
        motivos.append('upstream inválido.')
        upstream = {}
    for chave in ('origem', 'repositorio', 'revisao'):
        if not isinstance(upstream.get(chave), str) or not upstream[chave].strip():
            motivos.append('upstream incompleto: ' + chave)
    arquivos = _arquivos(origem)
    if 'LICENSE' not in arquivos:
        motivos.append('Arquivo LICENSE ausente na fixture.')
    adaptador = str(manifesto.get('adaptador') or '')
    if adaptador not in arquivos:
        motivos.append('Adaptador declarado ausente na fixture.')
    hashes = {nome: hashlib.sha256(conteudo).hexdigest()
              for nome, conteudo in sorted(arquivos.items())}
    if motivos:
        return {'ok': False, 'motivos': tuple(motivos)}
    manifesto_final = dict(manifesto)
    manifesto_final['hashes'] = hashes
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix('.tmp')
    with zipfile.ZipFile(temporario, 'w', zipfile.ZIP_DEFLATED) as zf:
        for nome in sorted(arquivos):
            info = zipfile.ZipInfo(nome, DATA_FIXA)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, arquivos[nome])
        for nome, dados in (
            ('manifest.json', json.dumps(manifesto_final, ensure_ascii=False,
                                         sort_keys=True, indent=2).encode('utf-8')),
            ('upstream.json', json.dumps(upstream, ensure_ascii=False,
                                         sort_keys=True, indent=2).encode('utf-8')),
        ):
            info = zipfile.ZipInfo(nome, DATA_FIXA)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, dados)
    os.replace(temporario, destino)
    return {
        'ok': True,
        'proveniencia': {
            'origem': upstream['origem'],
            'repositorio': upstream['repositorio'],
            'revisao': upstream['revisao'],
            'arquivos': hashes,
            'pacote': str(destino),
        },
    }
