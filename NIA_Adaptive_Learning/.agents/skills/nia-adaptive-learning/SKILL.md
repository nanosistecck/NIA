---
name: nia-adaptive-learning
description: Implementar e validar escopo e invariantes no motor adaptativo da NIA.
---
# nia-adaptive-learning

## Escopo e invariantes
Leia `docs/adaptive_learning/00_MASTER_PLAN.md`.
Implementar aprendizado genérico por instrução, pesquisa, demonstração, colaboração, correção e experiência. Não treinar pesos nem executar código arbitrário aprendido. Preservar funções existentes, memória, SDK, permissões, dock, Canvas, voz, provedores e controle físico. Auditar antes de alterar; reutilizar serviços; não criar bancos ou motores concorrentes. Entregar todas as fases com evidências e migrações reversíveis.

## Arquitetura e auditoria
Leia `docs/adaptive_learning/01_ARCHITECTURE.md`.
Mapear entrada voz/chat, roteamento, ferramentas, memória, SDK/Factory, pesquisa, captura, controle, documentos, UI e workers. Registrar caminhos reais, contratos, testes baseline e dependências. Classificar reutilizar/evoluir/corrigir/criar. Propor adaptadores para CapabilityProvider, ObservationProvider, ActionProvider, KnowledgeProvider, ResearchProvider, WorkflowProvider, DocumentProvider, ValidationProvider e PermissionProvider. Eventos tipados com session_id, actor, correlation_id, timestamp, schema_version e cancel_generation. Estados principais e tarefas secundárias independentes. Não presumir módulos existentes.

## Avaliação de capacidade
Leia `docs/adaptive_learning/02_KNOWLEDGE_ENGINE.md`.
Decompor intenção em etapas; avaliar disponibilidade, permissão, conhecimento, contexto, validade e verificabilidade. Estados conhecido, parcial, desconhecido, desatualizado, indisponível, ambíguo, bloqueado e não confirmado. Executar partes seguras conhecidas; preservar progresso; pesquisar apenas lacunas. Não usar confiança do LLM como prova. Recuperar por intenção e contexto, distinguir preferências de instruções e evitar falsos matches.

## Roteamento e consolidação
Leia `docs/adaptive_learning/03_LEARNING_ENGINE.md`.
Rotas instrução, pesquisa, demonstração, colaboração, correção e experiência. Avisar lacuna; oferecer ensino verbal ou visual se pesquisa falhar. Estados descoberto, interpretado, testado, validado, consolidado, em revisão, obsoleto. Separar fatos, preferências, procedimentos, experiências, documentos e variáveis. Consolidar apenas evidências relevantes; preservar versão válida anterior. Correções explícitas têm precedência no escopo correto; permitir revisão, desativação e exclusão.

## Sequência e gates
Leia `docs/adaptive_learning/16_IMPLEMENTATION_PLAN.md`.
F00 auditoria; F01 contratos/avaliador; F02 memória; F03 pesquisa; F04 observação; F05 workflows; F06 colaboração; F07 documentos; F08 tarefas; F09 consolidação; F10 UI; F11 SDK; F12 segurança; F13 desempenho; F14 recuperação e aceitação. Segurança, cancelamento e testes desde F01, antes de habilitar ações reais. Cada fase: ler dependências, plano incremental, implementar, testar, corrigir, registrar evidências e checkpoint. Não avançar sobre falha crítica; continuar trabalhos independentes se seguro. Sem commits/push automáticos nem alterações destrutivas.

## Execução
Verifique checkpoint e arquitetura real; reutilize serviços, implemente incrementalmente, teste e registre evidências conforme prompt mestre. Não avance sobre falhas críticas.
