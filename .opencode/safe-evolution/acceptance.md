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

## Correcoes encontradas pelo TDD

- `interpretar` devolvia UTC (15h viraria 18h) → convertido para `America/Sao_Paulo`.
- `resolver_alvo` comparava "amanhã" acentuado com texto normalizado → corrigido.
- `QDateEdit`/`QTimeEdit` ausentes no import da janela → corrigido.
- Cards Hoje/Agenda nasciam sobrepostos em (0,0) → `arrange()` ao posicionar painéis.
- Dashboard quebrava com `host=None` → acesso protegido.
