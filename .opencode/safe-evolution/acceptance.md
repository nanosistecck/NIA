# Criterios de aceite e evidencias

| Requisito | Teste | Evidencia | Estado |
|---|---|---|---|
| "criar um novo card" nao vira criacao de plano | `test_cards_contexto_planos.py` (34 testes) | `CP.reconhecer` retorna `NENHUMA`; NIA cria `Novo card` no plano aberto | OK |
| "criar um card" cria no plano aberto | simulacao Canvas | card criado; registro "Alteração concluída..." | OK |
| "quero criar um card sobre X" cria card com titulo X | simulacao Canvas | card `Marketing` no mapa | OK |
| Criacao com titulo/tipo/status/descricao/posicao | teste de gramatica | `Validação`, tarefa, `concluido`, descricao e `(420,180)` | OK |
| Criacao de varios cards em um lote | teste de gramatica | 3 cards, 3 `temp_id` distintos | OK |
| Anexar ideias a card nomeado | simulacao Canvas | descricao de `Ideias sobre lançamento` contem as duas ideias | OK |
| Renomear rotulo de conexao | teste de gramatica | `editar_conexao` com `conexao_id` e rotulo | OK |
| "quais planos eu tenho" lista planos | `test_comandos_planos.py` | `LISTAR_PLANOS` com titulos ativos/arquivados | OK |
| Sem plano aberto, pedir card orienta abrir plano | simulacao Canvas | "Abra um plano no Canvas para eu criar o card." | OK |
| Criacao de plano legitima preservada | `test_criacao_voz.py` | 5 testes passaram | OK |
| Regressao dos 63 testes de controle | suite alvo | 146 testes das areas afetadas passaram | OK |
| Suite completa | `pytest -q` | **543 passed, 4 failed** (4 falhas preexistentes, vidas em `baseline.md`) | OK |
| Sintaxe | `compileall` / `git diff --check` | ambos limpos | OK |

## Evidencia visual

- Execucao real da interface PyQt6 em `QT_QPA_PLATFORM=offscreen`, janela 1280×820,
  com carregamento das fontes do Windows e plano ficticio `Produto NIA`.
- Seis frases processadas pela rota real `_executar_frase_habilidade`, todas `OK`.
- Mapa resultante: `Produto NIA`, `Novo card`, `Marketing`,
  `Ideias sobre lançamento`, `Validação` (status `CONCLUÍDO`).
- Captura: `logs/captura_controle_cards.png` (248.992 bytes), inspecionada
  diretamente — mostra os cinco cards distribuidos no Canvas e o status concluido.
- Ressalva: nao houve microfone, provedor externo nem tela fisica; voz e API
  seguem simuladas na entrada, mas a interface e o Canvas foram executados.
