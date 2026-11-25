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


## 2026-11-23T22:29:56.762125-03:00 — Programa EVOLUCAO-NIA

Auditoria: contratos reais documentados em EVOLUCAO-NIA/registros/01-INVENTARIO.md. Etapa 02: .gitignore, indice Git autorizado e eventuais regressoes confirmadas. Etapa 03: catalogo_habilidades e ponte existente em main, sem motor paralelo. Etapa 04: TaskRunner existente. Nenhuma alteracao de produto nesta auditoria.

## 2026-11-24 — Avaliação da Central

| Arquivo | Contrato | Mudança | Risco | Teste |
|---|---|---|---|---|
| `tests/test_interface_canvas.py` | `settle(app)` espera fixa | espera condicional por `motion.State.Stopped` | baixo; asserção inalterada | teste isolado com animação 1500 ms |
| `ui.py:4015-4017,5522` | `_lembrete_timer` rearmado com `QTimer.singleShot` (órfão) | usar o timer filho com `start()` | baixo | inspeção de `isActive()`/conexão |
| `core/config_dashboard.py` | página Integrações com 2 segmentos | 3º segmento "Serviços externos" (lazy) | médio: layout Qt | testes Qt offscreen |
| `core/credenciais_integracoes.py` (novo) | nenhum | Windows Credential Manager + JSON só com campos não secretos | médio: sem keyring em Linux | testes com store falso |
| `.opencode/safe-evolution/*.md` | estado persistente | registrar rodada | nenhum | revisão manual |

Fora de impacto: `TOOL_DECLARATIONS`, políticas de permissão, dock, voz,
núcleo visual, provedores de IA e dados locais do usuário.

## Rodada 15 — limpeza de código morto

| Alvo | Contrato/estado | Mudança | Risco | Validação |
|---|---|---|---|---|
| `EVOLUCAO-NIA/` (201 arquivos, ~984 KB) | diretório ignorado pelo Git (`.gitignore:53`), 0 arquivos versionados, 0 referências em `.py` | exclusão total, sem backup, aprovada pelo dono | **Alto e irreversível**: sem recuperação via Git | `Test-Path`, `git status`, testes de sanidade |
| Referências históricas em `.opencode/safe-evolution/*.md` | registros de rodadas antigas | nenhuma edição retroativa; apenas nota de que os caminhos não existem mais | baixo, apenas documental | leitura dos state files |
| Candidatos AST (defs/imports) | 110 definições sem referência direta; 1 import real suspeito | nenhuma remoção em bloco; triagem individual | alto: `getattr`/strings/callbacks de framework | grep de strings + leitura + testes |
| Demais módulos órfãos (`logs/canvas_qa.py`, `cache/preview_appearance.py`, `memory/config_manager.py`, `actions/system_monitor.py`, `core/installer.py`) | não importados pelo produto | **aguardando decisão do dono** | médio: podem ser ferramentas manuais | inventário + confirmação |

Fora de impacto nesta rodada: produto, dados de perfil, credenciais, testes e
todas as mudanças locais preexistentes fora de `EVOLUCAO-NIA/`.
