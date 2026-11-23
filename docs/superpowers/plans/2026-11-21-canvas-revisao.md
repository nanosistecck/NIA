# Canvas Infinito — revisão de escrita, conexões e contexto

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer com que o usuário escreva várias ideias em um card, conecte cards
existentes, consulte o mapa pela NIA e retome o plano após reiniciar, sem perder texto.

**Architecture:** Correções pontuais no fluxo atual: `EditorMapa` (QGraphicsScene +
QUndoStack + autosave), `CanvasEditor` (overlay), `NiaUI` (ponte thread-safe) e os
reconhecedores locais. Nenhuma mudança de formato do plano.

**Tech Stack:** Python 3.12.14, PyQt6 6.12.1, pytest 9.2.0, armazenamento JSON versionado.

**Spec:** `docs/superpowers/specs/2026-11-21-canvas-revisao-design.md`

## Global Constraints

- Perfil de teste isolado (`NIA_PLANOS_DIR`), plano fictício **Projeto dos lojistas**,
  cards **Público-alvo** e **Divulgação**. Nenhum dado do usuário tocado.
- `QT_QPA_PLATFORM=offscreen`, `.venv-apis/Scripts/python.exe`.
- Não alterar formato do plano; planos antigos abrem com texto/cards/posições/vínculos.
- Toda edição aplicada entra em `plano_atual()` e no `QUndoStack`; gravação pelo
  `atualizar()` atômico com revisão; falha mantém texto em memória e arquivo válido.
- Sem rede/API/Ollama para escrita, conexão, progresso e consulta estruturada.
- Preservar dock recolhido, núcleo no canto inferior direito, F2/F4/F6/F9/F11/ESC.

## Review Focus

1. Texto digitado e troca rápida de seleção → cada texto no ID certo, último valor prevalece → Task 1.
2. Duas gravações em sequência (autosave atrasado) → não sobrescrever a mais nova → Task 1.
3. Multisseleção de cards para conectar → origem/destino estáveis, `Esc` cancela → Task 2.
4. Contexto após edição manual → NIA lê o texto recém-aplicado, não snapshot antigo → Task 3.
5. Conflito manual vs lote assistido → guardião compara com estado vivo → Task 4.

---

### Ordem revisada (com evidência)

A ordem do prompt (A→B→C→D→E) foi ajustada para **B→A→C→D→E**:
`main._contexto_planos()` lê `plano_atual()`, que por sua vez lê `item.dados` da cena.
Se o texto do painel não for commitado na cena (causa B), nenhuma correção de contexto (C)
ou edição assistida (D) pode devolver o texto atual — e o guardião de conflito compara
sempre snapshot contra snapshot. Corrigir B primeiro é pré-requisito medido, não preferência.

---

### Task 1 (B): Escrita multilinha, commit e histórico

**Files:** Modify `core/interface_mapa.py`; Test `tests/test_edicao_texto.py` (novo).

**Interfaces:**
- Consumes: `EditorMapa.editar_card`, `plano_atual`, `_apos_mudanca`, `QUndoStack`.
- Produces: `campo_descricao: QTextEdit`, `aplicar_texto_painel()`, `texto_pendente()`.

- [ ] **Step 1:** Teste RED — escrever 2 parágrafos + lista com acentos/linhas em branco em
  `div`, trocar para `pub`, voltar; assertar `plano_atual()["descricao"]` igual ao texto.
  Outro teste: `Ctrl+Z` no campo desfaz o texto e não mexe na pilha do Canvas; `Ctrl+Z`
  com foco no mapa desfaz a última operação do Canvas.
- [ ] **Step 2:** Rodar e confirmar falha (campo é `QLineEdit`, texto volta vazio).
- [ ] **Step 3:** Substituir `campo_descricao` por `QTextEdit` com rolagem; adicionar
  `aplicar_texto_painel()` chamado em `focusOutEvent`, troca de seleção, `Ctrl+Enter` e
  botão Aplicar; criar `EditarTextoCommand` (ou reutilizar `EditarCardCommand`) com
  `beginMacro`/`endMacro` agrupando a sessão; marcar `mudancas_pendentes` uma vez;
  sincronizar o espelho de contexto via sinal.
