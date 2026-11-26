# -*- coding: utf-8 -*-
"""Rotinas locais persistentes: lembretes, recorrência e histórico.

Banco em ``~/.nia/rotinas.db`` (ou ``NIA_ROTINAS_DB``), na área de dados do
perfil — separado de ``config/``, da memória pessoal e do índice de textos.
Nenhuma rede, modelo ou serviço externo é necessário.

A separação tarefas/execuções e o log de resultados foram inspirados em
``src/openjarvis/scheduler/store.py``, OpenJarvis revisão ``427c2dd``
(Apache 2.0). Nenhum código foi copiado; a implementação usa somente
``sqlite3`` da biblioteca padrão.
"""
from __future__ import annotations

from calendar import monthrange
import os
import sqlite3
import threading
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TIPOS = ('unica', 'diaria', 'dias_uteis', 'semanal', 'mensal', 'intervalo')
ACOES = ('lembrete', 'resumo')
ESTADOS = ('ativo', 'pausado')
ORIGENS = ('agendada', 'manual')
LIMITE_HISTORICO = 100


def caminho_padrao() -> Path:
    externo = os.environ.get('NIA_ROTINAS_DB')
    if externo:
        return Path(externo).expanduser()
    return Path.home() / '.nia' / 'rotinas.db'


def fuso_padrao() -> str:
    env = os.environ.get('TZ')
    if env:
        return env
    try:
        return Path('/etc/timezone').read_text(encoding='utf-8').strip()
    except (OSError, ValueError):
        return 'America/Sao_Paulo'


def _iso(instante: datetime | None) -> str | None:
    if instante is None:
        return None
    return instante.astimezone(timezone.utc).isoformat()


def _de_iso(texto: str) -> datetime | None:
    try:
        return datetime.fromisoformat(texto).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _fuso(nome: str) -> ZoneInfo:
    try:
        return ZoneInfo(nome or fuso_padrao())
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(fuso_padrao())


def resolver_hora(dia: date, hora: time, fuso: str) -> datetime:
    """Hora local inequívoca em UTC.

    Horário ambíguo (outono) usa a primeira ocorrência (`fold=0`). Horário
    inexistente (primavera) avança minuto a minuto até o primeiro instante
    válido após a falha — nunca dispara no "buraco" do relógio.
    """
    zona = _fuso(fuso)
    ingenua = datetime.combine(dia, hora)
    candidata = ingenua.replace(tzinfo=zona, fold=0)
    ida = candidata.astimezone(timezone.utc).astimezone(zona)
    while ida.replace(tzinfo=None) != ingenua:
        ingenua += timedelta(minutes=1)
        candidata = ingenua.replace(tzinfo=zona, fold=0)
        ida = candidata.astimezone(timezone.utc).astimezone(zona)
    return candidata.astimezone(timezone.utc)


