# Canvas Infinito (Etapas 1, 2 e 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar base local versionada de planos, gerenciador no dock, editor visual de mapa com pan/zoom/undo/autosave e comandos de planejamento compartilhados por chat e voz, sem rede/API externa/Ollama.

**Architecture:** Camada de dados pura em `core/planos.py` (um JSON versionado por plano na área de dados do usuário, escrita atômica, revisão explícita). Duas camadas Qt separadas: `core/interface_planos.py` (gerenciador) e `core/interface_mapa.py` + `core/interface_canvas_planos.py` (editor `QGraphicsView` como overlay do `CanvasStage`, nunca janela separada). Comandos de linguagem natural em `core/comandos_planos.py`, acionados pelo único ponto compartilhado `_executar_frase_habilidade` de `main.py`, com respostas pendentes tratadas ao lado de `_tratar_confirmacao_sintese`.

**Tech Stack:** Python 3.12.14, PyQt6 6.12.1 (QGraphicsView/QUndoStack/QShortcut), pytest 9.2.0, stdlib (`json`, `uuid`, `unicodedata`, `os.replace`), `.venv-apis`.

**Spec:** `docs/superpowers/specs/2026-11-20-canvas-infinito-design.md`

## Global Constraints

- Nenhuma chamada de rede, API externa ou Ollama em criação/busca/edição/consulta de planos.
- Arquivos de plano, `.tmp` e cópias de recuperação **fora da árvore de trabalho**; base adotada `%LOCALAPPDATA%/NIA-CyberBot` (Windows), `XDG_DATA_HOME` ou `~/.local/share/NIA-CyberBot` (Linux), `~/Library/Application Support/NIA-CyberBot` (macOS). `NIA_PLANOS_DIR` tem precedência sobre a guarda de work-tree.
- `formato` (versão do formato) separado de `revisao` (revisão de conteúdo). `FORMATO=1` na Etapa 1, `FORMATO=2` na Etapa 2. `revisao` começa em 0 e só aumenta; gravação devolve novo `Plano`.
- Escrita: `<id>.json.tmp` na mesma pasta + `os.replace`; em falha manter último arquivo válido e objeto em memória; antes de substituir comparar `revisao` e levantar `ConflitoDeRevisao`.
- Nunca expor conteúdo de plano em log de diagnóstico; usar `main._voice_diag(evento, detalhe_seguro)` com id/tamanho, não texto.
- Não alterar `core/catalogo_habilidades.py` (teste fixa exatamente 3 habilidades); voz/texto de planos não entram no catálogo.
- Novos F-key globais: nenhum. F2/F4/F6/F9/F11/ESC permanecem intactos. Atalhos do mapa são locais e respeitam foco de `QLineEdit`/`QTextEdit`.
- Recolhimento do dock e âncora do núcleo no Canvas são **session-only**: nunca chamar `VerticalDock.toggle_dock()` nem `persist()` nesse caminho.
- Estilos/temas existentes (`C.*`, `PALETAS`, `GlassCard`, `StatusLabel`, `interface_en.py`); seleção precisa de indicação visual não baseada só em cor.
- Execução de testes: `$env:QT_QPA_PLATFORM='offscreen'; & .venv-apis/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=cache/pytest-canvas`
- Todo commit ao final de cada tarefa; sem push/PR.

## Review Focus

