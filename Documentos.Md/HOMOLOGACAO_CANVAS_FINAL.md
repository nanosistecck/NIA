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

## Janela principal maximizada (22/11/2026)

A NIA abre por padrão **maximizada com as bordas normais do Windows**, preservando o
acesso à barra de tarefas. Não usamos `showFullScreen()` (F11) como estado inicial.
A preferência `janela_sem_bordas` fica no nível superior de `config/interface.json`
(preservada por `DockPreferences` e pelo dashboard), padrão **`false`**. Ativando-a, a
janela continua maximizada, porém com `FramelessWindowHint` e geometria limitada a
`availableGeometry()` — ainda com barra de tarefas. O menu de contexto (botão direito
em qualquer lugar da NIA) oferece **Minimizar**, **Maximizar/Tela cheia**, **Restaurar
janela**, **Arrastar janela** (`startSystemMove`) e **Reduzir para bandeja** (F9).
Configurações → Aparência tem a opção "Janela sem bordas do Windows (ainda maximizada,
com barra de tarefas)", aplicada ao vivo.

Para preservar os testes que redimensionam a janela, o modo é aplicado no ponto de
entrada real (`NiaUI.__init__`), não no `MainWindow.__init__`.

Verificação: `tests/test_janela_tela_cheia.py` e `tests/test_janela_maximizada.py`
(7 testes RED→GREEN), cobrindo padrão maximizado, preferência, ausência de `fullScreen`
e ações do menu. Suíte: **401 passaram**; `compileall` e `git diff --check` limpos.

## Foco e contorno dos cards (21/11/2026)

Ao clicar, o card podia exibir moldura quadrada: o fundo do `QGraphicsView` ficava
branco e o foco padrão do widget desenhava um retângulo sem raio. Além disso, ao ampliar
o `boundingRect` para eliminar rastros, o `paint` passou a desenhar o corpo do card no
retângulo ampliado, deixando só o tracejado visível. Corrigido com: retângulo do corpo
fixo em `(0,0,CARD_W,CARD_H)` no `paint`, `boundingRect` ampliado apenas para invalidação,
`drawBackground` com gradiente radial escuro no `QGraphicsScene`, viewport transparente
e `WA_MacShowFocusRect=False`/`outline:none` no foco. Inspeção por captura confirmou
card preenchido, contorno tracejado arredondado e fundo escuro. Suíte: **394 passaram**.

## Rastros gráficos no arraste (21/11/2026)

Causa confirmada: `CardItem.paint` desenhava sombra (+4 px) e contorno de seleção
(-5 px) **fora do `boundingRect()`**. O Qt invalidava apenas essa região durante o
arraste, deixando rastros até um zoom forçar repaint completo. Corrigido com
`boundingRect` ampliado (-6, -6, +12/+12) e `FullViewportUpdate` no `MapaView`.
Teste: `tests/test_arraste_sem_rastros.py` (2 RED→GREEN). Suíte: **394 passaram**.
Medição com 41 cards/40 conexões: 200 pan/zoom em 1,469 s, RSS 77,1→80,8 MB,
0 reconstruções de cena no pan, timers estáveis em 14.

## Ajuste visual e botão Salvar (21/11/2026)

- **Botão Salvar:** o botão interno media 35×24 px e era fácil errar o clique. Criado
  **Salvar** na barra do Canvas (`salvar_canvas`, 76×32 px) ligado ao mesmo fluxo; botão
  interno passou a 64×30 px. Teste: `tests/test_botao_salvar.py` — clique real com
  `QTest.mouseClick` grava revisão e texto.
- **Visual:** overlay do Canvas passou a cobrir a **janela inteira** (sem borda interna);
  a reserva para o núcleo foi para as margens do conteúdo. Glass escuro estático com
  gradiente, bordas 1 px, foco 2 px e sombra desenhada nos cards — sem blur em tempo real.
  Direção: Windows 11 + macOS + web, mantendo o núcleo no canto inferior direito.
- **Causa raiz de instabilidade encontrada:** `selecionar()` disparava `selectionChanged`
  recursivamente e `_on_selection` re-selecionava um item arbitrário do `QSet`, trocando
  o alvo do texto. Corrigido com bloqueio de sinal durante a seleção programática e
  guarda de ID no handler. Isso explicava o texto indo para o card errado sob carga.
- **Card de hora/clima:** ao fechar, a geometria da esfera podia ficar no tamanho do card;
  `_brief_fade_finished` agora chama `arrange(False)` para volta imediata e estável.

Verificação: **392 testes passaram**, `compileall` e `git diff --check` limpos.

## Revisão Prompt 07 — exclusão permanente de arquivados (21/11/2026)

**O que já existia:** arquivar/restaurar e o botão de lembretes; **não existia** exclusão
permanente nem seleção múltipla no Gerenciador.

**Implementado:** `BP.excluir_permanentemente(plano_id, revisao)` exige status `arquivado`
e confere a revisão antes de apagar o JSON; `BP.excluir_lote(...)` processa item a item e
devolve `excluidos`/`falhas`. A lista agora usa `ExtendedSelection`, mostra **Excluir
permanentemente**, indica itens fora do filtro, exige confirmação com títulos/IDs e
**Cancelar como padrão**, e informa sucessos/falhas por plano com retry. Lembretes vivem no
JSON do plano e desaparecem junto com ele; nenhum arquivo compartilhado é removido.

**Verificação:** `tests/test_exclusao_planos.py` (7 testes RED→GREEN) cobre exclusão
individual, bloqueio de plano ativo, conflito de revisão, restauração entre seleção e
exclusão, lote parcial com retry, dois planos com o mesmo título, cancelamento e seleção
múltipla pela interface. Suíte: **390 testes passaram**; `compileall` e `git diff --check`
limpos. Interface Qt offscreen; falha parcial e conflito simulados.
