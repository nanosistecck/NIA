# Mapa de impacto — rodada 13 (CRUD completo da Agenda)

| Modulo/arquivo | Contrato existente | Mudanca necessaria | Risco | Teste de compatibilidade |
|---|---|---|---|---|
| `core/agenda.py` | `criar`, `editar`, `excluir`, `concluir`, `cancelar`, `listar`, `proximo` | Validar titulo/tipo/data/estado em `editar()` e `criar()`; `reabrir()` | Medio: pode rejeitar dados antes aceitos | testes puros de validacao |
| `core/comandos_agenda.py` | ramos de criar/mover/editar(concluir/cancelar/excluir)/listar | Novos ramos: renomear, tipo, notas, reabrir | Medio: pode capturar frases do Canvas | testes de parser e rota |
| `core/interface_agenda.py` | formulario so adiciona; `txt_compromissos` somente leitura | lista clicavel com `id`, campos notas/estado, botoes Salvar/Cancelar/Concluir/Reabrir/Excluir | Medio: layout e selecao | captura offscreen + testes Qt |
| `main.py` | `_processar_pedido_agenda` ja aplica edicoes | Aplicar novos campos e mensagens; atualizar card | Baixo | testes de rota |
| `ui.py` | ponte `_atualizar_cartao_agenda` | Nenhuma mudanca prevista | Nenhum | testes existentes |
| `.opencode/safe-evolution/*.md` | estado persistente | registrar rodada 13 | Nenhum | revisao manual |

Fora de impacto: planos, lembretes, clima, fala, PR #4 e dados de runtime do WhatsApp.
