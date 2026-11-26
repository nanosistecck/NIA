---
name: nia-knowledge-engine
description: Implementar e validar avaliação de capacidade no motor adaptativo da NIA.
---
# nia-knowledge-engine

## Avaliação de capacidade
Leia `docs/adaptive_learning/02_KNOWLEDGE_ENGINE.md`.
Decompor intenção em etapas; avaliar disponibilidade, permissão, conhecimento, contexto, validade e verificabilidade. Estados conhecido, parcial, desconhecido, desatualizado, indisponível, ambíguo, bloqueado e não confirmado. Executar partes seguras conhecidas; preservar progresso; pesquisar apenas lacunas. Não usar confiança do LLM como prova. Recuperar por intenção e contexto, distinguir preferências de instruções e evitar falsos matches.

## Execução
Verifique checkpoint e arquitetura real; reutilize serviços, implemente incrementalmente, teste e registre evidências conforme prompt mestre. Não avance sobre falhas críticas.
