# Fase 05 — Reconhecimento das mãos

## Protocolo obrigatório de execução
Leia `00_ORQUESTRADOR.md` e `progresso/CONTINUAR.md` antes de trabalhar. Use a raiz local real da NIA; não troque branch nem descarte alterações. Verifique o checkpoint e apenas os arquivos relevantes que mudaram. Reutilize padrões existentes. Antes de editar, registre plano, arquivos afetados e estratégia de reversão. Faça alterações pequenas, teste com backend simulado por padrão, preserve funcionalidades e registre evidências (comando, código de saída, resultado e arquivos). Não invente resultados. Não faça commit/push sem autorização. Atualize STATUS.json, IMPLEMENTACAO.md, DECISOES.md, TESTES.md, PENDENCIAS.md e CONTINUAR.md atomicamente ao concluir cada unidade. Se bloqueado, registre causa, tentativa, próxima ação e dependências afetadas; avance apenas em tarefas independentes seguras.

## Implementação
Adaptar HandLandmarker, 21 pontos por mão, timestamps monotônicos, normalização por escala da palma, lateralidade estável, confiança e filtro One Euro. Implementar histerese, debounce, prioridade, rearmamento e perda de rastreamento. Separar classificação de execução.

## Critérios de aceite
Fixtures sintéticas para uma/duas mãos, cruzamento, ruído, oclusão, pinça e gestos ambíguos; nenhuma entrada real.

## Saída
Registrar evidências e estado real: concluída, parcial ou bloqueada. Atualizar o checkpoint antes de avançar.