- [ ] **Step 4:** Rodar teste e suíte; verificar salvar→reabrir devolve o texto exato.
- [ ] **Step 5:** Commit `fix(canvas): editor multilinha com commit e historico`.

**Acceptance:** texto completo sobrevive a troca de seleção, `Ctrl+Z`, reinício e falha
de gravação; nenhuma gravação por tecla; planos antigos legíveis.

---

### Task 2 (A): Conexão entre cards existentes

**Files:** Modify `core/interface_mapa.py`; Test `tests/test_conexao_ui.py` (novo).

**Interfaces:**
- Consumes: `EditorMapa.conectar`, `CriarConexaoCommand`, `MapaView`.
- Produces: `iniciar_conexao(card_id)`, `concluir_conexao(card_id)`, `cancelar_conexao()`.

- [ ] **Step 1:** Teste RED — selecionar `pub`, clicar **Conectar**, clicar `div`;
  assertar 1 conexão `pub→div`, linha desenhada, `pilha.count()+1`, `desfazer`→0,
  `refazer`→1; segundo teste: `Esc` durante a escolha não cria conexão e restaura a seleção.
- [ ] **Step 2:** Rodar e confirmar falha (hoje `selectionChanged` colapsa a seleção e o
  botão não cria nada).
- [ ] **Step 3:** Implementar modo de conexão com origem fixa; desconectar
  `_on_selection` de `selecionar()` quando o modo estiver ativo; destino por clique no
  `CardItem` com `mousePressEvent` delegando; linha provisória com `QGraphicsLineItem`
  (sem timer); `Esc` via `QShortcut` com contexto de janela; validar self-loop/duplicata
  com mensagem curta. Dar `ItemIsSelectable` a `ConexaoItem` para permitir excluir uma
  conexão isolada via `ExcluirConexaoCommand`.
- [ ] **Step 4:** Rodar teste, suíte e medir novamente pan/zoom e montagens.
- [ ] **Step 5:** Commit `fix(canvas): conectar cards existentes por clique`.

**Acceptance:** origem destacada, linha provisória, `Esc` cancela, conexão persistida
após salvar/reabrir, desfazer/refazer em uma operação.

---

### Task 3 (C): Contexto vivo da NIA

**Files:** Modify `core/interface_canvas_planos.py`, `ui.py`, `main.py`,
`core/comandos_planos.py`, `core/assistencia_planos.py`;
Test `tests/test_contexto_canvas_vivo.py` (novo).

**Interfaces:**
- Consumes: `NiaUI.contexto_canvas`, `CanvasEditor.contexto()`, `AP.montar_contexto`.
- Produces: `NiaUI.contexto_canvas` sempre fresco quando o editor está aberto;
  intenções `CONTEUDO_CARD` e `CONEXOES_CARD`.

- [ ] **Step 1:** Teste RED — editar `div`, chamar `NiaUI.contexto_canvas()` e conferir o
  texto novo; perguntas "O que está escrito neste card?" e "Com quais cards ele está
  conectado?" devem ser tratadas localmente com o texto e os nomes dos vizinhos.
- [ ] **Step 2:** Rodar e confirmar falha (espelho antigo; intenções caem no LLM).
- [ ] **Step 3:** Fazer `contexto_canvas()` consultar `editor.contexto()` na thread da GUI
  via `QTimer.singleShot` + resultado síncrono seguro (ou espelho atualizado em toda
  mutação); adicionar as duas intenções aos reconhecedores com regex ancorada; responder
  com `descricao` completa, título do card e lista de vizinhos por ID/título;
  `Perguntar à NIA sobre este card` sincroniza o painel antes de capturar o contexto.
- [ ] **Step 4:** Rodar teste, suíte e teste integrado (texto→conexão→pergunta→edição→
  pergunta→reinício→pergunta pelo nome do plano).
- [ ] **Step 5:** Commit `fix(canvas): contexto da nia sobre o estado atual`.

**Acceptance:** a resposta cita o texto atualizado e as conexões do card selecionado,
antes e depois de reiniciar; sem chamada externa.

---

