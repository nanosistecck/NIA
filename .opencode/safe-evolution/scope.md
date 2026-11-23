# Escopo — rodada 12 (correcoes apontadas nos testes do dono)

## Solicitado
Corrigir os 6 erros encontrados nos testes reais da NIA e depois procurar mais
problemas que precisem de atencao.

## Correcoes
1. Agenda tem prioridade sobre o Canvas quando o texto e claramente de agenda.
2. Acao `excluir` (com `excluir(item_id)` no modulo puro).
3. Referencia de titulo que nao casa NAO cai para o proximo: "Nao encontrei...".
4. Mensagens por acao (concluido/cancelado/excluido/movido/preparo).
5. Listagem filtra periodo (hoje/amanha/proximo mes) e cita o proximo compromisso.
6. "bom dia" com saudacao.

## Preservado
Todas as funcionalidades e Rulings da rodada 11; suite 689/689 como baseline.

## Plano
- [x] Diagnosticar com testes reais
- [x] Escrever testes RED
- [x] Corrigir parser, modulo e rota
- [x] Rodar suite completa e varredura extra
- [x] Registrar evidencias

## Resultado
- 6 erros relatados + 6 da varredura extra, todos corrigidos.
- 18 testes novos; suite **707 passed, 0 failed**.
- Duas regressoes de rota com o Canvas corrigidas e testadas.

## Rodada 13 — CRUD completo (concluida)
- Usuario aprovou o desenho e a execucao.
- 5 tarefas executadas em modo nativo, TDD RED→GREEN.
- Builder check respondido; bug de tratamento de erro corrigido.
- Suite **724 passed, 0 failed**; captura da janela em modo edicao inspecionada.
- Ver `acceptance.md` e `changes.md`.