1. **Reentrega da mesma transcrição cria plano duplicado** → teste de dedup em `tests/test_comandos_planos.py` (Task 6, Step 1).
2. **Segundo autosave conflita com o primeiro** por revisão desatualizada em memória → teste de "duas gravações consecutivas" em `tests/test_planos.py` (Task 1, Step 1).
3. **Arquivo corrompido/desconhecido impede os demais** → teste de isolamento em `tests/test_planos.py` (Task 1, Step 1).
4. **Exclusão de card com conexões desfeita incompleta** → teste de undo/redo atômico em `tests/test_canvas_mapa.py` (Task 4, Step 1).
5. **Saída do editor com falha de gravação perde trabalho** → teste de close/back com pendência em `tests/test_integracao_canvas.py` (Task 5, Step 1).

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `core/planos.py` (novo) | persistência versionada, validação, busca, revisão, mapa no mesmo JSON |
| `core/interface_planos.py` (novo) | `PlanosWindow`: catálogo, filtros, formulário, estados de erro |
| `core/interface_mapa.py` (novo) | `MapaView`, `CardItem`, `ConexaoItem`, `EditorMapa`, comandos `QUndoCommand`, autosave |
| `core/interface_canvas_planos.py` (novo) | `CanvasEditor`: overlay, toolbar, contexto, integração com MainWindow |
| `core/comandos_planos.py` (novo) | reconhecedor local, sessão conversacional, dedup, resolução de referências |
| `ui.py` (modificar) | botão dock `planos`, abertura/reuso de janelas, wrappers `NiaUI`, flag de sessão no `CanvasStage` via `core/interface_canvas.py` |
| `core/interface_canvas.py` (modificar) | ícone `planos`, migração `dock_planos_v1`, flag `_canvas_editor_ativo` em `arrange()` |
| `main.py` (modificar) | hook do reconhecedor, pendente de planos, ações via `NiaUI`, logs seguros |
| `core/interface_en.py` (modificar) | traduções das strings novas |
| `tests/test_planos.py`, `tests/test_interface_planos.py`, `tests/test_canvas_mapa.py`, `tests/test_integracao_canvas.py`, `tests/test_comandos_planos.py` (novos) | cobertura pontual por risco |
| `tests/test_interface_canvas.py`, `tests/test_catalogo_habilidades.py` (modificar) | asserções de dock/regressão |

---

### Task 1: Camada de dados versionada (`core/planos.py`)

**Files:**
- Create: `core/planos.py`
- Test: `tests/test_planos.py`

**Interfaces:**
- Consumes: nada (stdlib).
- Produces: `FORMATO`, `TIPOS`, `STATUS`, `Plano`, `ErroPlano`, `PlanoInvalido`, `ConflitoDeRevisao`, `base_dados_usuario()`, `pasta_planos()`, `novo_id()`, `agora_iso()`, `listar()`, `carregar()`, `criar()`, `atualizar()`, `arquivar()`, `restaurar()`, `buscar()`.

`Plano` campos: `id, titulo, objetivo, tipo='Geral', status='ativo', criado_em='', atualizado_em='', formato=FORMATO, revisao=0, extras:dict, mapa:dict`. Métodos `para_json() -> dict` e `classmethod de_json(dados: dict) -> Plano`.

- [ ] **Step 1: Escrever testes de persistência e falhas**

`tests/test_planos.py` com fixture `pasta(tmp_path, monkeypatch)` que define `NIA_PLANOS_DIR` para `tmp_path/"dados"` (fora da árvore de trabalho do teste). Testes:
```python
def test_criar_revisao_e_reabrir_apos_reinicio(pasta):
    p = criar("Fotografia", "Estudar composição", "Estudos")
    assert p.id and p.revisao == 0 and p.tipo == "Estudos"
    p2 = atualizar(p.id, {"titulo": "Fotografia II"}, p.revisao)
    assert p2.revisao == 1 and p2.id == p.id
    assert carregar(p.id).titulo == "Fotografia II"
    assert carregar(p.id).revisao == 1

def test_duas_gravacoes_consecutivas_nao_conflitam(pasta):
    p = criar("A", "B")
    p2 = atualizar(p.id, {"titulo": "C"}, p.revisao)
    p3 = atualizar(p.id, {"objetivo": "D"}, p2.revisao)
    assert p3.revisao == 2

def test_conflito_de_revisao_nao_sobrescreve(pasta):
    p = criar("A", "B")
    atualizar(p.id, {"titulo": "Remoto"}, 0)
    with pytest.raises(ConflitoDeRevisao):
        atualizar(p.id, {"titulo": "Local"}, 0)
    assert carregar(p.id).titulo == "Remoto"

def test_arquivo_invalido_e_formato_desconhecido_isolados(pasta, caplog):
    p = criar("Ok", "Valido")
    (pasta_planos()/"quebrado.json").write_text("{", encoding="utf-8")
    (pasta_planos()/"futuro.json").write_text(
        json.dumps({"id":"x","formato":999,"titulo":"SEGREDO"}), encoding="utf-8")
    planos, avisos = listar()
    assert [x.id for x in planos] == [p.id]
    assert len(avisos) == 2 and all("SEGREDO" not in a for a in avisos)

def test_falha_de_escrita_preserva_arquivo(pasta, monkeypatch):
    p = criar("A", "B")
    original = (pasta_planos()/f"{p.id}.json").read_text(encoding="utf-8")
    def falhar(*args, **kwargs):
        raise OSError("disco cheio")
    monkeypatch.setattr("core.planos._replace", falhar)  # alias module-level de os.replace
    with pytest.raises(OSError):
        atualizar(p.id, {"titulo": "Nao grava"}, p.revisao)
    assert (pasta_planos()/f"{p.id}.json").read_text(encoding="utf-8") == original

def test_busca_aceita_acento_e_caixa_e_titulo_repetido(pasta):
    a = criar("Fotografia", "Luz", "Estudos")
    b = criar("Fotografia", "Cor", "Estudos")
    assert a.id != b.id
    encontrados = {x.id for x in buscar(listar()[0], "FOTOGRAFIA")}
    assert encontrados == {a.id, b.id}
    assert buscar(listar()[0], tipo="Produto") == []
```

