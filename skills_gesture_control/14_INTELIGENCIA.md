# Fase 14 — Integração com inteligência e Canvas

## Protocolo obrigatório de execução
Leia `00_ORQUESTRADOR.md` e `progresso/CONTINUAR.md` antes de trabalhar. Use a raiz local real da NIA; não troque branch nem descarte alterações. Verifique o checkpoint e apenas os arquivos relevantes que mudaram. Reutilize padrões existentes. Antes de editar, registre plano, arquivos afetados e estratégia de reversão. Faça alterações pequenas, teste com backend simulado por padrão, preserve funcionalidades e registre evidências (comando, código de saída, resultado e arquivos). Não invente resultados. Não faça commit/push sem autorização. Atualize STATUS.json, IMPLEMENTACAO.md, DECISOES.md, TESTES.md, PENDENCIAS.md e CONTINUAR.md atomicamente ao concluir cada unidade. Se bloqueado, registre causa, tentativa, próxima ação e dependências afetadas; avance apenas em tarefas independentes seguras.

## Implementação
Reutilizar dispatcher e permissões atuais; ferramenta agrupada gesture_control com ações abrir, ativar, desativar, pausar, retomar, status, calibrar, configurar, listar/configurar gestos, listar/selecionar perfis, câmeras e monitores, diagnóstico, treinamento e compacto. Validar schemas e respostas reais. Eventos de estado limitados; nunca enviar frames ao LLM. Integrar Canvas via APIs existentes para seleção, pan, zoom, arraste e contexto de card; não reescrever Canvas.

## Critérios de aceite
Testes de voz/texto via dispatcher, permissões negadas, estados reais, eventos e regressão do Canvas.

## Saída
Registrar evidências e estado real: concluída, parcial ou bloqueada. Atualizar o checkpoint antes de avançar.
