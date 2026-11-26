# -*- coding: utf-8 -*-
"""SDK versionado de plugins da NIA (Fase 04).

Contrato mínimo e DTOs serializáveis. Este módulo não importa ``main`` nem
``ui`` e não executa código de plugin durante a validação. O transporte local
é autenticado por token e roda no mesmo processo; nenhum socket é aberto.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hmac
import re

API = 1
VERSAO = '1.0.0'
METODOS = ('initialize', 'get_capabilities', 'execute', 'open_ui',
           'health_check', 'get_status', 'cancel', 'shutdown')


@dataclass(frozen=True)
class Resposta:
    ok: bool
    dados: object = field(default_factory=dict)
    erro: str = ''
    mensagem: str = ''

    def como_dict(self) -> dict:
        return {'ok': bool(self.ok), 'dados': self.dados,
                'erro': self.erro, 'mensagem': self.mensagem}


@dataclass(frozen=True)
class Status:
    estado: str
    detalhes: str = ''

    def como_dict(self) -> dict:
        return {'estado': self.estado, 'detalhes': self.detalhes}


def manifesto_padrao() -> dict:
    return {'api': API, 'versao': VERSAO, 'id': 'plugin_mock',
            'nome': 'Plugin de teste', 'imports': []}


def validar_manifesto(manifesto: dict) -> None:
    if not isinstance(manifesto, dict):
        raise ValueError('Manifesto deve ser um objeto.')
    if type(manifesto.get('api')) is not int or manifesto['api'] != API:
        raise ValueError('Versão de API incompatível.')
    versao = manifesto.get('versao')
    if not isinstance(versao, str) or not re.fullmatch(r'\d+\.\d+\.\d+', versao):
        raise ValueError('Versão de manifesto inválida.')
    imports = manifesto.get('imports', ())
    if not isinstance(imports, (list, tuple)):
        raise ValueError('Imports devem ser uma lista.')
    for nome in imports:
        if not isinstance(nome, str):
            raise ValueError('Import inválido.')
        if nome.split('.', 1)[0] in {'main', 'ui'}:
            raise PermissionError('Plugin não pode importar ' + nome)


def validar_contrato(plugin) -> bool:
    for metodo in METODOS:
        if not callable(getattr(plugin, metodo, None)):
            raise TypeError('Contrato incompleto: falta ' + metodo)
    return True


class MockPlugin:
    """Plugin confiável e determinístico, usado apenas em testes/homologação."""

    def __init__(self):
        self._estado = 'novo'
        self._cancelados: set[str] = set()
        self.falhar_proxima = False

    def initialize(self, configuracao=None):
        self._estado = 'pronto'
        return Resposta(True, {'configuracao': dict(configuracao or {})})

    def get_capabilities(self):
        return Resposta(True, [{
            'id': 'echo', 'nome': 'Eco',
            'descricao': 'Repete o texto informado, sem efeitos externos.',
            'schemas': {
                'entrada': {'type': 'object',
                            'properties': {'texto': {'type': 'STRING'}}},
                'saida': {'type': 'object',
                          'properties': {'texto': {'type': 'STRING'}}},
            },
        }])

    def execute(self, nome, argumentos=None):
        if self.falhar_proxima:
            self.falhar_proxima = False
            return Resposta(False, {}, 'falha_do_plugin', 'Falha simulada pelo mock.')
        if self._estado == 'encerrado':
            return Resposta(False, {}, 'encerrado', 'Plugin encerrado.')
        if nome not in ('eco', 'echo'):
            return Resposta(False, {}, 'desconhecida', 'Capacidade não registrada.')
        return Resposta(True, {'texto': str((argumentos or {}).get('texto', ''))})

    def open_ui(self):
        return Resposta(False, {}, 'sem_interface', 'O mock não tem interface.')

    def health_check(self):
        return Resposta(True, {'saudavel': self._estado != 'encerrado'})

    def get_status(self):
        return Status(self._estado)

    def cancel(self, identificador):
        self._cancelados.add(str(identificador))
        return True

    def shutdown(self):
        self._estado = 'encerrado'
        return True


class TransporteLocal:
    """Ponte autenticada em processo; não abre portas nem aceita código remoto."""

    def __init__(self, token: str, plugin=None):
        if not isinstance(token, str) or len(token) < 8:
            raise ValueError('Token de transporte inválido.')
        self._token = token
        self.plugin = plugin or MockPlugin()

    def chamar(self, metodo: str, argumentos=None, token: str = ''):
        if not isinstance(token, str) or not hmac.compare_digest(token, self._token):
            raise PermissionError('token inválido para transporte local')
        if metodo not in METODOS:
            raise ValueError('Método não faz parte do contrato.')
        argumentos = dict(argumentos or {})
        if metodo == 'initialize':
            resposta = self.plugin.initialize(argumentos)
        elif metodo == 'execute':
            resposta = self.plugin.execute(
                argumentos.get('nome', ''), argumentos.get('argumentos', {}))
        elif metodo == 'cancel':
            resposta = self.plugin.cancel(argumentos.get('id', ''))
        else:
            resposta = getattr(self.plugin, metodo)()
        if isinstance(resposta, Status):
            return Resposta(True, resposta.como_dict())
        if isinstance(resposta, bool):
            return Resposta(resposta)
        if not isinstance(resposta, Resposta):
            return Resposta(False, {}, 'contrato_invalido', 'Retorno fora do contrato.')
        return resposta
