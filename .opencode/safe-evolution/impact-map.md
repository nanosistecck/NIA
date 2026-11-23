# Mapa de impacto — rodada 11 (Agenda)

| Modulo/arquivo | Contrato existente | Mudanca necessaria | Risco | Teste de compatibilidade |
|---|---|---|---|---|
| `core/agenda.py` (novo) | — | Persistencia atômica por perfil em `~/.nia/agenda.json`, override `NIA_AGENDA` | Baixo | testes puros de CRUD e proximo compromisso |
| `core/comandos_agenda.py` (novo) | — | Parser de pedidos de agenda (puro, sem Qt) | Medio: pode capturar pedido de lembrete/plano | testes de intencao e rota |
| `core/interface_agenda.py` (novo) | — | Janela `AgendaWindow` com grade mensal e painel do dia | Medio: layout/DPI | captura offscreen e testes Qt |
| `core/interface_canvas.py` | `CanvasStage.hoje_host`, `_brief_geometries`, `arrange` | Novo `agenda_host` abaixo do Hoje, sinal de visibilidade | Medio: sobreposicao de cards | teste de geometria e fechamento |
| `ui.py` | `_build_dock`, `_abrir_planos`, `_show_canvas_brief`, `on_text_command` | Botao AGENDA, abertura da janela, atualizacao do card | Medio | testes de dock e ponte Qt |
| `main.py` | `_executar_frase_habilidade`, `_saudar_na_abertura`, `_falar_resumo` | Rota de comandos de agenda e lembrete contextual | Medio: pode roubar outras rotas | testes de rota e saudacao |
| `config/interface.json` | preferencia `cards.hoje` | nova chave `cards.agenda` (padrao visivel) | Baixo | teste de persistencia |
| `.opencode/safe-evolution/*.md` | estado persistente | registrar rodada 11 | Nenhum | revisao manual |

Fora de impacto: planos, lembretes atuais, formato de dados, clima, fala e PR #4.
