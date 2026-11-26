# Fase 01 — Auditoria e compatibilidade

## Protocolo obrigatório de execução
Leia `00_ORQUESTRADOR.md` e `progresso/CONTINUAR.md` antes de trabalhar. Use a raiz local real da NIA; não troque branch nem descarte alterações. Verifique o checkpoint e apenas os arquivos relevantes que mudaram. Reutilize padrões existentes. Antes de editar, registre plano, arquivos afetados e estratégia de reversão. Faça alterações pequenas, teste com backend simulado por padrão, preserve funcionalidades e registre evidências (comando, código de saída, resultado e arquivos). Não invente resultados. Não faça commit/push sem autorização. Atualize STATUS.json, IMPLEMENTACAO.md, DECISOES.md, TESTES.md, PENDENCIAS.md e CONTINUAR.md atomicamente ao concluir cada unidade. Se bloqueado, registre causa, tentativa, próxima ação e dependências afetadas; avance apenas em tarefas independentes seguras.

## Implementação
Mapear somente áreas relevantes da NIA local: runtime Python, UI, registro de apps, Dock, ferramentas, permissões, câmera, IPC, persistência, testes e alterações locais. Obter AirMouse de https://github.com/Rcidshacker/airmouse em área isolada; registrar commit, licença efetiva e dependências. Não copiar código sem autorização de licença verificável.

## Critérios de aceite
Mapa de integração com caminhos reais, baseline de testes e recursos, inventário de licenças e decisão de compatibilidade.

## Saída
Registrar evidências e estado real: concluída, parcial ou bloqueada. Atualizar o checkpoint antes de avançar.
