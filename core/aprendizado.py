# -*- coding: utf-8 -*-
"""Aprendizado personalizado explícito (Fase 07).

Associa frases ditas pelo usuário a IDs de capacidades já registradas. Nunca
aprende autorização, não executa texto arbitrário e reavalia a existência da
capacidade no momento da resolução (plugin ausente não é resolvido).
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import os
import re
import tempfile

from core import registro_aplicativos as RA

_PERMISSAO = re.compile(
    r'(autoriz|permit|confirm|senha|password|token|credencial|permiss|api[_-]?key)')
_PARAR = frozenset(('a', 'o', 'as', 'os', 'de', 'do', 'da', 'para', 'por',
                    'com', 'um', 'uma', 'me', 'minha', 'meu', 'nisso'))


def _chave(frase: str) -> str:
    bruto = RA.normalizar(frase).casefold()
    limpo = re.sub(r"[^a-z0-9\s]", " ", bruto)
    return re.sub(r"\s+", " ", limpo).strip()


class Aprendizado:
    def __init__(self, caminho=None, capacidades=()):
        self.caminho = Path(caminho) if caminho else Path.home() / '.nia' / 'aprendizado.json'
        self._capacidades = frozenset(str(c) for c in (capacidades or ()))
        self._dados = self._carregar()

    def _carregar(self) -> dict:
        if not self.caminho.is_file():
            return {'versao': 1, 'associacoes': {}, 'preferencias': {},
                    'procedimentos': {}}
        try:
            dados = json.loads(self.caminho.read_text(encoding='utf-8'))
            if isinstance(dados.get('associacoes'), dict):
                return dados
        except (ValueError, OSError):
            pass
        return {'versao': 1, 'associacoes': {}, 'preferencias': {},
                'procedimentos': {}}

    def _salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        fd, temporario = tempfile.mkstemp(prefix='aprendizado-', suffix='.json',
                                          dir=str(self.caminho.parent))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as arquivo:
                json.dump(self._dados, arquivo, ensure_ascii=False, indent=2)
                arquivo.write('\n')
                arquivo.flush()
                os.fsync(arquivo.fileno())
            os.replace(temporario, self.caminho)
        finally:
            if os.path.exists(temporario):
                os.unlink(temporario)

    def aprender(self, frase: str, capacidade: str) -> bool:
        if not isinstance(frase, str) or not frase.strip():
            raise ValueError('Frase vazia não pode ser aprendida.')
        chave = _chave(frase)
        if _PERMISSAO.search(chave):
            raise PermissionError('Não aprendo frases de permissão ou segredo.')
        if not isinstance(capacidade, str) or capacidade not in self._capacidades:
            raise ValueError('Capacidade desconhecida: ' + str(capacidade))
        atual = self._dados['associacoes'].get(chave)
        if atual is not None:
            if atual.get('capacidade') == capacidade:
                return False
            raise ValueError('conflito de aprendizagem para esta frase.')
        self._dados['associacoes'][chave] = {
            'frase': frase.strip(), 'capacidade': capacidade, 'versao': 1,
            'criada_em': datetime.now(timezone.utc).isoformat(),
        }
        self._salvar()
        return True

    def corrigir(self, frase: str, capacidade: str) -> bool:
        chave = _chave(frase)
        atual = self._dados['associacoes'].get(chave)
        if atual is None:
            return False
        if not isinstance(capacidade, str) or capacidade not in self._capacidades:
            raise ValueError('Capacidade desconhecida: ' + str(capacidade))
        atual['capacidade'] = capacidade
        atual['versao'] = int(atual.get('versao', 1)) + 1
        self._salvar()
        return True

    def esquecer(self, frase: str) -> bool:
        removido = self._dados['associacoes'].pop(_chave(frase), None)
        if removido is not None:
            self._salvar()
        return removido is not None

    def resolver(self, frase: str) -> str | None:
        chave = _chave(frase)
        if not chave:
            return None
        exata = self._dados['associacoes'].get(chave)
        if exata is not None:
            return exata['capacidade'] if exata['capacidade'] in self._capacidades else None
        tokens = {t for t in chave.split() if len(t) > 2 and t not in _PARAR}
        if not tokens:
            return None
        candidatos = []
        for item in self._dados['associacoes'].values():
            alvo = {t for t in _chave(item['frase']).split()
                    if len(t) > 2 and t not in _PARAR}
            # Frases equivalentes podem acrescentar verbo/vocativo: medir
            # contra o tamanho do alvo evita que "abra meu escritório" perca
            # a associação aprendida para "escritório".
            pontos = len(tokens & alvo) / max(1, len(alvo))
            if pontos >= 0.6:
                candidatos.append((pontos, item['capacidade']))
        if not candidatos:
            return None
        melhor = max(pontos for pontos, _ in candidatos)
        vencedores = {cap for pontos, cap in candidatos if pontos == melhor}
        if len(vencedores) != 1:
            return None
        capacidade = next(iter(vencedores))
        return capacidade if capacidade in self._capacidades else None

    def listar(self) -> tuple:
        return tuple({'frase': item['frase'], 'capacidade': item['capacidade'],
                      'versao': item.get('versao', 1)}
                     for item in self._dados['associacoes'].values())

    def definir_preferencia(self, chave: str, valor) -> None:
        if not isinstance(chave, str) or not chave.strip():
            raise ValueError('Chave de preferência inválida.')
        if isinstance(valor, (dict, list)):
            raise ValueError('Preferência deve ser um valor simples.')
        self._dados.setdefault('preferencias', {})[chave.strip()] = str(valor)
        self._salvar()

    def preferencias(self) -> dict:
        return dict(self._dados.get('preferencias', {}))

    def registrar_procedimento(self, nome: str, etapas: tuple) -> None:
        if not isinstance(nome, str) or not nome.strip():
            raise ValueError('Nome de procedimento inválido.')
        procedimentos = self._dados.setdefault('procedimentos', {})
        atual = procedimentos.get(nome.strip(), {'versao': 0})
        procedimentos[nome.strip()] = {
            'versao': int(atual.get('versao', 0)) + 1,
            'etapas': [str(e) for e in (etapas or ())],
        }
        self._salvar()