### Task 4 (D): Edição assistida sobre o estado vivo

**Files:** Modify `main.py`, `core/assistencia_planos.py`;
Test `tests/test_assistencia_contexto_vivo.py` (novo).

**Interfaces:**
- Consumes: Task 3 (`contexto_canvas` vivo), `AP.validar_lote`, `AP.aplicar_lote`.
- Produces: validação contra `editor.plano_atual()`, não contra snapshot do espelho.

- [ ] **Step 1:** Teste RED — editar manualmente `div`, pedir alteração assistida no mesmo
  campo; o lote deve ser recusado com "edição manual preservada"; resposta atrasada após
  troca de plano não altera o novo mapa.
- [ ] **Step 2:** Rodar e confirmar falha (hoje `validar_lote` compara snapshot consigo).
- [ ] **Step 3:** Em `_processar_pedido_assistido`, buscar o plano vivo via nova ponte
  `NiaUI.estado_canvas_vivo()` e usar esse `Plano` em `montar_contexto` e `validar_lote`;
  manter a política de saída `filtrar_contexto` antes de qualquer provedor e em fallback;
  registrar `plano_id`/`card_id`/fingerprint da intenção.
- [ ] **Step 4:** Rodar teste e suíte; confirmar que lote inválido não aplica nada e que
  o lote válido continua sendo um único desfazer.
- [ ] **Step 5:** Commit `fix(canvas): assistida usa estado vivo e detecta conflito`.

**Acceptance:** conflito detectado, alvo original preservado, nenhuma sobrescrita por
resposta atrasada, privacidade aplicada em todas as tentativas.

---

### Task 5 (E): Interface, desempenho e homologação

**Files:** Modify `core/interface_canvas.py` (QSS/foco), `ui.py` (botão **Perguntar à NIA
sobre este card**), `Documentos.Md/HOMOLOGACAO_CANVAS.md`; Testes de regressão existentes.

- [ ] **Step 1:** Aplicar a prévia aprovada: `QTextEdit` com foco visível, painel em janela
  menor, linha provisória, rótulo do botão de conversa; sem blur em tempo real.
- [ ] **Step 2:** Repetir medição com 41 cards/40 conexões e comparar com o baseline
  (6,235 s/200 ops, CPU 47,6%, RSS 77,0→80,6 MB, montagens 1→1→11, timers 14).
- [ ] **Step 3:** Rodar suíte completa (`QT_QPA_PLATFORM=offscreen`), `compileall`,
  `git diff --check`; verificar dock/núcleo/chat/voz/atalhos/Gerenciador.
- [ ] **Step 4:** Atualizar relatório com antes/depois, o que foi interface vs simulação.
- [ ] **Step 5:** Commit `test(canvas): homologacao da revisao de escrita e contexto`.

## Verificação obrigatória de cada etapa

1. Reproduzir a falha e registrar o resultado antes da alteração (scripts em `%TEMP%`).
2. Implementar pelo fluxo real da NIA, com teste RED→GREEN.
3. Revisar (substituto do `opencode-power-pack`: `code-reviewer` + `verification-before-completion`)
   e rodar testes existentes + novo teste.
4. Retestar o cenário original e fluxos vizinhos; bloqueio real → registrar impacto.
5. Registrar melhora, medição e mudança de plano diante de nova evidência.

**Teste integrado final:** escrever duas ideias em **Divulgação** → ligar a **Público-alvo**
→ perguntar texto e conexão → editar uma ideia → perguntar de novo → reiniciar → consultar
pelo nome do plano. Esperado: resposta com o texto atualizado e mapa com conexão/posições.

## Riscos registrados

- `test_canvas_brief.py::test_fecha_durante_entrada_cancela_reentrada_e_timer` falhou uma
  vez na suíte em segundo plano (345/346) e passou isolado em 3,28 s — flaky de tempo,
  sem relação com código alterado (nenhum código foi modificado nesta etapa).
- Reentrada de `selectionChanged` ao trocar `setSelected` pode reaparecer se o modo de
  conexão não isolar o handler.
- Sem `opencode-power-pack`, a revisão estrutural por etapa fica sem a cobertura pedida.
