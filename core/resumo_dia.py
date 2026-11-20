# -*- coding: utf-8 -*-
"""Resumo do dia a partir de fontes locais: rotinas e diário.

Nenhuma inferência, rede ou serviço externo participa da geração: o texto é
montado localmente, com limite de tamanho e linguagem adequada para leitura
em voz alta. O fluxo foi inspirado no Morning Digest do OpenJarvis (coleta →
resumo falado → texto sempre disponível), sem reaproveitar código externo.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from core import rotinas as R

LIMITE_TEXTO = 700
LIMITE_NOTAS = 5


def caminho_padrao() -> Path:
    externo = os.environ.get('NIA_RESUMO_DIA')
    if externo:
        return Path(externo).expanduser()
    return Path.home() / '.nia' / 'resumo_dia.json'


def perfil_atual() -> str:
    return str(os.environ.get('NIA_PERFIL') or 'principal')


def leitura_automatica() -> bool:
    from core.config_preferencias import ConfigService  # noqa: PLC0415
    try:
        return ConfigService().resumo_leitura_automatica()
    except Exception:
        return False


_TRAVA = threading.RLock()


def carregar(perfil: str | None = None) -> dict | None:
    try:
        dados = json.loads(caminho_padrao().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(dados, dict):
        return None
    item = dados.get(perfil or perfil_atual())
    return item if isinstance(item, dict) else None


def salvar(resultado: dict, perfil: str | None = None) -> None:
    """Grava somente um resumo bem-sucedido, de forma atômica."""
    with _TRAVA:
        caminho = caminho_padrao()
        caminho.parent.mkdir(parents=True, exist_ok=True)
        try:
            dados = json.loads(caminho.read_text(encoding='utf-8'))
            if not isinstance(dados, dict):
                dados = {}
        except (OSError, ValueError):
            dados = {}
        dados[perfil or perfil_atual()] = {
            'texto': str(resultado.get('texto') or '')[:LIMITE_TEXTO],
            'gerado_em': resultado.get('gerado_em'),
            'data': resultado.get('data'),
            'fontes': resultado.get('fontes') or [],
        }
        temporario = caminho.with_suffix('.tmp')
        temporario.write_text(
            json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')
        temporario.replace(caminho)


def _notas_de_hoje(dia: date, diario_path: Path | None = None,
                   limite: int = LIMITE_NOTAS) -> tuple[list[dict], bool]:
    caminho = diario_path or (Path(__file__).resolve().parent.parent
                              / 'memory' / 'diario.jsonl')
    try:
        linhas = caminho.read_text(encoding='utf-8', errors='ignore').splitlines()
    except OSError:
        return [], True
    encontradas = []
    prefixo = dia.strftime('%d/%m')
    for linha in reversed(linhas[-200:]):
        try:
            registro = json.loads(linha)
        except ValueError:
            continue
        if str(registro.get('quando') or '').startswith(prefixo):
            encontradas.append(registro)
            if len(encontradas) >= limite:
                break
    return list(reversed(encontradas)), False


def _rotinas_de_hoje(armazem, agora: datetime, fuso_exibicao: str):
    zona_exibicao = R._fuso(fuso_exibicao)
    local = agora.astimezone(zona_exibicao)
    inicio_local = datetime.combine(local.date(), time.min,
                                    tzinfo=zona_exibicao).astimezone(timezone.utc)
    fim_local = inicio_local + timedelta(days=1)
    itens = []
    for rotina in armazem.listar():
        zona = R._fuso(rotina.get('fuso') or R.fuso_padrao())
        inicio_rotina = inicio_local.astimezone(zona)
        ocorrencia = R.proxima_ocorrencia(
            rotina, inicio_rotina - timedelta(seconds=1))
        if ocorrencia is None or not (inicio_local <= ocorrencia < fim_local):
            continue
        historico = armazem.historico(rotina['id'], 20)
        concluida = any(
            str(item.get('ocorrencia') or '') == ocorrencia.isoformat()
            and item.get('resultado') == 'ok' for item in historico)
        itens.append({
            'titulo': rotina['titulo'],
            'acao': rotina.get('acao', 'lembrete'),
            'quando': ocorrencia.astimezone(zona_exibicao),
            'concluida': concluida,
        })
    itens.sort(key=lambda item: item['quando'])
    return itens


def gerar(agora: datetime | None = None, perfil: str | None = None,
          armazem=None, diario_path: Path | None = None,
          fuso_exibicao: str | None = None) -> dict:
    agora = agora or datetime.now(timezone.utc)
    perfil = perfil or perfil_atual()
    armazem = armazem or R.ArmazemRotinas()
    fuso = fuso_exibicao or R.fuso_padrao()
    local = agora.astimezone(R._fuso(fuso))

    erros = []
    try:
        rotinas = _rotinas_de_hoje(armazem, agora, fuso)
    except Exception:
        rotinas, erros = [], erros + ['rotinas']
    notas, falha_diario = _notas_de_hoje(local.date(), diario_path)
    if falha_diario:
        erros.append('diario')

    partes = [f'Bom dia. Hoje é {local.strftime("%d de %m")}.']
    if rotinas:
        for item in rotinas:
            horario = item['quando'].strftime('%H:%M')
            if item['acao'] == 'resumo':
                acao = ('resumo do dia concluído' if item['concluida']
                        else 'resumo do dia a seguir')
            else:
                acao = 'concluída' if item['concluida'] else 'a seguir'
            partes.append(f'{horario}, {item["titulo"]}, {acao}.')
    else:
        partes.append('Nenhuma rotina agendada para hoje.')
    if notas:
        resumos = [str(n.get('texto') or '')[:90].strip() for n in notas]
        resumos = [r for r in resumos if r]
        partes.append('Do diário: ' + '; '.join(resumos[:3]) + '.')
    else:
        partes.append('Nenhuma anotação recente no diário.')

    fontes = [f'{len(rotinas)} rotina(s)', f'{len(notas)} anotação(ões)']
    if erros:
        partes.append('Resumo parcial: falha na leitura de ' + ', '.join(erros) + '.')
    partes.append('Fontes: ' + ', '.join(fontes) + '.')
    texto = ' '.join(partes)
    return {
        'texto': texto[:LIMITE_TEXTO],
        'gerado_em': R._iso(agora),
        'data': local.date().isoformat(),
        'fontes': fontes,
        'rotinas': len(rotinas),
        'notas': len(notas),
        'parcial': bool(erros),
        'erros': erros,
        'perfil': perfil,
        'vazio': not rotinas and not notas,
    }


def gerar_e_salvar(**kwargs) -> dict:
    """Geração compartilhada pelos disparos manual e agendado."""
    try:
        resultado = gerar(**kwargs)
    except Exception as exc:
        return {'ok': False, 'erro': type(exc).__name__}
    try:
        salvar(resultado, resultado.get('perfil'))
    except Exception:
        # Texto gerado continua disponível mesmo se a gravação falhar.
        return {**resultado, 'ok': True, 'salvo': False}
    return {**resultado, 'ok': True, 'salvo': True}
