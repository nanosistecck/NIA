# -*- coding: utf-8 -*-
"""Índice textual local de documentos .txt, reconstruível e sem rede.

Guarda apenas dados derivados em ``~/.nia/indice_local.db`` (ou ``NIA_INDICE_DB``),
separados de ``config/`` e de ``memory/``. O banco é de propriedade da NIA e
pode ser apagado e reconstruído a partir das pastas configuradas.

A separação configuração/serviço/modelo e o uso de FTS5 foram inspirados em
``src/openjarvis/tools/storage/sqlite.py`` do OpenJarvis, revisão ``427c2dd``
(licença Apache 2.0). Nenhum código daquele projeto foi copiado: a
implementação abaixo usa somente ``sqlite3`` da biblioteca padrão e mantém
documentos, trechos e índice coerentes por transação.
"""
from __future__ import annotations

import os
import re
import sqlite3
import threading
import time
import unicodedata
from pathlib import Path

TAMANHO_MAXIMO = 2_000_000       # 2 MB por arquivo
TRECHO_TAMANHO = 1200            # caracteres por trecho
TRECHO_SOBREPOSICAO = 120       # contexto entre trechos
LOTE_PADRAO = 100                # arquivos por chamada de atualização
COMMIT_A_CADA = 25               # arquivos por transação


def caminho_padrao() -> Path:
    externo = os.environ.get('NIA_INDICE_DB')
    if externo:
        return Path(externo).expanduser()
    return Path.home() / '.nia' / 'indice_local.db'


def normalizar(caminho) -> str:
    """Chave estável do documento, conforme as regras do sistema operacional."""
    return os.path.normcase(str(Path(caminho).resolve()))


def fts5_disponivel() -> bool:
    """Testa o runtime real: PRAGMA e criação de uma tabela descartável."""
    try:
        conexao = sqlite3.connect(':memory:')
        try:
            opcoes = [str(linha[0]).upper()
                      for linha in conexao.execute('PRAGMA compile_options')]
            if not any('FTS5' in opcao for opcao in opcoes):
                # Alguns builds omitem a opção mas ainda aceitam a tabela.
                pass
            conexao.execute(
                "CREATE VIRTUAL TABLE _teste USING fts5(texto, "
                "tokenize='porter unicode61')")
            return True
        finally:
            conexao.close()
    except sqlite3.Error:
        return False


def ler_texto(caminho: Path) -> str:
    """UTF-8 com ou sem BOM; recai para cp1252/latin-1 como a Secretária."""
    dados = caminho.read_bytes()
    if len(dados) > TAMANHO_MAXIMO:
        raise ValueError('arquivo acima do limite')
    for codificacao in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            return dados.decode(codificacao)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError('indice_local', dados[:32], 0, 1, 'codificação desconhecida')


