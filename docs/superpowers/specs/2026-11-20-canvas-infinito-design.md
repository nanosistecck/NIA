# Canvas Infinito + Gerenciador de Planos — desenho combinado (Etapas 1 e 2)

Data: 2026-11-20 · Repositório: NIA (branch `CANVAS-INFINITO`, igual a `main` no início) · Árvore limpa.

## Intenção e porquê

O pedido do dono entrega o Canvas Infinito em duas etapas. A Etapa 1 cria a base local e o
Gerenciador de Planos: abrir **Planos** pelo dock, criar plano com título/objetivo/tipo,
buscar, visualizar, editar, arquivar, restaurar e reabrir após reiniciar. A Etapa 2 usa esse
mesmo plano como documento do editor visual: cards conectados, pan/zoom, progresso, desfazer/
refazer, salvamento automático e volta ao mesmo mapa após reiniciar. Tudo local, sem rede, API
externa ou Ollama. As duas etapas são um único projeto porque a Etapa 2 estende o formato
JSON e o componente de armazenamento da Etapa 1.

## Objetivos

- Plano persistido como JSON UTF-8 versionado, um arquivo por plano, na área de dados do
  usuário, fora da árvore de trabalho, com ID estável e revisão explícita.
- Ferramenta **Planos** no dock, personalizável, com busca tolerante a caixa/acento, filtros
  e ações que funcionam.
- Editor visual no mapa: card central, cards comuns, conexões, progresso de tarefas,
  desfazer/refazer, câmera persistida e salvamento automático com estados de falha.
- Ao abrir o editor: dock recolhido e núcleo no canto inferior direito **sem** mexer nas
  preferências; ao sair: restauração da sessão e volta à lista com filtros e seleção.

## Não-objetivos (nesta entrega)

Comandos de voz/texto, edição assistida, geração de modelos, lembretes, publicação, cards
conectados a dados externos e colaboração. Nenhuma chamada de rede. Nenhum novo F-key global.

## Restrições descobertas no código (recon)

- `CONFIG_DIR` (`ui.py:76-86`) é `BASE_DIR/config`, **dentro da árvore de trabalho**; não pode
  guardar arquivos de usuário. A NIA já adotou `%LOCALAPPDATA%\NIA-CyberBot`
  (`core/secretaria.py:256-264`) e `~/.local/share/NIA-CyberBot` fora do Windows
  (`core/secretaria_chat.py:84-86`).
- Dock: `_build_dock()` (`ui.py:5105-5225`) coleta botões por `objectName` e passa ao
  `VerticalDock` (`core/interface_canvas.py:557-610`), que alimenta sozinho a página
  *Aparência → Ferramentas do dock* (`core/config_dashboard.py:2624-2644`). A migração em
  `interface_canvas.py:570-578` só oculta chaves `skill_*` em perfis existentes.
- `toggle_dock()` (`interface_canvas.py:672-674`) grava `expanded` em `interface.json`;
  **não pode ser chamado** no modo Canvas. `expanded` só é lido em `__init__` (`:583`).
- `CanvasStage.anchor` (`interface_canvas.py:295`, `set_anchor` em `:485-487`) não é
  persistido; `arrange()` (`:492-530`) aceita `'bottom-right'`. `results`/`hoje_host` são
  reposicionados por `arrange()`. `brief` ignora o anchor enquanto visível (`:496-506`).
- `_janela_coberta()` / `_conferir_se_esta_a_vista()` (`ui.py:5253-5306`) pausa HUD e timers
  quando uma janela cobre a principal. Isso descarta editor em janela separada.
- Não existe `QGraphicsScene`/`QGraphicsView`/`QGraphicsItem` no repo (apenas efeitos).
  Não existe preferência de movimento reduzido. Durações atuais: 160/200/220 ms.
- Catálogo de habilidades (`core/catalogo_habilidades.py:58-83`) tem exatamente 3 entradas e
  `tests/test_catalogo_habilidades.py:20-28` fixa essa tupla. Voz/texto são etapa futura:
  **não** mexer no catálogo.