- [ ] **Step 2: Rodar e confirmar falha** — `pytest tests/test_planos.py -q` → FAIL (módulo inexistente).

- [ ] **Step 3: Implementar `core/planos.py`**

Expor `_replace = os.replace` no nível do módulo para permitir monkeypatch isolado. `base_dados_usuario()` usa `NIA_PLANOS_DIR` primeiro; senão `LOCALAPPDATA`/`XDG_DATA_HOME`/`Path.home()` por plataforma; se o caminho resolvido for relativo à raiz do repo (`Path(__file__).resolve().parents[1]`), usar fallback da plataforma. `listar()` lê `*.json` uma vez, isola exceções por arquivo e devolve avisos sem conteúdo. `criar/atualizar/arquivar/restaurar` validam antes de gravar, releem para conferir `revisao`, gravam `.tmp` + `os.replace` e devolvem novo `Plano`. `buscar()` normaliza NFKD+casefold.

- [ ] **Step 4: Rodar testes** — `pytest tests/test_planos.py -q` → PASS.

- [ ] **Step 5: Commit** — `git add core/planos.py tests/test_planos.py && git commit -m "feat(planos): base local versionada com gravacao atomica"`

---

### Task 2: Gerenciador de Planos e dock

**Files:**
- Create: `core/interface_planos.py`, `tests/test_interface_planos.py`
- Modify: `ui.py`, `core/interface_canvas.py`, `core/interface_en.py`, `tests/test_interface_canvas.py`

**Interfaces:**
- Consumes: Task 1 (`criar`, `listar`, `buscar`, `atualizar`, `arquivar`, `restaurar`, `Plano`).
- Produces: `PlanosWindow(fechada=pyqtSignal(), abrir_canvas=pyqtSignal(str))` com `plano_selecionado_id`, `aplicar_filtros()`, `recarregar()`, `selecionar(plano_id)`; `MainWindow._abrir_planos()`, `NiaUI.abrir_planos()`.

- [ ] **Step 1: Escrever testes do fluxo por clique**

`tests/test_interface_planos.py`: fixture `app` (module, `QApplication.instance() or QApplication([])`) e `janela(tmp_path, monkeypatch)` com `QT_QPA_PLATFORM=offscreen` antes do import, `monkeypatch.setattr(ui, "CONFIG_DIR", tmp_path)` e `NIA_PLANOS_DIR=tmp_path/"dados"`. Testes:
```python
def test_criar_buscar_visualizar_editar_arquivar_restaurar(janela):
    plano_id = criar_plano_pela_tela(janela, "Fotografia", "Estudar luz", "Estudos")
    buscar_pela_tela(janela, "fotogra")  # sem acento
    assert janela.plano_selecionado_id == plano_id
    editar_titulo_pela_tela(janela, "Fotografia II")
    assert carregar(plano_id).id == plano_id
    assert carregar(plano_id).titulo == "Fotografia II"
    arquivar_pela_tela(janela)
    assert carregar(plano_id).status == "arquivado"
    restaurar_pela_tela(janela)
    assert carregar(plano_id).status == "ativo"

def test_estados_vazios_e_erro_preserva_digitado(janela, monkeypatch):
    # lista vazia, busca sem resultado
    # monkeypatch atualizar para levantar OSError
    # "Falha ao salvar" visivel e campos ainda preenchidos
```

