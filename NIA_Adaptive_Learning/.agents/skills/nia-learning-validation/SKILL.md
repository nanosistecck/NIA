---
name: nia-learning-validation
description: Implementar e validar aceitação no motor adaptativo da NIA.
---
# nia-learning-validation

## Aceitação
Leia `docs/adaptive_learning/15_ACCEPTANCE_TESTS.md`.
Executar matriz TEST_MATRIX.md; unitários, integração, segurança, regressão, desempenho e E2E Windows. Fixtures determinísticas sem rede e testes reais separados. Não confundir mock com E2E. Testar tarefa inédita sem hardcode, troca de resolução/idioma, falhas, reinício, troca de modelo, concorrência, privacidade, ESC e recuperação. Evidência de pós-condição, logs redigidos e comandos de teste. Bloqueio ambiental marcado PENDENTE, nunca PASS.

## Sequência e gates
Leia `docs/adaptive_learning/16_IMPLEMENTATION_PLAN.md`.
F00 auditoria; F01 contratos/avaliador; F02 memória; F03 pesquisa; F04 observação; F05 workflows; F06 colaboração; F07 documentos; F08 tarefas; F09 consolidação; F10 UI; F11 SDK; F12 segurança; F13 desempenho; F14 recuperação e aceitação. Segurança, cancelamento e testes desde F01, antes de habilitar ações reais. Cada fase: ler dependências, plano incremental, implementar, testar, corrigir, registrar evidências e checkpoint. Não avançar sobre falha crítica; continuar trabalhos independentes se seguro. Sem commits/push automáticos nem alterações destrutivas.

## Execução
Verifique checkpoint e arquitetura real; reutilize serviços, implemente incrementalmente, teste e registre evidências conforme prompt mestre. Não avance sobre falhas críticas.