def dividir_trechos(texto: str):
    """Trechos com sobreposição pequena, carregando a posição no documento."""
    texto = texto.replace('\r\n', '\n').replace('\r', '\n')
    inicio = 0
    tamanho = len(texto)
    while inicio < tamanho:
        fim = min(tamanho, inicio + TRECHO_TAMANHO)
        if fim < tamanho:
            quebra = max(texto.rfind('\n', inicio + TRECHO_TAMANHO // 2, fim),
                         texto.rfind('. ', inicio + TRECHO_TAMANHO // 2, fim))
            if quebra > inicio:
                fim = quebra + 1
        yield inicio, texto[inicio:fim]
        if fim >= tamanho:
            break
        inicio = max(fim - TRECHO_SOBREPOSICAO, inicio + 1)


class IndiceLocal:
    def __init__(self, db_path=None, fontes=None):
        self.db_path = Path(db_path) if db_path else caminho_padrao()
        self.fontes = list(fontes or [])
        self._cancelar = threading.Event()
        self._trava = threading.RLock()

    # ── infraestrutura ─────────────────────────────────────────────────────
    def _conectar(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conexao = sqlite3.connect(str(self.db_path), timeout=15)
        conexao.row_factory = sqlite3.Row
        conexao.execute('PRAGMA journal_mode=WAL')
        conexao.execute('PRAGMA synchronous=NORMAL')
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS documentos (
                caminho   TEXT PRIMARY KEY,
                fonte     TEXT NOT NULL,
                tamanho   INTEGER NOT NULL,
                mtime_ns  INTEGER NOT NULL,
                atualizado REAL NOT NULL,
                erro      TEXT NOT NULL DEFAULT ''
            )""")
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS trechos (
                id       INTEGER PRIMARY KEY,
                caminho  TEXT NOT NULL,
                ordem    INTEGER NOT NULL,
                posicao  INTEGER NOT NULL,
                texto    TEXT NOT NULL
            )""")
        conexao.execute('CREATE INDEX IF NOT EXISTS trechos_caminho ON trechos(caminho)')
        if fts5_disponivel():
            conexao.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS trechos_fts USING fts5(
                    texto, trecho_id UNINDEXED, tokenize='porter unicode61')""")
        return conexao

    def contar(self) -> dict:
        with self._trava, self._conectar() as conexao:
            documentos = conexao.execute(
                'SELECT COUNT(*) FROM documentos').fetchone()[0]
            trechos = conexao.execute(
                'SELECT COUNT(*) FROM trechos').fetchone()[0]
        return {'documentos': documentos, 'trechos': trechos,
                'fontes': len(self.fontes), 'fts5': fts5_disponivel()}

    def interromper(self) -> None:
        self._cancelar.set()

    # ── fontes ─────────────────────────────────────────────────────────────
    def definir_fontes(self, fontes) -> dict:
        """Sincroniza o banco com a lista nova de raízes autorizadas."""
        novas = list(dict.fromkeys(str(Path(f).expanduser()) for f in (fontes or [])))
        removidas = [f for f in self.fontes if f not in novas]
        self.fontes = novas
        if not removidas:
            return {'removidos': 0}
        removidos = 0
        with self._trava, self._conectar() as conexao:
            linhas = conexao.execute(
                'SELECT caminho, fonte FROM documentos').fetchall()
            for linha in linhas:
                if linha['fonte'] not in removidas:
                    continue
                caminho = Path(linha['caminho'])
                real = normalizar(caminho)
                nova_fonte = None
                for fonte in novas:
                    raiz = Path(fonte)
                    if raiz.exists():
                        try:
                            if Path(real).is_relative_to(raiz.resolve()):
                                nova_fonte = fonte
                                break
                        except (OSError, ValueError):
                            continue
                if nova_fonte is not None:
                    conexao.execute(
                        'UPDATE documentos SET fonte=? WHERE caminho=?',
                        (nova_fonte, linha['caminho']))
                else:
                    self._remover_documento(conexao, linha['caminho'])
                    removidos += 1
        return {'removidos': removidos}

    def _remover_documento(self, conexao, caminho: str) -> None:
        ids = [linha[0] for linha in conexao.execute(
            'SELECT id FROM trechos WHERE caminho=?', (caminho,))]
        if ids:
            marcas = ','.join('?' for _ in ids)
            try:
                conexao.execute(
                    f'DELETE FROM trechos_fts WHERE trecho_id IN ({marcas})', ids)
            except sqlite3.Error:
                pass
        conexao.execute('DELETE FROM trechos WHERE caminho=?', (caminho,))
        conexao.execute('DELETE FROM documentos WHERE caminho=?', (caminho,))

    # ── atualização ────────────────────────────────────────────────────────
    def _descobertos(self):
        encontrados = {}
        indisponiveis = []
        for fonte in self.fontes:
            raiz = Path(fonte).expanduser()
            if not raiz.exists() or not raiz.is_dir():
                indisponiveis.append(fonte)
                continue
            try:
                base = raiz.resolve()
            except OSError:
                indisponiveis.append(fonte)
                continue
            for caminho in raiz.rglob('*'):
                if not caminho.is_file() or caminho.suffix.lower() != '.txt':
                    continue
                try:
                    real = caminho.resolve(strict=True)
                except OSError:
                    continue
                if not real.is_relative_to(base):
                    continue  # link/junction apontando para fora da raiz
                chave = normalizar(real)
                if chave not in encontrados:
                    encontrados[chave] = (real, fonte)
        return encontrados, indisponiveis

    def atualizar(self, limite: int = LOTE_PADRAO, forcar: bool = False) -> dict:
        with self._trava:
            self._cancelar.clear()
            encontrados, indisponiveis = self._descobertos()
            itens = list(encontrados.items())
            estatistica = {'descobertos': len(itens), 'processados': 0,
                           'atualizados': 0, 'removidos': 0, 'erros': [],
                           'pendentes': max(0, len(itens) - limite),
                           'interrompido': False,
                           'fontes_indisponiveis': indisponiveis}
            lote = 0
            with self._conectar() as conexao:
                for chave, (caminho, fonte) in itens[:limite]:
                    if self._cancelar.is_set():
                        estatistica['interrompido'] = True
                        estatistica['pendentes'] = len(itens) - estatistica['processados']
                        break
                    try:
                        info = caminho.stat()
                    except OSError as exc:
                        estatistica['erros'].append((str(caminho), type(exc).__name__))
                        continue
                    anterior = conexao.execute(
                        'SELECT tamanho, mtime_ns FROM documentos WHERE caminho=?',
                        (chave,)).fetchone()
                    if (anterior and not forcar and
                            anterior['tamanho'] == info.st_size and
                            anterior['mtime_ns'] == info.st_mtime_ns):
                        estatistica['processados'] += 1
                        continue
                    try:
                        texto = ler_texto(caminho)
                    except Exception as exc:  # isola arquivo ilegível
                        estatistica['erros'].append((str(caminho), type(exc).__name__))
                        continue
                    with conexao:  # transação por arquivo
                        self._remover_documento(conexao, chave)
                        conexao.execute("""
                            INSERT INTO documentos
                            (caminho, fonte, tamanho, mtime_ns, atualizado, erro)
                            VALUES (?, ?, ?, ?, ?, '')""",
                            (chave, fonte, info.st_size, info.st_mtime_ns, time.time()))
                        for ordem, (posicao, trecho) in enumerate(dividir_trechos(texto)):
                            cursor = conexao.execute("""
                                INSERT INTO trechos (caminho, ordem, posicao, texto)
                                VALUES (?, ?, ?, ?)""",
                                (chave, ordem, posicao, trecho))
                            try:
                                conexao.execute("""
                                    INSERT INTO trechos_fts (texto, trecho_id)
                                    VALUES (?, ?)""",
                                    (trecho, cursor.lastrowid))
                            except sqlite3.Error:
                                pass
                    estatistica['atualizados'] += 1
                    estatistica['processados'] += 1
                    lote += 1
                    if lote >= COMMIT_A_CADA:
                        lote = 0

                # Remoção confirmada: a raiz existe e o arquivo não está mais lá.
                for linha in conexao.execute(
                        'SELECT caminho, fonte FROM documentos').fetchall():
                    raiz = Path(linha['fonte'])
                    if not raiz.exists():
                        continue  # indisponibilidade temporária: preserva
                    if normalizar(linha['caminho']) not in encontrados:
                        with conexao:
                            self._remover_documento(conexao, linha['caminho'])
                        estatistica['removidos'] += 1
            return estatistica

    def reconstruir(self, limite: int = LOTE_PADRAO) -> dict:
        with self._trava, self._conectar() as conexao:
            conexao.execute('DELETE FROM trechos')
            try:
                conexao.execute('DELETE FROM trechos_fts')
            except sqlite3.Error:
                pass
            conexao.execute('DELETE FROM documentos')
        return self.atualizar(limite=limite, forcar=True)

    # ── consulta ───────────────────────────────────────────────────────────
    @staticmethod
    def _termos(texto: str) -> list[str]:
        sem_acento = unicodedata.normalize('NFKD', str(texto or ''))
        sem_acento = ''.join(c for c in sem_acento if not unicodedata.combining(c))
        return [t for t in re.findall(r"\w+", sem_acento.casefold()) if len(t) > 1]

    def buscar(self, texto: str, limite: int = 10) -> list[dict]:
        termos = self._termos(texto)
        if not termos or not fts5_disponivel():
            return []
        consulta = ' '.join(f'"{termo}"' for termo in termos)
        with self._trava, self._conectar() as conexao:
            try:
                linhas = conexao.execute("""
                    SELECT t.caminho, t.texto, t.posicao, t.ordem,
                           d.fonte, bm25(trechos_fts) AS pontuacao
                    FROM trechos_fts
                    JOIN trechos t ON t.id = trechos_fts.trecho_id
                    JOIN documentos d ON d.caminho = t.caminho
                    WHERE trechos_fts MATCH ?
                    ORDER BY pontuacao
                    LIMIT ?""", (consulta, max(1, min(int(limite), 50)))).fetchall()
            except sqlite3.Error:
                return []
        return [{'arquivo': linha['caminho'], 'trecho': linha['texto'],
                 'posicao': linha['posicao'], 'ordem': linha['ordem'],
                 'fonte': linha['fonte'], 'pontuacao': float(linha['pontuacao'])}
                for linha in linhas]
