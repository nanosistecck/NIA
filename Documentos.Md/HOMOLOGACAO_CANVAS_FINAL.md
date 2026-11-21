# Homologação final do Canvas Infinito — revisão Prompt 06

Data: 21/11/2026 · Branch `CANVAS-INFINITO` · Perfil isolado (`NIA_PLANOS_DIR`) ·
Planos fictícios **Projeto dos lojistas** com **Público-alvo** e **Divulgação**.

## Ambiente e linha de base

- Windows 11 (10.0.26200), Python 3.12.14, PyQt6 6.12.1, pytest 9.2.0, `offscreen`.
- Antes de alterar nesta rodada: **374 testes passaram**. Nenhuma falha pré-existente.
- Mapa de referência: 41 cards e 40 conexões, janela 1280×820, núcleo em repouso.
- Suíte final: **383 testes passaram**; `compileall` e `git diff --check` limpos.

## Skills

Carregadas nesta revisão: `brainstorming`, `writing-plans`, `ui-ux-pro-max`,
`pyqt6-ui-designer`, `systematic-debugging`, `verification-before-completion`.
Indisponíveis: `awesome-design-skills` e `opencode-power-pack`. Lacuna: revisão estrutural
por etapa do `opencode-power-pack` não foi executada; substituída por TDD RED→GREEN,
suíte completa e verificação explícita.

## Resultado por área

| Área | Status | Cenário e evidência |
|---|---|---|
| Mapa e conexões | **Aprovado** | Botão **Conectar** inicia modo com origem destacada em verde e linha provisória tracejada; clique no destino cria vínculo; `Esc` cancela sem mudar mapa/histórico; `ConexaoItem` tem `ItemIsSelectable`, shape com traço de 14 px e contorno tracejado quando selecionado; linha acompanha movimento com zoom. `tests/test_conexao_ui.py` (7) |
| Escrita multilinha | **Aprovado** | `QTextEdit`, parágrafos/listas/acentos sobrevivem à troca de seleção e reabertura; uma operação de undo por sessão; sinais bloqueados ao carregar outro card. `tests/test_edicao_texto.py` (12) |
| Conversa com a NIA | **Aprovado** (com simulação) | Listar cards, ler texto, conexões com rótulo/direção, plano fechado por nome, restrito filtrado. `tests/test_consulta_canvas.py` (8). Botão **Perguntar à NIA sobre este card** ligado à casca real |
| Edição assistida | **Aprovado** (com simulação) | Lote estruturado, alvo capturado, conflito detectado contra estado vivo, resposta atrasada descartada, lote inválido sem aplicação. `tests/test_edicao_assistida_revisao.py` (8) |
| Janela, dock e núcleo | **Aprovado** | Testes anteriores de abertura/fechamento, âncora `bottom-right`, dock recolhido sem persistir preferência e retorno ao gerenciador (`test_nucleo_canvas.py`, `test_integracao_canvas.py`) |
| Fluxo integrado | **Aprovado** (Qt offscreen) | `tests/test_homologacao_final.py` (2): escrever → conectar pela UI → consultar texto e vínculo → destacar card pela ponte real |
| Desempenho | **Aprovado** com ressalvas | Ver tabela abaixo; CPU medida em janela curta não é estável |
| Voz real / STT | **Pendente** | Ambiente sem microfone/transcritor; transcrição final simulada nos testes |
| API/Ollama reais | **Pendente** | Nenhuma credencial/serviço; provedor simulado |
| Inspeção visual em desktop | **Pendente** | Execução homologada em `offscreen`; sem captura visual |
| Notificação com NIA fechada | **Pendente** | Depende de integração com SO (etapa própria) |
| Publicação real do Canvas | **Bloqueada** | Saída desativada; bloqueios validados com destino simulado |

## Correções realizadas nesta rodada

1. **Conectar cards existentes não funcionava.** Causa: `selectionChanged → _on_selection → selecionar()`
   desfazia a multisseleção; `ScrollHandDrag` impedia rubber-band e `ConexaoItem` não era
   selecionável. Solução: modo de conexão com origem fixa, linha provisória, `Esc` cancela,
   destino por clique, `ConexaoItem` selecionável com traço largo. Arquivo: `core/interface_mapa.py`.
   Verificação: `test_conexao_ui.py` RED→GREEN (6 falhas → 7 passos).
2. **Edição rápida em dois cards podia trocar o texto de destino.** Causa: sinal de texto
   atrasado podia chegar após a troca de seleção. Solução: `_fechar_sessao_texto()` sempre
   na troca e guarda de ID do comando contra o card atual. Arquivo: `core/interface_mapa.py`.
   Verificação: `test_duplas_edicoes_rapidas_em_cards_diferentes` estável na suíte final.
3. **Ponte da NIA para o estado vivo não existia no aplicativo** (só em testes). Causa:
   `main.py` chamava `ui.estado_canvas_vivo()`/`destacar_card()`, mas `NiaUI` não tinha
   esses métodos — conflito e resposta atrasada nunca eram detectados de fato. Solução:
   implementados em `ui.py`, com destaque apenas quando o plano correspondente está visível.
   Verificação: `test_pontes_reais_estado_e_destaque`.
4. **Faltava o botão de contexto da conversa.** Solução: **Perguntar à NIA sobre este card**
   em `CanvasEditor`, ligado a `NiaUI.perguntar_sobre_card`.
5. **Nenhuma remoção de código** — nenhuma função, sinal, atalho ou registro ficou sem uso.

## Desempenho — antes e depois

Condições: Windows 11, offscreen, 41 cards/40 conexões, 200 operações de pan/zoom,
10 ciclos abrir/fechar, núcleo em repouso.

| Métrica | Antes (Prompt 01) | Depois | Observação |
|---|---|---|---|
| 200 pan/zoom | 6,235 s | **2,063 s** | Sem reconstrução de cena (`montar` 1→1) |
| CPU durante pan/zoom | 47,6% | 100,0% | Janela curta; não comparável diretamente |
| RSS inicial → pan → 10 ciclos | 77,0 → 77,4 → 80,6 MB | 77,0 → 77,4 → 80,6 MB | Sem crescimento por ciclo |
| `CenaMapa.montar` | 1 → 1 → 11 | 1 → 1 → 11 | 11 = 1 inicial + 10 reaberturas |
| Timers após saída | 14 | 14 | Sem vazamento por ciclo |
| Digitação de 600 chars | 0,003 s | 0,003 s | 0 reconstruções, 1 comando de texto |

Não foi possível medir com núcleo falando nem com renderização real de desktop; a CPU em
janela curta deve ser repetida com amostragem longa para conclusão.

## Testes executados

- Suíte completa: **383 passaram** (`QT_QPA_PLATFORM=offscreen`).
- Novos: `test_conexao_ui.py`, `test_homologacao_final.py`.
- Regressão: testes de escrita, consulta, edição assistida, núcleo, voz, lembretes,
  gerenciador e planos antigos incluídos na suíte.

## Pendências e impacto

| Pendência | Impacto | Teste necessário |
|---|---|---|
| Voz real | Não valida STT/configuração do microfone | Gravação real com transcrição final |
| API/Ollama reais | Não valida redação do provedor | Integração com credenciais |
| Inspeção visual desktop | Não confirma contraste/foco na tela real | Captura em 1280×820 e janela menor |
| CPU com núcleo falando | Possível contendimento de thread | Medição com TTS ativo e amostragem longa |
| Notificação com NIA fechada | Avisos só na próxima abertura | Integração com SO |
| Publicação real | Saída permanece desativada | Integração própria |
