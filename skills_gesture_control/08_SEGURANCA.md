# Fase 08 — Segurança operacional

## Protocolo obrigatório de execução
Leia `00_ORQUESTRADOR.md` e `progresso/CONTINUAR.md` antes de trabalhar. Use a raiz local real da NIA; não troque branch nem descarte alterações. Verifique o checkpoint e apenas os arquivos relevantes que mudaram. Reutilize padrões existentes. Antes de editar, registre plano, arquivos afetados e estratégia de reversão. Faça alterações pequenas, teste com backend simulado por padrão, preserve funcionalidades e registre evidências (comando, código de saída, resultado e arquivos). Não invente resultados. Não faça commit/push sem autorização. Atualize STATUS.json, IMPLEMENTACAO.md, DECISOES.md, TESTES.md, PENDENCIAS.md e CONTINUAR.md atomicamente ao concluir cada unidade. Se bloqueado, registre causa, tentativa, próxima ação e dependências afetadas; avance apenas em tarefas independentes seguras.

## Implementação
Validar watchdog independente, hotkey global configurável Ctrl+Alt+F12, pausa por perda de mãos, câmera, IPC, sessão bloqueada e suspensão. Liberar somente entradas sintéticas próprias, testar falhas abruptas e evitar reativação automática. Exigir ativação explícita, indicador de câmera e consentimento. Não elevar privilégios nem contornar UAC.

## Critérios de aceite
Gate obrigatório antes de habilitar backend real: testes de emergência, falha e liberação; teste físico autorizado e supervisionado.

## Saída
Registrar evidências e estado real: concluída, parcial ou bloqueada. Atualizar o checkpoint antes de avançar.
