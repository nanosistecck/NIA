# Matriz de rastreabilidade

Estados: NAO IMPLEMENTADO | IMPLEMENTADO PARCIALMENTE | IMPLEMENTADO SEM VALIDACAO |
FALHA IDENTIFICADA | EM CORRECAO | VALIDADO | BLOQUEADO POR DEPENDENCIA EXTERNA.

| ID | Requisito | Arquivos/símbolos | Integração no motor | UI | Voz/chat | Permissão | Testes/evidência | Problema | Correção | Estado |
|---|---|---|---|---|---|---|---|---|---|---|
| R01 | Auditoria e proteção | `NIA_CORE_EVOLUTION/state/INVENTORY.md`, `tools/perf_probe.py` | baseline e sondas | — | — | — | 1005 passed baseline | nenhum | — | VALIDADO |
| R02 | Contrato universal | `core/catalogo_habilidades.py`, `core/registro_aplicativos.py`, `core/contrato_universal.py` | sincronização de descritores | Central | reconhecedor local | declarativa | `test_contrato_universal.py`, `test_integracao_contrato_registro.py` | nenhum | — | VALIDADO |
| R03 | Capability Gateway | `core/capability_gateway.py`, `main.py:_execute_tool` | validação antes do executor | — | 4 origens | PF | `test_gateway_integrado.py`, `test_capability_gateway.py` | nenhum | — | VALIDADO |
| R04 | Plugin SDK | `core/plugin_sdk.py` | contrato injetável | sob demanda | — | transporte autenticado | `test_plugin_sdk.py` | nenhum | — | VALIDADO |
| R05 | Formato .niateck | `core/niateck.py` | inspeção antes de staging | — | — | hashes/assinatura | `test_niateck.py`, `test_prontidao_niateck.py` | nenhum | — | VALIDADO |
| R06 | Gerenciador de plugins | `core/gestor_plugins.py` | staging/ativar/reparar/remover | Central futura | — | confiança local | `test_gestor_plugins.py` | nenhum | — | VALIDADO |
| R07 | Aprendizado | `core/aprendizado.py`, `main.py:_habilidade_aprendida` | rota local após reconhecer | — | voz/chat | reavalia capacidade | `test_aprendizado.py`, `test_integracao_aprendizado.py` | nenhum | — | VALIDADO |
| R08 | Memória SQLite | `core/memoria_sqlite.py`, `core/memoria_sqlite_adapter.py` | adaptador opt-in | — | — | backup/perfis | `test_memoria_sqlite*.py` | nenhum | — | VALIDADO |
| R09 | Consolidação da memória | `core/consolidacao_memoria.py` | sobre registros explícitos | — | — | exclusão com índices | `test_consolidacao_memoria.py` | nenhum | — | VALIDADO |
| R10 | Motor de conhecimento | `core/motor_conhecimento.py`, `core/busca_fontes.py`, `core/indice_local.py` | Canvas por ID | Canvas | voz/chat | fontes autorizadas | `test_motor_conhecimento.py`, `test_busca_fontes.py` | nenhum | — | VALIDADO |
| R11 | Planos executáveis | `core/fluxo_executavel.py` | validação no gateway | — | — | aprovação/orçamento | `test_fluxo_executavel.py` | nenhum | — | VALIDADO |
| R12 | Agendador persistente | `core/rotinas.py` | agendador único | — | voz/chat | escopo de habilidade | `test_rotinas*.py` | nenhum | — | VALIDADO |
| R13 | Motor de eventos | `core/barramento_eventos.py` | fila limitada | — | — | dedupe | `test_barramento_eventos.py` | nenhum | — | VALIDADO |
| R14 | Notificações | `core/outbox_notificacoes.py`, `core/integracao_notificacoes.py`, `main.py` | injetado no agendador | painel/voz | voz | canais injetados | `test_outbox_notificacoes.py`, `test_integracao_notificacoes.py` | nenhum | — | VALIDADO |
| R15 | Segundo plano | `core/autonomia_segundo_plano.py`, `core/segundo_plano.py` | F9/sinal | bandeja | — | autorização | `test_autonomia_segundo_plano.py` | nenhum | — | VALIDADO |
| R16 | Segurança e isolamento | `core/politica_confianca.py`, `core/permissoes_ferramentas.py` | porte de ferramentas | diálogo de permissão | voz/chat | PF | `test_politica_confianca.py`, `test_permissoes*.py` | em auditoria | — | EM CORRECAO |
| R17 | UI Kit | `core/nia_ui_kit.py`, `core/config_dashboard.py` | painel Geral | sim | — | — | `test_nia_ui_kit.py`, capturas | em auditoria de resoluções | — | EM CORRECAO |
| R18 | Plugin Factory | `core/fabrica_plugins.py` | build local | — | — | fixture local | `test_fabrica_plugins.py` | upstream em desenvolvimento | — | BLOQUEADO POR DEPENDENCIA EXTERNA |
| R19 | Atualização | `core/atualizador_local.py` | staging/backup/rollback | — | — | sem git pull | `test_atualizador_local.py` | nenhum | — | VALIDADO |
| R20 | Homologação | `docs/nia-final-audit/*` | suíte completa | capturas | — | — | 1005 passed | em andamento | — | EM CORRECAO |
| RA01 | WhatsApp real | `actions/whatsapp_bridge.py`, `main.py` | polling/ação | botão dock | voz/chat | consentimento | `REVIEW_EXISTING.md` + testes | revisão documental | — | VALIDADO |
| RA02 | Microfone/voz | `core/audio_dispositivos.py`, `core/gemini_voice.py` | loop de voz | — | voz | — | testes de fala/interrupção | revisão documental | — | VALIDADO |
| RA03 | Câmera | `main.py` webcam/vision | ferramentas | janelas | voz/chat | confirmação | testes de visão | revisão documental | — | VALIDADO |
| RA04 | Tray/DPI | `ui.py`, `core/windows_frame.py` | bandeja/frame | sim | — | — | `test_windows_frame.py` | revisão documental | — | VALIDADO |
| RA05 | Provedores de IA | `core/llm_router.py` | fallback/chaves | Configurações | — | cofre | `test_llm_router.py` | revisão documental | — | VALIDADO |
| RA06 | Preflight | a criar | antes da inicialização | — | — | determinístico | a implementar | ausente | pendente | NAO IMPLEMENTADO |
