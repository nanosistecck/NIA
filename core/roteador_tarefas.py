# -*- coding: utf-8 -*-
"""Política de seleção por tarefa sobre o roteador único da NIA.

Nenhuma chamada de IA é usada para classificar o pedido: o fluxo que já
conhece a tarefa informa apenas os requisitos (geração, imagem, síntese de
documentos e autorização). A decisão é determinística, local e barata.

As regras por heurística e a separação requisitos/decisão foram inspiradas
em ``src/openjarvis/learning/routing/`` (OpenJarvis, revisão 427c2dd,
Apache 2.0). Nenhum código foi copiado. A NIA mantém o ``llm_router`` como
único dono da disponibilidade, do fallback e do estado das chaves.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from core import llm_client, llm_router, provedores

# Famílias que a NIA já trata por adaptadores nativos com suporte a imagem.
_VISAO_PROVEDORES = frozenset({'gemini', 'openai'})
_VISAO_MODELO = re.compile(r'vision|image|gpt-4o|gpt-5|gemini', re.I)


@dataclass(frozen=True)
class Requisitos:
    geracao: bool = True
    imagem: bool = False
    documentos: bool = False
    autorizado: bool = False
    origem: str = 'chat'


@dataclass(frozen=True)
class Decisao:
    provedor: str
    modelo: str
    motivo: str
    local: bool
    permitido: bool = True
    aviso: str = ''

    def assinatura(self) -> str:
        return f'{self.provedor}|{self.modelo}'


_ULTIMA_DECISAO: Decisao | None = None


def registrar_decisao(decisao: Decisao) -> None:
    """Guarda só a última decisão, para o diagnóstico explicar a escolha."""
    global _ULTIMA_DECISAO
    _ULTIMA_DECISAO = decisao


def ultima_decisao() -> Decisao | None:
    return _ULTIMA_DECISAO


def _modelo_do_provedor(provedor: str, chave) -> str:
    modelo = str(getattr(chave, 'modelo', '') or '').strip()
    if modelo:
        return modelo
    catalogo = provedores.modelos_do_provedor(provedor) or []
    return str(catalogo[0]) if catalogo else ''


def decidir(requisitos: Requisitos | None = None, preferencia: str | None = None,
            roteador=None, *, registrar: bool = True) -> Decisao:
    """Escolhe a rota sem acessar rede, modelos locais ou catálogos remotos."""
    requisitos = requisitos or Requisitos()
    if not requisitos.geracao:
        decisao = Decisao(
            provedor='local', modelo='', local=True, permitido=True,
            motivo='Operação resolvida por serviços locais, sem inferência.')
        if registrar:
            registrar_decisao(decisao)
        return decisao

    pref = preferencia or llm_client.preferencia_conversa()
    if pref == 'ollama':
        _, modelo = llm_client.get_llm_settings()
        aviso = ''
        if requisitos.imagem:
            aviso = ('Capacidade de imagem do modelo local não foi confirmada; '
                     'o erro real do cliente será tratado se ocorrer.')
        decisao = Decisao(
            provedor='ollama', modelo=modelo, local=True, permitido=True,
            motivo='Preferência local salva: Ollama, sem fallback externo.',
            aviso=aviso)
        if registrar:
            registrar_decisao(decisao)
        return decisao

    if requisitos.documentos and not requisitos.autorizado:
        decisao = Decisao(
            provedor='', modelo='', local=False, permitido=False,
            motivo='Síntese externa exige autorização dos trechos exibidos.',
            aviso='Os trechos locais continuam disponíveis para consulta.')
        if registrar:
            registrar_decisao(decisao)
        return decisao

    roteador = roteador or llm_router.carregar_router()
    ordem = list(roteador.cadeia or llm_router.Router.CADEIA_PADRAO)
    if requisitos.imagem:
        ordem = ([p for p in ordem if llm_router.provedor_canonico(p) in _VISAO_PROVEDORES]
                 + [p for p in ordem
                    if llm_router.provedor_canonico(p) not in _VISAO_PROVEDORES])

    escolhido = None
    provedor_tentado = ''
    for nome in ordem:
        par = roteador.escolher(nome)
        if par is not None:
            escolhido = par
            provedor_tentado = llm_router.provedor_canonico(nome)
            break
    if escolhido is None:
        decisao = Decisao(
            provedor='', modelo='', local=False, permitido=False,
            motivo='Nenhum provedor externo disponível para esta tarefa.',
            aviso='Use os recursos locais; a inferência externa ficou pendente.')
        if registrar:
            registrar_decisao(decisao)
        return decisao

    _provedor, chave = escolhido
    provedor = llm_router.provedor_canonico(provedor_tentado)
    modelo = _modelo_do_provedor(provedor, chave)
    compativel = (provedor in _VISAO_PROVEDORES
                  or bool(_VISAO_MODELO.search(modelo)))
    if requisitos.imagem and compativel:
        motivo = 'Modelo compatível com imagens nas configurações.'
    elif requisitos.documentos:
        motivo = 'Síntese autorizada com o provedor configurado.'
    else:
        motivo = 'Conversa comum: preferência e roteador salvos.'
    aviso = ''
    if requisitos.imagem and not compativel:
        aviso = ('Capacidade de imagem não confirmada para o modelo '
                 'configurado; o erro real do cliente será tratado.')
    decisao = Decisao(provedor=provedor, modelo=modelo, motivo=motivo,
                      local=False, permitido=True, aviso=aviso)
    if registrar:
        registrar_decisao(decisao)
    return decisao
