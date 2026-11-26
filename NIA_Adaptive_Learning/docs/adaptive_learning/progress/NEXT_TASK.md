# NEXT_TASK

F02: memória procedural persistente.

- Criar `core/aprendizado_adaptativo/memoria.py` com SQLite em `~/.nia/aprendizado_adaptativo.db`.
- Tabelas: knowledge, procedures, versions, steps, sessions, observations, experiences, workspaces, documents, items, tasks, checkpoints, corrections, sources.
- IDs estáveis, versão, estado, evidência, última validação e histórico.
- Migração idempotente (`PRAGMA user_version`) com backup antes de alterar esquema.
- Exclusão invalida caches; redigir segredos antes de gravar.
- Testes RED: reinício, versionamento, correção, exclusão, backup/migração, privacidade.