- Padrões reutilizáveis: gravação atômica `.tmp` + `replace`
  (`core/config_preferencias.py:58-64`, `DockPreferences.save()` em `interface_canvas.py:550-554`),
  janela não modal com `fechada` e cache em `self`
  (`ConfigDashboardWindow` em `core/config_dashboard.py:663-726`, `_abrir_dashboard_config`
  em `ui.py:4967-5004`), `StatusLabel.mostrar()` (`:397-415`), `GlassCard` (`:592-610`),
  tokens `C.*` (`ui.py:96-121`) e paletas semânticas (`config_dashboard.py:43-94`).

## Abordagens consideradas

1. **Editor como overlay na janela principal (escolhida).** Widget filho do `centralWidget`,
   sobre a área do stage. Dock recolhido em sessão, núcleo ancorado em `bottom-right` e
   raising acima do overlay. Única opção que mantém escuta/processamento/fala do núcleo
   ativos e atende “núcleo permanece fixo na janela durante pan e zoom”.
2. **Janela separada não modal** (padrão dashboard). Descartada: o núcleo fica atrás e os
   timers pausam por `_janela_coberta()`.
3. **Janela separada com réplica do núcleo.** Descartada: duplicidade de estado e mais risco.

Para o mapa, `QGraphicsScene`/`QGraphicsView` foi escolhido: pan (`ScrollHandDrag`), zoom
ancorado no ponteiro (`AnchorUnderMouse`), `fitInView`, `sceneRect` elástico e itens desenhados
com `QPainter` — sem `QGraphicsProxyWidget`, sem timer próprio e sem renderização contínua.

## Decisões do construtor (registradas como minhas, não do dono)

- Registro de **Planos** como botão fixo do dock (`planos`), não como habilidade do catálogo:
  voz/texto ficam para etapa futura e o teste do catálogo fixa 3 habilidades. Para não alterar
  altura/posições de perfis já existentes, acrescento um marcador de migração
  `dock_planos_v1` em `VerticalDock.__init__`, no mesmo espírito de `skill_atalhos_v1`, que
  oculta `planos` por padrão em perfis antigos; perfis novos mostram o botão.
- `movimento_reducido` é lido de `appearance` em `config/interface.json` com padrão `false`,
  sem novo controle de UI; quando ativo, animações de entrada/saída são substituídas por
  `setVisible` imediato.
- Status internos: `ativo` / `arquivado`. Tipos: `Geral`, `Produto`, `Projeto`, `Conteúdo`,
  `Estudos`, `Finanças` (padrão `Geral`). Formato `formato=1` na Etapa 1, `formato=2` na
  Etapa 2; `revisao` é a revisão de conteúdo, independente do formato.
- O editor é session-only: nada do que faz com dock/anchor/results/HOJE/brief é gravado em
  preferências. Restauração usa valores capturados na abertura.

## Respostas ao builder check (chamadas do construtor)

1. **Dono da `revisao`.** Toda função de gravação devolve um **novo `Plano`** com `revisao`
   incrementada (e não muta o objeto recebido). O editor sempre reatribui `self._plano` ao
   retorno antes de qualquer outra gravação; assim o segundo autosave usa a revisão correta
   e não conflita com o primeiro. `revisao_esperada` é sempre a do objeto em memória.
2. **Conflito ≠ falha de I/O.** `OSError`/`ValueError` → estado *Falha ao salvar* com botão
   **Tentar novamente**, que repete a mesma gravação com a mesma revisão esperada.
   `ConflitoDeRevisao` → estado *Conflito de revisão*, sem auto-sobrescrita: botões
   **Recarregar do disco** (descarta a versão local após confirmação explícita) e
   **Salvar mesmo assim** (releitura + revisão atualizada, sobrescrita deliberada). O trabalho
   em memória nunca é descartado automaticamente.
3. **Saída com pendências.** O botão *← Voltar aos planos* usa a mesma máquina de
   `closeEvent`: se houver alterações pendentes, tenta salvar; se o salvamento falhar ou
   houver conflito, mostra *Salvar e sair / Sair sem salvar / Cancelar*. Escolher
   *Salvar e sair* com falha mantém o editor aberto e o aviso visível — nunca sai
   silenciosamente. Sem alterações pendentes, sai direto.
