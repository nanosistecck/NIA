# Criterios de aceite e evidencias — status final

## Rodada 9 — 4 falhas persistentes resolvidas

| Falha | Causa | Correcao | Estado |
|---|---|---|---|
| `test_botao_salvar_no_overlay_e_grava` | botão `salvar_canvas` criado oculto e nunca posicionado | `_reposicionar` mostra e posiciona o botão (110x32) ao lado do chat | OK |
| `test_dock_delega_a_aparencia_e_aplica_preferencias` | Qt nao posiciona widget oculto; composer ficava em (0,0) | teste mostra o composer para medir o layout e o esconde depois | OK |
| `test_excluir_card_suspende_e_desfazer_restaura` | guarda de revisao confundia exclusao do card com edicao externa | guarda removida; `suspender_por_card`/`restaurar_por_card` so mexem nos lembretes | OK |
| `test_topo_compacto` | cache global de `nomes_tela` vazava "Nome de teste" | fixture `config_isolada` limpa `nomes_tela._cache` | OK |

## Resultado final da suíte

- `python -m pytest -q`: **643 passed, 0 failed**.
- Nenhuma falha preexistente restante.
- `compileall` e `git diff --check`: limpos.

## Rodadas anteriores (resumo)

| Rodada | Entrega | Evidencia |
|---|---|---|
| 1 | gramatica de cards/ideias, prioridade de plano, resumo sem IDs | 34 testes novos |
| 2 | conversa priorizada no chat do Canvas | 18 testes novos |
| 3 | pedido generativo sobre a NIA, retomada, contexto real | 14 testes novos |
| 4 | interrupção conversacional e "faz até o final" | 18 testes novos |
| 5 | troca rápida de assunto (bypass da trava da boca) | 6 testes novos |
| 6 | fala completa (sem teto de palavras em explicações) | 10 testes novos |
| 7 | fala cortada no meio (silêncio 20s, régua 0.85) | 5 testes novos |
| 8 | clima "agora a tarde" com hora local da cidade | 11 testes novos |
| 9 | 4 falhas antigas resolvidas | suíte 643/643 |

Ressalvas: sintese de voz real, provedor de IA e microfone nao disponiveis;
validacao feita com interface Qt executada e dados simulados.
