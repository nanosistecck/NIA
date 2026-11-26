# Fase 04 — Integração da webcam

## Protocolo obrigatório de execução
Leia `00_ORQUESTRADOR.md` e `progresso/CONTINUAR.md` antes de trabalhar. Use a raiz local real da NIA; não troque branch nem descarte alterações. Verifique o checkpoint e apenas os arquivos relevantes que mudaram. Reutilize padrões existentes. Antes de editar, registre plano, arquivos afetados e estratégia de reversão. Faça alterações pequenas, teste com backend simulado por padrão, preserve funcionalidades e registre evidências (comando, código de saída, resultado e arquivos). Não invente resultados. Não faça commit/push sem autorização. Atualize STATUS.json, IMPLEMENTACAO.md, DECISOES.md, TESTES.md, PENDENCIAS.md e CONTINUAR.md atomicamente ao concluir cada unidade. Se bloqueado, registre causa, tentativa, próxima ação e dependências afetadas; avance apenas em tarefas independentes seguras.

## Implementação
Reutilizar serviço de câmera existente quando possível; caso contrário coordenar posse exclusiva ou compartilhamento eficiente. Enumerar dispositivos, selecionar, espelhar preview sem inverter lateralidade lógica, tratar desconexão e câmera ocupada. Capturar frame mais recente, liberar recursos ao parar.

## Critérios de aceite
Testes de câmera ausente, ocupada, troca, desconexão e encerramento; teste físico pendente quando necessário.

## Saída
Registrar evidências e estado real: concluída, parcial ou bloqueada. Atualizar o checkpoint antes de avançar.