4. **Card raiz.** O mapa passa a guardar `raiz_id`. O card central criado na inicialização
   é o raiz, não pode ser excluído (Delete é ignorado com aviso) e é o alvo de
   *Voltar ao card central*. Cards comuns criados depois são todos excluíveis. Isso evita a
   ambiguidade de "primeiro card" após exclusões e mantém o undo de exclusão simples.
5. **Inglês.** As strings novas de dock, gerenciador e editor são registradas no dicionário
   `core/interface_en.py`, seguindo o padrão existente, com um teste pontual confirmando que
   os rótulos principais têm tradução. Custo pequeno; evita rótulos PT para clientes `en`.
6. **Override de teste.** `NIA_PLANOS_DIR` tem precedência sobre a guarda "base dentro da
   árvore de trabalho": ela existe para garantir isolamento em testes (`--basetemp` fica
   dentro do repo) e deve ser aceita sem fallback. A guarda continua valendo para o
   caminho resolvido automaticamente.

---

# Parte A — Etapa 1: base local e Gerenciador de Planos

## A1. `core/planos.py` (novo, só stdlib)

- `pasta_dados_usuario()` → base already adopted: `LOCALAPPDATA/NIA-CyberBot` no Windows,
  `XDG_DATA_HOME` ou `~/.local/share/NIA-CyberBot` no Linux, `~/Library/Application Support/
  NIA-CyberBot` no macOS. Override de teste `NIA_PLANOS_DIR`. Se a base resolvida estiver
  **dentro** da árvore de trabalho (comparação de `is_relative_to`), cai para a localização
  por usuário da plataforma. `pasta_planos()` = base/`planos`, criada sob demanda.
- `FORMATO = 1`, `TIPOS`, `STATUS`, `novo_id()` (UUID4), `agora_iso()`.
- `@dataclass Plano`: `id, titulo, objetivo, tipo, status, criado_em, atualizado_em,
  formato, revisao`. Métodos `para_json()` / `de_json()` com validação estrita de tipos,
  faixas e enumerações; campos desconhecidos de versões futuras são preservados em
  `extras`. Título repetido é permitido; renomear/arquivar/restaurar não troca o ID.
- API central (uma única leitura/escrita para catálogo e editor):
  `listar()`, `carregar(id)`, `criar(titulo, objetivo, tipo)`,
  `atualizar(id, mudancas, revisao_esperada)`, `arquivar(id, revisao_esperada)`,
  `restaurar(id, revisao_esperada)`, `excluir(id)` (usado só em testes/limpeza).
- `listar()` varre `planos/*.json` uma vez por abertura, isolando falhas por arquivo e
  devolvendo `(planos, avisos)`; arquivo corrompido, JSON inválido ou `formato` desconhecido
  é ignorado, **preservado no disco** e vira aviso sem conteúdo (nem trecho do JSON) em log.
- Escrita: gravação em `<id>.tmp` na mesma pasta + `os.replace` atômico; `fsync` opcional;
  regrava `atualizado_em`, incrementa `revisao`. Antes de substituir, relê o arquivo e
  compara `revisao`; se divergir, levanta `ConflitoDeRevisao` sem sobrescrever. Em `OSError`,
  mantém o último arquivo válido, apaga o `.tmp` e deixa o chamador com o objeto em memória
  para nova tentativa.
- `buscar(planos, termo, tipo, status)` normaliza com NFKD + `lower()` (mesma ideia de
  `catalogo_habilidades._normalizar`), ordena por `atualizado_em` desc.

## A2. `core/interface_planos.py` (novo, PyQt)

- `PlanosWindow(QWidget)` espelhando `ConfigDashboardWindow`: `fechada = pyqtSignal()`,
  `Window` flag, `WA_DeleteOnClose=False`, `StrongFocus`, tamanho mínimo, estilos via
  `PALETAS`/`C.*` e `StatusLabel`.
