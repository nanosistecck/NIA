# Canvas Infinito — revisão de escrita, conexões e contexto

Data: 21/11/2026 · Branch `CANVAS-INFINITO` · Perfil de teste isolado (`NIA_PLANOS_DIR`)
· Plano fictício **Projeto dos lojistas** com cards **Público-alvo** e **Divulgação**.

## Intenção

O usuário consegue abrir e salvar planos, mas no dia a dia: não consegue ligar dois cards
existentes, perde o que escreve ao trocar de card, e a NIA responde como se não conhecesse
o mapa. Corrigir esses três pontos sem trocar a arquitetura: mesmo JSON versionado, mesmo
`QGraphicsScene`, mesmo `QUndoStack`, mesmo fluxo de gravação atômica.

## Skills

**Carregadas:** `brainstorming`, `writing-plans`, `ui-ux-pro-max`, `pyqt6-ui-designer`
(Canvas confirmado PyQt6), `systematic-debugging` (já carregada na sessão) e
`verification-before-completion` (já carregada na sessão).

**Indisponíveis neste ambiente:** `awesome-design-skills` e `opencode-power-pack`.
Cobertura sem substituto: o `opencode-power-pack` faria a revisão estruturada de cada
etapa; usei `code-reviewer`/verificação explícita com testes como substituto, e registro
isso como lacuna de processo.

## Diagnóstico — evidências

Método: scripts de instrumentação somente-leitura em `%TEMP%`, com `QT_QPA_PLATFORM=offscreen`,
plano fictício e `NiaUI`/`MainWindow` reais. Nenhum arquivo de produto foi alterado.

| Cenário | Esperado | Observado | Evidência | Classificação |
|---|---|---|---|---|
| Conectar dois cards existentes | Ctrl+clique em `Público-alvo` + `Divulgação`, botão **Conectar** cria a linha | Após `setSelected(True)` nos dois, `cena.selectedItems()` continha **só `pub`**; botão não criou conexão; `status` permaneceu `3 card(s).` | `repro_revisao.py`, bloco A1 | **Causa confirmada** |
| Mover com conexão | Linha acompanha o card | `bbox` da curva mudou de `(98,42,260,0)` para `(98,42,500,250)`; posições e conexão salvas corretamente | `repro_revisao3.py`, blocos 1 e 2 | Funciona |
| Desfazer/refazer conexão | Uma operação | API `conectar()` → 1 conexão; `desfazer` → 0; `refazer` → 1 | `repro_revisao.py`, A2/A3 | Funciona na API; bloqueado na UI |
| Escrever duas ideias | Parágrafos no card | `campo_descricao` é `QLineEdit` (não multilinha); `Enter` concatenou `Primeira ideiaSegunda ideia`; ao trocar de card e voltar, descrição voltou a `''`; `salvar()` gravou `''` | `repro_revisao.py` B1-B3; `repro_revisao3.py` atalhos | **Causa confirmada** |
| Consultar "O que está escrito neste card?" | Resposta local com o texto | `comandos_planos.reconhecer` → `EXPLICAR` (regex `o que e` casa `o que esta`), `processar` devolve `tratado=False`; `assistencia.reconhecer_intencao` → `NENHUMA`; cai no LLM genérico sem contexto | `repro_revisao.py` C1; subagent de contexto | **Causa confirmada** |
| Consultar "Com quais cards ele está conectado?" | Lista de vizinhos | `NENHUMA` em todos os reconhecedores; cai no LLM genérico; nenhuma intenção de vínculos existe | idem | **Causa confirmada** |
| Consultar após editar | Ver texto recém-editado | Espelho `w._contexto_canvas` ficou com `'texto original'` enquanto `editor.plano_atual()` já tinha `'Primeira ideia nova.\nSegunda ideia nova.'` | `repro_revisao2.py` | **Causa confirmada** |
| Reiniciar e consultar pelo nome | Texto atualizado | Como o texto nunca entra no Plano, reiniciar devolve o texto antigo/vazio | consequência direta de B | **Causa confirmada** |
| Desempenho | Reprodutível e sem reconstrução | 41 cards/40 conexões: 200 pan/zoom = 6,235 s (≈31 ms/op), CPU 47,6%, RSS 77,0 → 77,4 → 80,6 MB após 10 aberturas; `CenaMapa.montar` = 1 no início, 1 após pan, 11 após 10 ciclos; timers = 14. Mapa de 3 cards: 0,483 s/100 ops. | `medir_revisao.py`, `repro_revisao2.py` | Medição realizada (sem baseline anterior desta revisão) |

Ambiente das medições: Windows 11 10.0.26200, Python 3.12.14, PyQt6 6.12.1, pytest
9.2.0, `offscreen`, janela 1280×820, 41 cards/40 conexões em grade 8×5.

### Causas raízes

1. **Conexão inoperante pela UI.** `cena.selectionChanged` → `EditorMapa._on_selection`
   (`interface_mapa.py:756-768`) chama `selecionar()` (`:574-581`), que faz `setSelected`
   em todos os cards com `ident == card_id`. O Ctrl+clique que seleciona o segundo card
   dispara o sinal sincronamente e o handler desfaz a multisseleção. Há reentrada
   (setSelected volta a emitir `selectionChanged`), convergindo para um único sobrevivente
   arbitrário. Além disso `MapaView` usa apenas `ScrollHandDrag` (`:254-259`), sem
   `RubberBandDrag`, e `ConexaoItem` não tem `ItemIsSelectable` (`:150-159`) — os ramos
   de excluir/editar conexão em `excluir_selecionado`/`_salvar_detalhes` estão mortos.
   O dado em si está correto: `conectar()` (`:635-648`), `CriarConexaoCommand`,
   `plano_atual()` e `salvar()` funcionam.
