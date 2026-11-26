# -*- coding: utf-8 -*-
"""Fase 12 — novas recorrências no agendador único existente."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core import rotinas as R


def _utc(texto):
    return datetime.fromisoformat(texto.replace('Z', '+00:00')).astimezone(timezone.utc)


def test_tipos_de_recorrencia_incluem_semanal_mensal_e_intervalo():
    """Quebra: o agendador só conhecia única/diária/dias úteis."""
    assert {'semanal', 'mensal', 'intervalo'} <= set(R.TIPOS)


def test_recorrencia_semanal_usa_o_dia_da_semana_da_data_ancora():
    """Quebra: semanal não avançava para o próximo mesmo dia da semana."""
    rotina = {'repeticao': 'semanal', 'data': '2026-11-20', 'hora': '09:00',
              'fuso': 'America/Sao_Paulo'}
    proxima = R.proxima_ocorrencia(rotina, _utc('2026-11-25T12:00:00Z'))
    assert proxima == _utc('2026-11-27T12:00:00Z')


def test_recorrencia_mensal_respeita_o_dia_do_mes():
    """Quebra: mensal não era calculada."""
    rotina = {'repeticao': 'mensal', 'data': '2026-11-30', 'hora': '09:00',
              'fuso': 'America/Sao_Paulo'}
    proxima = R.proxima_ocorrencia(rotina, _utc('2026-11-25T12:00:00Z'))
    assert proxima == _utc('2026-11-30T12:00:00Z')


def test_recorrencia_mensal_limita_dia_inexistente():
    """Quebra: dia 31 em fevereiro gerava data inválida."""
    rotina = {'repeticao': 'mensal', 'data': '2026-01-31', 'hora': '09:00',
              'fuso': 'America/Sao_Paulo'}
    proxima = R.proxima_ocorrencia(rotina, _utc('2026-02-25T12:00:00Z'))
    assert proxima.date() == _utc('2026-02-28T12:00:00Z').date()


def test_recorrencia_por_intervalo_avanca_a_partir_da_ancora():
    """Quebra: intervalos não eram suportados."""
    rotina = {'repeticao': 'intervalo', 'data': '2026-11-25', 'hora': '09:00',
              'intervalo_minutos': 120, 'fuso': 'America/Sao_Paulo'}
    proxima = R.proxima_ocorrencia(rotina, _utc('2026-11-25T15:30:00Z'))
    assert proxima == _utc('2026-11-25T16:00:00Z')


def test_tipo_desconhecido_continua_caindo_para_unica(tmp_path):
    """Quebra: regressão no fallback de tipos antigos."""
    armazem = R.ArmazemRotinas(db_path=tmp_path / 'rotinas.db')
    rotina = armazem.criar({'titulo': 'Teste', 'mensagem': 'Teste', 'acao': 'lembrete',
                            'repeticao': 'inexistente', 'data': '2026-11-25',
                            'hora': '09:00'})
    assert rotina['repeticao'] == 'unica'