- Layout: campo de busca, combo de tipo, combo de status (Ativos/Arquivados/Todos),
  ordenação por última alteração, `QListWidget`/`QTableWidget` com título/tipo/status/
  última alteração, botões **Novo plano**, **Visualizar**, **Editar**, **Arquivar**,
  **Restaurar** (visível no filtro de arquivados), **Abrir no Canvas** (Etapa 2).
- Formulário em painel lateral (não modal dentro da janela): título e objetivo obrigatórios,
  tipo padrão `Geral`; visualização abre os mesmos campos em `readOnly`; edição permite
  título/objetivo/tipo e preserva o ID. Erro de gravação mantém os valores digitados e
  mostra "Falha ao salvar" com **Tentar novamente**.
- Estados explícitos: lista vazia, busca sem resultados, falha de leitura, falha de gravação.
  Seleção e filtros ficam em campos da janela e são preservados quando ela é escondida pelo
  editor.
- Sinais: `abrir_canvas = pyqtSignal(str)` (id do plano) e `voltar = pyqtSignal()`.

## A3. Integração `ui.py`

- `_make_control_button("planos", "▦\nPLANOS\nABRIR", C.PRI)` em `_build_dock`, ligado a
  `_abrir_planos()`. Ícone vetorial `planos` em `_ICONS` (`interface_canvas.py`).
- `_abrir_planos()` segue o padrão `_abrir_dashboard_config`: cache `self._planos_window`,
  `showNormal/raise_/activateWindow`, `fechada` zera o cache.
- `NiaUI` ganha um wrapper thread-safe com `QTimer.singleShot(0, ...)` ao lado dos existentes.
- `VerticalDock.__init__`: marcador `dock_planos_v1` para ocultar `planos` em perfil antigo.

---

# Parte B — Etapa 2: Canvas Infinito

## B1. Extensão do formato em `core/planos.py`

- `FORMATO = 2`, migração aditiva de `formato=1`: `mapa` vazio. `Plano` ganha `mapa: dict`
  com `versao_mapa`, `inicializado`, `cards`, `conexoes`, `camera`.
- Card: `id, tipo (tarefa|ideia|referencia), titulo, resumo, descricao, status, x, y`.
  `status` só é obrigatório para `tarefa`: `pendente|em_andamento|bloqueado|concluido`.
  Conexão: `id, origem, destino, rotulo`. Câmera: `cx, cy, zoom`.
- Validação na leitura e antes de salvar: IDs únicos, referências de conexão existentes,
  sem self-loop, tipos/status enumerados, coordenadas finitas. Referência quebrada é
  descartada com aviso; o restante do mapa continua acessível.
- `inicializar_mapa(id)` cria o card central **somente se** `mapa.cards` estiver vazio e
  `inicializado` for falso; usa `titulo`/`objetivo` do próprio plano como fonte única; marca
  `inicializado=True` na mesma gravação. É repetível: segunda chamada não duplica.
- `resumo_progresso(plano)` conta só cards `tipo == 'tarefa'` agrupados por status.

## B2. `core/interface_mapa.py` (novo, PyQt)

- `MapaView(QGraphicsView)` com `ScrollHandDrag`, `AnchorUnderMouse`, `RubberBandDrag`,
  `TransformationAnchor` e `ViewportAnchor`; roda aplica fator de zoom limitado (0.2–3.0).
  `fitInView` com margem que reserva o canto do núcleo; `voltar_ao_central()` centraliza no
  card raiz. `sceneRect` cresce conforme os cards se movem — sem varredura de arquivos.
- `CardItem(QGraphicsItem)` desenhado com QPainter: título, resumo curto, badge de status
  quando tarefa; seleção com traço mais espesso **e** contorno tracejado (indicador que não
  depende de cor). `itemChange(ItemPositionHasChanged)` atualiza apenas as conexões
  incidentes. Durante arraste, posição visual muda; a gravação acontece no `mouseReleaseEvent`.
- `ConexaoItem(QGraphicsPathItem)` com rótulo opcional; recalcula a curva quando um card se
  move. Excluir card remove as conexões incidentes na **mesma operação**.