def proxima_ocorrencia(rotina: dict, agora: datetime | None = None) -> datetime | None:
    """Próxima ocorrência futura, calculada no horário local da rotina."""
    agora = agora or datetime.now(timezone.utc)
    fuso = rotina.get('fuso') or fuso_padrao()
    local = agora.astimezone(_fuso(fuso))
    hora = time.fromisoformat(rotina['hora'])
    tipo = rotina.get('repeticao') or 'unica'
    if tipo == 'unica':
        dia = date.fromisoformat(rotina['data']) if rotina.get('data') else local.date()
        candidata = resolver_hora(dia, hora, fuso)
        return candidata if candidata > agora else None
    if tipo == 'intervalo':
        try:
            minutos = int(rotina.get('intervalo_minutos') or 0)
        except (TypeError, ValueError):
            return None
        if minutos <= 0:
            return None
        if not rotina.get('data'):
            return None
        ancora = resolver_hora(date.fromisoformat(rotina['data']), hora, fuso)
        if ancora <= agora:
            decorridos = (agora - ancora).total_seconds() // 60
            saltos = int(decorridos // minutos) + 1
            ancora += timedelta(minutes=minutos * saltos)
        return ancora if ancora > agora else None
    if tipo == 'semanal':
        if not rotina.get('data'):
            return None
        alvo = date.fromisoformat(rotina['data']).weekday()
        dia = local.date()
        for _ in range(10):
            if dia.weekday() == alvo:
                candidata = resolver_hora(dia, hora, fuso)
                if candidata > agora:
                    return candidata
            dia += timedelta(days=1)
        return None
    if tipo == 'mensal':
        if not rotina.get('data'):
            return None
        dia_alvo = date.fromisoformat(rotina['data']).day
        ano, mes = local.year, local.month
        for _ in range(14):
            ultimo = monthrange(ano, mes)[1]
            candidata = resolver_hora(date(ano, mes, min(dia_alvo, ultimo)), hora, fuso)
            if candidata > agora:
                return candidata
            mes += 1
            if mes > 12:
                ano, mes = ano + 1, 1
        return None
    dia = local.date()
    for _ in range(10):
        if tipo == 'dias_uteis' and dia.weekday() > 4:
            dia += timedelta(days=1)
            continue
        candidata = resolver_hora(dia, hora, fuso)
        if candidata > agora:
            return candidata
        dia += timedelta(days=1)
    return None


class ArmazemRotinas:
    """CRUD de rotinas e reserva atômica de execuções."""

    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else caminho_padrao()
        self._trava = threading.RLock()
        self._bloqueios: dict[str, threading.Lock] = {}
        with self._conectar() as conexao:
            pass

    def _conectar(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conexao = sqlite3.connect(str(self.db_path), timeout=10)
        conexao.row_factory = sqlite3.Row
        conexao.execute('PRAGMA journal_mode=WAL')
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS rotinas (
                id TEXT PRIMARY KEY,
                titulo TEXT NOT NULL,
                mensagem TEXT NOT NULL,
                acao TEXT NOT NULL DEFAULT 'lembrete',
                estado TEXT NOT NULL DEFAULT 'ativo',
                repeticao TEXT NOT NULL DEFAULT 'unica',
                data TEXT,
                intervalo_minutos INTEGER,
                hora TEXT NOT NULL,
                fuso TEXT NOT NULL,
                proxima_execucao TEXT,
                ultima_execucao TEXT,
                criada_em TEXT NOT NULL,
                atualizada_em TEXT NOT NULL
            )""")
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS execucoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rotina_id TEXT NOT NULL,
                ocorrencia TEXT NOT NULL,
                origem TEXT NOT NULL,
                iniciada_em TEXT NOT NULL,
                finalizada_em TEXT,
                resultado TEXT NOT NULL DEFAULT 'em_execucao',
                erro TEXT NOT NULL DEFAULT '',
                UNIQUE(rotina_id, ocorrencia, origem)
            )""")
        conexao.execute('CREATE INDEX IF NOT EXISTS execucoes_rotina ON execucoes(rotina_id, id)')
        colunas = {linha[1] for linha in conexao.execute('PRAGMA table_info(rotinas)')}
        if 'acao' not in colunas:
            conexao.execute(
                "ALTER TABLE rotinas ADD COLUMN acao TEXT NOT NULL DEFAULT 'lembrete'")
        if 'intervalo_minutos' not in colunas:
            conexao.execute('ALTER TABLE rotinas ADD COLUMN intervalo_minutos INTEGER')
        return conexao

    @staticmethod
    def _linha(row) -> dict:
        return dict(row) if row is not None else {}

    # ── CRUD ────────────────────────────────────────────────────────────────
    def listar(self, estado: str | None = None) -> list[dict]:
        with self._trava, self._conectar() as conexao:
            if estado:
                linhas = conexao.execute(
                    'SELECT * FROM rotinas WHERE estado=? ORDER BY criada_em',
                    (estado,)).fetchall()
            else:
                linhas = conexao.execute(
                    'SELECT * FROM rotinas ORDER BY criada_em').fetchall()
        return [self._linha(l) for l in linhas]

    def obter(self, rotina_id: str) -> dict | None:
        with self._trava, self._conectar() as conexao:
            linha = conexao.execute(
                'SELECT * FROM rotinas WHERE id=?', (rotina_id,)).fetchone()
        return self._linha(linha) or None

    def criar(self, dados: dict) -> dict:
        agora = _iso(datetime.now(timezone.utc))
        rotina = {
            'id': str(dados.get('id') or uuid.uuid4().hex[:12]),
            'titulo': str(dados.get('titulo') or 'Rotina').strip()[:120],
            'mensagem': str(dados.get('mensagem') or '').strip()[:500],
            'acao': dados.get('acao') if dados.get('acao') in ACOES else 'lembrete',
            'estado': 'ativo',
            'repeticao': dados.get('repeticao') if dados.get('repeticao') in TIPOS else 'unica',
            'data': str(dados.get('data') or '') or None,
            'intervalo_minutos': None,
            'hora': str(dados.get('hora') or '09:00'),
            'fuso': str(dados.get('fuso') or fuso_padrao()),
            'criada_em': agora,
            'atualizada_em': agora,
        }
        if rotina['repeticao'] == 'intervalo':
            try:
                minutos = int(dados.get('intervalo_minutos') or 0)
            except (TypeError, ValueError):
                minutos = 0
            rotina['intervalo_minutos'] = minutos if minutos > 0 else None
        rotina['proxima_execucao'] = (
            _iso(proxima_ocorrencia(rotina)) if rotina['estado'] == 'ativo' else None)
        with self._trava, self._conectar() as conexao:
            conexao.execute("""
                INSERT INTO rotinas
                (id, titulo, mensagem, acao, estado, repeticao, data, intervalo_minutos,
                 hora, fuso, proxima_execucao, ultima_execucao, criada_em, atualizada_em)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL,?,?)""",
                (rotina['id'], rotina['titulo'], rotina['mensagem'], rotina['acao'],
                 rotina['estado'], rotina['repeticao'], rotina['data'],
                 rotina['intervalo_minutos'], rotina['hora'], rotina['fuso'],
                 rotina['proxima_execucao'], rotina['criada_em'], rotina['atualizada_em']))
        return rotina

    def atualizar(self, rotina_id: str, mudancas: dict) -> dict | None:
        with self._trava:
            atual = self.obter(rotina_id)
            if not atual:
                return None
            atual.update({k: v for k, v in mudancas.items()
                          if k in ('titulo', 'mensagem', 'acao', 'repeticao',
                                   'data', 'hora', 'fuso', 'intervalo_minutos')})
            if atual['repeticao'] == 'intervalo':
                try:
                    minutos = int(atual.get('intervalo_minutos') or 0)
                except (TypeError, ValueError):
                    minutos = 0
                atual['intervalo_minutos'] = minutos if minutos > 0 else None
            if atual['repeticao'] == 'unica' and not atual.get('data'):
                atual['data'] = date.today().isoformat()
            atual['atualizada_em'] = _iso(datetime.now(timezone.utc))
            if atual['estado'] == 'ativo':
                proxima = proxima_ocorrencia(atual)
                atual['proxima_execucao'] = _iso(proxima) if proxima else None
            with self._conectar() as conexao:
                conexao.execute("""
                    UPDATE rotinas SET titulo=?, mensagem=?, acao=?, repeticao=?, data=?,
                    intervalo_minutos=?, hora=?, fuso=?, proxima_execucao=?,
                    atualizada_em=? WHERE id=?""",
                    (atual['titulo'], atual['mensagem'], atual.get('acao', 'lembrete'),
                     atual['repeticao'], atual['data'], atual.get('intervalo_minutos'),
                     atual['hora'], atual['fuso'], atual['proxima_execucao'],
                     atual['atualizada_em'], rotina_id))
        return atual

    def pausar(self, rotina_id: str) -> bool:
        return self._mudar_estado(rotina_id, 'pausado')

    def reativar(self, rotina_id: str) -> bool:
        return self._mudar_estado(rotina_id, 'ativo')

    def _mudar_estado(self, rotina_id: str, estado: str) -> bool:
        with self._trava:
            atual = self.obter(rotina_id)
            if not atual:
                return False
            agora = datetime.now(timezone.utc)
            proxima = (_iso(proxima_ocorrencia(atual, agora))
                       if estado == 'ativo' else None)
            with self._conectar() as conexao:
                conexao.execute("""
                    UPDATE rotinas SET estado=?, proxima_execucao=?, atualizada_em=?
                    WHERE id=?""", (estado, proxima, _iso(agora), rotina_id))
        return True

    def remover(self, rotina_id: str) -> bool:
        with self._trava, self._conectar() as conexao:
            cursor = conexao.execute('DELETE FROM rotinas WHERE id=?', (rotina_id,))
            return cursor.rowcount > 0

    def avancar(self, rotina_id: str, agora: datetime | None = None) -> None:
        """Recalcula a próxima ocorrência após uma execução concluída."""
        with self._trava:
            rotina = self.obter(rotina_id)
            if not rotina or rotina['estado'] != 'ativo':
                return
            proxima = proxima_ocorrencia(rotina, agora or datetime.now(timezone.utc))
            with self._conectar() as conexao:
                conexao.execute(
                    'UPDATE rotinas SET proxima_execucao=? WHERE id=?',
                    (_iso(proxima) if proxima else None, rotina_id))

    # ── agendamento e execução ──────────────────────────────────────────────
    def proximas(self, agora: datetime | None = None) -> list[dict]:
        limite = _iso(agora or datetime.now(timezone.utc))
        with self._trava, self._conectar() as conexao:
            linhas = conexao.execute("""
                SELECT * FROM rotinas WHERE estado='ativo'
                AND proxima_execucao IS NOT NULL AND proxima_execucao<=?
                ORDER BY proxima_execucao""", (limite,)).fetchall()
        return [self._linha(l) for l in linhas]

    def proxima_programada(self) -> datetime | None:
        with self._trava, self._conectar() as conexao:
            linha = conexao.execute("""
                SELECT MIN(proxima_execucao) AS proxima FROM rotinas
                WHERE estado='ativo' AND proxima_execucao IS NOT NULL""").fetchone()
        return _de_iso(linha['proxima']) if linha and linha['proxima'] else None

    def bloqueio(self, rotina_id: str) -> threading.Lock:
        with self._trava:
            return self._bloqueios.setdefault(rotina_id, threading.Lock())

    def reservar(self, rotina_id: str, ocorrencia: str,
                 origem: str = 'agendada') -> int | None:
        """Reserva atômica: devolve o id do log ou None se já reservada."""
        with self._trava, self._conectar() as conexao:
            try:
                cursor = conexao.execute("""
                    INSERT INTO execucoes
                    (rotina_id, ocorrencia, origem, iniciada_em)
                    VALUES (?,?,?,?)""",
                    (rotina_id, ocorrencia, origem,
                     _iso(datetime.now(timezone.utc))))
            except sqlite3.IntegrityError:
                return None
            return int(cursor.lastrowid)

    def finalizar(self, log_id: int, ok: bool, erro: str = '') -> None:
        with self._trava, self._conectar() as conexao:
            conexao.execute("""
                UPDATE execucoes SET finalizada_em=?, resultado=?, erro=?
                WHERE id=? AND finalizada_em IS NULL""",
                (_iso(datetime.now(timezone.utc)),
                 'ok' if ok else 'falha', str(erro)[:240], log_id))
            linha = conexao.execute(
                'SELECT rotina_id FROM execucoes WHERE id=?', (log_id,)).fetchone()
            if linha:
                conexao.execute(
                    'UPDATE rotinas SET ultima_execucao=? WHERE id=?',
                    (_iso(datetime.now(timezone.utc)), linha[0]))
                total = conexao.execute(
                    'SELECT COUNT(*) FROM execucoes WHERE rotina_id=?',
                    (linha[0],)).fetchone()[0]
                if total > LIMITE_HISTORICO:
                    conexao.execute("""
                        DELETE FROM execucoes WHERE rotina_id=? AND id IN (
                          SELECT id FROM execucoes WHERE rotina_id=?
                          ORDER BY id LIMIT ?)""",
                        (linha[0], linha[0], total - LIMITE_HISTORICO))

    def historico(self, rotina_id: str, limite: int = 10) -> list[dict]:
        with self._trava, self._conectar() as conexao:
            linhas = conexao.execute("""
                SELECT * FROM execucoes WHERE rotina_id=?
                ORDER BY id DESC LIMIT ?""", (rotina_id, max(1, min(int(limite), 100)))).fetchall()
        return [self._linha(l) for l in linhas]

    def recuperar(self, agora: datetime | None = None) -> list[dict]:
        """Marca interrompidas e consolida atrasos sem disparo em massa."""
        agora = agora or datetime.now(timezone.utc)
        atrasadas = []
        with self._trava, self._conectar() as conexao:
            conexao.execute("""
                UPDATE execucoes SET finalizada_em=?, resultado='interrompida',
                erro='Execução interrompida; use executar agora.'
                WHERE finalizada_em IS NULL""", (_iso(agora),))
            for rotina in self.listar('ativo'):
                proxima = _de_iso(rotina.get('proxima_execucao'))
                if proxima is None or proxima > agora:
                    continue
                # Vários horários perdidos: só a ocorrência mais recente.
                ocorrencia = proxima.isoformat()
                try:
                    cursor = conexao.execute("""
                        INSERT INTO execucoes
                        (rotina_id, ocorrencia, origem, iniciada_em,
                         finalizada_em, resultado, erro)
                        VALUES (?,?,?,?,?,'atrasada',?)""",
                        (rotina['id'], ocorrencia, 'agendada', _iso(agora),
                         _iso(agora),
                         'Ocorrência perdida enquanto a NIA estava fechada; '
                         'apenas a mais recente foi registrada.'))
                    if cursor.rowcount:
                        atrasadas.append(rotina['id'])
                except sqlite3.IntegrityError:
                    pass  # já registrada/reservada: não notifica duas vezes
                proxima_futura = proxima_ocorrencia(rotina, agora)
                conexao.execute(
                    'UPDATE rotinas SET proxima_execucao=? WHERE id=?',
                    (_iso(proxima_futura) if proxima_futura else None, rotina['id']))
        return atrasadas


class Agendador:
    """Despertador único por processo: sem sondagem e sem serviço extra."""

    def __init__(self, armazem=None, notificador=None, db_path=None):
        self.armazem = armazem or ArmazemRotinas(db_path=db_path)
        self._notificador = notificador
        self.ao_resumo = None
        self.resumo_leitura_automatica = self._leitura_automatica_padrao
        self._evento = threading.Event()
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self._trava = threading.Lock()

    def definir_notificador(self, notificador) -> None:
        """Troca o canal de avisos sem recriar o agendador nem o armazem."""
        if notificador is not None and not callable(notificador):
            raise TypeError('Notificador deve ser chamável.')
        with self._trava:
            self._notificador = notificador

    @staticmethod
    def _leitura_automatica_padrao() -> bool:
        try:
            from core import resumo_dia  # noqa: PLC0415
            return resumo_dia.leitura_automatica()
        except Exception:
            return False

    def iniciar(self) -> None:
        with self._trava:
            if self._thread is not None and self._thread.is_alive():
                return
            self._parar.clear()
            try:
                self.armazem.recuperar()
            except Exception:
                pass
            self._thread = threading.Thread(
                target=self._laco, daemon=True, name='nia-rotinas')
            self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        self._evento.set()

    def recalcular(self) -> None:
        self._evento.set()

    def _gerar_resumo(self) -> tuple[bool, str]:
        try:
            from core import resumo_dia  # noqa: PLC0415
            resultado = resumo_dia.gerar_e_salvar()
        except Exception as exc:
            return False, type(exc).__name__
        if not resultado.get('ok'):
            return False, 'geracao'
        if self.ao_resumo is not None and self.resumo_leitura_automatica():
            try:
                self.ao_resumo(str(resultado.get('texto') or ''))
            except Exception:
                pass  # texto permanece no card mesmo se a voz falhar
        return True, ''

    def _notificar(self, mensagem: str) -> tuple[bool, str]:
        try:
            if self._notificador is not None:
                return bool(self._notificador(mensagem)), ''
            from actions.reminder import notificar  # noqa: PLC0415
            return bool(notificar(mensagem)), ''
        except Exception as exc:
            return False, type(exc).__name__

    def _laco(self) -> None:
        while not self._parar.is_set():
            try:
                agora = datetime.now(timezone.utc)
                devidas = self.armazem.proximas(agora)
                if not devidas:
                    proxima = self.armazem.proxima_programada()
                    espera = 3600.0
                    if proxima is not None:
                        espera = max(0.1, (proxima - datetime.now(timezone.utc))
                                     .total_seconds())
                    self._evento.wait(min(espera, 3600))
                    self._evento.clear()
                    continue
                if self._parar.is_set():
                    break
                for rotina in self.armazem.proximas():
                    with self.armazem.bloqueio(rotina['id']):
                        atual = self.armazem.obter(rotina['id'])
                        if not atual or atual['estado'] != 'ativo':
                            continue
                        ocorrencia = atual['proxima_execucao']
                        if not ocorrencia:
                            continue
                        log = self.armazem.reservar(
                            rotina['id'], ocorrencia, 'agendada')
                        if log is None:
                            continue  # já executada/reservada: não repete
                        if atual.get('acao') == 'resumo':
                            ok, erro = self._gerar_resumo()
                        else:
                            ok, erro = self._notificar(atual['mensagem'])
                        self.armazem.finalizar(log, ok, erro)
                        self.armazem.avancar(rotina['id'])
            except Exception:
                # O agendador nunca pode derrubar a NIA: tenta de novo no
                # próximo ciclo, sem varredura frequente.
                self._evento.wait(60)
                self._evento.clear()


_AGENDADOR: Agendador | None = None


def agendador_global() -> Agendador:
    global _AGENDADOR
    if _AGENDADOR is None:
        _AGENDADOR = Agendador()
    return _AGENDADOR
