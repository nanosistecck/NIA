# PROJECT_MAP — NIA Adaptive Learning Engine (F00)

Data: 2026-11-26. Branch: `superInteligenciaNIA-NiaSDK`, HEAD `5de8fe4`. Baseline: ver `progress/baseline_pytest.log` e `baseline_exit.txt`.

## Estado do Git

- Working tree: apenas `NIA_Adaptive_Learning/` (pacote de especificações) como untracked; preservado.
- Nenhum commit, push, branch, stash ou exclusão realizado nesta F00.
- Convenção Safe Evolution lida em `.opencode/safe-evolution/*.md`; `.opencode/autonomous-builder/` não existe.

## Mapa real (caminhos e símbolos)

### Entrada, roteamento e executor (REUTILIZAR)

| Arquivo | Símbolos | Papel |
|---|---|---|
| `main.py` | `NiaLive._execute_tool`, `_autorizar_ferramenta`, `_executar_ferramenta_local`, `_olhar_e_clicar`, `interrupt` | Única porta de ferramentas; voz/chat/Canvas/remoto. |
| `core/capability_gateway.py` | `CapabilityGateway.validar/executar`, `Solicitacao`, `ResultadoGateway`, `Cancelamento` | Validação/correlação/timeout antes do executor. |
| `core/contexto_ferramentas.py` | `ContextoFerramentas`, `AcaoTipada`, `ResultadoTipado` | Ação tipada ativa, TTL, conclusão/cancelamento. |
| `core/permissoes_ferramentas.py` | `preparar`, `confirmar`, `usar`, `revogar`, `verificar`, `validar_caminho` | Consentimento por hash, token com prazo, redação de logs. |
| `core/catalogo_habilidades.py` | `Habilidade`, `registrar_modulo`, `executar_modulo`, `definir_origem` | Catálogo único e despacho de módulos. |
| `core/registro_aplicativos.py` | `DescritorApp`, `registrar`, `todos`, `por_id` | Descoberta declarativa para dock/Central. |
| `core/roteador_tarefas.py` | `decidir`, `Requisitos`, `Decisao` | Escolha de provedor/modelo por requisitos. |
| `core/llm_router.py` | `Router`, `KeyPool`, `executar_fallback` | Fallback de provedores e chaves. |

### Conhecimento, pesquisa e memória (REUTILIZAR / EVOLUIR)

| Arquivo | Símbolos | Classificação |
|---|---|---|
| `core/aprendizado.py` | `Aprendizado.aprender/corrigir/esquecer/resolver`, `definir_preferencia` | Evoluir: associações frase→capacidade e preferências; não é procedimento. |
| `core/motor_conhecimento.py` | `MotorConhecimento.registrar/revisar/integrar_canvas/excluir/buscar` | Evoluir: conclusões, fontes e revisões; base para knowlege engine. |
| `core/indice_local.py` | `IndiceLocal`, FTS5/fallback | Reutilizar: índice local com citações. |
| `core/busca_fontes.py` | `planejar_pedido`, `buscar`, `contexto_minimo`, `filtrar_referencias` | Reutilizar: busca local e filtro de referências. |
| `actions/web_search.py` | `web_search`, `_research`, `_ddg_search`, `_gemini_search` | Reutilizar: pesquisa externa com provedores existentes. |
| `memory/memory_manager.py` | `load_memory`, `update_memory`, `remember`, `forget` | Reutilizar: memória de perfil (não substituir). |
| `memory/diario.py` | `anotar`, `ler`, `procurar`, `resumo_para_o_cerebro` | Reutilizar: diário local. |
| `core/memoria_sqlite.py` / `core/memoria_sqlite_adapter.py` | `MigradorMemoria`, `MemoriaSQLite` | Reutilizar padrão de migração/adapter; procedimentos terão DB próprio e separado. |

### Controle, observação e colaboração (REUTILIZAR)

| Arquivo | Símbolos | Papel |
|---|---|---|
| `core/controle_sessao.py` | `SessaoControle`, `EstadoControle`, `EventoControle`, `TokenControle`, `controle_de_tela` | Gate fail-closed, pausa/retomada/parada, ESC. |
| `core/overlay_controle/` | `GerenciadorOverlay`, `JanelaBorda`, `JanelaBanner`, `JanelaControles`, `JanelaAtividades` | Overlay visual por monitor; reutilizar com cores por modo. |
| `actions/usar_computador.py` | `usar_computador`, `_executar`, `FreioEsc` | Laço real de mouse/teclado e cancelamento. |
| `actions/tela_visao.py` | `olhar`, `_grab`, `janela_em_frente` | Captura autorizada/visão; usar sob demanda. |
| `core/segundo_plano.py` | `ligado`, `ligar`, `desligar`, `pedir_para_aparecer` | Modo segundo plano; respeitar ao mostrar UI. |

### SDK, plugins e workers (REUTILIZAR)

| Arquivo | Símbolos | Classificação |
|---|---|---|
| `core/plugin_sdk.py` | `Resposta`, `Status`, `manifesto_padrao`, `validar_manifesto`, `MockPlugin` | Reutilizar/adaptar sem novo SDK. |
| `core/fabrica_plugins.py` | `construir` | Reutilizar para lacunas de ferramentas (sem instalação automática). |
| `core/config_dashboard.py` | `TaskRunner`, `PainelLaboratorio` integração | Reutilizar padrão de workers com cancelamento. |
| `core/tema.py`, `core/nia_ui_kit.py`, `core/frame_nativo.py` | tokens, componentes, janela nativa | Reutilizar para UI. |
| `ui.py` | `_build_dock`, `_executar_dock_pela_central`, `NiaUI` | Integrar Central de Aprendizado ao dock/Central. |

## Decisão arquitetural F00

Criar `core/aprendizado_adaptativo/` com módulos pequenos e contratos tipados; **nenhum** motor de memória, controle, pesquisa ou executor paralelo. A persistência procedural será SQLite própria em `~/.nia/` com migração idempotente e backup, isolada da memória de perfil existente (domínio diferente, não concorrente). Todas as ações reais passam por `CapabilityGateway` + `permissoes_ferramentas` + executor de `main.py`. Observação só dentro de `SessaoControle` com overlay visível; ESC cancela e revoga lease.

## Fora de escopo / limitações

- Credenciais reais, contas externas, downloads e execução de código aprendido.
- Captura contínua de teclado, desktop seguro, OTP/senhas.
- Testes físicos com Windows interativo, DPI e hardware quando indisponíveis.
- Nenhum commit/push automático nesta rodada.
