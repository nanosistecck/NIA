# -*- coding: utf-8 -*-
"""Validação de credenciais sem geração de texto nem alteração de registros.

Distingue autenticação, conectividade, permissões, cota e falhas de rede.
Catálogos genéricos também são consultados sem autenticação para identificar
respostas públicas. Mensagens do servidor não são reproduzidas na interface.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from urllib.parse import urlencode, urlsplit, urljoin, quote
import time
from core.http_seguranca import abrir, validar_endpoint

from core.llm_router import provedor_canonico

_PRAZO_S = 6.0

# Como cada familia prova que a chave vale: uma leitura barata do catalogo.
ROTULOS_STATUS = {'validado': 'Validado', 'invalido': 'Inválido', 'esgotado': 'Esgotado',
                  'limitado': 'Limite temporário', 'inconclusivo': 'Inconclusivo',
                  'nao_verificada': 'Não verificada'}


def status_registro(row):
    if row['status'] == 'invalida':
        return 'invalido'
    if row['status'] == 'esgotada' and row.get('validacao_estado') != 'limitado':
        return 'esgotado'
    return row.get('validacao_estado', 'nao_verificada')

def _get(url: str, cabecalho: dict) -> tuple[int, str]:
    headers = {'Accept': 'application/json', 'User-Agent': 'NIA/1.0 API-Configuration'}
    headers.update(cabecalho)
    pedido = urllib.request.Request(url, headers=headers, method="GET")
    return _http(pedido)


def _http(pedido, timeout=_PRAZO_S):
    try:
        with abrir(pedido, timeout=timeout) as r:
            return int(getattr(r, "status", 200)), r.read(16_000_000).decode("utf-8", "ignore")
    except urllib.error.HTTPError as exc:
        try:
            corpo = exc.read(4000).decode("utf-8", "ignore")
        except Exception:
            corpo = ""
        return int(exc.code), corpo
    except TimeoutError:
        raise TimeoutError('tempo esgotado') from None
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise TimeoutError('tempo esgotado') from None
        raise RuntimeError('sem resposta do provedor') from None
    except Exception:
        raise RuntimeError('sem resposta do provedor') from None


def validar(provedor: str, chave: str, base_url: str = "") -> tuple[bool, str]:
    """Compatibilidade da assinatura; somente sucesso verificável retorna True."""
    resultado = testar(provedor, chave, base_url)
    return resultado.apta, resultado.mensagem


@dataclass(frozen=True)
class ResultadoValidacao:
    estado: str
    mensagem: str
    http_status: int = 0
    codigo: str = ''
    temporario: bool = False
    modelos: tuple[str, ...] = ()
    catalogo_completo: bool = False
    catalogo_mensagem: str = ''
    catalogo_publico: bool = False

    @property
    def apta(self):
        return self.estado == 'verificada'

    @property
    def status_exibicao(self):
        if self.apta:
            return 'validado'
        if self.estado == 'recusada':
            return 'invalido'
        if self.estado == 'cota':
            return 'limitado' if self.temporario else 'esgotado'
        return 'inconclusivo'


def _json(corpo):
    try:
        return json.loads(corpo)
    except (ValueError, TypeError):
        return None


def interpretar_resposta(status, corpo):
    """Interpreta HTTP e códigos do provedor sem persistir mensagens arbitrárias."""
    dados = _json(corpo)
    erro = dados.get('error') if isinstance(dados, dict) else None
    falha_explicita = isinstance(dados, dict) and dados.get('success') is False
    if 200 <= status < 300 and not erro and not falha_explicita:
        return ResultadoValidacao('verificada', 'Autenticação confirmada pelo provedor.', status)
    if isinstance(erro, dict):
        texto = json.dumps(erro, ensure_ascii=False).lower()
    else:
        texto = str(erro or corpo or '').lower()
    # Não transformar 'quota exceeded' em chave inválida nem confundir 403 com 401.
    invalidas = ('api_key_invalid', 'invalid_api_key', 'api key not valid', 'invalid api key',
                 'authentication_error', 'invalid_token', 'invalid api token', 'expired_api_key',
                 'api key expired', 'revoked_api_key')
    sem_saldo = ('insufficient_quota', 'insufficient_balance', 'credit_balance',
                 'insufficient credits', 'insufficient credit', 'insufficient funds',
                 'billing_hard_limit', 'quota_exceeded', 'quota exceeded', 'resource_exhausted')
    if status == 401 or any(c in texto for c in invalidas):
        return ResultadoValidacao('recusada', 'Credencial inválida, expirada ou revogada.', status, 'autenticacao')
    if status == 429 and any(c in texto for c in ('perminute', 'per_minute', 'rate_limit_exceeded', 'rate limit')):
        return ResultadoValidacao('cota', 'Limite temporário de requisições; tente novamente mais tarde.', status, 'rate_limit', True)
    if status == 402 or any(c in texto for c in sem_saldo):
        return ResultadoValidacao('cota', 'Créditos ou cota esgotados; a chave não foi marcada como inválida.', status, 'cota')
    if status == 403:
        if dados is None and any(c in texto for c in ('cloudflare', 'access denied', 'captcha', 'error code: 1010')):
            return ResultadoValidacao('indisponivel', 'Acesso bloqueado pelo serviço ou proxy; validade da chave não confirmada.', status, 'bloqueio_acesso')
        return ResultadoValidacao('permissao', 'Credencial sem permissão para esta operação.', status, 'permissao')
    if status == 429:
        return ResultadoValidacao('cota', 'Limite temporário de requisições; tente novamente mais tarde.', status, 'rate_limit', True)
    if status in (408, 504):
        return ResultadoValidacao('timeout', 'Tempo de resposta esgotado.', status, 'timeout', True)
    if status >= 500:
        return ResultadoValidacao('indisponivel', 'Provedor temporariamente indisponível.', status, 'servidor', True)
    if not 200 <= status < 300 or erro or falha_explicita:
        return ResultadoValidacao('endpoint', 'Endpoint incorreto ou resposta incompatível.', status, 'endpoint')
    return ResultadoValidacao('verificada', 'Autenticação confirmada pelo provedor.', status)


def _consultar(url, headers):
    # Uma repetição limitada para falhas transitórias, apenas nos workers/CLI.
    for tentativa in range(2):
        try:
            status, corpo = _get(url, headers)
            resultado = interpretar_resposta(status, corpo)
        except TimeoutError:
            status, corpo = 0, ''
            resultado = ResultadoValidacao('timeout', 'Tempo de resposta esgotado.', temporario=True)
        except RuntimeError:
            status, corpo = 0, ''
            resultado = ResultadoValidacao('rede', 'Sem resposta; confira a rede e teste novamente.', temporario=True)
        if not resultado.temporario or resultado.estado == 'cota' or tentativa:
            return resultado, _json(corpo)
        time.sleep(0.15)


def _catalogo(alvo, headers, gemini=False):
    modelos = []
    visitadas = set()
    atual = alvo
    primeiro = None
    for _ in range(50):
        if atual in visitadas:
            break
        visitadas.add(atual)
        resultado, dados = _consultar(atual, headers)
        if primeiro is None:
            primeiro = resultado
        if not resultado.apta:
            diagnostico = resultado if resultado.estado in ('recusada', 'cota') else (primeiro if modelos else resultado)
            return replace(diagnostico, modelos=tuple(modelos),
                           catalogo_mensagem='Catálogo incompleto: ' + resultado.mensagem)
        itens = dados.get('models' if gemini else 'data') if isinstance(dados, dict) else None
        if not isinstance(itens, list):
            return replace(resultado, estado='endpoint', modelos=tuple(modelos),
                           mensagem='Resposta de catálogo inválida.', catalogo_mensagem='Catálogo indisponível.')
        for item in itens:
            if not isinstance(item, dict) or item.get('active') is False:
                continue
            nome = item.get('name' if gemini else 'id')
            if isinstance(nome, str) and nome.strip():
                segredos = [v.removeprefix('Bearer ') for v in headers.values()]
                if any(segredo and segredo in nome for segredo in segredos):
                    continue
                nome = nome.removeprefix('models/') if gemini else nome
                if nome not in modelos:
                    modelos.append(nome)
        token = dados.get('nextPageToken') or dados.get('next_page_token') or dados.get('next_cursor')
        if token:
            campo = 'pageToken' if gemini else ('page_token' if 'next_page_token' in dados else 'cursor')
            atual = alvo + ('&' if '?' in alvo else '?') + urlencode({campo: token})
        elif dados.get('has_more') and itens:
            cursor = itens[-1].get('id')
            if not cursor:
                break
            atual = alvo + ('&' if '?' in alvo else '?') + urlencode({'after_id': cursor})
        elif dados.get('next'):
            seguinte = urljoin(atual, str(dados['next']))
            origem, destino = urlsplit(alvo), urlsplit(seguinte)
            if ((origem.scheme, origem.netloc) != (destino.scheme, destino.netloc)
                    or destino.username or destino.password
                    or not destino.path.startswith(origem.path)):
                break  # Nunca repassa o segredo para outra conexão.
            atual = seguinte
        else:
            return replace(resultado, modelos=tuple(modelos), catalogo_completo=True,
                           catalogo_mensagem='Catálogo remoto atualizado.')
    return replace(primeiro, modelos=tuple(modelos), catalogo_mensagem='Catálogo parcial: paginação interrompida.')


def testar(provedor, chave, base_url=''):
    """Autentica e descobre modelos da mesma conexão, sem gerar texto."""
    from core.provedores import base_url_do_provedor, PROVEDORES
    nome = provedor_canonico(provedor)
    if not str(chave or '').strip():
        return ResultadoValidacao('recusada', 'Chave vazia.')
    try:
        base = validar_endpoint(base_url or base_url_do_provedor(provedor))
    except ValueError:
        return ResultadoValidacao('endpoint', 'URL do endpoint inválida ou não configurada.')
    spec = PROVEDORES.get('google' if nome == 'gemini' else nome, {})
    if spec.get('tipo', 'llm') != 'llm':
        return ResultadoValidacao('indisponivel', 'Este serviço não expõe um catálogo LLM; teste específico indisponível.')
    headers = {'x-goog-api-key': chave} if nome == 'gemini' else {'Authorization': f'Bearer {chave}'}
    oficial = not base_url or base == base_url_do_provedor(provedor).rstrip('/')
    autenticacao = None
    if nome == 'openrouter' and oficial:
        autenticacao, conta = _consultar(base + '/key', headers)
        if not autenticacao.apta:
            return autenticacao
        info = conta.get('data') if isinstance(conta, dict) else None
        if not isinstance(info, dict):
            return ResultadoValidacao('endpoint', 'Resposta de autenticação inválida.', autenticacao.http_status)
        if info.get('is_management_key') or info.get('is_provisioning_key'):
            return ResultadoValidacao('permissao', 'Chave de gerenciamento; use uma chave de inferência.', autenticacao.http_status)
        gratuitos = info.get('free_model_daily_requests') or {}
        saldo = info.get('limit_remaining')
        if isinstance(saldo, (int, float)) and saldo <= 0 and gratuitos.get('remaining') == 0:
            autenticacao = replace(autenticacao, estado='cota', codigo='cota',
                                  mensagem='Limites pagos e gratuitos esgotados.')
    catalogo = _catalogo(base + '/models', headers, gemini=nome == 'gemini')
    # Os catálogos dos principais provedores nativos exigem autenticação.
    if autenticacao is not None:
        return replace(autenticacao, modelos=catalogo.modelos, catalogo_completo=catalogo.catalogo_completo,
                       catalogo_mensagem=catalogo.catalogo_mensagem or catalogo.mensagem)
    if not catalogo.apta:
        return catalogo
    if nome in ('gemini', 'openai', 'groq') and oficial:
        return catalogo
    sem_auth, _ = _consultar(base + '/models', {})
    if sem_auth.estado in ('recusada', 'permissao'):
        return catalogo
    return replace(catalogo, estado='conectividade', catalogo_publico=True,
                   mensagem='Catálogo público acessível; a validade da chave exige uma chamada autenticada de uso.')


def testar_geracao(provedor, chave, modelo, base_url=''):
    """Uma chamada explícita de uso, com prompt fixo e possível consumo de cota."""
    from core.provedores import base_url_do_provedor
    nome = provedor_canonico(provedor)
    if not chave or not modelo:
        return ResultadoValidacao('endpoint', 'Informe a chave e selecione um modelo para testar o uso.')
    try:
        base = validar_endpoint(base_url or base_url_do_provedor(provedor))
    except ValueError:
        return ResultadoValidacao('endpoint', 'Endpoint inválido ou não configurado.')
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json',
               'User-Agent': 'NIA/1.0 API-Configuration'}
    prompt = 'Responda apenas OK.'
    if nome == 'gemini':
        alvo = base + '/models/' + quote(modelo.removeprefix('models/'), safe='') + ':generateContent'
        headers['x-goog-api-key'] = chave
        payload = {'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {'maxOutputTokens': 8}}
        campo = 'candidates'
    elif nome == 'openai':
        alvo = base + '/responses'
        headers['Authorization'] = 'Bearer ' + chave
        payload = {'model': modelo, 'input': prompt, 'max_output_tokens': 16}
        campo = 'output'
    else:
        alvo = base + '/chat/completions'
        headers['Authorization'] = 'Bearer ' + chave
        payload = {'model': modelo, 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 8}
        campo = 'choices'
    pedido = urllib.request.Request(alvo, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
    try:
        status, corpo = _http(pedido, timeout=30)
    except TimeoutError:
        return ResultadoValidacao('timeout', 'Teste de uso excedeu o tempo de resposta.', temporario=True)
    except RuntimeError:
        return ResultadoValidacao('rede', 'Sem resposta no teste de uso.', temporario=True)
    resultado = interpretar_resposta(status, corpo)
    if status in (404, 410) and resultado.estado == 'endpoint':
        return replace(resultado, estado='modelo', codigo='modelo', mensagem='Modelo ou operação indisponível; a credencial não foi invalidada.')
    if not resultado.apta:
        return resultado
    dados = _json(corpo)
    if not isinstance(dados, dict) or not isinstance(dados.get(campo), list):
        return ResultadoValidacao('endpoint', 'Resposta inesperada no teste de uso.', status)
    return replace(resultado, mensagem='Chamada autenticada de uso confirmada no modelo selecionado.')