- `Adicionar conectado` posiciona o novo card a uma distância fixa do originador, deslocado
  em leque, **sem** reprogramar cards que o usuário já moveu.
- Painel de detalhes (`QWidget` lateral): título, resumo, descrição, tipo, progresso,
  rótulo da conexão selecionada, botões Salvar/Excluir. Atalhos Delete/Backspace,
  Ctrl+Z, Ctrl+Y/Ctrl+Shift+Z com `Qt.ShortcutContext.WidgetWithChildrenShortcut` e guarda
  `isinstance(QApplication.focusWidget(), (QLineEdit, QTextEdit, QPlainTextEdit))`.
- `QUndoStack` com comandos: `CriarCard`, `EditarCard`, `MoverCard` (uma operação por soltar),
  `AlterarProgresso`, `CriarConexao`, `EditarConexao`, `ExcluirCard` (guarda card + conexões,
  restaura ambos no undo), `ExcluirConexao`.
- Salvamento: `QTimer` de debounce (~400 ms para edições, ~600 ms para câmera) dispara
  `salvar()`; estados `Salvando… / Salvo / Falha ao salvar` no `StatusLabel`. Falha mantém
  objeto em memória, mostra **Tentar novamente** e não descarta nada. `closeEvent` com
  alterações pendentes: tenta salvar; se ainda falhar, `QMessageBox` com
  *Salvar e sair / Sair sem salvar / Cancelar*.

## B3. `core/interface_canvas_planos.py` (novo) — `CanvasEditor`

- Overlay filho do **`CanvasStage`** (não do `centralWidget`): sendo irmão de `hud_stack`
  dentro do mesmo pai, `stage.hud_stack.raise_()` realmente o coloca acima do overlay.
  Se fosse filho do `centralWidget`, o overlay seria irmão do próprio stage e o `raise_()`
  interno não adiantaria. Geometria = `stage.rect()` menos a reserva do núcleo, recalculada
  no `resizeEvent` do stage (o recolhimento do dock muda a largura do stage via relayout).
  Toolbar com **← Voltar aos planos**, Novo card, Adicionar conectado,
  Conexão, Enquadrar, Card central, Desfazer, Refazer e o `StatusLabel`.
- Para impedir que `arrange()` reexiba `results`/`hoje_host` e que um brief ignorando o
  anchor apareça sobre o mapa, `CanvasStage` ganha uma flag de sessão `_canvas_editor_ativo`
  (padrão `False`): `arrange()` não mostra `results`/`hoje` enquanto ela estiver ativa e
  `_show_canvas_brief` em `ui.py` descarta briefs recebidos nesse estado. Ao sair, a flag
  volta a `False` e o estado original dos painéis é reaplicado. Nada disso é persistido.
- Abertura (`MainWindow._abrir_canvas_do_plano(id)`):
  1. esconde `PlanosWindow` (mantém cache, filtros e seleção);
  2. captura `dock.expanded`, `stage.anchor`, visibilidade de `results`/`hoje_host`/brief;
  3. `dock.expanded=False; dock.apply()` (sem `persist()`), `stage.set_anchor('bottom-right')`,
     esconde resultados/HOJE/brief, `_position_canvas_panels()`;
  4. `inicializar_mapa(id)` se preciso, carrega o mapa, mostra o overlay e faz
     `stage.hud_stack.raise_()` para manter o núcleo acima;
  5. animação curta de entrada (ou `setVisible` imediato se `movimento_reducido`).
- Saída (`Voltar aos planos`): salva pendências, restaura dock/anchor/painéis com os valores
  capturados (sem gravar preferências), esconde o overlay, reexibe `PlanosWindow` com os
  filtros e o plano selecionado.
- `QShortcut` herdados da MainWindow continuam ativos; os atalhos do mapa são locais ao
  overlay e respeitam o foco de texto.

---

# Parte C — Etapa 3: comandos por voz e texto (Prompt 03)

## C1. Fluxo compartilhado (recon)

