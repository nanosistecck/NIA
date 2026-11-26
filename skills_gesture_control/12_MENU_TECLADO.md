# Fase 12 — Menu radial e teclado

## Protocolo obrigatório de execução
Leia `00_ORQUESTRADOR.md` e `progresso/CONTINUAR.md` antes de trabalhar. Use a raiz local real da NIA; não troque branch nem descarte alterações. Verifique o checkpoint e apenas os arquivos relevantes que mudaram. Reutilize padrões existentes. Antes de editar, registre plano, arquivos afetados e estratégia de reversão. Faça alterações pequenas, teste com backend simulado por padrão, preserve funcionalidades e registre evidências (comando, código de saída, resultado e arquivos). Não invente resultados. Não faça commit/push sem autorização. Atualize STATUS.json, IMPLEMENTACAO.md, DECISOES.md, TESTES.md, PENDENCIAS.md e CONTINUAR.md atomicamente ao concluir cada unidade. Se bloqueado, registre causa, tentativa, próxima ação e dependências afetadas; avance apenas em tarefas independentes seguras.

## Implementação
Criar overlay radial leve com seleção direcional e pinça, cancelamento e submenus; suspender gestos concorrentes. Teclado ABNT2 com acentos, números, caracteres especiais, backspace, enter, espaço, seleção por permanência opcional. Preservar foco do destino, verificar mudança de janela, integrar ditado existente se disponível; não registrar texto digitado.

## Critérios de aceite
Testes de seleção, cancelamento, foco, Unicode, layout, múltiplos monitores e ausência de ações duplicadas.

## Saída
Registrar evidências e estado real: concluída, parcial ou bloqueada. Atualizar o checkpoint antes de avançar.