2. **Texto perdido.** `campo_titulo`, `campo_resumo` e `campo_descricao` são `QLineEdit`
   (`:485-490`). Nenhum `textChanged`/`editingFinished`/`focusOutEvent` commita o texto:
   o único leitor dos campos é `_salvar_detalhes` (`:783-792`), ligado só ao botão.
   `plano_atual()` (`:560-568`) lê `CenaMapa.mapa_atual()`, que copia `item.dados`, não
   os widgets. Trocar de seleção (`_on_selection` → `_selecionar_dados`) sobrescreve os
   campos com o dado antigo; `mudancas_pendentes` nunca é marcado, então nem o autosave
   nem o aviso de saída veem a edição. Um autosave disparado por outro movimento pode
   ainda gravar o valor antigo por cima.
3. **Contexto da NIA desatualizado e sem intenções de leitura.**
   `CanvasEditor.contexto()` é vivo, mas o espelho `ui._contexto_canvas` só é atualizado
   por `contexto_mudou`, emitido apenas em `abrir()`, `selecionar_card()` e
   `adicionar_modelo()`. Nenhuma edição emite. Assim `main._contexto_planos()` entrega um
   `Plano` snapshot antigo; pior, `validar_lote` compara `contexto["card"]` com esse mesmo
   snapshot, então o guardião de edição manual não consegue detectar conflito. As duas
   perguntas do usuário não têm intenção local: caem no LLM genérico, que não recebe
   plano/card/vínculos.

## Abordagens consideradas

- **A) Corrigir o fluxo existente (escolhida).** Manter `QGraphicsScene`/`QUndoStack`/
  `core.planos`. Trocar o campo por `QTextEdit` com commit explícito, adicionar um modo
  de conexão com origem fixa e destino escolhido por clique, e tornar o contexto vivo
  sob demanda. Custo baixo, compatível com planos antigos e com a arquitetura aprovada.
- **B) Reescrever o editor com `QGraphicsProxyWidget` em cada card.** Daria edição inline,
  mas quebra o desenho leve (um widget por card), aumenta custo de renderização e exige
  migração de formato. Descartada.
- **C) Resolver só no provedor/IA.** Contraria o requisito local/offline e não corrige
  perda de dados. Descartada.

## Design aprovado (prévia)

Paleta e temas atuais da NIA (tokens `C.*`/`PALETAS`), superfície escura `#010d14`,
borda `#0f4060`, acento `#00d4ff`, foco visível de 2 px, transparência estática, sem
blur em tempo real. Liquid Glass restrito ao painel/flutuante de confirmação.

**Estado 1 — conexão entre cards existentes**

```
[ Conectar ]  ->  Origem: Público-alvo  ✓   (linha tracejada saindo do card)
                  "Clique no card de destino · Esc cancela"

   ┌──────────────────┐          · · · · · · · ▶
   │ Público-alvo  ◆  │ · · · · ·              ┌──────────────────┐
   │ Lojistas         │                        │ Divulgação       │
   └──────────────────┘                        └──────────────────┘
```
A origem fica com contorno sólido + marcador; a linha provisória acompanha o cursor;
`Esc` cancela sem criar nada. Destino inválido (si mesmo/duplicata) mostra aviso curto.

**Estado 2 — escrita no card**

```
Mapa:  ┌────────────────────────────┐
       │ Divulgação                 │
       │ Canais digitais · parcerias│  <- resumo curto, 2 linhas no máximo
       └────────────────────────────┘

Painel de detalhes (lateral):
  Título   [ Divulgação                         ]
  Resumo   [ Canais digitais e parcerias         ]
  Ideias   ┌────────────────────────────────────┐
           │ Primeira ideia: feiras regionais   │
           │                                    │
           │ Segunda ideia:                      │
           │ - parceria com associações          │
           │ - divulgar no grupo da cidade      │
           └────────────────────────────────────┘
  [ Aplicar ]      (Ctrl+Enter também aplica)
```
`QTextEdit` com rolagem; `Enter` quebra linha; `Ctrl+Z`/`Delete` pertencem ao campo
enquanto ele tiver foco. O mapa mostra só o resumo; o texto completo fica no plano.

**Estado 3 — conversa com a NIA**

```
[ Perguntar à NIA sobre este card ]  -> conversa com alvo = Divulgação

Você: O que está escrito neste card?
NIA:  Em Divulgação: "Primeira ideia: feiras regionais ...".
      Conexões: ligado a Público-alvo.
      [ Abrir Divulgação no mapa ]
```
O alvo é o ID do card no momento do pedido; a resposta cita o card de origem e as
conexões registradas.

## Decisões do construtor

- Modo de conexão por clique (origem → destino) em vez de multisseleção: não depende de
  `RubberBandDrag`, mantém `ScrollHandDrag` para pan e funciona com teclado.
- Commit do texto em eventos explícitos (`focusOut`, troca de seleção, `Ctrl+Enter`,
  botão Aplicar) com `QUndoCommand` por sessão de edição, não por tecla.
- Contexto da NIA passa a ser **lido sob demanda do editor vivo** no momento do pedido;
  o espelho vira cache invalidado por sinal, não fonte de verdade.
- `Perguntar à NIA sobre este card` sincroniza o campo antes de capturar o contexto.
- Sem mudança de formato: `descricao` já existe; planos antigos continuam válidos.
