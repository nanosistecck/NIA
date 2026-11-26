# -*- coding: utf-8 -*-
"""RED F12: permissões independentes do LLM, ESC e redação de logs."""
from __future__ import annotations

import pytest

from core.aprendizado_adaptativo.seguranca import (
    PoliticaAprendizado, Escopo, ConfirmacaoNecessaria)


def test_llm_nao_concede_permissao():
    p = PoliticaAprendizado()
    assert p.permite('controle_fisico', 'clicar', origem='llm') is False
    assert p.permite('leitura', 'listar', origem='llm') is True


def test_acao_sensivel_exige_confirmacao_explicita():
    p = PoliticaAprendizado()
    with pytest.raises(ConfirmacaoNecessaria):
        p.exigir('acao_sensivel', 'apagar', origem='usuario')
    token = p.confirmar('acao_sensivel', 'apagar')
    assert p.permite('acao_sensivel', 'apagar', token=token) is True


def test_revogacao_bloqueia_callback_tardio():
    p = PoliticaAprendizado()
    token = p.confirmar('alteracao_externa', 'enviar')
    assert p.revogar(token) is True
    assert p.permite('alteracao_externa', 'enviar', token=token) is False


def test_esc_cancela_filas_e_lease():
    p = PoliticaAprendizado()
    p.confirmar('controle_fisico', 'mover')
    p.esc()
    assert p.cancelado is True
    assert p.permite('controle_fisico', 'mover') is False
    assert p.lease is None


def test_logs_redigidos():
    p = PoliticaAprendizado()
    texto = p.redigir('senha: ABC123 token=XYZ api_key: SEGREDO')
    for segredo in ('ABC123', 'XYZ', 'SEGREDO'):
        assert segredo not in texto
    assert texto.count('***') >= 3
