# Fase 06 — Mouse virtual

## Protocolo obrigatório de execução
Leia `00_ORQUESTRADOR.md` e `progresso/CONTINUAR.md` antes de trabalhar. Use a raiz local real da NIA; não troque branch nem descarte alterações. Verifique o checkpoint e apenas os arquivos relevantes que mudaram. Reutilize padrões existentes. Antes de editar, registre plano, arquivos afetados e estratégia de reversão. Faça alterações pequenas, teste com backend simulado por padrão, preserve funcionalidades e registre evidências (comando, código de saída, resultado e arquivos). Não invente resultados. Não faça commit/push sem autorização. Atualize STATUS.json, IMPLEMENTACAO.md, DECISOES.md, TESTES.md, PENDENCIAS.md e CONTINUAR.md atomicamente ao concluir cada unidade. Se bloqueado, registre causa, tentativa, próxima ação e dependências afetadas; avance apenas em tarefas independentes seguras.

## Implementação
Adaptar SendInput com DPI e desktop virtual incluindo coordenadas negativas; modos absoluto, relativo e precisão. Implementar movimento, clique esquerdo/direito/central, duplo, arraste, scroll vertical/horizontal, punho de descanso. Usar transições down/up e registrar apenas entradas próprias. Injeção real bloqueada até fase 08.

## Critérios de aceite
Testes com backend falso de limites, monitores, clique único por gesto, arraste e liberação em falha.

## Saída
Registrar evidências e estado real: concluída, parcial ou bloqueada. Atualizar o checkpoint antes de avançar.