Acrescentar em `tests/test_interface_canvas.py`:
```python
def test_botao_planos_registrado_e_personalizavel(window):
    dock = window._right_panel
    assert "planos" in dock.buttons
    assert dock.buttons["planos"].objectName() == "planos"
    assert "planos" in dock.preferences.data.get("order", [])
```

- [ ] **Step 2: Rodar e confirmar falha** — `pytest tests/test_interface_planos.py tests/test_interface_canvas.py -q` → FAIL.

- [ ] **Step 3: Implementar `PlanosWindow` e integração**

`core/interface_planos.py` espelha `ConfigDashboardWindow` (`Window` flag, `WA_DeleteOnClose=False`, `StrongFocus`, `fechada`). Busca com `QLineEdit`, combos de tipo/status, `QListWidget`, painel de formulário, `StatusLabel`. Em `ui.py`: `_make_control_button("planos", ...)` em `_build_dock`, ligação a `_abrir_planos()` com cache `self._planos_window` no padrão `_abrir_dashboard_config`; wrapper `NiaUI.abrir_planos()` com `QTimer.singleShot(0, ...)`. Em `core/interface_canvas.py`: ícone `planos` em `_ICONS` e marcador `dock_planos_v1` em `VerticalDock.__init__` que oculta `planos` só em perfil existente. Traduções em `interface_en.py`.

- [ ] **Step 4: Rodar testes** — `pytest tests/test_interface_planos.py tests/test_interface_canvas.py -q` → PASS.

- [ ] **Step 5: Commit** — `git add ... && git commit -m "feat(planos): gerenciador no dock com busca, filtros e CRUD"`

---

### Task 3: Extensão do formato com mapa (Etapa 2, dados)

**Files:**
- Modify: `core/planos.py`
- Test: `tests/test_plano_mapa.py` (novo)

**Interfaces:**
- Consumes: Task 1.
- Produces: `FORMATO=2`, `TIPOS_CARD`, `STATUS_TAREFA`, `mapa_vazio()`, `validar_mapa(mapa)->(dict, list[str])`, `inicializar_mapa(plano_id)->Plano`, `resumo_progresso(plano)->dict`, `card_por_id(plano, card_id)->dict|None`.

`mapa` = `{'versao_mapa': 1, 'inicializado': bool, 'raiz_id': str, 'cards': [...], 'conexoes': [...], 'camera': {'cx':0.0,'cy':0.0,'zoom':1.0}}`.

- [ ] **Step 1: Escrever testes de migração e validação**
```python
def test_plano_v1_abre_e_inicializa_card_central_uma_vez(pasta):
    p = criar("Produto X", "Vender para lojistas", "Produto")  # FORMATO=2 ao criar
    # simular plano v1 gravando JSON sem 'mapa'
    ...
    p1 = carregar(p.id)
    assert p1.mapa["cards"] == []
    p2 = inicializar_mapa(p.id)
    p3 = inicializar_mapa(p2.id)
    assert len(p3.mapa["cards"]) == 1
    central = p3.mapa["cards"][0]
    assert central["titulo"] == p3.titulo
    assert central["descricao"] == p3.objetivo
    assert p3.mapa["raiz_id"] == central["id"]

def test_referencia_quebrada_de_conexao_e_descartada_com_aviso(pasta):
    # mapa com conexao apontando id inexistente
    mapa, avisos = validar_mapa(mapa)
    assert mapa["conexoes"] == [] and avisos

def test_resumo_progresso_conta_so_tarefas(pasta):
    # 2 tarefas (uma concluida, uma bloqueada) + 1 ideia
    r = resumo_progresso(plano)
    assert r["pendente"] == 0 and r["em_andamento"] == 0
    assert r["bloqueado"] == 1 and r["concluido"] == 1 and r["total"] == 2
```

- [ ] **Step 2: Rodar e confirmar falha** → FAIL.

