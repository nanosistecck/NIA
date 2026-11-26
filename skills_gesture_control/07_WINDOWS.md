# Fase 07 — Controle do Windows

## Protocolo obrigatório de execução
Leia `00_ORQUESTRADOR.md` e `progresso/CONTINUAR.md` antes de trabalhar. Use a raiz local real da NIA; não troque branch nem descarte alterações. Verifique o checkpoint e apenas os arquivos relevantes que mudaram. Reutilize padrões existentes. Antes de editar, registre plano, arquivos afetados e estratégia de reversão. Faça alterações pequenas, teste com backend simulado por padrão, preserve funcionalidades e registre evidências (comando, código de saída, resultado e arquivos). Não invente resultados. Não faça commit/push sem autorização. Atualize STATUS.json, IMPLEMENTACAO.md, DECISOES.md, TESTES.md, PENDENCIAS.md e CONTINUAR.md atomicamente ao concluir cada unidade. Se bloqueado, registre causa, tentativa, próxima ação e dependências afetadas; avance apenas em tarefas independentes seguras.

## Implementação
Criar catálogo tipado e allowlist de ações: janelas, desktops, navegação, edição, mídia, volume, brilho suportado, captura e slides. Usar APIs existentes ou SendInput; detectar indisponibilidade e UIPI. Ações críticas exigem confirmação deliberada; não expor shell arbitrário.

## Critérios de aceite
Testes simulados de atalhos, modificadores, conflitos, ações indisponíveis e confirmação; sem execução real até fase 08.

## Saída
Registrar evidências e estado real: concluída, parcial ou bloqueada. Atualizar o checkpoint antes de avançar.
