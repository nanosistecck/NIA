# -*- coding: utf-8 -*-
"""Sessão única de controle do computador.

Este módulo é o portão que o motor de desktop e o overlay compartilham. Ele não
importa PyQt6, não desenha nada e não executa ações: apenas mantém o estado
(IDLE → STARTING → ACTIVE → PAUSED → STOPPING → IDLE), publica eventos tipados
e responde se uma ação pode ou não acontecer.

Regra de ouro: nenhuma ação de mouse/teclado começa antes de o indicador ser
apresentado. Quem chama `iniciar()` recebe um token; sem apresentação
confirmada, a exceção `ControleIndisponivel` impede o trabalho.
"""
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
import os
import re
import sys
import threading
import time
import unicodedata
import uuid

__all__ = [
    'ControleIndisponivel',
    'EstadoControle',
    'EventoControle',
    'SessaoControle',
    'TokenControle',
    'controle_de_tela',
    'em_sessao',
    'sessao',
]


class EstadoControle(str, Enum):
    IDLE = 'IDLE'
    STARTING = 'STARTING'
    ACTIVE = 'ACTIVE'
    WAITING = 'WAITING'
    PAUSING = 'PAUSING'
    PAUSED = 'PAUSED'
    STOPPING = 'STOPPING'
    FAILED = 'FAILED'


class ControleIndisponivel(RuntimeError):
    """O indicador não apareceu; a ação de desktop deve ser recusada."""


@dataclass(frozen=True)
class EventoControle:
    tipo: str
    sessao_id: str
    sequencia: int
    quando: float
    estado: str
    descricao: str = ''
    status: str = ''


@dataclass(frozen=True)
class TokenControle:
    sessao_id: str
    geracao: int
    aninhado: bool = False


_RE_SEGREDO = re.compile(
    r'(?i)\b(senha|password|passwd|token|chave|api[_-]?key|cartao|cvv)\b'
    r'\s*[:=]?\s*\S+')
_RE_CONTROLE = re.compile(r'[\x00-\x1f\x7f]')


def sanitizar(texto, limite: int = 90) -> str:
    """Remove quebras/controle, credenciais aparentes e corta o tamanho."""
    valor = unicodedata.normalize('NFKC', str(texto or ''))
    valor = _RE_CONTROLE.sub(' ', valor)
    valor = _RE_SEGREDO.sub(lambda m: m.group(1) + ': ***', valor)
    valor = re.sub(r'\s+', ' ', valor).strip()
    return valor[:max(1, int(limite))]


def ambiente_sem_interface() -> bool:
    """True quando não existe uma tela real para apresentar o overlay.

    Usado apenas por testes automatizados/headless. No aplicativo normal o
    apresentador é registrado e a ausência dele bloqueia a ação.
    """
    if os.environ.get('NIA_OVERLAY_SIMULADO', '').strip().lower() in (
            '1', 'true', 'sim', 'on', 'yes'):
        return True
    if os.environ.get('QT_QPA_PLATFORM', '').strip().lower() == 'offscreen':
        return True
    return 'pytest' in sys.modules


