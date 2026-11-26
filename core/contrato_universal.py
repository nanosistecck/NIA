# -*- coding: utf-8 -*-
"""Contrato universal das capacidades da NIA (Fase 02).

Une, sem substituir, os dois registros existentes — ``catalogo_habilidades``
e ``registro_aplicativos`` — numa descrição comum e serializável. A descoberta
é puramente declarativa: nenhum carregador é importado e nenhum plugin é
executado aqui.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from core import catalogo_habilidades as CH
from core import registro_aplicativos as RA

TIPOS_ESQUEMA = frozenset(
    ('STRING', 'BOOLEAN', 'INTEGER', 'NUMBER', 'ARRAY', 'OBJECT'))


@dataclass(frozen=True)
class Contrato:
    id: str
    nome: str
    descricao: str
    origem: str
    versao: str
    api: int
    permissoes: tuple[str, ...]
    capacidades: tuple[str, ...]
    agendavel: bool
    esquema_entrada: dict | None
    esquema_saida: dict | None
    aliases: tuple[str, ...]

    def como_dict(self) -> dict:
        return {
            'id': self.id, 'nome': self.nome, 'descricao': self.descricao,
            'origem': self.origem, 'versao': self.versao, 'api': self.api,
            'permissoes': list(self.permissoes),
            'capacidades': list(self.capacidades),
            'agendavel': self.agendavel,
            'esquema_entrada': self.esquema_entrada,
            'esquema_saida': self.esquema_saida,
            'aliases': list(self.aliases),
        }


def validar_esquema(esquema) -> None:
    """Valida o subconjunto de JSON Schema usado pelas capacidades locais."""
    if esquema is None:
        return
    if not isinstance(esquema, dict):
        raise ValueError('Esquema deve ser um objeto.')
    if esquema.get('type', 'object') != 'object':
        raise ValueError('Esquema de raiz deve ser object.')
    propriedades = esquema.get('properties', {})
    if not isinstance(propriedades, dict):
        raise ValueError('properties deve ser um objeto.')
    for nome, definicao in propriedades.items():
        if not isinstance(nome, str) or not nome:
            raise ValueError('Nome de propriedade inválido.')
        if not isinstance(definicao, dict):
            raise ValueError('Definição de propriedade inválida.')
        tipo = definicao.get('type')
        if tipo is not None and str(tipo).upper() not in TIPOS_ESQUEMA:
            raise ValueError('Tipo de propriedade não reconhecido: ' + str(tipo))
    obrigatorios = esquema.get('required', ())
    if not isinstance(obrigatorios, (list, tuple)):
        raise ValueError('required deve ser uma lista.')
    for nome in obrigatorios:
        if not isinstance(nome, str) or nome not in propriedades:
            raise ValueError('required fora de properties: ' + str(nome))


def descrever(item) -> Contrato:
    """Converte Habilidade ou DescritorApp em contrato canônico, sem efeitos."""
    if isinstance(item, CH.Habilidade):
        origem = CH.origem() if CH.origem() not in ('', 'catalogo') else 'catalogo'
        nome, descricao = item.nome, item.descricao
        versao, api = item.versao, item.api
        permissoes, capacidades = item.permissoes, item.capacidades
        schemas = (item.esquema_entrada, item.esquema_saida)
        agendavel, aliases = item.agendavel, item.aliases
    elif isinstance(item, RA.DescritorApp):
        origem = item.origem
        nome, descricao = item.nome, item.descricao
        versao, api = item.versao, item.api
        permissoes, capacidades = item.permissoes, ()
        schemas = (item.esquema_entrada, item.esquema_saida)
        agendavel, aliases = item.agendavel, item.aliases
    else:
        raise TypeError('Item não é uma capacidade registrável.')
    if not isinstance(versao, str) or not re.fullmatch(r'\d+\.\d+\.\d+', versao):
        raise ValueError('Versão de manifesto inválida.')
    if type(api) is not int or api != 1:
        raise ValueError('Versão de API incompatível.')
    for esquema in schemas:
        validar_esquema(esquema)
    return Contrato(
        id=item.id, nome=nome, descricao=descricao, origem=str(origem),
        versao=versao, api=api,
        permissoes=tuple(permissoes or ()),
        capacidades=tuple(capacidades or ()),
        agendavel=bool(agendavel),
        esquema_entrada=schemas[0], esquema_saida=schemas[1],
        aliases=tuple(aliases or ()),
    )


def _chave(texto: str) -> str:
    return RA.normalizar(texto).casefold()


def indice(itens: Iterable[Contrato]) -> dict[str, Contrato]:
    """Índice local por ID e aliases; colisões são recusadas antes do uso."""
    resultado: dict[str, Contrato] = {}
    for contrato in itens:
        chaves = [_chave(contrato.id)] + [_chave(a) for a in contrato.aliases]
        if len(set(chaves)) != len(chaves):
            raise ValueError('Colisão de alias no próprio manifesto: ' + contrato.id)
        for chave in chaves:
            if chave in resultado:
                raise ValueError('Colisão de identificador ou alias: ' + chave)
        for chave in chaves:
            resultado[chave] = contrato
    return resultado


def resolver(indice_de_contratos: dict[str, Contrato], identificador: str) -> Contrato | None:
    if not isinstance(identificador, str):
        return None
    return indice_de_contratos.get(_chave(identificador))
