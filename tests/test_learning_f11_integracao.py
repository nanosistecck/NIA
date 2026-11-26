# -*- coding: utf-8 -*-
"""RED F11: integração DLL/dock/SDK sem desviar do executor central."""
from __future__ import annotations

import pytest


def test_descritor_da_central_aprendizado_registrado():
    from core import registro_aplicativos as RA
    from core.registro_nativo import registrar_nativos
    registrar_nativos()
    d = RA.por_id('aprendizado')
    assert d is not None
    assert d.janela == 'aprendizado'
    assert d.possui_interface is True


def test_capacidades_registradas_no_catalogo_real():
    from core import catalogo_habilidades as CH
    from core.aprendizado_adaptativo.integracao import registrar_no_catalogo
    registrar_no_catalogo()
    hab = CH.por_id('aprendizado_adaptativo')
    assert hab is not None
    assert 'aprendizado.avaliar' in hab.capacidades
    executar = CH._MODULOS['aprendizado_adaptativo'].executar
    r = executar('abrir central')
    assert r.ok is True
    assert isinstance(r, CH.Resultado)


def test_manifesto_sdk_valido_sem_importar_main_ou_ui():
    from core import plugin_sdk as PS
    from core.aprendizado_adaptativo.integracao import manifesto
    m = manifesto()
    PS.validar_manifesto(m)
    assert m['api'] == PS.API
    assert m['imports'] == []