O texto digitado entra por `MainWindow._send` (`ui.py:6106-6112`) → `on_text_command` →
`main._on_text_command` (`main.py:3417`). A voz local entrega a transcrição final em
`_ouvir_agora` (`main.py:9169`, uso em `9773-9780`) e a Gemini Live em `_receive_audio`
(`main.py:11861`, bloco `turn_complete` `12087-12134`). **Os três canais chamam
`_executar_frase_habilidade(texto, origem)`** (`main.py:6960`, chamadas em `3522`, `9777`,
`12131`). É esse o ponto único do reconhecedor de planejamento, ao lado de `CH.reconhecer`
(`6962`), antes de qualquer LLM, com `return True` quando a intenção foi tratada.

Perguntas pendentes precisam de tratamento anterior e separado: `_tratar_confirmacao_sintese`
é chamado em `3436`, `9773` e `12119`. `_tratar_pendente_planos(texto)` será chamado nos
mesmos três pontos, imediatamente antes dele, para que "o segundo", "cancelar" ou o tema
faltante sejam consumidos como resposta à pergunta anterior, sem virar novo comando.

Saída: `ui.write_log` para a conversa, `ui.show_content` para card rico, `_falar_local`
para TTS quando fizer sentido; abertura de tela **somente** por wrapper thread-safe da
`NiaUI` (`QTimer.singleShot(0, ...)`), nunca tocando Qt da thread do motor.

## C2. `core/comandos_planos.py` (novo, local, sem IA/rede)

- `normalizar()` com NFKD + `casefold` (mantém o original para gravar título/objetivo).
- `reconhecer(texto, contexto) -> (intencao, dados)` com intenções: `CRIAR`, `RETOMAR`,
  `ABRIR`, `OBJETIVO`, `PROGRESSO`, `CARD_TITULO`, `EXPLICAR` (repasse), `NEGAR`
  (sem ação), `NENHUMA`. Reconhece variações abrir/retomar/continuar/criar/começar/iniciar/
  planejar; distingue negação ("ainda não quero"), pergunta informativa ("me explica como")
  e hipotético do pedido real. Extrai tipo (produto/projeto/estudo/conteúdo/finanças →
  `Estudos`) e tema/título/objetivo da frase.
- `SessaoComandos`: `pendente` (tipo, dados já coletados, campos faltantes, `seq`, `em`),
  `opcoes` (ids apresentados para "o segundo"), `plano_contexto_id`, `card_contexto_id`,
  `vistos` (chave normalizada + timestamp, janela curta). Expira pendências após ~180 s;
  `cancelar` limpa sem salvar. Dedup reusa a ideia de `main._transcript_key()` e
  `secretaria_chat._vistos`: mesma chave em janela curta é reentrega e não cria nada.
- Resolução de referência: nome explicitado tem prioridade; "esse projeto" usa
  `plano_contexto_id`; "esse card" usa `card_contexto_id`. Referência que não existe mais
  pede nova indicação. Vários resultados → opções com título/tipo/última alteração e
  seleção por ordinal conferida contra a lista viva. Nenhum resultado → oferece Gerenciador
  ou criar, **sem criar automaticamente**. Plano só arquivado → informa e oferece
  visualizar/restaurar.
- Consultas usam o mapa em memória quando o editor está aberto (via callback de contexto)
  e a versão salva quando fechado; progresso conta só tarefas e distingue "sem tarefas"
  de "todas concluídas".

## C3. Integração

- `main.py`: `_tratar_pendente_planos()` ao lado de `_tratar_confirmacao_sintese`;
  reconhecedor em `_executar_frase_habilidade`; método `_acao_comando_plano(...)` que
  executa ações devolvidas (`criar`, `abrir_canvas`, `abrir_manager`, `responder`) via
  `self.ui.*`. Logs técnicos só por `_voice_diag(evento, detalhe_seguro)` (`main.py:854-855`):
  nome do evento, id do plano e tamanho — **nunca** conteúdo do plano.
