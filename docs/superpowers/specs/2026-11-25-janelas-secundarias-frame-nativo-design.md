# Barra nativa sem título/ícone nas janelas secundárias da NIA

Data: 2026-11-25

## Intenção

As janelas separadas da NIA que hoje mostram a legenda nativa do Windows
(Configurações, Agenda, Planos e Globo) devem passar a mostrar **somente os três
botões** (minimizar, maximizar/restaurar, fechar), sem texto de título e sem
ícone, com a faixa da legenda na cor da própria janela. O efeito deve ser o mesmo
já usado pela `MainWindow`, mas reutilizável para janelas futuras do mesmo tipo.

## Goals

- Configurações (`ConfigDashboardWindow`), Agenda (`AgendaWindow`), Planos
  (`PlanosWindow`) e Globo (`globo/janela.py`) abrem com os 3 controles nativos,
  sem título/ícone visíveis e com a faixa na cor da janela.
- Uma única implementação do efeito, importável por processos separados (Globo
  roda com `QApplication` própria).
- Janelas separadas criadas no futuro seguem a mesma convenção (mixin/helper).
- `windowTitle()` continua preenchido para barra de tarefas e acessibilidade;
  o título desaparece apenas visualmente na legenda.

## Non-goals

- Não mexer na janela do WhatsApp (`secretaria/navegador_qt.py`) nesta rodada —
  o usuário vai tratar a aparência dela depois.
- Não mexer em `AvisoComputador`, cartão da secretária, overlays de QR/remote,
  menus, tooltips nem diálogos modais: são janelas sem borda ou sem barra de
  título por desenho.
- Não mudar o comportamento da `MainWindow` (tamanho, maximização, gradiente).
- Não trocar `FramelessWindowHint`, `showFullScreen()` nem a preferência
  `janela_sem_bordas`.

## Anti-goals

- Criar botões próprios (`─ ▢ ×`) em Qt. A solução anterior foi removida em
  `dc72822` porque não ficou boa.
- Aplicar o frame a toda janela top-level sem critério (capturaria `QMessageBox`,
  diálogos de arquivo, popups do WebEngine e janelas que mudam flags depois).

## Constraints

- `core/windows_frame.py` foi escrito para a `MainWindow`: lê
  `centralWidget().layout()` e o cache `_cache` do `CanvasBackground`
  (`windows_frame.py:99-100, 143-148`). As secundárias não têm `centralWidget`
  nem `_cache`.
- O truque que esconde título/ícone mantendo os botões é o DIB com alpha=0 na
  faixa estendida pelo DWM (`windows_frame.py:130-167`); simplesmente limpar
  `setWindowTitle()`/ícone apagaria também o rótulo na barra de tarefas.
- `GerenciadorJanelas` cobre Configurações/Agenda/Planos/Globo, mas Globo e
  WhatsApp rodam em processo separado (`secretaria/motor.py:1946`).
- A suíte roda com Qt offscreen: o helper precisa ser no-op fora do Windows.

## Approaches

- **A (escolhida):** módulo `core/frame_nativo.py` com
  `aplicar_frame_nativo(janela, cor=None)` e `FrameNativoMixin`; o `WindowsFrame`
  existente é generalizado para aceitar uma cor de legenda e um layout sem
  `centralWidget`. Cada janela chama o helper/herda o mixin. Previsível, testável
  e não afeta quem não optou por isso.
- **B (rejeitada):** event filter global no `QApplication`. Cobre janelas futuras
  automaticamente, mas captura diálogos/popups e depende da ordem dos eventos de
  `show()` e de mudanças de flags.
- **C (rejeitada):** aplicar dentro de `GerenciadorJanelas.abrir()`. Não cobre
  Globo (processo separado) nem janelas futuras não registradas.

## Como (decisões já tomadas)

- `core/windows_frame.py`: construtor aceita uma fonte de pixels da legenda.
  Quando não é informada, mantém o comportamento atual (cache do Canvas da
  principal). `reserve_caption()` usa `janela.layout()` quando não há
  `centralWidget()`. `paint_caption()` preenche a faixa com a cor informada
  quando não há cache (alpha zerado para esconder os glifos do DWM).
- `core/frame_nativo.py` (novo): `FrameNativoMixin` fornece `event()` e
  `nativeEvent()` delegando ao frame, espelhando `ui.py:4606-4632`, e um método
  para instalar. `aplicar_frame_nativo()` é a função de conveniência.
- Cor da faixa: explícita em cada janela, retirada do valor que ela já usa
  (palette/tema ou CSS). Sem `cor=`, o helper usa `QPalette.ColorRole.Window`.
- `core/config_dashboard.py`, `core/interface_agenda.py`,
  `core/interface_planos.py`: herdam o mixin e instalam o frame ao fim de
  `__init__`, depois de definir título/estilo/tema.
- `globo/janela.py`: trocar o `QMainWindow()` local por uma subclasse mínima com
  o mixin (a janela é criada dentro de uma função).
- `MainWindow` continua usando o `WindowsFrame` com os mesmos argumentos de
  antes — nenhuma mudança de comportamento.
- Fora do Windows o helper retorna `False` e não altera a janela.

## Deixado para a implementação

- Testes: confirmar que as quatro janelas instalam o frame, que `windowTitle()`
  permanece preenchido, que nada muda em offscreen e que a principal segue
  maximizada sem `FramelessWindowHint`.
- Rodar a suíte completa e `git diff --check`.
- Janelas futuras: documentar a convenção no próprio `core/frame_nativo.py`.
