# -*- coding: utf-8 -*-
"""Catálogo único das habilidades nativas da NIA.

Uma única definição por habilidade (identificador estável, nome, descrição,
frase de exemplo e ação) alimenta o dashboard, os atalhos do Canvas, o chat e
a voz. A seleção é local: nenhuma rede, inferência, indexagem ou sondagem
acontece ao carregar o catálogo.

A forma de descrever e descobrir habilidades foi inspirada em
``src/openjarvis/skills/`` (OpenJarvis, revisão 427c2dd, Apache 2.0): um
manifesto por habilidade com nome, descrição e etapas reutilizáveis. Nenhum
código foi copiado; a NIA usa uma estrutura Python simples e executores já
existentes, sem carregar manifestos remotos.
"""
from __future__ import annotations

import contextvars
import re
import threading
import unicodedata
from dataclasses import dataclass
from typing import Callable

# Executor registrado uma única vez pelo ponto de entrada real (main.py).
# Assim dashboard, Canvas, chat e voz chamam exatamente a mesma operação.
_EXECUTOR: Callable[[str, str], tuple[bool, str]] | None = None
_ORIGEM = contextvars.ContextVar('nia_habilidade_origem', default='catalogo')


def definir_origem(origem: str):
    """Marca quem acionou a habilidade (chat, voz, canvas) neste contexto."""
    return _ORIGEM.set(str(origem or 'catalogo'))


def restaurar_origem(token) -> None:
    _ORIGEM.reset(token)


def origem() -> str:
    return _ORIGEM.get()


@dataclass(frozen=True)
class Habilidade:
    id: str
    nome: str
    descricao: str
    exemplo: str
    acao: str
    config: str = ''
    versao: str = '1.0.0'
    api: int = 1
    capacidades: tuple[str, ...] = ()
    permissoes: tuple[str, ...] = ()
    # Campos opcionais do contrato universal (Fase 02). Valores padrão
    # preservam todos os manifestos e chamadas existentes.
    esquema_entrada: dict | None = None
    esquema_saida: dict | None = None
    agendavel: bool = False
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class Disponibilidade:
    pronta: bool
    motivo: str


@dataclass(frozen=True)
class Resultado:
    ok: bool
    mensagem: str
    codigo: str = 'ok'

    def como_tupla(self) -> tuple[bool, str]:
        return self.ok, self.mensagem


@dataclass(frozen=True)
class _Modulo:
    habilidade: Habilidade
    executar: Callable[[str], Resultado]
    disponibilidade: Callable[[], Disponibilidade] | None = None
    encerrar: Callable[[], None] | None = None
    ativo: bool = True


_MODULOS: dict[str, _Modulo] = {}
_TRAVA_MODULOS = threading.RLock()


def registrar_modulo(habilidade: Habilidade, executar: Callable[[str], Resultado],
                     *, disponibilidade: Callable[[], Disponibilidade] | None = None,
                     encerrar: Callable[[], None] | None = None) -> None:
    """Registro explícito pelo código local confiável, sem import ou descoberta.

    Permissões são declarações de escopo; autorização em execução é uma política
    separada. Não registrar conteúdo de páginas, respostas de modelos ou JSON remoto.
    O callback roda pela ponte única de NiaLive, nunca durante o registro.
    """
    if not isinstance(habilidade, Habilidade):
        raise TypeError('Manifesto deve ser uma Habilidade.')
    if (type(habilidade.api) is not int or habilidade.api != 1
            or not re.fullmatch(r'\d+\.\d+\.\d+', habilidade.versao)):
        raise ValueError('Versão de manifesto incompatível.')
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', habilidade.id):
        raise ValueError('Identificador de habilidade inválido.')
    for campo in (habilidade.nome, habilidade.descricao, habilidade.exemplo, habilidade.acao):
        if not isinstance(campo, str) or not campo.strip():
            raise ValueError('Manifesto incompleto.')
    for escopos in (habilidade.capacidades, habilidade.permissoes):
        if (not isinstance(escopos, tuple)
                or any(not isinstance(s, str) or not s.strip() for s in escopos)):
            raise ValueError('Capacidades e permissões devem ser tuplas de nomes.')
    if not callable(executar) or any(f is not None and not callable(f)
                                     for f in (disponibilidade, encerrar)):
        raise TypeError('Callbacks locais inválidos.')
    if type(habilidade.agendavel) is not bool:
        raise ValueError('Agendabilidade deve ser booleana.')
    if (not isinstance(habilidade.aliases, tuple)
            or any(not isinstance(a, str) or not a.strip() for a in habilidade.aliases)):
        raise ValueError('Aliases devem ser tuplas de nomes.')
    if habilidade.esquema_entrada is not None or habilidade.esquema_saida is not None:
        from core.contrato_universal import validar_esquema  # importação local
        validar_esquema(habilidade.esquema_entrada)
        validar_esquema(habilidade.esquema_saida)
    with _TRAVA_MODULOS:
        if por_id(habilidade.id) is not None:
            raise ValueError('Identificador já registrado.')
        _MODULOS[habilidade.id] = _Modulo(habilidade, executar, disponibilidade, encerrar)


