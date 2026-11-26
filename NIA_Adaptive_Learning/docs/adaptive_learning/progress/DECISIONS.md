# DECISIONS

## 2026-11-26 — F00

- Decisão: criar `core/aprendizado_adaptativo/` como camada nova e fina, sem substituir memória, controle, pesquisa ou executor existentes.
- Alternativas: estender `core/aprendizado.py` (rejeitada: é associação frase→capacidade, não procedimentos versionados); gravar tudo em JSON (rejeitada: perde integridade e migração).
- Motivo: preservar contratos e dados atuais; permitir rollback por arquivo novo.
- Impacto: nenhuma mudança de comportamento existente até F01.

## 2026-11-26 — F01

- Decisão: confiança do modelo nunca conta como evidência; estados vêm de capacidade registrada + permissão + evidência com data.
- Alternativas: aceitar `confianca >= 0.8` (rejeitada por especificação 02).
- Motivo: evitar aliases e falsos positivos.
- Impacto: avaliador pode devolver PARCIAL e executar só partes seguras.