- [ ] **Step 3: Implementar extensão**

`FORMATO=2`; `Plano.de_json` preenche `mapa` vazio quando ausente (migração aditiva) e preserva `extras`. `validar_mapa` remove conexões com origem/destino inexistente, self-loop e status inválidos, devolvendo avisos. `inicializar_mapa` é idempotente por `inicializado`/`raiz_id` e grava na mesma revisão atômica. `resumo_progresso` filtra `tipo == 'tarefa'`.

- [ ] **Step 4/5: Rodar testes e commit** — `pytest tests/test_plano_mapa.py -q`; `git commit -m "feat(planos): mapa versionado no mesmo JSON do plano"`

---

### Task 4: Editor visual `QGraphicsView`

**Files:**
- Create: `core/interface_mapa.py`, `tests/test_canvas_mapa.py`

**Interfaces:**
- Consumes: Task 3 (`inicializar_mapa`, `validar_mapa`, `resumo_progresso`, `atualizar`).
- Produces: `EditorMapa(QWidget)` com `carregar(plano: Plano)`, `plano_atual() -> Plano`, `selecionar(card_id)`, `criar_card(dados)`, `adicionar_conectado(origem_id)`, `excluir_selecionado()`, `desfazer()`, `refazer()`, `salvar() -> tuple[bool, str]`, `enquadrar()`, `voltar_ao_central()`, `mudancas_pendentes: bool`, sinal `estado_salvamento = pyqtSignal(str)`.

- [ ] **Step 1: Escrever testes do mapa**
```python
def test_excluir_card_com_conexoes_e_desfeito_e_refeito(app, plano_com_mapa):
    ed = EditorMapa(); ed.carregar(plano_com_mapa)
    antes = len(ed.plano_atual().mapa["conexoes"])
    ed.selecionar(card_id); ed.excluir_selecionado()
    assert len(ed.plano_atual().mapa["cards"]) == N-1
    assert todas as conexoes incidentes sumiram
    ed.desfazer()
    assert len(ed.plano_atual().mapa["cards"]) == N
    assert len(ed.plano_atual().mapa["conexoes"]) == antes
    ed.refazer(); ...

def test_conexoes_acompanham_movimento(app, plano_com_mapa):
    # mover item via setPos e mouseRelease simulado
    # assert endpoints da ConexaoItem mudaram e uma unica entrada na pilha de undo

def test_camera_e_posicoes_restauradas(app, pasta):
    # editar, salvar, criar novo EditorMapa e carregar carregar(id)
    assert camera == ... and posicoes == ...

def test_falha_de_gravacao_mantem_trabalho(app, plano_com_mapa, monkeypatch):
    def falhar(*args, **kwargs):
        raise OSError("disca cheia")
    monkeypatch.setattr("core.interface_mapa.atualizar", falhar)
    ok, erro = ed.salvar()
    assert not ok and ed.mudancas_pendentes and ed.plano_atual().mapa == antes
```

- [ ] **Step 2: Rodar e confirmar falha** → FAIL.

- [ ] **Step 3: Implementar editor**

`MapaView(QGraphicsView)` com `DragMode.ScrollHandDrag`, `ViewportAnchor.AnchorUnderMouse`, zoom por roda limitado a 0.2–3.0, `fitInView` com margem reservando o canto do núcleo. `CardItem(QGraphicsItem)` desenhado com `QPainter`: título, resumo, badge de status para tarefa; seleção com traço espesso + contorno tracejado. `ConexaoItem(QGraphicsPathItem)` recalcula curva no `itemChange(ItemPositionHasChanged)` do card. Comandos `QUndoCommand`: `CriarCard`, `EditarCard`, `MoverCard` (um por soltar), `AlterarProgresso`, `CriarConexao`, `EditarConexao`, `ExcluirCard` (guarda card + conexões), `ExcluirConexao`. Autosave com `QTimer` de debounce (400 ms edições, 600 ms câmera); estados `Salvando…/Salvo/Falha ao salvar/Conflito de revisão`; `Tentar novamente`, `Recarregar do disco`, `Salvar mesmo assim`. Atalhos locais `WidgetWithChildrenShortcut` com guarda de foco de texto.

