---
name: nia-procedural-memory
description: Implementar e validar persistência no motor adaptativo da NIA.
---
# nia-procedural-memory

## Persistência
Leia `docs/adaptive_learning/04_PROCEDURAL_MEMORY.md`.
Reutilizar armazenamento; SQLite/FTS5 se adequado. Entidades lógicas knowledge, procedures, versions, steps, sessions, observations, experiences, workspaces, documents, items, tasks, checkpoints, corrections, sources. IDs estáveis, origem, escopo, versão, estado, evidência, última validação, dependências e histórico. Transações, índices, migrações com backup e rollback, integridade referencial, exclusão que invalida caches. Dados locais fora do Git; não registrar credenciais. Testar reinício, troca de provedor e migração.

## Execução
Verifique checkpoint e arquitetura real; reutilize serviços, implemente incrementalmente, teste e registre evidências conforme prompt mestre. Não avance sobre falhas críticas.
