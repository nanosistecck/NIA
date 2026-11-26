# Bandeja com as ferramentas do dock

Data: 2026-11-25

## Intenção

A Central de Aplicativos deve expor as 18 entradas do menu "Todas as ferramentas"
do dock, sem duplicatas e com o mesmo comportamento de clique dos botões do
dock. O Canvas Infinito sai (abre a mesma janela de Planos) e o indicador
verde/laranja de disponibilidade dos blocos é removido, porque aumenta a altura
do bloco e a área de clique.

## Goals

- Grade final com 18 blocos: os 9 controles, Globo, Planos, Agenda, Central de
  Aplicativos, Configurações, Sistema/visão e as 3 habilidades nativas.
- Nenhum bloco repetido: os que já estão na bandeja (Planos, Agenda,
  Configurações, Globo) continuam uma vez cada.
- Clique em qualquer bloco mapeado para o dock chama o botão real do dock,
  inclusive se ele estiver oculto no dock.
- Cada bloco com ícone relacionado à ferramenta, sem depender de fonte de ícones
  instalada.
- Sem o pontinho `●`/`○` abaixo do nome nos blocos.

## Non-goals

- Não alterar `hidden`, `order` ou a página Aparência → Ferramentas do dock.
- Não copiar a lógica dos controles (mic, interromper, segundo plano etc.) para
  a bandeja.
- Não mexer nos atalhos `tool_*` nem no caminho de voz/chat das habilidades.
- Não criar botão novo no dock.

## Anti-goals

- Duplicar Planos/Canvas ou qualquer outro botão na grade.
- Trazer os 44 atalhos `tool_*` de volta.
- Fazer a bandeja depender dos widgets internos do dock para buscar/categorizar.

## Constraints

- `core/registro_aplicativos.py` é declarativo; nenhum módulo é importado só para
  descrever uma ferramenta.
- `core/interface_canvas.py:_ICONS` é a fonte dos traços vetoriais; o fallback é
  `system`.
- Os ids das 14 entradas novas precisam ser exatamente as chaves dos botões em
  `ui.py:_build_dock`, para a ponte funcionar.
- Suíte pytest com Qt offscreen.

## Approaches

- **A (escolhida): ponte para os botões reais do dock.** A MainWindow informa à
  bandeja quais ids são botões do dock; o clique emite um sinal e a MainWindow
  chama `botao.click()`. Os metadados vêm de descritores declarativos, então
  busca/categorias/favoritos continuam funcionando. Custo: um catálogo de 14
  descritores e uma ponte de sinal.
- **B (rejeitada): reimplementar as ações no registro.** Cada ferramenta teria
  um carregador próprio chamando métodos da UI; duplica lógica e as duas vias
  divergem com o tempo.
- **C (rejeitada): a bandeja ler direto os botões do dock.** Sem catálogo, mas
  acopla a grade aos widgets internos e complica busca, categorias e favoritos.

## Como (decisões tomadas)

- `core/registro_nativo.py`: remover o descritor `canvas`; acrescentar 14
  descritores com `id` igual à chave do botão do dock (`mute`, `so_nome`,
  `interrupt`, `whatsapp`, `remote`, `webcam`, `cowork`, `computer_use`,
  `segundo_plano`, `central`, `system`, `skill_secretaria`,
  `skill_buscar_arquivos`, `skill_resumo_dia`), `origem='dock'`,
  `dominio_ferramenta='dock'`, `possui_interface=False` e
  `fixavel_no_dock=True`. Registrá-los em `registrar_nativos()`.
- `core/interface_canvas.py`: acrescentar traços vetoriais para Secretaria,
  busca de arquivos e resumo; reaproveitar `mute`, `so_nome`, `interrupt`,
  `whatsapp`, `remote`, `webcam`, `cowork`, `computer_use`, `segundo_plano`,
  `menu` (Central) e `system` para os demais.
- `core/central_aplicativos.py`: novo sinal `dock_acao_solicitada(str)` e método
  `definir_acoes_dock(ids)`; `abrir_app()` verifica esse conjunto primeiro e
  emite o sinal em vez de abrir janela/ferramenta. Remover o `QLabel` de estado
  (`●`/`○`) do `AppTile`.
- `ui.py`: ligar o sinal ao novo método `_executar_dock_pela_central(chave)`,
  que fecha a bandeja e chama `self._right_panel.buttons[chave].click()`.
- Ao clicar em qualquer ferramenta mapeada para o dock, a bandeja fecha —
  inclusive no bloco "Central de Aplicativos", que funciona como toggle.

## Deixado para a implementação

- Testes: catálogo completo sem duplicatas, clique emitindo o sinal, ponte
  chamando `.click()`, ausência do indicador verde e ícones novos.
- Rodar a suíte completa e `git diff --check`.
