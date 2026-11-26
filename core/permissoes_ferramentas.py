"""Consentimento local, revogável e vinculado a ferramenta/argumentos exatos.

Somente código da aplicação após confirmação do usuário deve chamar confirmar.
Conteúdo web, saídas de modelos e manifestos remotos nunca são autorizações.
Não persiste credenciais, argumentos ou tokens em disco.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import asyncio
import hashlib
import json
import math
from pathlib import Path
import re
import secrets
import threading
import time
import unicodedata
import os


@dataclass(frozen=True)
class Previa:
    ferramenta: str
    assinatura: str
    escopos: tuple[str, ...]


_ATUAL = ContextVar('nia_autorizacao_ferramenta', default=None)
_CONCESSOES: dict[str, tuple[Previa, float]] = {}
_TRAVA = threading.RLock()
_CAMPO_SEGREDO = re.compile(
    r'''(?i)(["']?(?:api[_-]?key|[a-z_]*api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|senha|secret|authorization)["']?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;}]+)''')
_BEARER = re.compile(r'(?i)\bBearer\s+[^\s,;"\']+')
_CHAVE_CONHECIDA = re.compile(r'\b(?:sk-[A-Za-z0-9_-]{10,}|AIza[A-Za-z0-9_-]{20,})')
_URL_CREDENCIAL = re.compile(r'(https?://)[^\s/@]+:[^\s/@]+@', re.I)


def redigir_diagnostico(texto: str, *, manter_linhas: bool = False) -> str:
    """Redige formatos conhecidos sem consultar ou carregar credenciais reais."""
    texto = str(texto or '').replace('\x00', '')
    texto = _BEARER.sub('Bearer [oculto]', texto)
    texto = _CAMPO_SEGREDO.sub(lambda m: m[1] + '[oculto]', texto)
    texto = _CHAVE_CONHECIDA.sub('[oculto]', texto)
    texto = _URL_CREDENCIAL.sub(r'\1[oculto]@', texto)
    return texto if manter_linhas else texto.replace('\r', r'\r').replace('\n', r'\n')


def preparar(ferramenta: str, argumentos: dict, escopos: tuple[str, ...]) -> Previa:
    if not isinstance(ferramenta, str) or not ferramenta.strip():
        raise ValueError('Ferramenta inválida.')
    if not isinstance(argumentos, dict) or not isinstance(escopos, tuple):
        raise ValueError('Argumentos ou escopos inválidos.')
    if any(not isinstance(e, str) or not e.strip() for e in escopos):
        raise ValueError('Escopo inválido.')
    try:
        texto = json.dumps([ferramenta, argumentos, sorted(set(escopos))],
                           sort_keys=True, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        raise ValueError('Argumentos devem ser JSON finito.') from None
    if len(texto) > 64000:
        raise ValueError('Argumentos excedem o limite.')
    return Previa(ferramenta, hashlib.sha256(texto.encode('utf-8')).hexdigest(),
                  tuple(sorted(set(escopos))))


def confirmar(previa: Previa, *, confirmado: bool = False, duracao: float = 60) -> str:
    """Confirmação explícita de prévia já exibida pela aplicação, uso único."""
    if confirmado is not True or not isinstance(previa, Previa):
        raise PermissionError('Confirmação explícita necessária.')
    if (isinstance(duracao, bool) or not isinstance(duracao, (int, float))
            or not math.isfinite(duracao) or not 0 < duracao <= 300):
        raise ValueError('Duração inválida.')
    with _TRAVA:
        agora = time.monotonic()
        for chave in tuple(_CONCESSOES):
            if _CONCESSOES[chave][1] <= agora:
                _CONCESSOES.pop(chave)
        if len(_CONCESSOES) >= 256:
            raise PermissionError('Limite de autorizações pendentes.')
        token = secrets.token_urlsafe(32)
        _CONCESSOES[token] = previa, agora + duracao
        return token


@contextmanager
def usar(token: str):
    marcador = _ATUAL.set(token)
    try:
        yield
    finally:
        _ATUAL.reset(marcador)


def revogar(token: str) -> bool:
    with _TRAVA:
        return _CONCESSOES.pop(token, None) is not None


def verificar(ferramenta: str, argumentos: dict, escopos: tuple[str, ...]) -> None:
    esperada = preparar(ferramenta, argumentos, escopos)
    with _TRAVA:
        token = _ATUAL.get()
        autorizacao = _CONCESSOES.get(token)
        if (autorizacao is None or autorizacao[1] <= time.monotonic()
                or autorizacao[0] != esperada):
            raise PermissionError('Ação sem autorização válida para esta prévia.')
        _CONCESSOES.pop(token)


def tem_autorizacao(ferramenta: str, argumentos: dict, escopos: tuple[str, ...]) -> bool:
    esperada = preparar(ferramenta, argumentos, escopos)
    with _TRAVA:
        item = _CONCESSOES.get(_ATUAL.get())
        return bool(item and item[0] == esperada and item[1] > time.monotonic())


def validar_caminho(caminho: str, raizes: tuple[str, ...]) -> Path:
    """Resolve symlinks/junções antes de conferir contenção; sem expandir escopo."""
    if not isinstance(caminho, str) or not caminho or '\x00' in caminho:
        raise PermissionError('Caminho inválido.')
    pedido = Path(caminho)
    if not pedido.is_absolute() or '..' in pedido.parts or not raizes:
        raise PermissionError('Caminho fora das raízes autorizadas.')
    destino = pedido.resolve()
    for raiz in raizes:
        base = Path(raiz)
        if base.is_absolute() and destino.is_relative_to(base.resolve()):
            return destino
    raise PermissionError('Caminho fora das raízes autorizadas.')


# Políticas explícitas. Ferramenta fora desta tabela nunca executa por fallback.
_GRUPOS = {
    'aplicativos:abrir': ('open_app', 'fechar_app'),
    'rede:consultar': ('web_search', 'youtube_video', 'flight_finder'),
    'navegador:controlar': ('browser_control',),
    'mensagens:acessar': ('send_message', 'whatsapp_bridge', 'secretaria_whatsapp'),
    'arquivos:acessar': ('file_controller', 'file_processor', 'organizar_pasta'),
    'computador:controlar': ('desktop_control', 'computer_control', 'usar_computador',
                            'digitar_na_tela', 'desenhar_na_tela', 'desfazer'),
    'sistema:alterar': ('computer_settings', 'game_updater', 'shutdown_nia'),
    'codigo:executar': ('code_helper', 'executar_tarefa', 'executar_comando', 'dev_agent', 'cowork'),
    'dados:enviar': ('codex_remote', 'editar_imagem', 'buscar_leads', 'screen_process', 'marcar_na_tela'),
    'dados:gravar': ('reminder', 'save_memory', 'editar_video'),
    'dispositivos:acessar': ('remote_media', 'vision_control'),
    'mapa:abrir': ('globo',),
    'consulta:publica': ('hora_agora', 'weather_report', 'system_status', 'close_camera'),
}
ESCOPOS_LEGADOS = {nome: (escopo,) for escopo, nomes in _GRUPOS.items() for nome in nomes}
_SEM_CONFIRMACAO = frozenset(_GRUPOS['consulta:publica'])
_ALIASES = {
    'whatsapp_bridge': {'receiver': 'STRING', 'message_text': 'STRING', 'text': 'STRING'},
    'file_controller': {'append': 'BOOLEAN'},
    'desenhar_na_tela': {'melhorar': 'BOOLEAN', 'critica': 'STRING'},
    'editar_imagem': {'image': 'STRING'},
    'marcar_na_tela': {'target': 'STRING'},
}


def validar_caminho_operacao(caminho: str) -> None:
    """Rejeita travessia e credenciais internas sem ler arquivos nem varrer disco.

    Aliases como desktop/documentos são resolvidos pelos adaptadores existentes.
    A raiz autorizada é verificada separadamente quando a ação tem essa restrição.
    """
    if not isinstance(caminho, str) or '\x00' in caminho:
        raise PermissionError('Caminho inválido.')
    raw = os.path.expandvars(caminho.strip().strip('"').strip("'"))
    partes = [p.casefold() for p in re.split(r'[/\\]+', raw)]
    if '..' in partes:
        raise PermissionError('Travessia de caminhos recusada.')
    protegidos = {'.git', '.ssh', '.aws', '.env', 'api_keys.json', 'id_rsa', 'id_ed25519', 'nia.db', 'jarvis.db'}
    if any(p in protegidos for p in partes):
        raise PermissionError('Arquivo interno de credenciais ou controle protegido.')
    if raw and Path(raw).is_absolute():
        resolvido = Path(raw).resolve()
        if any(p.casefold() in protegidos for p in resolvido.parts):
            raise PermissionError('Destino protegido após resolução do caminho.')


def validar_chamada(nome: str, argumentos: dict, declaracoes) -> tuple[str, ...]:
    escopos = ESCOPOS_LEGADOS.get(nome)
    if escopos is None:
        raise PermissionError('Ferramenta sem política registrada.')
    preparar(nome, argumentos, escopos)
    if nome == 'executar_comando':
        esquema = {'properties': {'comando': {'type': 'STRING'}}, 'required': ['comando']}
    else:
        esquema = next((d.get('parameters', {}) for d in declaracoes if d.get('name') == nome), None)
        if esquema is None:
            raise PermissionError('Ferramenta sem esquema registrado.')
    propriedades = dict(esquema.get('properties', {}))
    propriedades.update({chave: {'type': tipo} for chave, tipo in _ALIASES.get(nome, {}).items()})
    for chave in esquema.get('required', []):
        if chave not in argumentos or argumentos[chave] is None or argumentos[chave] == '':
            if nome == 'web_search' and chave == 'query' and argumentos.get('mode') == 'compare' and argumentos.get('items'):
                continue
            raise ValueError('Argumento obrigatório ausente: ' + chave)
    for chave, valor in argumentos.items():
        if chave not in propriedades:
            raise ValueError('Argumento não reconhecido: ' + str(chave))
        tipo = propriedades[chave].get('type', '').upper()
        valido = {'STRING': isinstance(valor, str), 'BOOLEAN': type(valor) is bool,
                  'INTEGER': type(valor) is int, 'NUMBER': type(valor) in (int, float),
                  'ARRAY': isinstance(valor, list), 'OBJECT': isinstance(valor, dict)}
        if tipo in valido and not valido[tipo]:
            raise ValueError('Tipo inválido de argumento: ' + chave)
        if tipo == 'ARRAY' and propriedades[chave].get('items', {}).get('type', '').upper() == 'STRING':
            if any(not isinstance(item, str) for item in valor):
                raise ValueError('Itens inválidos no argumento: ' + chave)
        if chave in {'path', 'destination', 'output_path', 'file_path', 'imagem', 'image', 'video', 'pasta', 'referencia'} and isinstance(valor, str):
            # destination de voo é cidade/aeroporto; também não pode conter travessia.
            validar_caminho_operacao(valor)
        if chave in {'name', 'new_name', 'output_name', 'filename'} and nome == 'file_controller':
            validar_caminho_operacao(valor)
    return escopos


def exige_confirmacao(nome: str) -> bool:
    return nome not in _SEM_CONFIRMACAO


def decisao_consentimento(texto: str) -> bool | None:
    normal = ''.join(c for c in unicodedata.normalize('NFKD', str(texto).lower()) if not unicodedata.combining(c))
    normal = re.sub(r'\s+', ' ', normal).strip(' .!?')
    if normal in {'sim', 'autorizo', 'confirmo', 'pode executar', 'permitir uma vez'}:
        return True
    if normal in {'nao', 'cancelar', 'cancela', 'revogar', 'nego', 'nao autorizo'}:
        return False
    return None


class Consentimentos:
    """Uma prévia por motor, sem threads/timers residentes, resposta correlacionada."""
    def __init__(self):
        self._trava = threading.RLock()
        self._pendente = None

    @property
    def pendente(self):
        with self._trava:
            return self._pendente[0] if self._pendente else None

    def responder(self, identificador: str, permitido: bool) -> bool:
        with self._trava:
            item = self._pendente
            if item is None or item[0] != identificador or type(permitido) is not bool:
                return False
            self._pendente = None
        _, loop, futuro = item
        def entregar():
            if not futuro.done():
                futuro.set_result(permitido)
        try:
            loop.call_soon_threadsafe(entregar)
        except RuntimeError:
            return False
        return True

    def cancelar(self) -> None:
        pedido = self.pendente
        if pedido:
            self.responder(pedido, False)

    async def solicitar(self, nome, argumentos, escopos, exibir, *, timeout=60):
        previa = preparar(nome, argumentos, escopos)
        loop = asyncio.get_running_loop()
        identificador = secrets.token_hex(12)
        futuro = loop.create_future()
        with self._trava:
            if self._pendente is not None:
                return None
            self._pendente = (identificador, loop, futuro)
        try:
            # Callback somente da aplicação; nenhuma chave de argumentos é autoridade.
            exibir(identificador, nome, redigir_diagnostico(json.dumps(argumentos, ensure_ascii=False)),
                   lambda permitir: self.responder(identificador, permitir))
            permitido = await asyncio.wait_for(futuro, timeout=timeout)
            if permitido:
                return confirmar(previa, confirmado=True)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            if asyncio.current_task().cancelling():
                raise
        except Exception:
            pass
        finally:
            with self._trava:
                if self._pendente and self._pendente[0] == identificador:
                    self._pendente = None
        return None
