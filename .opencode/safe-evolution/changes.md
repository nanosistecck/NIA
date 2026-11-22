# Historico incremental

Para cada etapa registre: data, tarefa, arquivos, motivo, testes executados, resultados, riscos, decisao e proxima etapa. Nao registre tokens, senhas ou credenciais.

## 22/11/2026 — Diagnostico e baseline
- Tarefa: mapear roteamento de Planos/Canvas, reproduzir a confusao "card vs plano" e registrar estado.
- Arquivos lidos: `core/comandos_planos.py`, `core/assistencia_planos.py`, `core/controle_canvas.py`, `core/interface_canvas_planos.py`, `core/interface_mapa.py`, `main.py`, `ui.py`, testes de Canvas/Planos.
- Testes: 63 testes de controle passaram; 137/138 de Planos/Canvas passaram.
- Falha preexistente: `test_dock_delega_a_aparencia_e_aplica_preferencias` (layout do composer), nao relacionada.
- Causa confirmada: `CP.reconhecer("criar um novo card") == CRIAR`; gramatica local gera titulos ruins ou falha sem titulo.
- Riscos: alterar `reconhecer` pode afetar criacao de planos legitimos; coberto por testes.
- Proxima etapa: escrever testes RED e implementar.

## 22/11/2026 — Etapa 1: roteamento de intencao e consulta de planos
- Arquivos: `core/comandos_planos.py`, `main.py`, `tests/test_cards_contexto_planos.py` (novo).
- Motivo: "criar um novo card" casava `criar (um|...)` e virava criacao de plano.
- Implementado: `_CRIACAO_DE_CARD`/`_QUERO_CARD` exigem objeto `card`; `LISTAR_PLANOS`
  responde "quais planos eu tenho"/"liste meus planos"; "gerenciar planos" abre o gerenciador;
  titulo explicito `chamado/com titulo` tambem e lido na criacao de plano.
- Testes: 17 novos testes de roteamento/listagem passaram.
- Riscos: criacao legitima de plano preservada por testes (`test_criacao_voz.py`).

## 22/11/2026 — Etapa 2: gramatica local de cards e ideias
- Arquivos: `core/controle_canvas.py`, `main.py`, `tests/test_cards_contexto_planos.py`.
- Motivo: criacao local gerava titulos ruins ("sobre X", "com ideias...") e falhava sem titulo.
- Implementado: parser com titulo explicito/topico, tipo, status, descricao, posicao,
  conexao, varios cards em um lote, anexar ideias a card nomeado/selecionado e
  renomear rotulo de conexao. Mensagem sem plano orienta abrir o Canvas.
- Testes: 34 novos testes passaram; 146 testes dasAreas afetadas passaram.
- Correcoes no caminho: nome de funcao no import do `main.py` (`ImportError` silencioso)
  e extracao de valor das clauses (grupos de captura, nao intervalo apos o match).
- Riscos: parser intercepta pedidos generativos; provedor continua disponivel para
  pedidos que nao casam a gramatica local.
- Proxima etapa: suite completa, revisao de diff e captura offscreen.

## 22/11/2026 — Etapa 3: distribuicao de cards e validacao final
- Arquivos: `core/controle_canvas.py`.
- Motivo: cards criados em pedidos seguintes ficavam na mesma posicao (270,110) e
  ficavam escondidos uns atr dos outros na captura.
- Implementado: `_posicao_livre` procura a primeira posicao sem sobreposicao,
  mantendo as coordenadas explicitas intactas.
- Testes: 95 testes de Canvas/Planos passaram apos a mudanca.
- Suite completa: 543 passed, 4 failed. Todas as 4 falhas eram preexistentes
  (`test_botao_salvar`, `test_dock_delega_a_aparencia...`, `test_excluir_card_suspende...`,
  `test_topo_compacto` por ordem de testes). Nenhuma area alterada por esta etapa.
- `compileall` e `git diff --check`: limpos.
- Evidencia visual: interface executada offscreen, seis comandos aplicados e
  captura inspecionada em `logs/captura_controle_cards.png`.
- Riscos restantes: `.gitignore` preexistente ignora `.opencode/` e `tests/*`,
  entao os novos testes/estado nao aparecem como untracked no Git (nao alterado).
- Decisao: nao commitar, nao criar branch e nao tocar nas mudancas locais do usuario.

## 22/11/2026 — Rodada 2: prioridade da conversa e resumo legivel
- Tarefa: no chat do Canvas, priorizar conversa sobre o plano e parar de revelar IDs.
- Diagnostico (antes de editar): reproduzido com `%TEMP%\diag_prioridade.py`.
  - Causa 1: frases sobre o plano nao casavam reconhecedor local; `_on_text_command`
    seguia para `_responder_texto_local`, que usa OpenRouter com ferramentas.
  - Causa 2: `ui.py` montava a confirmacao com `card_id`/`origem`/`titulo` crus.
- Arquivos: `core/assistencia_planos.py`, `main.py`, `ui.py`,
  `tests/test_prioridade_conversa_plano.py` (novo).
- Implementado: `conversa_sobre_plano`, `resumo_conversa_plano`, `resumo_lote`,
  `_responder_conversa_plano` na rota antes de `CH.reconhecer`, e confirmacao
  via `resumo_lote` no lugar da lista de IDs.
- Testes: 17 RED → 18 GREEN; 190 testes da area passaram; suite completa
  561 passed, 4 failed (mesmas preexistentes da rodada 1).
- `compileall` e `git diff --check`: limpos.
- Evidencia: captura `logs/captura_prioridade_plano.png` e mensagens verificadas
  sem nenhum hash de 32 caracteres.
- Riscos: reconhecedor e deliberadamente restrito a termos de plano/card e a
  titulos de cards; hora, clima e busca local explicita foram testados a parte.
- Proxima etapa: aprovacao do dono antes de qualquer commit ou nova area.

## 22/11/2026 — Rodada 3: interacao completa com o Canvas
- Tarefa: corrigir falso "O plano mudou", retomada de pedido e cards sobre a NIA.
- Diagnostico: tres reproducoes em `%TEMP%` antes de editar (ver `baseline.md`).
- Arquivos: `core/controle_canvas.py`, `core/assistencia_planos.py` (inalterado nesta
  rodada), `main.py`, `ui.py`, `tests/test_interacao_canvas_pedido.py` (novo).
- Implementado:
  - `_CARDS_FUNCIONAMENTO_NIA`, `pedido_funcionamento_nia`, `pedido_retomada` e
    `_pedido_funcionamento_nia` em `core/controle_canvas.py`;
  - `NiaUI.plano_canvas_vivo` em `ui.py` como fonte de verdade quando o espelho
    de sinal esta vazio;
  - `vivo_atual()` no `main.py`, preservando o descarte quando a ponte existe e
    o plano realmente troca;
  - `_retomar_pedido_canvas` e `_ultimo_pedido_canvas` (5 minutos, mesmo plano/sessao).
- Testes: 13 RED → 14 GREEN; 196 testes da area passaram; suite completa
  575 passed, 4 failed (mesmas preexistentes).
- Correcoes no caminho: pontes ausentes em testes com `SimpleNamespace` exigiram
  `getattr` para `_retomar_pedido_canvas` e `tem_ponte` antes de descartar.
- `compileall` e `git diff --check`: limpos.
- Evidencia: `logs/captura_interacao_canvas.png` e mensagens sem "O plano mudou".
- Riscos: a retomada repete o pedido (pode duplicar cards se o primeiro ja
  tiver sido aplicado); comportamento intencional de "faz de novo".
- Decisao: sem commit, sem branch, sem tocar nas mudancas locais preexistentes.
