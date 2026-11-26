# -*- coding: utf-8 -*-
"""Inspetor do formato .niateck (Fase 05).

A inspeção é somente leitura: nenhum arquivo é extraído, importado ou
executado. Hash confirma integridade de bytes, não autoria; uma assinatura
sem verificador disponível é registrada como pendente e recusada.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import stat
import zipfile

LIMITE_BYTES = 32 * 1024 * 1024
LIMITE_ARQUIVOS = 200
LIMITE_EXPANSAO = 64 * 1024 * 1024
RESERVADOS = frozenset(
    {'CON', 'PRN', 'AUX', 'NUL'} |
    {f'COM{i}' for i in range(1, 10)} | {f'LPT{i}' for i in range(1, 10)})
_ID = re.compile(r'^[a-z][a-z0-9_]{0,63}$')
_VERSAO = re.compile(r'^\d+\.\d+\.\d+$')


@dataclass(frozen=True)
class Relatorio:
    ok: bool
    motivos: tuple[str, ...] = ()
    manifest: dict = field(default_factory=dict)
    upstream: dict = field(default_factory=dict)
    entradas: tuple[str, ...] = ()


def _seguro(caminho: str) -> str:
    return caminho.replace('\\', '/').strip('/')


def _validar_nome(nome: str, motivos: list[str]) -> str | None:
    if not nome or nome.startswith('/') or re.match(r'^[A-Za-z]:', nome):
        motivos.append('caminho absoluto ou inválido no ZIP: ' + nome)
        return None
    normalizado = _seguro(nome)
    partes = normalizado.split('/')
    if any(parte == '..' for parte in partes):
        motivos.append('travessia de diretório (..) no ZIP: ' + nome)
        return None
    for parte in partes:
        if not parte or parte.endswith('.') or parte.endswith(' '):
            motivos.append('nome de arquivo inválido no Windows: ' + nome)
            return None
        if parte.split('.', 1)[0].upper() in RESERVADOS:
            motivos.append('nome reservado do Windows no ZIP: ' + nome)
            return None
    return normalizado


def _validar_manifesto(dados: dict, entradas: set[str], zf, motivos: list[str]) -> None:
    if type(dados.get('api')) is not int or dados['api'] != 1:
        motivos.append('API do manifesto incompatível.')
    if not isinstance(dados.get('versao'), str) or not _VERSAO.fullmatch(dados['versao']):
        motivos.append('Versão do manifesto inválida.')
    if not isinstance(dados.get('id'), str) or not _ID.fullmatch(dados['id']):
        motivos.append('Identificador do manifesto inválido.')
    if not isinstance(dados.get('nome'), str) or not dados['nome'].strip():
        motivos.append('Nome do manifesto ausente.')
    if not isinstance(dados.get('licenca'), str) or not dados['licenca'].strip():
        motivos.append('Licença do manifesto ausente.')
    adaptador = dados.get('adaptador')
    if not isinstance(adaptador, str) or _seguro(adaptador) not in entradas:
        motivos.append('Adaptador declarado não está no pacote.')
    hashes = dados.get('hashes', {})
    if not isinstance(hashes, dict):
        motivos.append('Hashes devem ser um objeto.')
    else:
        for caminho, esperado in hashes.items():
            alvo = _seguro(str(caminho))
            if not isinstance(esperado, str) or not re.fullmatch(r'[0-9a-f]{64}', esperado):
                motivos.append('Hash inválido no manifesto: ' + alvo)
                continue
            try:
                encontrado = hashlib.sha256(zf.read(alvo)).hexdigest()
            except KeyError:
                motivos.append('Arquivo do hash ausente: ' + alvo)
                continue
            if encontrado != esperado:
                motivos.append('Hash não confere: ' + alvo)
    if 'assinatura' in dados and dados['assinatura']:
        motivos.append('Assinatura presente sem verificador disponível: pendente.')


def _validar_upstream(dados: dict, motivos: list[str]) -> None:
    if not isinstance(dados, dict):
        motivos.append('upstream.json inválido.')
        return
    for chave in ('origem', 'repositorio', 'revisao'):
        if not isinstance(dados.get(chave), str) or not dados[chave].strip():
            motivos.append('upstream.json incompleto: ' + chave)
    for valor in dados.values():
        if isinstance(valor, str) and re.search(r'https?://[^/\s]+:[^/\s]+@', valor):
            motivos.append('URL com credencial no upstream.json.')


def inspecionar(caminho, *, limite_bytes=LIMITE_BYTES,
                limite_arquivos=LIMITE_ARQUIVOS,
                limite_expansao=LIMITE_EXPANSAO) -> Relatorio:
    """Devolve relatório de segurança sem extrair nem executar nada."""
    motivos: list[str] = []
    caminho = Path(caminho)
    if not caminho.is_file() or caminho.stat().st_size > limite_bytes:
        return Relatorio(False, ('arquivo ausente ou acima do limite de tamanho',))
    try:
        with zipfile.ZipFile(caminho) as zf:
            entradas_originais = zf.infolist()
            if len(entradas_originais) > limite_arquivos:
                motivos.append('quantidade de entradas acima do limite.')
            nomes: list[str] = []
            normalizados: set[str] = set()
            visiveis: set[str] = set()
            total = 0
            for info in entradas_originais:
                nome = _validar_nome(info.filename, motivos)
                if nome is None:
                    continue
                chave = nome.casefold()
                if chave in visiveis:
                    motivos.append('colisão de caminhos no Windows: ' + nome)
                visiveis.add(chave)
                normalizados.add(nome)
                nomes.append(nome)
                total += info.file_size
            if total > limite_expansao:
                motivos.append('expansão total acima do limite (ZIP bomb).')
            for info in entradas_originais:
                modo = info.external_attr >> 16
                if stat.S_ISLNK(modo):
                    motivos.append('symlink não é permitido no pacote.')
            if 'manifest.json' not in normalizados or 'upstream.json' not in normalizados:
                motivos.append('manifest.json ou upstream.json ausente.')
                return Relatorio(False, tuple(motivos))
            try:
                manifest = json.loads(zf.read('manifest.json'))
                upstream = json.loads(zf.read('upstream.json'))
            except (ValueError, KeyError, UnicodeDecodeError):
                motivos.append('JSON do manifesto/upstream inválido.')
                return Relatorio(False, tuple(motivos))
            if not isinstance(manifest, dict):
                motivos.append('Manifesto deve ser um objeto.')
            else:
                _validar_manifesto(manifest, normalizados, zf, motivos)
            _validar_upstream(upstream, motivos)
    except zipfile.BadZipFile:
        return Relatorio(False, ('ZIP inválido ou corrompido',))
    return Relatorio(not bool(motivos), tuple(motivos), manifest, upstream,
                     tuple(nomes))
