---
name: nia-task-orchestrator
description: Implementar e validar concorrência no motor adaptativo da NIA.
---
# nia-task-orchestrator

## Concorrência
Leia `docs/adaptive_learning/10_TASK_ORCHESTRATOR.md`.
UI PyQt6 na thread principal; workers/async conforme arquitetura. Prioridades emergência 100, comando 90, voz 80, controle 70, documento 60, pesquisa 40, consolidação 20; evitar starvation. Até três pesquisas concorrentes inicialmente, filas limitadas, timeout, cancel tokens e geração de cancelamento. Resultados atrasados descartados. Pesquisa interna sem roubar foco, mouse ou teclado; apresentar resultados com fonte. Encerrar workers e liberar recursos.

## Execução
Verifique checkpoint e arquitetura real; reutilize serviços, implemente incrementalmente, teste e registre evidências conforme prompt mestre. Não avance sobre falhas críticas.
