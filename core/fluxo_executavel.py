# -*- coding: utf-8 -*-
"""Planos executáveis persistentes (Fase 11).

Workflow leve com etapas tipadas, dependências, estado, orçamento, tentativas
limitadas e cancelamento. Não substitui os planos visuais do Canvas: apenas
registra a execução validada das ações. Nenhum executor é criado aqui.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import os
import tempfile


@dataclass(frozen=True)
class Etapa:
    id: str
    tipo: str
    ferramenta: str
    argumentos: dict = field(default_factory=dict)
    dependencias: tuple = ()
    tentativas_limite: int = 2
    exige_aprovacao: bool = False


@dataclass(frozen=True)
class ResultadoEtapa:
    ok: bool
    pulada: bool = False
    motivo: str = ''
    estado: str = ''


class PlanoExecutavel:
    def __init__(self, caminho=None, orcamento: int = 10):
        self.caminho = Path(caminho) if caminho else Path.home() / '.nia' / 'fluxo_executavel.json'
        self.orcamento = max(1, int(orcamento))
        self._dados = self._carregar()

    def _carregar(self) -> dict:
        if not self.caminho.is_file():
            return {'etapas': {}, 'execucoes': 0}
        try:
            dados = json.loads(self.caminho.read_text(encoding='utf-8'))
            if isinstance(dados.get('etapas'), dict):
                return dados
        except (ValueError, OSError):
            pass
        return {'etapas': {}, 'execucoes': 0}

    def _salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        fd, temporario = tempfile.mkstemp(prefix='fluxo-', suffix='.json',
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

    def adicionar(self, etapa: Etapa) -> None:
        if not isinstance(etapa, Etapa):
            raise TypeError('Etapa inválida.')
        if not isinstance(etapa.id, str) or not etapa.id.strip():
            raise ValueError('Identificador de etapa inválido.')
        if etapa.tipo not in ('ferramenta', 'local'):
            raise ValueError('Tipo de etapa desconhecido.')
        if not isinstance(etapa.ferramenta, str) or not etapa.ferramenta.strip():
            raise ValueError('Ferramenta da etapa inválida.')
        if not isinstance(etapa.argumentos, dict) or not isinstance(etapa.dependencias, (list, tuple)):
            raise ValueError('Argumentos/dependências inválidos.')
        if etapa.id in self._dados['etapas']:
            raise ValueError('Etapa duplicada: ' + etapa.id)
        # Referências antecipadas são permitidas para que um ciclo seja
        # detectado quando a última etapa é acrescentada, não antes.
        for dependencia in etapa.dependencias:
            if not isinstance(dependencia, str) or not dependencia.strip():
                raise ValueError('Dependência inválida: ' + str(dependencia))
        registro = asdict(etapa)
        registro['dependencias'] = list(etapa.dependencias)
        registro['estado'] = 'pendente'
        registro['tentativas'] = 0
        self._dados['etapas'][etapa.id] = registro
        if self._tem_ciclo():
            del self._dados['etapas'][etapa.id]
            raise ValueError('ciclo nas dependências do plano.')
        self._salvar()

    def _tem_ciclo(self) -> bool:
        grafo = {id: list(item.get('dependencias', ()))
                 for id, item in self._dados['etapas'].items()}
        estado: dict[str, int] = {}

        def visitar(no: str) -> bool:
            if estado.get(no) == 1:
                return True
            if estado.get(no) == 2:
                return False
            estado[no] = 1
            for vizinho in grafo.get(no, ()):
                if visitar(vizinho):
                    return True
            estado[no] = 2
            return False

        return any(visitar(no) for no in grafo)

    def estado(self, identificador: str) -> str | None:
        registro = self._dados['etapas'].get(identificador)
        return registro.get('estado') if registro else None

    def proximas(self) -> tuple:
        prontas = []
        for identificador, registro in self._dados['etapas'].items():
            if registro.get('estado') != 'pendente':
                continue
            if all(self.estado(d) == 'concluida' for d in registro.get('dependencias', ())):
                prontas.append(identificador)
        return tuple(prontas)

    def cancelar(self, identificador: str) -> bool:
        registro = self._dados['etapas'].get(identificador)
        if registro is None:
            return False
        registro['estado'] = 'cancelada'
        self._salvar()
        return True

    def executar(self, identificador: str, executor, validador=None,
                 aprovador=None) -> ResultadoEtapa:
        registro = self._dados['etapas'].get(identificador)
        if registro is None:
            raise KeyError('Etapa não registrada: ' + identificador)
        estado_atual = registro.get('estado')
        if estado_atual == 'concluida':
            return ResultadoEtapa(True, pulada=True, estado=estado_atual)
        if estado_atual == 'cancelada':
            return ResultadoEtapa(False, motivo='cancelada', estado=estado_atual)
        if estado_atual == 'falhou':
            return ResultadoEtapa(False, motivo='etapa_falhou', estado=estado_atual)
        pendentes = [d for d in registro.get('dependencias', ())
                     if self.estado(d) != 'concluida']
        if pendentes:
            raise ValueError('dependências pendentes: ' + ', '.join(pendentes))
        if registro.get('exige_aprovacao') and (aprovador is None or not aprovador(registro)):
            return ResultadoEtapa(False, motivo='aprovacao_negada', estado=estado_atual)
        if int(registro.get('tentativas', 0)) >= int(registro.get('tentativas_limite', 2)):
            registro['estado'] = 'falhou'
            self._salvar()
            return ResultadoEtapa(False, motivo='tentativas_esgotadas', estado='falhou')
        if int(self._dados.get('execucoes', 0)) >= self.orcamento:
            return ResultadoEtapa(False, motivo='orcamento_esgotado', estado=estado_atual)
        if validador is not None:
            try:
                if validador(registro['ferramenta'], registro['argumentos']) is False:
                    return ResultadoEtapa(False, motivo='validacao_negada', estado=estado_atual)
            except (ValueError, TypeError, PermissionError, OSError) as exc:
                return ResultadoEtapa(False, motivo='validacao:' + type(exc).__name__,
                                      estado=estado_atual)
        try:
            bruto = executor(registro['ferramenta'], dict(registro['argumentos']))
        except Exception as exc:
            registro['tentativas'] = int(registro.get('tentativas', 0)) + 1
            self._salvar()
            return ResultadoEtapa(False, motivo='erro:' + type(exc).__name__,
                                  estado=registro['estado'])
        if isinstance(bruto, tuple) and len(bruto) == 2 and type(bruto[0]) is bool:
            ok, mensagem = bruto
        elif isinstance(bruto, str):
            ok, mensagem = True, bruto
        else:
            ok, mensagem = bool(bruto), ''
        if ok:
            registro['estado'] = 'concluida'
            self._dados['execucoes'] = int(self._dados.get('execucoes', 0)) + 1
        else:
            registro['tentativas'] = int(registro.get('tentativas', 0)) + 1
        self._salvar()
        return ResultadoEtapa(bool(ok), motivo=str(mensagem)[:200], estado=registro['estado'])