def ativar_modulo(identificador: str, ativo: bool) -> bool:
    """Desativa novas chamadas sem descarregar serviços ou executar código."""
    from dataclasses import replace
    if type(ativo) is not bool:
        raise TypeError('Estado deve ser booleano.')
    with _TRAVA_MODULOS:
        modulo = _MODULOS.get(identificador)
        if modulo is None:
            return False
        _MODULOS[identificador] = replace(modulo, ativo=ativo)
        return True


def modulo_registrado(identificador: str) -> bool:
    with _TRAVA_MODULOS:
        return identificador in _MODULOS


def desregistrar_modulo(identificador: str) -> Resultado:
    """Retira o módulo antes de seu fechamento; módulos nativos são preservados."""
    with _TRAVA_MODULOS:
        modulo = _MODULOS.pop(identificador, None)
    if modulo is None:
        return Resultado(False, 'Módulo não registrado.', 'ausente')
    try:
        if modulo.encerrar is not None:
            modulo.encerrar()
    except Exception:
        return Resultado(False, 'Falha ao encerrar o módulo.', 'erro_encerramento')
    return Resultado(True, 'Módulo encerrado.')


def executar_modulo(identificador: str, termo: str = '') -> Resultado:
    """Adaptador chamado exclusivamente pela ponte de execução existente."""
    if not isinstance(termo, str):
        return Resultado(False, 'Argumento da ferramenta inválido.', 'argumento_invalido')
    with _TRAVA_MODULOS:
        modulo = _MODULOS.get(identificador)
    if modulo is None:
        return Resultado(False, 'Módulo não registrado.', 'ausente')
    if not modulo.ativo:
        return Resultado(False, 'Módulo desativado.', 'desativado')
    try:
        estado = modulo.disponibilidade() if modulo.disponibilidade else Disponibilidade(True, 'Pronta.')
        if not isinstance(estado, Disponibilidade):
            return Resultado(False, 'Estado do módulo inválido.', 'contrato_invalido')
        if not estado.pronta:
            return Resultado(False, estado.motivo, 'indisponivel')
        from core.permissoes_ferramentas import verificar
        try:
            verificar(identificador, {'termo': termo}, modulo.habilidade.permissoes)
        except (PermissionError, ValueError):
            return Resultado(False, 'Esta ferramenta exige confirmação da ação.', 'permissao_negada')
        resultado = modulo.executar(termo)
        if not isinstance(resultado, Resultado) or type(resultado.ok) is not bool or not isinstance(resultado.mensagem, str):
            return Resultado(False, 'Resultado do módulo inválido.', 'contrato_invalido')
        return resultado
    except Exception:
        # O texto de uma exceção de integração pode conter credenciais.
        return Resultado(False, 'Não foi possível executar o módulo.', 'erro')


CATALOGO: tuple[Habilidade, ...] = (
    Habilidade(
        id='secretaria',
        nome='Consultar a Secretaria',
        descricao='Abre a janela da Secretaria ou a área para ativá-la.',
        exemplo='NIA, abra a Secretaria.',
        acao='abrir_secretaria',
        config='secretaria',
    ),
    Habilidade(
        id='buscar_arquivos',
        nome='Buscar nos arquivos',
        descricao='Busca com fontes verificáveis da Skill 03, sem inferência.',
        exemplo='NIA, procure nos meus arquivos por garantia.',
        acao='abrir_busca',
        config='documentos',
    ),
    Habilidade(
        id='resumo_dia',
        nome='Preparar resumo do dia',
        descricao='Gera o resumo local do Hoje sem alterar a rotina agendada.',
        exemplo='NIA, prepare o resumo do dia.',
        acao='gerar_resumo',
        config='geral',
    ),
)


def todas() -> tuple[Habilidade, ...]:
    with _TRAVA_MODULOS:
        return CATALOGO + tuple(m.habilidade for m in _MODULOS.values())


def por_id(identificador: str) -> Habilidade | None:
    return next((h for h in todas() if h.id == identificador), None)


def registrar_executor(funcao: Callable[[str, str], tuple[bool, str]]) -> None:
    """Registra o ponto de entrada único; chamadas repetidas substituem a ponte."""
    global _EXECUTOR
    _EXECUTOR = funcao


