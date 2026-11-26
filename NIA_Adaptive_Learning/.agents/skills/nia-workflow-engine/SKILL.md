---
name: nia-workflow-engine
description: Implementar e validar procedimentos declarativos no motor adaptativo da NIA.
---
# nia-workflow-engine

## Procedimentos declarativos
Leia `docs/adaptive_learning/07_WORKFLOW_ENGINE.md`.
Esquema versionado com objetivo, aliases, contexto, variáveis tipadas, ferramentas permitidas, etapas, precondições, alvo semântico, ação, pós-condição, timeout, retry, fallback e pontos de decisão humana. Sem eval, shell ou código arbitrário aprendido. Resolver alvos novamente antes de agir; validar estado final; evitar alternar opção já ativa. Checkpoints e idempotência; não repetir efeitos externos de resultado incerto. Em falha reavaliar contexto, limitar tentativas, pedir orientação. Data dinâmica, nunca fixar dia 15.

## Execução
Verifique checkpoint e arquitetura real; reutilize serviços, implemente incrementalmente, teste e registre evidências conforme prompt mestre. Não avance sobre falhas críticas.
