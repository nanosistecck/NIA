# -*- coding: utf-8 -*-
"""Fase 07 — aprendizado explícito de frases por ID de habilidade."""
from __future__ import annotations

import pytest

from core import aprendizado as AP

CAPACIDADES = ('relatorio_mensal', 'relatorio_anual', 'abrir_agenda')


def test_associacao_explicita_persiste_e_resolve(tmp_path):
    """Quebra: não existe associação persistida frase -> capacidade."""
    caminho = tmp_path / 'aprendizado.json'
    aprendizado = AP.Aprendizado(caminho=caminho, capacidades=CAPACIDADES)
    assert aprendizado.aprender('relatorio do mes', 'relatorio_mensal') is True
    assert AP.Aprendizado(caminho=caminho, capacidades=CAPACIDADES).resolver(
        'relatório do mês') == 'relatorio_mensal'


def test_aprendizado_recusa_frase_de_permissao(tmp_path):
    """Quebra: texto de autorização podia virar comando aprendido."""
    aprendizado = AP.Aprendizado(caminho=tmp_path / 'a.json', capacidades=CAPACIDADES)
    with pytest.raises(PermissionError, match='permiss'):
        aprendizado.aprender('autorizo o envio', 'abrir_agenda')


def test_conflito_de_frase_nao_sobrescreve_associacao(tmp_path):
    """Quebra: uma frase podia ser silenciosamente remapeada."""
    aprendizado = AP.Aprendizado(caminho=tmp_path / 'a.json', capacidades=CAPACIDADES)
    aprendizado.aprender('relatorio', 'relatorio_mensal')
    with pytest.raises(ValueError, match='conflito'):
        aprendizado.aprender('relatório', 'relatorio_anual')
    assert aprendizado.resolver('relatorio') == 'relatorio_mensal'


def test_correcao_incrementa_versao_e_muda_o_alvo(tmp_path):
    """Quebra: correção não era versionada."""
    aprendizado = AP.Aprendizado(caminho=tmp_path / 'a.json', capacidades=CAPACIDADES)
    aprendizado.aprender('relatorio', 'relatorio_mensal')
    assert aprendizado.corrigir('relatorio', 'relatorio_anual') is True
    item = aprendizado.listar()[0]
    assert item['versao'] == 2
    assert aprendizado.resolver('relatorio') == 'relatorio_anual'


def test_exclusao_remove_associacao(tmp_path):
    """Quebra: não havia forma de esquecer uma associação."""
    aprendizado = AP.Aprendizado(caminho=tmp_path / 'a.json', capacidades=CAPACIDADES)
    aprendizado.aprender('relatorio', 'relatorio_mensal')
    assert aprendizado.esquecer('relatorio') is True
    assert aprendizado.resolver('relatorio') is None


def test_capacidade_ausente_e_rejeitada_na_resolucao(tmp_path):
    """Quebra: plugin desinstalado continuava resolvido."""
    caminho = tmp_path / 'a.json'
    AP.Aprendizado(caminho=caminho, capacidades=CAPACIDADES).aprender(
        'relatorio', 'relatorio_mensal')
    sem_plugin = AP.Aprendizado(caminho=caminho, capacidades=('abrir_agenda',))
    assert sem_plugin.resolver('relatorio') is None


def test_ambiguidade_por_tokens_nao_escolhe_um_alvo(tmp_path):
    """Quebra: aproximação por tokens escolhia um alvo arbitrário."""
    aprendizado = AP.Aprendizado(caminho=tmp_path / 'a.json', capacidades=CAPACIDADES)
    aprendizado.aprender('abrir relatorio mensal', 'relatorio_mensal')
    aprendizado.aprender('abrir relatorio anual', 'relatorio_anual')
    assert aprendizado.resolver('abrir relatorio') is None
