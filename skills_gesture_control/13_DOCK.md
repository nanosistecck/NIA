# Fase 13 — Dock e Central de Aplicativos

## Protocolo obrigatório de execução
Leia `00_ORQUESTRADOR.md` e `progresso/CONTINUAR.md` antes de trabalhar. Use a raiz local real da NIA; não troque branch nem descarte alterações. Verifique o checkpoint e apenas os arquivos relevantes que mudaram. Reutilize padrões existentes. Antes de editar, registre plano, arquivos afetados e estratégia de reversão. Faça alterações pequenas, teste com backend simulado por padrão, preserve funcionalidades e registre evidências (comando, código de saída, resultado e arquivos). Não invente resultados. Não faça commit/push sem autorização. Atualize STATUS.json, IMPLEMENTACAO.md, DECISOES.md, TESTES.md, PENDENCIAS.md e CONTINUAR.md atomicamente ao concluir cada unidade. Se bloqueado, registre causa, tentativa, próxima ação e dependências afetadas; avance apenas em tarefas independentes seguras.

## Implementação
Registrar ferramenta no catálogo existente, ícone de mão, abertura única, fixação opcional no Dock, modo compacto e segundo plano com indicador persistente e botão parar. Abrir interface não implica ativar câmera; fechar encerra por padrão, segundo plano somente por preferência explícita.

## Critérios de aceite
Testes de registro, abertura repetida, minimização, encerramento da NIA e ausência de processos órfãos.

## Saída
Registrar evidências e estado real: concluída, parcial ou bloqueada. Atualizar o checkpoint antes de avançar.
