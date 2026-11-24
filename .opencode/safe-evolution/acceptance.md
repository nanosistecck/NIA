# Criterios de aceite e evidencias — rodada 11 (Agenda)

| Requisito | Teste | Evidencia | Estado |
|---|---|---|---|
| Persistencia atomica por perfil | `tests/test_agenda.py` (8) | JSON em `~/.nia/agenda.json`, `.tmp` removido | OK |
| Proximo compromisso e vencidos | `test_vencido_aparece_na_lista_mas_nao_no_proximo` | vencido fora do proximo | OK |
| Interpretacao em fuso local | `test_interpretar_data_e_hora` | 15h nao vira 18h | OK |
| Comandos e alvo (titulo/data/proximo/ambiguo) | `tests/test_comandos_agenda.py` (16) | 5 frases ambiguas/validas | OK |
| Rota chat/voz e bom dia | `tests/test_agenda_rota.py` (4) | `CH.reconhecer` nao chamado | OK |
| Janela e botao no dock | `tests/test_interface_agenda.py` (2) | clique abre janela; dia e preparo no painel | OK |
| Card no Canvas principal | `tests/test_agenda_card.py` (1) | fechar persiste; comando reabre | OK |
| Dashboard com checkbox de visibilidade | `tests/test_config_dashboard.py` | host None protegido | OK |
| Suite completa | `pytest -q` | **685 passed, 0 failed, exit 0** | OK |
| Sintaxe e diff | `compileall` / `git diff --check` | limpos | OK |

## Evidencias visuais (interface executada, offscreen)

- `logs/captura_agenda.png` — janela Agenda: grade mensal de novembro/2026,
  dia atual em ciano, dias com compromisso em borda verde, painel com
  "Consulta médica · preparar às 08:45". Inspecionada.
- `logs/captura_agenda_card.png` — Canvas principal: card HOJE acima e
  PRÓXIMO COMPROMISSO abaixo, com "Consulta médica / Tue 24/11 09:00 ·
  preparar às 08:45" e botão ×. Inspecionada.
- Capturas em `logs/` nao sao versionadas (`.gitignore`).

## Revisao final de branch (servico gratuito)

- Revisor `opencode/tidepool-alpha-free` avaliou `cd72528..b33cb01`.
- 1 Critical: card aparecia sem compromisso → corrigido e verificado
  (sem compromisso: `agenda_visivel=False`; com: `True`).
- 3 Important: mensagem "Card exibido" sem compromisso; "ambiguo" com agenda
  vazia; card nao atualizava apos mudanca por chat → corrigidos.
- 1 Minor: mes do calendario em ingles → corrigido para portugues.
- 4 testes novos cobrem os achados; suite final **689 passed, 0 failed, exit 0**.
- Commit de correcao: `caa9b90`.
- Evidencia: `logs/captura_agenda_final.png` inspecionada.

## Rodada 12 — testes reais do dono e correcoes

| Erro relatado/encontrado | Correcao | Evidencia |
|---|---|---|
| "adicione/mude/exclua" caiam no Canvas | Agenda priorizada e detector restringido a termos de agenda; frases com "card" vao ao Canvas | testes reais e 18 testes novos |
| `excluir` inexistente | `AG.excluir` + acao no parser | "Compromisso excluído: Revisão dezembro." |
| titulo inexistente caira no proximo | referencia explicita nao casa → "Não encontrei..." | teste dedicado |
| "Compromisso concluir:" | mensagens por acao (concluído/cancelado/excluído/movido/preparo) | teste dedicado |
| listagens sem filtro e sem proximo | `filtrar_por_periodo` (hoje/amanha/proximo mes/semana/proxima semana) + resumo do proximo | teste dedicado |
| "bom dia" sem saudacao | saudacao conforme faixa (bom dia/tarde/noite) + resumo | 3 parametros |
| Varredura extra: titulo com data, dia do mes, ambiguidade, "exclua todos" | corrigidos | 18 testes + 2 varreduras reais |
| Suite final | `pytest -q` | **707 passed, 0 failed, exit 0** |
| Sintaxe | `compileall` / `git diff --check` | limpos |

Pendencia menor observada: "desfaça a exclusão" cai no Canvas ("Abra um plano..."),
pois nao existe lixeira/desfazer de exclusao na Agenda — fora de escopo.

## Rodada 13 — CRUD completo

| Requisito | Evidencia | Estado |
|---|---|---|
| Validacao em `editar`/`criar` e `reabrir` | 5 testes em `tests/test_agenda_crud.py` | OK |
| Renomear/tipo/notas/reabrir por voz | 4 testes de parser + 3 de rota | OK |
| Erro de validacao nao cai no modelo | teste `test_erro_de_validacao_nao_cai_no_modelo` | OK |
| Janela: selecionar, editar todos os campos, concluir, reabrir, excluir com confirmacao | 5 testes em `tests/test_interface_agenda_crud.py` | OK |
| Builder check: 5 perguntas respondidas no spec; bug de tratamento de erro corrigido | spec + teste | OK |
| Regressao de rota: "Renomeie o produto..." continua no Canvas | teste existente verde | OK |
| Suite final | `pytest -q` → **724 passed, 0 failed, exit 0** | OK |
| Sintaxe | `compileall` / `git diff --check` limpos | OK |

Evidencia visual: `logs/captura_agenda_crud.png` inspecionada — formulario com
titulo, data, hora, tipo, preparo, notas e estado preenchidos, botoes
Salvar/Cancelar/Concluir/Reabrir/Excluir e grade com o dia selecionado.

## Rodada 14 — frase real "adicione na agenda"

| Requisito | Teste | Evidencia | Estado |
|---|---|---|---|
| "adicione na agenda buscar a maria as 21:06" cria compromisso | `tests/test_agenda_frase_real.py` (6) | `Compromisso salvo: buscar a maria. Proximo compromisso: buscar a maria as 21:06.` | OK |
| Hora sem data: hoje se futura, amanha se passou | `test_hora_passada_vai_para_amanha` | 21:06 passou → 24/11 | OK |
| Data explicita respeitada | `test_com_data_explicita_respeita_data` | amanha mantido | OK |
| Sem hora continua perguntando | `test_sem_hora_continua_perguntando` | mantido | OK |
| "adicione um card" continua no Canvas | `test_adicionar_card_continua_no_canvas` | `tratado=False` | OK |
| Rota nao cai no Canvas | `test_rota_cria_sem_cair_no_canvas` | sem "Abra um plano" | OK |
| Suite final | `pytest -q` | **730 passed, 0 failed, exit 0** (duas execucoes) | OK |
| Sintaxe | `compileall` / `git diff --check` | limpos | OK |

## Correcoes encontradas pelo TDD

- `interpretar` devolvia UTC (15h viraria 18h) → convertido para `America/Sao_Paulo`.
- `resolver_alvo` comparava "amanhã" acentuado com texto normalizado → corrigido.
- `QDateEdit`/`QTimeEdit` ausentes no import da janela → corrigido.
- Cards Hoje/Agenda nasciam sobrepostos em (0,0) → `arrange()` ao posicionar painéis.
- Dashboard quebrava com `host=None` → acesso protegido.
