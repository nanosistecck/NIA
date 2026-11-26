# -*- coding: utf-8 -*-
"""Ambiente isolado do laboratório: perfil temporário e efeitos simulados."""
from __future__ import annotations

import os
import tempfile
import threading
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import main
from actions import relogio_falado as RF
from core import agenda as AG
from core import planos as PL
from core import resumo_dia as RD
from memory import memory_manager as MM


class LabEnvironment:
    """Contexto com diretório temporário e nenhum efeito real."""

    def __init__(self):
        self.temporario = tempfile.TemporaryDirectory(prefix='nia-lab-')
        self.raiz = Path(self.temporario.name)
        self._stack = ExitStack()
        self.observado: list[str] = []
        self.respostas: list[str] = []
        self.argumentos: list[dict] = []

    def __enter__(self):
        for chave in ('NIA_PLANOS_DIR', 'NIA_AGENDA', 'NIA_PERFIL',
                      'NIA_ROTINAS_DB', 'HOME'):
            self._stack.enter_context(patch.dict(os.environ, {chave: str(self.raiz / chave)}))
        self._stack.enter_context(patch.object(main.Path, 'home',
                                               classmethod(lambda cls: self.raiz)))
        self._stack.enter_context(patch.dict(os.environ, {'NIA_MODO_LIVRE': '1'}))

        def registrar(nome, retorno='ok'):
            def _fn(*args, **kwargs):
                self.observado.append(nome)
                self.argumentos.append({'args': args, 'kwargs': kwargs})
                return retorno
            return _fn

        alvos = (
            (main, 'get_system_status', registrar('system_status', 'status ok')),
            (main, 'weather_action', registrar('weather_report', 'previsao ok')),
            (main, 'web_search_action', registrar('web_search', 'resultados')),
            (main, 'open_app', registrar('open_app', 'aberto')),
            (main, 'file_controller', registrar('file_controller', 'ok')),
            (main, 'reminder', registrar('reminder', 'lembrete ok')),
            (AG, 'criar', registrar('agenda_criar', {'id': 'lab'})),
            (AG, 'editar', registrar('agenda_editar', {'id': 'lab'})),
            (AG, 'excluir', registrar('agenda_excluir', True)),
            (AG, 'concluir', registrar('agenda_concluir', True)),
            (PL, 'criar', registrar('plano_criar', {'id': 'lab'})),
            (PL, 'arquivar', registrar('plano_arquivar', True)),
            (PL, 'excluir_permanentemente', registrar('plano_excluir', True)),
            (RF, 'agora_falado', registrar('hora_agora', {'falar_assim': 'São 10h'})),
            (RD, 'gerar_e_salvar', registrar('resumo_dia', {'ok': True})),
            (MM, 'update_memory', registrar('save_memory', True)),
            (main, 'update_memory', registrar('save_memory', True)),
        )
        for modulo, nome, funcao in alvos:
            if hasattr(modulo, nome):
                self._stack.enter_context(patch.object(modulo, nome, funcao))

        laboratorio = self

        def registrar_metodo(rotulo, retorno=True):
            def _fn(_instancia, *args, **kwargs):
                laboratorio.observado.append(rotulo)
                laboratorio.argumentos.append({'args': args, 'kwargs': kwargs})
                return retorno
            return _fn

        # Chamado no fim de praticamente toda frase; não é sinal de intenção.
        self._stack.enter_context(
            patch.object(main.NiaLive, '_buscar_arquivos_local',
                         lambda self, texto, origem='texto': False))
        laboratorio = self

        def falar_local(_self, texto, *args, **kwargs):
            laboratorio.respostas.append(str(texto))
            return True

        self._stack.enter_context(
            patch.object(main.NiaLive, '_falar_local', falar_local))

        def falar(texto, origem='chat'):
            self.respostas.append(str(texto))

        self._stack.enter_context(
            patch.object(main.NiaLive, '_falar_resposta_comando', falar))
        self._stack.enter_context(
            patch.object(main.NiaLive, 'speak', lambda self, texto: falar(texto)))
        return self

    def __exit__(self, *exc):
        self._stack.close()
        self.temporario.cleanup()

    def motor(self):
        obj = object.__new__(main.NiaLive)
        obj.ui = SimpleNamespace(
            write_log=Mock(), set_state=Mock(), muted=True,
            solicitar_permissao=Mock(side_effect=AssertionError('lab não deve pedir permissão')),
            fechar_permissao=Mock(), show_content=Mock(), current_file='')
        obj._current_input_transcript = ''
        obj._ultima_fala_do_dono = ''
        obj._pending_manual_save_destination = ''
        obj._pending_manual_save_extension = ''
        obj._ferramenta_atual = None
        obj._brief_lock = threading.Lock()
        obj._brief_token = 0
        obj._turno_seq = 0
        obj._interrupted = False
        obj._speaking_lock = threading.Lock()
        obj._loop = None
        obj._pendente_sintese = None
        obj._last_user_speech = 0.0
        obj._modo_local = True
        obj._cerebro = 'openrouter'
        obj._openrouter = None
        obj._buf_local = []
        obj._pre_local = []
        from core.contexto_ferramentas import ContextoFerramentas
        obj._contexto_ferramentas = ContextoFerramentas()
        obj._usando_pc = False
        obj._parar_pc = False
        obj._pergunta_pendente = False
        obj._pergunta_sim_nao = False
        obj._resposta_do_dono = None
        obj._so_com_nome = False
        obj._acordado_ate = 0.0
        obj._pending_delete_args = None
        obj._pending_delete_label = ''
        obj._pending_literal_confirmation = ''
        obj._vision_busy = False
        obj._vision_last_time = 0.0
        obj._sys_monitor = None
        obj._pc_liberado_ate = 0.0
        obj._esperando_tarefa_pc_ate = 0.0
        obj._tentativas_tarefa_pc = 0
        obj._correcoes_pc = []
        obj._parou_pc_em = 0.0
        return obj
