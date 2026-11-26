# Fase 15 — Otimização e diagnóstico

## Protocolo obrigatório de execução
Leia `00_ORQUESTRADOR.md` e `progresso/CONTINUAR.md` antes de trabalhar. Use a raiz local real da NIA; não troque branch nem descarte alterações. Verifique o checkpoint e apenas os arquivos relevantes que mudaram. Reutilize padrões existentes. Antes de editar, registre plano, arquivos afetados e estratégia de reversão. Faça alterações pequenas, teste com backend simulado por padrão, preserve funcionalidades e registre evidências (comando, código de saída, resultado e arquivos). Não invente resultados. Não faça commit/push sem autorização. Atualize STATUS.json, IMPLEMENTACAO.md, DECISOES.md, TESTES.md, PENDENCIAS.md e CONTINUAR.md atomicamente ao concluir cada unidade. Se bloqueado, registre causa, tentativa, próxima ação e dependências afetadas; avance apenas em tarefas independentes seguras.

## Implementação
Medir baseline e incremento de CPU total, RAM do conjunto de processos, FPS efetivo e latência mediana/p95; documentar hardware e método. Perfis econômico 640x480 15–20 FPS uma mão, equilibrado 30 FPS duas mãos, desempenho até 720p conforme hardware. Reduzir frequência ociosa, descartar frames antigos, lazy load, limitar preview. Metas indicativas CPU adicional 10 pontos percentuais, RAM 250 MB, latência mediana 80 ms; não falsificar resultados.

## Critérios de aceite
Relatório comparativo, testes prolongados, vazamentos, desativado sem worker/câmera e degradação adaptativa.

## Saída
Registrar evidências e estado real: concluída, parcial ou bloqueada. Atualizar o checkpoint antes de avançar.
