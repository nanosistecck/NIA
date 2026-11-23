# Escopo e requisitos — rodada 10 (ação no PC) — CONCLUÍDO

## Ideia
"abra o youtube e toque uma musica" não pode ser tratado como abertura de
plano; a frase deve seguir para a habilidade/rota de PC.

## Causa e solução
- `CP.reconhecer` tinha um regex final que capturava qualquer "abra" como ABRIR.
- Agora só `continua|continue|retoma|retome` caem nesse regex; abertura de plano
  por nome continua no regex específico (`abra o plano/projeto/produto ...`).

## Preservado
- "abra o plano X", "Abre o projeto Y", "abra o produto Z" → ABRIR.
- Retomar estudo, gerenciador, listar planos.
- Rodadas 1-9: suíte 643/643.

## Resultado
- 11 testes novos; suíte completa **654 passed, 0 failed**.
- Frase do relato: `CP.reconhecer → NENHUMA`, habilidade chamada, sem listar planos.

## Rodada 11 — Agenda (concluida)
- Desenho e plano aprovados; execucao nativa.
- 6 tarefas concluidas; suíte **685 passed, 0 failed**.
- Janela com grade mensal no dock e card no Canvas principal.
- Ver detalhes em `acceptance.md` e `changes.md`.