- [ ] **Step 4/5: Rodar testes e commit** — `pytest tests/test_canvas_mapa.py -q`; `git commit -m "feat(canvas): editor de mapa com undo/redo e autosave"`

---

### Task 5: Integração do editor na janela principal

**Files:**
- Create: `core/interface_canvas_planos.py`, `tests/test_integracao_canvas.py`
- Modify: `ui.py`, `core/interface_canvas.py`, `tests/test_interface_canvas.py`

**Interfaces:**
- Consumes: Task 2 (`PlanosWindow`), Task 4 (`EditorMapa`).
- Produces: `CanvasEditor(QWidget)` com `abrir(plano: Plano)`, `contexto() -> {'plano_id','card_id','plano'}`, `fechar_com_seguranca() -> bool`, sinal `voltar = pyqtSignal()`. `MainWindow._abrir_canvas_do_plano(plano_id)`, `NiaUI.abrir_plano(id)` e `NiaUI.contexto_canvas()`.

- [ ] **Step 1: Escrever testes de integração**
```python
def test_abrir_editor_recolhe_dock_sem_persistir_e_restaura(app, window):
    antes = window._right_panel.preferences.data["expanded"]
    window._abrir_canvas_do_plano(id)
    assert window._right_panel.expanded is False
    assert window._right_panel.preferences.data["expanded"] == antes
    assert window._stage.anchor == "bottom-right"
    editor = window._canvas_editor
    editor.voltar.emit()
    assert window._right_panel.expanded == antes
    assert window._stage.anchor == antes_anchor
    assert window._planos_window.isVisible()

def test_saida_com_falha_de_gravacao_nao_perde_trabalho(app, window, monkeypatch):
    # alterar plano, forcar falha, emitir voltar
    # mock QMessageBox para "Cancelar": editor continua aberto e mudancas_pendentes
```

- [ ] **Step 2: Rodar e confirmar falha** → FAIL.

- [ ] **Step 3: Implementar integração**

`CanvasEditor` é filho de `CanvasStage` (para `hud_stack.raise_()` funcionar), geometria = `stage.rect()` menos reserva do núcleo, recalculada no resize. Abertura: esconder `PlanosWindow`, capturar `dock.expanded`/`stage.anchor`/painéis, `dock.expanded=False; dock.apply()` (sem `persist()`), `stage.set_anchor('bottom-right')`, `_canvas_editor_ativo=True`, esconder results/HOJE/brief, `_position_canvas_panels()` via `QTimer.singleShot(0, ...)`, `inicializar_mapa(id)`, `hud_stack.raise_()`. Saída: `fechar_com_seguranca()` (salvar ou diálogo de 3 opções), restaurar tudo, reexibir `PlanosWindow` com filtros/seleção. `core/interface_canvas.py`: `arrange()` não mostra results/HOJE com `_canvas_editor_ativo`; `ui.py`: `_show_canvas_brief` descarta briefs nesse estado.

- [ ] **Step 4/5: Rodar testes e commit** — `pytest tests/test_integracao_canvas.py tests/test_interface_canvas.py -q`; `git commit -m "feat(canvas): editor integrado ao dock e ao nucleo em sessao"`

---

### Task 6: Comandos por voz e texto

**Files:**
- Create: `core/comandos_planos.py`, `tests/test_comandos_planos.py`
- Modify: `main.py`, `ui.py`, `core/interface_en.py`, tests de integração conforme necessário

**Interfaces:**
- Consumes: Tasks 1, 3, 5 (`criar`, `listar`, `buscar`, `arquivar`, `restaurar`, `resumo_progresso`, `NiaUI.abrir_plano`, `NiaUI.abrir_planos`, `NiaUI.contexto_canvas`).
- Produces: `normalizar(texto)->str`, `reconhecer(texto, contexto)->Intencao`, `SessaoComandosPlanos.processar(texto, origem, contexto, storage)->ResultadoComando`. `Intencao(tipo: str, dados: dict)`; `ResultadoComando(tratado: bool, resposta: str, acoes: list[dict], opcoes: list[dict], pendente: bool)`.