def executar(identificador: str, termo: str = '') -> tuple[bool, str]:
    """Executa uma habilidade pelo mesmo caminho usado por chat e voz."""
    if por_id(identificador) is None:
        return False, 'Habilidade desconhecida.'
    if _EXECUTOR is None:
        return False, 'A ponte da NIA ainda não foi inicializada.'
    return _EXECUTOR(identificador, termo or '')


def executar_resultado(identificador: str, termo: str = '') -> Resultado:
    """Resultado tipado com a mesma execução de chat/voz, sem executor paralelo."""
    if por_id(identificador) is None:
        return Resultado(False, 'Habilidade desconhecida.', 'ausente')
    if _EXECUTOR is None:
        return Resultado(False, 'A ponte da NIA ainda não foi inicializada.', 'nao_inicializado')
    try:
        ok, mensagem = executar(identificador, termo)
        if type(ok) is not bool or not isinstance(mensagem, str):
            return Resultado(False, 'Resultado da ponte inválido.', 'contrato_invalido')
        return Resultado(ok, mensagem, 'ok' if ok else 'falha')
    except Exception:
        return Resultado(False, 'Não foi possível executar a habilidade.', 'erro')


def disponibilidade(identificador: str) -> Disponibilidade:
    """Estado local da habilidade, sem rede, modelo ou varredura."""
    habilidade = por_id(identificador)
    if habilidade is None:
        return Disponibilidade(False, 'Habilidade desconhecida.')
    with _TRAVA_MODULOS:
        modulo = _MODULOS.get(identificador)
    if modulo is not None:
        if not modulo.ativo:
            return Disponibilidade(False, 'Módulo desativado.')
        try:
            estado = modulo.disponibilidade() if modulo.disponibilidade else Disponibilidade(True, 'Módulo pronto.')
            return estado if isinstance(estado, Disponibilidade) else Disponibilidade(False, 'Estado do módulo inválido.')
        except Exception:
            return Disponibilidade(False, 'Módulo indisponível.')
    if habilidade.id == 'secretaria':
        try:
            from core import secretaria  # noqa: PLC0415
            if not secretaria.carregar().get('ligada'):
                return Disponibilidade(
                    False, 'Secretária desligada: ative-a em Configurações → '
                           'Integrações → Secretária.')
        except Exception:
            return Disponibilidade(False, 'Módulo da Secretária indisponível.')
        return Disponibilidade(True, 'Secretária ativa e pronta para abrir.')
    if habilidade.id == 'buscar_arquivos':
        try:
            from core import indice_local  # noqa: PLC0415
            if not indice_local.fts5_disponivel():
                return Disponibilidade(
                    False, 'Este Python não tem FTS5; configure o índice local '
                           'em Configurações → Documentos.')
            from core.config_preferencias import ConfigService  # noqa: PLC0415
            if not ConfigService().carregar_fontes_indice():
                return Disponibilidade(
                    False, 'Nenhuma pasta configurada: adicione fontes em '
                           'Configurações → Documentos.')
        except Exception as exc:
            return Disponibilidade(False, f'Índice local indisponível: {type(exc).__name__}.')
        return Disponibilidade(True, 'Busca local disponível, mesmo sem rede.')
    return Disponibilidade(True, 'Resumo local sempre disponível.')


def _normalizar(texto: str) -> str:
    bruto = unicodedata.normalize('NFKD', str(texto or '')).lower()
    return ''.join(c for c in bruto if not unicodedata.combining(c)).strip()


_PADROES: dict[str, str] = {
    'secretaria': r'^(?:nia[,:]?\s+)?(?:abra|abrir) a secretaria\.?$',
    'buscar_arquivos': (r'^(?:nia[,:]?\s+)?(?:procure|busque|pesquise) '
                        r'(?:nos|nas|em|no|na) (?:meus|minhas|meu|minha)?\s*'
                        r'(?:arquivos|documentos)'
                        r'(?:\s+por\s+(?P<termo>.+?))?\.?$'),
    'resumo_dia': (r'^(?:nia[,:]?\s+)?(?:prepare|gere|faca) o resumo '
                   r'do dia\.?$'),
}


def reconhecer(texto: str) -> tuple[Habilidade | None, str]:
    """Reconhece apenas as frases de exemplo documentadas, sem IA."""
    limpo = _normalizar(texto)
    for habilidade in CATALOGO:
        padrao = _PADROES.get(habilidade.id)
        if not padrao:
            continue
        encontrado = re.match(padrao, limpo)
        if encontrado:
            return habilidade, (encontrado.groupdict().get('termo') or '').strip(' .!?;:')
    return None, ''
