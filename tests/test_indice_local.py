"""Índice local de documentos: banco temporário, sem rede e sem modelos."""
import os
from pathlib import Path

import pytest

from core import indice_local as IL


@pytest.fixture
def pasta(tmp_path):
    destino = tmp_path / 'documentos'
    destino.mkdir()
    return destino


@pytest.fixture
def indice(tmp_path):
    return IL.IndiceLocal(db_path=tmp_path / 'indice.db')


def test_indexa_txt_e_encontra_trecho_com_arquivo(pasta, indice):
    (pasta / 'recados.TXT').write_text(
        'A secretária anotou o recado da Maria.', encoding='utf-8')
    indice.fontes = [str(pasta)]
    assert indice.atualizar()['atualizados'] == 1
    resultados = indice.buscar('recado da maria')
    assert resultados
    assert Path(resultados[0]['arquivo']).name.lower() == 'recados.txt'
    assert 'recado' in resultados[0]['trecho'].lower()
    assert resultados[0]['posicao'] == 0


def test_reindexa_sem_duplicar_nem_reler_inalterado(pasta, indice, monkeypatch):
    arquivo = pasta / 'a.txt'
    arquivo.write_text('Palavra repetida para teste.', encoding='utf-8')
    indice.fontes = [str(pasta)]
    chamadas = []
    original = IL.ler_texto

    def contado(caminho):
        chamadas.append(caminho)
        return original(caminho)

    monkeypatch.setattr(IL, 'ler_texto', contado)
    indice.atualizar()
    assert len(chamadas) == 1
    indice.atualizar()
    assert len(chamadas) == 1
    assert indice.contar() == {'documentos': 1, 'trechos': 1,
                               'fontes': 1, 'fts5': IL.fts5_disponivel()}
    os.utime(arquivo, ns=(arquivo.stat().st_atime_ns, arquivo.stat().st_mtime_ns + 10_000))
    indice.atualizar()
    assert len(chamadas) == 2
    assert indice.contar()['documentos'] == 1
    assert len(indice.buscar('palavra')) == 1


def test_edita_renomeia_e_remove_arquivo(pasta, indice):
    arquivo = pasta / 'a.txt'
    arquivo.write_text('Primeiro conteudo antigo.', encoding='utf-8')
    indice.fontes = [str(pasta)]
    indice.atualizar()
    assert indice.buscar('antigo')

    arquivo.write_text('Segundo conteudo novo.', encoding='utf-8')
    os.utime(arquivo, ns=(arquivo.stat().st_atime_ns, arquivo.stat().st_mtime_ns + 10_000))
    indice.atualizar()
    assert not indice.buscar('antigo')
    assert indice.buscar('novo')

    renomeado = pasta / 'b.txt'
    arquivo.rename(renomeado)
    indice.atualizar()
    resultados = indice.buscar('novo')
    assert resultados
    assert all(Path(item['arquivo']) == renomeado for item in resultados)

    renomeado.unlink()
    indice.atualizar()
    assert not indice.buscar('novo')
    assert indice.contar()['documentos'] == 0


def test_remover_pasta_preserva_arquivo_de_outra_raiz(pasta, tmp_path, indice):
    sub = pasta / 'sub'
    sub.mkdir()
    (pasta / 'so_a.txt').write_text('Somente na raiz maior.', encoding='utf-8')
    (sub / 'nos_dois.txt').write_text('Pertence as duas pastas.', encoding='utf-8')
    indice.fontes = [str(pasta), str(sub)]
    indice.atualizar()
    assert indice.contar()['documentos'] == 2

    indice.definir_fontes([str(sub)])
    assert indice.buscar('duas pastas')
    assert not indice.buscar('raiz maior')
    assert indice.contar()['documentos'] == 1

    indice.definir_fontes([])
    assert indice.contar()['documentos'] == 0


def test_arquivo_ilegivel_pasta_indisponivel_e_sem_fts(pasta, indice, monkeypatch):
    (pasta / 'ruim.txt').write_text('conteudo', encoding='utf-8')
    (pasta / 'bom.txt').write_text('texto indexavel', encoding='utf-8')
    indice.fontes = [str(pasta)]
    original = IL.ler_texto

    def irregular(caminho):
        if caminho.name == 'ruim.txt':
            raise OSError('ilegível')
        return original(caminho)

    monkeypatch.setattr(IL, 'ler_texto', irregular)
    resultado = indice.atualizar()
    assert len(resultado['erros']) == 1
    assert indice.buscar('indexavel')
    assert indice.buscar('') == []

    # A mesma pasta configurada fica temporariamente ausente: não apaga.
    ausente = pasta.with_name('ausente')
    pasta.rename(ausente)
    try:
        # O caminho configurado é o antigo, agora ausente.
        indice.fontes = [str(pasta)]
        resultado = indice.atualizar()
        assert resultado['fontes_indisponiveis']
        assert indice.contar()['documentos'] >= 1
    finally:
        ausente.rename(pasta)

    monkeypatch.setattr(IL, 'fts5_disponivel', lambda: False)
    assert indice.buscar('indexavel') == []
    assert indice.contar()['fts5'] is False


def test_interrupcao_e_reinicio_deixam_banco_consistente(pasta, indice, monkeypatch):
    for i in range(4):
        (pasta / f'{i}.txt').write_text(f'documento numero {i}', encoding='utf-8')
    indice.fontes = [str(pasta)]
    original = IL.ler_texto
    interrompeu = []

    def as_vezes(caminho):
        if not interrompeu:
            interrompeu.append(True)
            indice.interromper()
        return original(caminho)

    monkeypatch.setattr(IL, 'ler_texto', as_vezes)
    parcial = indice.atualizar(limite=10)
    assert parcial['interrompido'] is True
    # Banco segue consultável mesmo após a interrupção.
    assert isinstance(indice.buscar('documento'), list)

    monkeypatch.setattr(IL, 'ler_texto', original)
    completo = indice.atualizar(limite=10)
    assert completo['interrompido'] is False
    assert indice.contar()['documentos'] == 4
    assert indice.contar()['documentos'] == len({r['arquivo'] for r in indice.buscar('documento')})