- `ui.py`: `NiaUI.abrir_plano(id)`, `abrir_planos()`, `contexto_canvas()` e
  `definir_contexto_canvas(plano_id, card_id)` com `QTimer.singleShot(0, ...)`;
  `MainWindow._abrir_plano(id)` reusa exatamente `_abrir_canvas_do_plano(id)` da Etapa 2,
  incluindo salvar/restaurar se houver mudanças pendentes.
- Derivação para criação: título e objetivo obrigatórios são preenchidos a partir do tema
  informado quando claro (ex.: "Vamos planejar um produto para pequenos lojistas" → tipo
  `Produto`, título "Produto para pequenos lojistas", objetivo = frase original); se faltar
  campo, pergunta e aguarda; falha de gravação preserva os dados para nova tentativa.
- `core/interface_en.py`: novas respostas e rótulos também traduzidos.

## C4. Testes da Etapa 3

- `tests/test_comandos_planos.py`: reconhecimento das 10 frases do prompt; negação,
  informativo e mudança de assunto; criação completa e incompleta com cancelamento;
  ambiguidade com "o segundo"; plano arquivado; nenhum resultado; dedup de reentrega;
  expiração de pendência; contexto de card/plano; progresso com e sem tarefas.
- Teste de integração: mesma intenção enviada por `on_text_command` e por transcrição
  simulada em `_executar_frase_habilidade` deve criar **um** plano e abrir o Canvas uma vez.
- Sem rede/Ollama nos testes; transcrição de voz simulada será explicitada na entrega.

# Testes

- `tests/test_planos.py`: ID estável em renomear/arquivar/restaurar; persistência após
  "reinício" (nova instância da API sobre a mesma pasta); título repetido; tipos; escrita
  interrompida preserva o arquivo anterior (monkeypatch em `os.replace`/`Path.write_text`);
  JSON corrompido e `formato` desconhecido isolados sem expor conteúdo; conflito de revisão;
  busca sem acento/caixa; arquivos fora da árvore de trabalho (override `NIA_PLANOS_DIR`).
- `tests/test_interface_planos.py`: fluxo por clique (criar → buscar → visualizar → editar
  sem trocar ID → arquivar → restaurar), estados vazios e mensagens de erro.
- `tests/test_canvas_mapa.py`: plano antigo `formato=1` abre e inicializa card central uma
  única vez; criar/editar/mover/conectar/excluir e desfazer/refazer; exclusão com conexões
  desfeita e refeita junta; conexões acompanham o movimento; progresso conta só tarefas;
  câmera e posições restauradas após reinício; falha de gravação e conflito preservam o
  trabalho; debounce agrupa gravações.
- `tests/test_interface_canvas.py`: acrescentar asserção de que `planos` está em
  `_right_panel.buttons`, aparece na página de Ferramentas do dock e é ocultado por padrão
  em perfil antigo; confirmar que `toggle_dock()` normal ainda persiste.
- `tests/test_integracao_final.py` (ou novo teste pontual): abrir/fechar editor restaura
  dock, anchor e lista; F2/F4/F6/F9/F11/ESC e chat/brief continuam respondendo.

Execução: `$env:QT_QPA_PLATFORM='offscreen'; & .venv-apis/Scripts/python.exe -m pytest -q
-p no:cacheprovider --basetemp=cache/pytest-canvas` (Python 3.12.14, PyQt6 6.12.1, pytest 9.2.0).

# Riscos e mitigação

- `arrange()` com brief visível ignora anchor → esconder brief ao abrir e restaurar ao sair.
- `setMaximumHeight` do dock dispara relayout → chamar `_position_canvas_panels()` via
  `QTimer.singleShot(0, ...)`.
- `os.replace` em disco de rede pode falhar → tratado como falha de gravação com retry.
- QUndoStack comandos e autosave precisam ser idempotentes por `revisao`; conflito detectado
  antes de cada gravação.
- Nenhum timer novo em repouso: `QGraphicsView` só repinta quando algo muda.

# Entrega e verificação

Ao final: resumo do implementado, componentes reaproveitados, remoções justificadas (nenhuma
prevista além de imports mortos), comandos executados, resultados e validações pendentes com
motivo. Nenhum commit/push/PR sem pedido explícito.
