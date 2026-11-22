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
