# Escopo e requisitos — rodada 9 (falhas persistentes) — CONCLUÍDO

## Ideia
Resolver as 4 falhas que apareciam desde a primeira rodada.

## Causas e solucoes
1. Botao Salvar oculto → `_reposicionar` mostra e posiciona.
2. Composer oculto sem geometria → teste mostra antes de medir o layout.
3. Lembrete nao suspendia → guarda de revisao removida; funcoes de lembrete
   alteram somente os lembretes, nunca o mapa do editor.
4. Titulo "Nome de teste" → cache de `nomes_tela` limpo no fixture isolado.

## Resultado
- `pytest -q`: **643 passed, 0 failed**.
- Nenhuma funcionalidade das rodadas 1-8 regressiu.
- Arquivos de clima do usuario preservados.

## Plano sequencial
- [x] Diagnosticar as 4 causas com reproducao
- [x] Corrigir sem mudar contratos publicos
- [x] Validar isolado e na suite completa (643/643)
