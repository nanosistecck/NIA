# -*- coding: utf-8 -*-
"""Fase 05 — formato .niateck: fixtures válidas e maliciosas, sem execução."""
from __future__ import annotations

import hashlib
import json
import zipfile

import pytest

from core import niateck as NT

MANIFESTO = {
    'api': 1, 'versao': '1.0.0', 'id': 'plugin_mock', 'nome': 'Plugin mock',
    'licenca': 'MIT', 'adaptador': 'adapter.py', 'hashes': {},
}


def _zip(tmp_path, nome, arquivos, manifesto=None, upstream=None):
    caminho = tmp_path / nome
    with zipfile.ZipFile(caminho, 'w', zipfile.ZIP_DEFLATED) as zf:
        for caminho_interno, conteudo in arquivos.items():
            zf.writestr(caminho_interno, conteudo)
        if manifesto is not None:
            zf.writestr('manifest.json', json.dumps(manifesto))
        else:
            zf.writestr('manifest.json', json.dumps(MANIFESTO))
        if upstream is None:
            upstream = {'origem': 'local', 'repositorio': 'fixture', 'revisao': 'abc123'}
        zf.writestr('upstream.json', json.dumps(upstream))
    return caminho


def test_pacote_valido_e_aceito(tmp_path):
    """Quebra: não existe validador de pacote .niateck."""
    caminho = _zip(tmp_path, 'valido.niateck', {
        'adapter.py': 'VALOR = 1\n', 'LICENSE': 'MIT\n',
    })
    relatorio = NT.inspecionar(caminho)
    assert relatorio.ok is True
    assert relatorio.manifest['id'] == 'plugin_mock'


def test_hash_declarado_e_conferido(tmp_path):
    """Quebra: hashes do manifesto não eram verificados."""
    conteudo = b'VALOR = 1\n'
    manifesto = dict(MANIFESTO)
    manifesto['hashes'] = {
        'adapter.py': hashlib.sha256(conteudo).hexdigest(),
    }
    caminho = _zip(tmp_path, 'hash.niateck',
                   {'adapter.py': conteudo, 'LICENSE': b'MIT\n'}, manifesto)
    assert NT.inspecionar(caminho).ok is True
    manifesto['hashes']['adapter.py'] = '0' * 64
    caminho_ruim = _zip(tmp_path, 'hash_ruim.niateck',
                        {'adapter.py': conteudo, 'LICENSE': b'MIT\n'}, manifesto)
    relatorio = NT.inspecionar(caminho_ruim)
    assert relatorio.ok is False
    assert any('hash' in m.lower() for m in relatorio.motivos)


def test_traversal_e_recusado(tmp_path):
    """Quebra: entradas com .. podiam escapar do destino."""
    caminho = _zip(tmp_path, 'traversal.niateck', {'../fora.txt': 'x'})
    relatorio = NT.inspecionar(caminho)
    assert relatorio.ok is False
    assert any('..' in m for m in relatorio.motivos)


def test_colisao_windows_por_caixa_e_recusada(tmp_path):
    """Quebra: Adapter.py e adapter.py colidem em Windows."""
    caminho = _zip(tmp_path, 'colisao.niateck', {
        'adapter.py': 'a', 'Adapter.py': 'b', 'LICENSE': 'MIT',
    })
    relatorio = NT.inspecionar(caminho)
    assert relatorio.ok is False
    assert any('colis' in m.lower() for m in relatorio.motivos)


def test_expansao_excessiva_e_recusada(tmp_path):
    """Quebra: ZIP bomb era aceito antes da extração."""
    caminho = tmp_path / 'bomba.niateck'
    with zipfile.ZipFile(caminho, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('adapter.py', b'A' * 200000)
        zf.writestr('manifest.json', json.dumps(MANIFESTO))
        zf.writestr('upstream.json', json.dumps(
            {'origem': 'local', 'repositorio': 'fixture', 'revisao': 'abc'}))
    relatorio = NT.inspecionar(caminho, limite_expansao=1000)
    assert relatorio.ok is False
    assert any('expans' in m.lower() for m in relatorio.motivos)


def test_manifesto_invalido_e_recusado(tmp_path):
    """Quebra: manifesto sem licença/adaptador era aceito."""
    manifesto = dict(MANIFESTO)
    manifesto['licenca'] = ''
    caminho = _zip(tmp_path, 'sem_licenca.niateck',
                   {'adapter.py': 'a'}, manifesto)
    relatorio = NT.inspecionar(caminho)
    assert relatorio.ok is False
    assert any('licen' in m.lower() for m in relatorio.motivos)


def test_assinatura_sem_verificador_fica_pendente(tmp_path):
    """Quebra: assinatura presente era ignorada como se válida fosse."""
    manifesto = dict(MANIFESTO)
    manifesto['assinatura'] = 'placeholder'
    caminho = _zip(tmp_path, 'assinado.niateck',
                   {'adapter.py': 'a'}, manifesto)
    relatorio = NT.inspecionar(caminho)
    assert relatorio.ok is False
    assert any('assinat' in m.lower() for m in relatorio.motivos)
