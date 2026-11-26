# Fase 11 — Perfis e personalização

## Protocolo obrigatório de execução
Leia `00_ORQUESTRADOR.md` e `progresso/CONTINUAR.md` antes de trabalhar. Use a raiz local real da NIA; não troque branch nem descarte alterações. Verifique o checkpoint e apenas os arquivos relevantes que mudaram. Reutilize padrões existentes. Antes de editar, registre plano, arquivos afetados e estratégia de reversão. Faça alterações pequenas, teste com backend simulado por padrão, preserve funcionalidades e registre evidências (comando, código de saída, resultado e arquivos). Não invente resultados. Não faça commit/push sem autorização. Atualize STATUS.json, IMPLEMENTACAO.md, DECISOES.md, TESTES.md, PENDENCIAS.md e CONTINUAR.md atomicamente ao concluir cada unidade. Se bloqueado, registre causa, tentativa, próxima ação e dependências afetadas; avance apenas em tarefas independentes seguras.

## Implementação
Criar perfis Desktop, Navegador, Apresentações, Multimídia, Canvas, Acessibilidade e Personalizado. Editor de mapeamento com detecção de conflitos, importação/exportação validada e migração. Contexto por aplicativo em primeiro plano opcional; nunca trocar durante arraste.

## Critérios de aceite
Testes de CRUD, migração, conflitos, troca de contexto e recuperação de configuração inválida.

## Saída
Registrar evidências e estado real: concluída, parcial ou bloqueada. Atualizar o checkpoint antes de avançar.
