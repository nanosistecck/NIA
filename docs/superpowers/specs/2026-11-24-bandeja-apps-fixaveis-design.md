# Bandeja de aplicativos = apps fixáveis no dock

Data: 2026-11-24

## Intenção

A Central de Aplicativos (bandeja) deve mostrar somente os apps do registro que
podem ser fixados no dock, independentemente de `visivel_na_central`. Os
controles do dock (microfone, interromper, webcam, Cowork etc.) continuam fora.
O usuário escolheu a opção B e vai conferir depois se falta algo.

## Goals

- A seleção da grade passa a ser `fixavel_no_dock=True`, sem olhar
  `visivel_na_central`.
- Os 44 atalhos `tool_*` deixam de ser marcados como fixáveis — são atalhos do
  modelo, não apps do dock — e não voltam para a grade.
- Cada app da bandeja ganha um ícone coerente com a ferramenta: ícones vetoriais
  próprios para Canvas Infinito e Agenda, no lugar de `planos` e `save`.
- Testes do registro e da Central acompanham a nova regra.

## Non-goals

- Não expor controles do dock na Central.
- Não alterar `hidden`/`order` do dock nem a página Ferramentas do dock.
- Não criar botão de dock para `canvas` nesta rodada.
- Não mudar o comportamento de abrir habilidades por voz/chat ou pelos atalhos.

## Anti-goals

- Trazer os atalhos `tool_*` de volta para a grade (foram removidos de propósito
  em 2026-11-24).
- Fazer a bandeja depender do estado "oculto" do dock.

## Constraints

- `core/registro_aplicativos.py` é declarativo: nenhum módulo é importado só para
  descrever um app. Os filtros continuam sendo feitos em memória.
- `icon()` em `core/interface_canvas.py` usa o dicionário `_ICONS` e faz fallback
  para `system` quando o nome não existe.
- A suíte roda com Qt offscreen; os testes da Central esperam hoje 3 blocos com
  uma habilidade incluída e precisam ser ajustados.

## Approaches

- **A (rejeitada):** mostrar quem tem `visivel_na_central` **ou**
  `fixavel_no_dock`. Mantém os 12 blocos atuais, mas não entrega "somente apps
  fixáveis" — habilidades continuariam na grade.
- **B (escolhida):** filtro único por `fixavel_no_dock`. Resultado imediato:
  Canvas Infinito, Planos, Agenda, Configurações e Globo. As habilidades saem
  da grade e continuam acessíveis por voz/chat e pelos atalhos do dock.

## Como (decisões já tomadas)

- `core/registro_aplicativos.py`: `sincronizar_ferramentas()` registra os
  `tool_*` com `fixavel_no_dock=False`; `buscar()` filtra por `fixavel_no_dock`
  em vez de `visivel_na_central`; `categorias()` usa o mesmo conjunto visível,
  para não deixar botão de categoria sem blocos.
- `core/interface_canvas.py`: novos traços vetoriais `canvas` e `agenda` em
  `_ICONS`.
- `core/registro_nativo.py`: `canvas` com `icone='canvas'` e `agenda` com
  `icone='agenda'`. Os demais mantêm `planos`, `config` e `globo`, já coerentes.
- `core/central_aplicativos.py`: nenhuma mudança de lógica necessária — a grade
  já consome `buscar()`.
- Testes: atualizar `tests/test_registro_aplicativos.py` (atalho não fixável e
  fora da busca) e `tests/test_central_aplicativos.py` (grade com os apps
  fixáveis; favoritos e abertura sem depender de habilidade na grade).

## Deixado para a implementação

- Verificar o contexto "Fixar no dock" de `canvas`, que não tem botão homônimo
  no dock. Reportar como ressalva, sem alterar o dock nesta rodada.
- Rodar a suíte completa e `git diff --check`.