class SessaoControle:
    """Estado compartilhado entre o motor, a interface e o SDK."""

    def __init__(self, relogio=None, id_factory=None):
        self._trava = threading.RLock()
        self._cond = threading.Condition(self._trava)
        self._relogio = relogio if callable(relogio) else time.monotonic
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex[:12])
        self._estado = EstadoControle.IDLE
        self._sessao_id = ''
        self._geracao = 0
        self._sequencia = 0
        self._owners = 0
        self._motivo = ''
        self._cancelar = threading.Event()
        self._pausado = threading.Event()
        self._suspenso = False
        self._simulado = False
        self._eventos: deque[EventoControle] = deque(maxlen=64)
        self._atividades: deque[dict] = deque(maxlen=3)
        self._ouvintes: list = []
        self._apresentador = None
        self._ao_parar = None
        self._freio = None

    # ── leitura ─────────────────────────────────────────────────────────────
    @property
    def estado(self) -> EstadoControle:
        with self._trava:
            return self._estado

    @property
    def sessao_id(self) -> str:
        with self._trava:
            return self._sessao_id

    @property
    def sequencia(self) -> int:
        with self._trava:
            return self._sequencia

    @property
    def simulado(self) -> bool:
        with self._trava:
            return self._simulado

    @property
    def atividades(self) -> tuple[dict, ...]:
        with self._trava:
            return tuple(dict(item) for item in self._atividades)

    @property
    def eventos(self) -> tuple[EventoControle, ...]:
        with self._trava:
            return tuple(self._eventos)

    def ativo(self) -> bool:
        return self.estado in (EstadoControle.ACTIVE, EstadoControle.PAUSED,
                               EstadoControle.WAITING, EstadoControle.PAUSING)

    def permitido(self) -> bool:
        """Gate consultado antes de CADA ação de mouse/teclado."""
        with self._trava:
            return (self._estado is EstadoControle.ACTIVE
                    and not self._cancelar.is_set()
                    and not self._pausado.is_set()
                    and not self._suspenso)

    def parada_solicitada(self) -> bool:
        with self._trava:
            return (self._cancelar.is_set()
                    or self._estado in (EstadoControle.STOPPING,
                                        EstadoControle.FAILED))

    # ── observadores ────────────────────────────────────────────────────────
    def registrar_ouvinte(self, funcao) -> None:
        if not callable(funcao):
            raise TypeError('Ouvinte inválido.')
        with self._trava:
            if funcao not in self._ouvintes:
                self._ouvintes.append(funcao)

    def remover_ouvinte(self, funcao) -> None:
        with self._trava:
            try:
                self._ouvintes.remove(funcao)
            except ValueError:
                pass

    def registrar_apresentador(self, funcao) -> None:
        """A interface registra aqui a função que mostra e confirma o overlay."""
        if not callable(funcao):
            raise TypeError('Apresentador inválido.')
        with self._trava:
            self._apresentador = funcao

    def remover_apresentador(self, funcao=None) -> None:
        with self._trava:
            if funcao is None or self._apresentador is funcao:
                self._apresentador = None

    # ── ciclo de vida ───────────────────────────────────────────────────────
    def iniciar(self, motivo: str = 'controle', *, obrigatorio: bool = True,
                timeout: float = 3.0, ao_parar=None,
                monitorar_esc: bool = True,
                simulado: bool | None = None) -> TokenControle:
        """Abre (ou reutiliza) a sessão e só volta depois do overlay aparecer."""
        with self._cond:
            if self._estado in (EstadoControle.ACTIVE, EstadoControle.PAUSED,
                                EstadoControle.WAITING, EstadoControle.PAUSING):
                self._owners += 1
                token = TokenControle(self._sessao_id, self._geracao, True)
                self._emitir('reutilizada', f'controle compartilhado ({self._owners})')
                return token
            if self._estado is EstadoControle.STARTING:
                limite = self._relogio() + max(0.1, float(timeout))
                while (self._estado is EstadoControle.STARTING
                       and self._relogio() < limite):
                    self._cond.wait(0.05)
                if self._estado in (EstadoControle.ACTIVE, EstadoControle.PAUSED,
                                    EstadoControle.WAITING):
                    self._owners += 1
                    return TokenControle(self._sessao_id, self._geracao, True)
                raise ControleIndisponivel(
                    'outra sessão de controle não confirmou o indicador')

            self._geracao += 1
            self._sessao_id = str(self._id_factory())
            self._estado = EstadoControle.STARTING
            self._owners = 1
            self._motivo = sanitizar(motivo, 80)
            self._cancelar.clear()
            self._pausado.clear()
            self._suspenso = False
            self._atividades.clear()
            self._ao_parar = ao_parar
            self._simulado = bool(ambiente_sem_interface() if simulado is None
                                  else simulado)
            self._emitir('iniciando', self._motivo)

        apresentado = self._apresentar(max(0.2, float(timeout)))
        if not apresentado:
            with self._cond:
                self._estado = EstadoControle.FAILED
                self._owners = 0
                self._emitir('falha', 'o indicador não foi apresentado')
            raise ControleIndisponivel(
                'o indicador de controle não apareceu; nenhuma ação foi executada')

        with self._cond:
            if self._estado is not EstadoControle.STARTING:
                self._owners = max(0, self._owners - 1)
                raise ControleIndisponivel('sessão cancelada durante a abertura')
            self._estado = EstadoControle.ACTIVE
            self._emitir('ativo', self._motivo)

        if monitorar_esc:
            self._ligar_freio()
        return TokenControle(self._sessao_id, self._geracao, False)

    def encerrar(self, token: TokenControle | None = None,
                 motivo: str = 'concluido') -> None:
        """Libera o token; o overlay só some depois do último dono."""
        with self._cond:
            if token is not None and token.sessao_id != self._sessao_id:
                return
            if self._estado in (EstadoControle.IDLE, EstadoControle.FAILED):
                return
            if self._owners > 1:
                self._owners -= 1
                self._emitir('liberada', f'restam {self._owners} donos')
                return
            self._owners = 0
            self._estado = EstadoControle.STOPPING
            self._emitir('encerrando', sanitizar(motivo, 80))
            simulado = self._simulado

        self._desligar_freio()
        if simulado or self._apresentador is None:
            self._finalizar_encerramento()
            return
        # A interface confirma o fim do fade; o prazo evita ficar preso se ela
        # morrer no meio do encerramento.
        threading.Timer(1.2, self._finalizar_encerramento).start()

    def _finalizar_encerramento(self) -> None:
        with self._cond:
            if self._estado is not EstadoControle.STOPPING:
                return
            self._estado = EstadoControle.IDLE
            self._emitir('encerrado', 'recursos liberados')
            self._sessao_id = ''
            self._atividades.clear()

    def confirmar_encerramento(self) -> None:
        """Chamado pelo overlay depois do fade de saída."""
        self._finalizar_encerramento()

    # ── pausa / retomada / parada ───────────────────────────────────────────
    def pausar(self, motivo: str = 'pedido do usuário') -> bool:
        with self._cond:
            if self._estado is not EstadoControle.ACTIVE:
                return False
            self._estado = EstadoControle.PAUSING
            self._emitir('pausando', sanitizar(motivo, 80))
            simulado = self._simulado or self._apresentador is None
        if simulado:
            self.confirmar_pausa()
        return True

    def confirmar_pausa(self) -> None:
        with self._cond:
            if self._estado is not EstadoControle.PAUSING:
                return
            self._pausado.set()
            self._estado = EstadoControle.PAUSED
            self._emitir('pausado', 'novas ações bloqueadas')

    def retomar(self, motivo: str = 'pedido do usuário') -> bool:
        with self._cond:
            if self._estado is not EstadoControle.PAUSED:
                return False
            self._pausado.clear()
            self._suspenso = False
            self._estado = EstadoControle.ACTIVE
            self._emitir('retomado', sanitizar(motivo, 80))
            return True

    def suspender(self, motivo: str = 'ambiente inseguro') -> bool:
        """Pausa com motivo técnico (monitor removido, UAC, overlay perdido)."""
        with self._cond:
            if self._estado not in (EstadoControle.ACTIVE,
                                    EstadoControle.PAUSED,
                                    EstadoControle.PAUSING):
                return False
            self._pausado.set()
            self._suspenso = True
            self._estado = EstadoControle.PAUSED
            self._emitir('suspenso', sanitizar(motivo, 80))
            return True

    def solicitar_parada(self, motivo: str = 'pedido do usuário') -> bool:
        """ESC/botão: fecha o gate imediatamente e avisa quem estiver no laço."""
        with self._cond:
            if self._estado in (EstadoControle.IDLE, EstadoControle.FAILED):
                return False
            self._cancelar.set()
            self._pausado.clear()
            self._emitir('parada', sanitizar(motivo, 80))
            callback = self._ao_parar
        if callable(callback):
            threading.Thread(target=self._chamar_parada, args=(callback,),
                             daemon=True, name='controle-parada').start()
        return True

    @staticmethod
    def _chamar_parada(callback) -> None:
        try:
            callback()
        except Exception:
            pass

    def falhar(self, motivo: str = 'falha do indicador') -> None:
        with self._cond:
            if self._estado in (EstadoControle.IDLE, EstadoControle.FAILED):
                return
            self._cancelar.set()
            self._estado = EstadoControle.FAILED
            self._emitir('falha', sanitizar(motivo, 80))
        self._desligar_freio()

    # ── atividades ──────────────────────────────────────────────────────────
    def registrar_atividade(self, descricao: str,
                            status: str = 'executando') -> None:
        with self._cond:
            if self._estado in (EstadoControle.IDLE, EstadoControle.FAILED):
                return
            item = {'descricao': sanitizar(descricao, 90),
                    'status': sanitizar(status, 20),
                    'quando': self._relogio()}
            self._atividades.append(item)
            self._emitir('atividade', item['descricao'], status=item['status'])

    def marcar_ultima(self, status: str) -> None:
        """Atualiza o estado da última atividade (concluida/erro/teclado)."""
        with self._cond:
            if not self._atividades:
                return
            item = dict(self._atividades[-1])
            item['status'] = sanitizar(status, 20)
            self._atividades[-1] = item
            self._emitir('atividade', item['descricao'], status=item['status'])

    # ── interno ─────────────────────────────────────────────────────────────
    def _apresentar(self, timeout: float) -> bool:
        with self._trava:
            apresentador = self._apresentador
            simulado = self._simulado
        if apresentador is None:
            return bool(simulado)
        try:
            return bool(apresentador(self._sessao_id, timeout))
        except Exception:
            return False

    def _emitir(self, tipo: str, descricao: str = '', status: str = '') -> None:
        with self._trava:
            self._sequencia += 1
            evento = EventoControle(
                tipo=tipo,
                sessao_id=self._sessao_id,
                sequencia=self._sequencia,
                quando=self._relogio(),
                estado=self._estado.value,
                descricao=descricao,
                status=status,
            )
            self._eventos.append(evento)
            ouvintes = tuple(self._ouvintes)
        for ouvinte in ouvintes:
            try:
                ouvinte(evento)
            except Exception:
                pass

    def _ligar_freio(self) -> None:
        try:
            from actions.usar_computador import FreioEsc  # noqa: PLC0415
            freio = FreioEsc(ao_apertar=self._ao_esc)
            freio.ligar()
            self._freio = freio
        except Exception:
            self._freio = None

    def _desligar_freio(self) -> None:
        with self._trava:
            freio, self._freio = self._freio, None
        if freio is not None:
            try:
                freio.parar()
            except Exception:
                pass

    def _ao_esc(self) -> None:
        self.solicitar_parada('ESC')


sessao = SessaoControle()


def em_sessao() -> bool:
    return sessao.ativo()


@contextmanager
def controle_de_tela(motivo: str = 'controle', **opcoes):
    """Contexto reutilizável por ferramentas e plugins.

    Exemplo::

        with controle_de_tela('plugin:minha_acao') as token:
            ...
    """
    token = sessao.iniciar(motivo, **opcoes)
    try:
        yield token
    finally:
        sessao.encerrar(token, motivo)
