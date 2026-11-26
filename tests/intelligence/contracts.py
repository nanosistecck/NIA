# -*- coding: utf-8 -*-
"""Contratos verificáveis dos cenários do laboratório de inteligência."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Scenario:
    id: str
    category: str
    kind: str
    message: str
    expected: str
    allowed: tuple = ()
    forbidden: tuple = ()
    effect: str = ''
    arguments: dict = field(default_factory=dict)
    seed: int = 0
    tags: tuple = ()
    provider: str = 'local'
    blocked: bool = False

    def as_dict(self) -> dict:
        return {
            'id': self.id, 'category': self.category, 'kind': self.kind,
            'message': self.message, 'expected': self.expected,
            'allowed': list(self.allowed), 'forbidden': list(self.forbidden),
            'effect': self.effect, 'arguments': dict(self.arguments),
            'seed': self.seed,
            'tags': list(self.tags), 'provider': self.provider,
            'blocked': self.blocked,
        }


@dataclass(frozen=True)
class Evaluation:
    scenario_id: str
    ok: bool
    intent_ok: bool = False
    tool_ok: bool = False
    params_ok: bool = False
    effect_ok: bool = False
    response_ok: bool = False
    security_ok: bool = True
    observed: tuple = ()
    details: str = ''
    blocked: bool = False

    def as_dict(self) -> dict:
        return {
            'scenario_id': self.scenario_id, 'ok': self.ok,
            'intent_ok': self.intent_ok, 'tool_ok': self.tool_ok,
            'params_ok': self.params_ok, 'effect_ok': self.effect_ok,
            'response_ok': self.response_ok, 'security_ok': self.security_ok,
            'observed': list(self.observed), 'details': self.details,
            'blocked': self.blocked,
        }
