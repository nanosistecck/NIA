# Cenários de integração A–L — rastreio de evidências

Cenário | Fluxo exigido | Testes/evidências | Resultado
---|---|---|---
A — Aprendizado | ensinar comando, reiniciar, executar | `tests/test_aprendizado.py`, `tests/test_integracao_aprendizado.py` (persistência em arquivo e rota real após reconstruir instância) | coberto; sem conexão com provedor
B — Memória histórica | registrar estudo, reiniciar, recuperar por data/assunto | `tests/test_memoria_sqlite.py`, `tests/test_memoria_sqlite_adapter.py`, `tests/test_motor_conhecimento.py` | coberto com dados sintéticos
C — Conhecimento | recuperar pesquisa, lacunas, revisões, fontes | `tests/test_motor_conhecimento.py`, `tests/test_busca_fontes.py`, `tests/test_indice_local.py` | coberto; índice injetado/fixture
D — Automação | criar rotina, persistir, reiniciar, executar | `tests/test_rotinas.py`, `tests/test_rotinas_recorrencia.py`, `tests/test_fluxo_executavel.py`, `tests/test_integracao_agendador_outbox.py` | coberto com relógio controlado
E — Eventos | evento controlado do WhatsApp → notificação | `tests/test_barramento_eventos.py`, `tests/test_outbox_notificacoes.py`, `tests/test_integracao_notificacoes.py`; `REVIEW_EXISTING.md` | coberto com eventos simulados; envio real não exercitado
F — Plugins | instalar, executar, atualizar, restaurar, desinstalar `.niateck` | `tests/test_prontidao_niateck.py`, `tests/test_gestor_plugins.py`, `tests/test_atualizador_local.py`, `tests/test_niateck.py`, `tests/test_fabrica_plugins.py` | coberto com fixture local
G — Interface | abrir ferramentas, navegar, redimensionar, controles | `tests/test_nia_ui_kit.py`, `tests/test_integracao_ui_kit_dashboard.py`, `tests/test_config_dashboard.py`, `UI_PROBE_*.json` + 12 capturas | coberto em 4 resoluções x 3 escalas
H — Recuperação | interrupção durante tarefa | `test_gestor_plugins.py::test_recuperacao_reconcilia_staging_interrompido`, `test_atualizador_local.py::test_interrupcao_e_recuperada_pelo_estado`, `test_fluxo_executavel.py` | coberto
I — Falha de provedor | indisponibilidade e fallback | `tests/test_llm_router.py`, `tests/test_planejamento_provedor_canvas.py` | coberto com falhas simuladas
J — Segundo plano | recolher interface e manter tarefas autorizadas | `tests/test_autonomia_segundo_plano.py`, `tests/test_timers_interface.py`, `tests/test_janelas_ferramentas.py` | coberto; bandeja física não acionada
K — Segurança | executar habilidade sem permissão | `tests/test_politica_confianca.py`, `tests/test_permissoes_legadas.py`, `tests/test_gateway_integrado.py` | coberto
L — Preservação | funcionalidades anteriores após correções | suíte completa `pytest tests -q` | 1005 passed no baseline; final a confirmar após correções

Nota: cenários que dependem de credenciais, hardware ou upstream real são
executados com mocks/fixtures e rotulados como simulação, não validação real.