- [ ] **Step 1: Escrever testes de intenção e sessão**
```python
@pytest.mark.parametrize("frase,tipo", [
    ("Vamos planejar um produto para pequenos lojistas.", "CRIAR"),
    ("Quero criar um projeto.", "CRIAR"),
    ("Quero continuar meus estudos.", "RETOMAR"),
    ("Continua meu estudo de fotografia.", "RETOMAR"),
    ("Abre o projeto do aplicativo de estoque.", "ABRIR"),
    ("Qual era meu objetivo no plano de fotografia?", "OBJETIVO"),
    ("O que falta nesse projeto?", "PROGRESSO"),
    ("Qual é o título desse card?", "CARD_TITULO"),
    ("Me explica como planejar um produto.", "EXPLICAR"),
    ("Ainda não quero começar o projeto.", "NEGAR"),
])
def test_reconhecer_frases(frase, tipo): ...

def test_criacao_incompleta_e_cancelamento(storage):
    r = sessao.processar("Quero criar um projeto.", "texto", {}, storage)
    assert r.pendente and "qual" in r.resposta.lower()
    r2 = sessao.processar("cancelar", "texto", {}, storage)
    assert not r2.pendente and listar()[0] == []

def test_escolha_por_ordinal_usa_id_da_lista(storage):
    # dois planos parecidos -> opcoes; "o segundo" -> acao abrir_canvas com id correto

def test_reentrega_de_transcricao_nao_cria_dois(storage):
    r1 = sessao.processar("Vamos planejar um produto para pequenos lojistas.", "voz", {}, storage)
    r2 = sessao.processar(mesma, "voz", {}, storage)
    assert r1.tratado and not r2.tratado

def test_contexto_de_card_e_progresso(storage):
    # selecionar card, perguntar titulo; mudar status e perguntar "o que falta"
```

- [ ] **Step 2: Rodar e confirmar falha** → FAIL.

- [ ] **Step 3: Implementar reconhecedor e integração**

`core/comandos_planos.py`: NFKD+casefold para comparação, preservando original para gravar. Intenções, extração de tipo/tema, negação/interrogativo/hipotético, sessão com `pendente`/`opcoes`/`vistos`/contexto e expiração ~180 s. Sem CLI externa. Em `main.py`: `_tratar_pendente_planos(texto)` chamado imediatamente antes de `_tratar_confirmacao_sintese` nos três pontos (`3436`, `9773`, `12119`); reconhecedor em `_executar_frase_habilidade` ao lado de `CH.reconhecer`; `_acao_comando_plano()` executa ações via `self.ui.write_log/show_content/abrir_plano/abrir_planos`; diagnóstico só `_voice_diag`. Em `ui.py`: `NiaUI.abrir_planos`, `abrir_plano`, `contexto_canvas`, `definir_contexto_canvas` via `QTimer.singleShot(0, ...)`; `MainWindow._abrir_plano(id)` delega a `_abrir_canvas_do_plano(id)`. Traduções em `interface_en.py`.

- [ ] **Step 4/5: Rodar testes e commit** — `pytest tests/test_comandos_planos.py -q`; `git commit -m "feat(comandos): planejamento por chat e voz no fluxo compartilhado"`

---

### Task 7: Regressão final e limpeza

**Files:** nenhum novo; revisão de todos os arquivos alterados.

- [ ] **Step 1: Rodar suíte completa** — `$env:QT_QPA_PLATFORM='offscreen'; & .venv-apis/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=cache/pytest-canvas` → todos passam.
- [ ] **Step 2: Checar compilação e diff** — `& .venv-apis/Scripts/python.exe -m compileall -q core ui.py main.py` e `git diff --check`.
- [ ] **Step 3: Auditar remoções** — `git diff` procurando imports/handlers/estados mortos introduzidos; remover somente o que estiver comprovadamente sem referência (grep por nome, sinais, registros de dock e preferências antigas). Preservar F2/F4/F6/F9/F11/ESC, chat, cards de hora/data/clima e habilidades do catálogo.
- [ ] **Step 4: Documentar validação** — atualizar `Documentos.Md/INTERFACE_NIA_VALIDACAO.md` com resultados, comandos, limitações (voz validada com transcrição simulada se for o caso) e pendências.
- [ ] **Step 5: Commit final** — `git commit -m "test(canvas): regressao final e documentacao da entrega"`
