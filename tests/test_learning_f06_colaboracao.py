# -*- coding: utf-8 -*-
"""RED F06: sessão colaborativa com árbitro exclusivo e retomada segura."""
from __future__ import annotations

import time

from core.aprendizado_adaptativo.colaboracao import SessaoColaborativa


class ControleFalso:
    def __init__(self):
        self.ativo = True
        self.lease = None

    def assumir(self, dono):
        if self.lease not in (None, dono):
            return False
        self.lease = dono
        return True

    def revogar(self):
        self.lease = None


def test_usuario_assume_controle_e_lease_e_exclusivo():
    controle = ControleFalso()
    s = SessaoColaborativa(controle=controle, objetivo='Editar documento')
    assert s.proprietario == 'nia'
    assert s.assumir_controle('usuario') is True
    assert s.proprietario == 'usuario'
    assert s.assumir_controle('nia') is False


def test_selecao_recente_resolve_referencia_ambiguamente():
    s = SessaoColaborativa(objetivo='Escolher música', relogio=lambda: 100.0)
    s.registrar_selecao('Música A', origem='usuario', timestamp=99.0)
    assert s.resolver_referencia('essa música') == 'Música A'
    assert s.resolver_referencia('aquela música') is None


def test_selecao_antiga_pede_esclarecimento():
    s = SessaoColaborativa(objetivo='Escolher música', relogio=lambda: 200.0)
    s.registrar_selecao('Música A', origem='usuario', timestamp=10.0)
    assert s.resolver_referencia('essa música') is None
    assert s.precisa_esclarecer is True


def test_conclusao_nao_reativa_observacao_no_reinicio():
    s = SessaoColaborativa(objetivo='Repertório')
    s.registrar_decisao('Usar fonte X')
    s.concluir()
    assert s.estado == 'CONCLUIDA'
    assert s.ativo() is False
    nova = SessaoColaborativa.retomar({'objetivo': 'Repertório',
                                       'estado': 'CONCLUIDA'})
    assert nova.ativo() is False
    assert nova.acoes_pendentes == ()
