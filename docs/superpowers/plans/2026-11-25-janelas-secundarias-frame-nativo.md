# Janelas secundárias com barra nativa sem título/ícone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer Configurações, Agenda, Planos e Globo abrirem com só os 3 botões nativos, sem título/ícone visíveis e com a faixa na cor da janela, via helper reutilizável.

**Architecture:** Generalizar o `WindowsFrame` atual (que hoje só funciona com o cache do Canvas da `MainWindow`) para aceitar uma cor de legenda e um layout sem `centralWidget`. Um módulo novo `core/frame_nativo.py` expõe `aplicar_frame_nativo()` e `FrameNativoMixin`; as quatro janelas chamam o mixin. Fora do Windows nada muda.

**Tech Stack:** Python 3, PyQt6, Win32 via `ctypes` (`user32`, `dwmapi`, `gdi32`), pytest com `QT_QPA_PLATFORM=offscreen`.

**Spec:** `docs/superpowers/specs/2026-11-25-janelas-secundarias-frame-nativo-design.md`

## Global Constraints

- Só Windows recebe o frame; em qualquer outra plataforma o helper retorna `False` e não altera a janela.
- `windowTitle()` e `windowIcon()` **não** são limpos — o texto/ícone some apenas visualmente pelo DIB com alpha=0 na faixa DWM, igual a `core/windows_frame.py:130-167`.
- Não criar botões Qt próprios; não usar `FramelessWindowHint`, `showFullScreen()` nem mudar `janela_sem_bordas`.
- A `MainWindow` mantém comportamento idêntico (continua usando `WindowsFrame` sem `cor`).
- A janela do WhatsApp (`secretaria/navegador_qt.py`) não é tocada nesta rodada.
- Overlays, cartão da secretária, `AvisoComputador`, diálogos e menus não são tocados.
- Cor da faixa: valor explícito de cada janela; sem `cor`, `QPalette.ColorRole.Window`.
- Commits frequentes, um por tarefa.

## Review Focus

- **Plataforma não Windows / offscreen:** o helper precisa ser no-op e a suíte atual continua passando. Teste em Task 2 Step 1.
- **Janelas sem `centralWidget()`** (QWidget puro): `reserve_caption()` deve usar `janela.layout()` em vez de quebrar. Teste em Task 1 Step 1.
- **Cor acompanha a janela** (tema claro/escuro do Configurações, `#061524` da Agenda, `#081527` dos Planos, `#00060a` do Globo): teste em Task 1 Step 1 (cor no DIB) e Task 3 Step 1 (cor passada por cada janela).
- **Botões nativos continuam clicáveis e o rótulo da barra de tarefas continua existindo:** os hit-tests existentes em `tests/test_windows_frame.py` permanecem e `windowTitle()` é verificado em Task 3 Step 1.
- **Globo roda em processo separado** e a janela é criada dentro de `_abrir_com_qt()`: o mixin precisa funcionar em `QMainWindow` sem estado da `MainWindow`. Teste em Task 4 Step 1.

---

### Task 1: Generalizar `WindowsFrame` para cor própria e layout sem `centralWidget`

**Files:**
- Modify: `core/windows_frame.py:35-123,130-167`
- Test: `tests/test_windows_frame.py`

**Interfaces:**
- Consumes: nada (primeira tarefa).
- Produces: `WindowsFrame(window, *, cor=None)` — `cor` aceita `QColor | str | None`; `None` mantém o caminho atual do cache do Canvas. `WindowsFrame._layout() -> QLayout | None`. Com `cor` definida, `paint_caption()` preenche a faixa com essa cor (alpha zerado).

- [ ] **Step 1: Escrever os testes que falham em `tests/test_windows_frame.py`**

```python
def test_layout_sem_central_widget(app):
    from PyQt6.QtWidgets import QWidget, QVBoxLayout
    w = QWidget()
    layout = QVBoxLayout(w)
    frame = WindowsFrame(w)
    assert frame._layout() is layout

@pytest.mark.parametrize('cor', ['#061524', '#081527', '#00060a'])
def test_caption_preenchida_com_cor_da_janela(app, cor):
    window = QMainWindow()
    layout = QVBoxLayout(window)
    frame = WindowsFrame(window, cor=cor)
    frame.active, frame.hwnd, frame.caption_height = True, 1, 31
    frame._base_margins = layout.contentsMargins()
    copied = []
    frame.user = SimpleNamespace(GetDC=lambda _: 1, ReleaseDC=lambda *a: 1)
    frame.gdi = SimpleNamespace(SetDIBitsToDevice=lambda *a: copied.append(bytes(a[9])) or 31)
    frame.paint_caption()
    largura = max(1, int(window.width() * window.devicePixelRatioF()))
    referencia = QImage(largura, 31, QImage.Format.Format_RGB32)
    referencia.fill(QColor(cor))
    esperado = bytearray(referencia.constBits().asstring(referencia.sizeInBytes()))
    esperado[3::4] = bytes(len(esperado) // 4)  # alpha zero: esconde DWM
    assert copied[0] == bytes(esperado)
    assert layout.contentsMargins().top() == 16 + math.ceil(31 / window.devicePixelRatioF())
```

(Importar `QColor` e `QImage` do `PyQt6.QtGui` no teste.)

- [ ] **Step 2: Rodar os testes e confirmar a falha**

Run: `pytest tests/test_windows_frame.py -v`
Expected: FAIL com `AttributeError: '_layout'` / `TypeError: unexpected keyword argument 'cor'`.

- [ ] **Step 3: Implementar em `core/windows_frame.py`**

Assinatura: `def __init__(self, window, *, cor=None)`. Converter `cor` para `QColor` quando não for `None` e guardar em `self.cor`. Adicionar `def _layout(self)` que devolve `self.window.centralWidget().layout()` se houver `centralWidget()`, senão `self.window.layout()`. Usar `_layout()` em `install()` (linha ~100) e em `reserve_caption()` (linha ~120), com guarda para layout `None`. Em `paint_caption()` (linha ~143), quando `self.cor` existir construir `QImage(largura, height, QImage.Format.Format_RGB32)` preenchida com `self.cor` (largura física = `window.width() * devicePixelRatioF()`); caso contrário manter o caminho atual do `canvas._ensure_cache()`. O restante do DIB (alpha=0, `BitmapHeader`, `SetDIBitsToDevice`) continua idêntico. Importar `QColor` de `PyQt6.QtGui`.

- [ ] **Step 4: Rodar os testes e confirmar a passagem**

Run: `pytest tests/test_windows_frame.py -v`
Expected: PASS (incluindo os 5 testes existentes de hit-test/DPI/cache).

- [ ] **Step 5: Commit**

```bash
git add core/windows_frame.py tests/test_windows_frame.py
git commit -m "refactor(frame): generalizar WindowsFrame para cor própria e layout sem centralWidget"
```

---

### Task 2: Módulo `core/frame_nativo.py` (helper + mixin)

**Files:**
- Create: `core/frame_nativo.py`
- Test: `tests/test_frame_nativo_secundarias.py`

**Interfaces:**
- Consumes: `WindowsFrame(window, *, cor=None)` de Task 1.
- Produces: `aplicar_frame_nativo(janela, *, cor=None) -> bool` (guarda a instância em `janela._frame_nativo` e chama `install()`); `FrameNativoMixin` com `_instalar_frame_nativo(self, *, cor=None) -> bool` e delegação de `event()` / `nativeEvent()` para o frame, espelhando `ui.py:4606-4632`.

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_helper_no_op_fora_do_windows(monkeypatch):
    monkeypatch.setattr(QApplication, 'platformName', lambda: 'offscreen')
    w = QWidget()
    assert aplicar_frame_nativo(w) is False
    assert not hasattr(w, '_frame_nativo')

def test_helper_instala_frame_com_cor_da_janela(monkeypatch):
    chamados = []
    class FakeFrame:
        def __init__(self, janela, *, cor=None):
            chamados.append((janela, cor))
        def install(self):
            return True
    monkeypatch.setattr(QApplication, 'platformName', lambda: 'windows')
    monkeypatch.setattr(core.windows_frame, 'WindowsFrame', FakeFrame)
    w = QWidget()
    assert aplicar_frame_nativo(w, cor='#061524') is True
    assert chamados == [(w, QColor('#061524'))]
    assert isinstance(w._frame_nativo, FakeFrame)

def test_mixin_instala_e_delega_event(monkeypatch):
    class Janela(FrameNativoMixin, QWidget):
        pass
    w = Janela()
    w.installado = []
    monkeypatch.setattr(w, '_instalar_frame_nativo', lambda **kw: w.installado.append(kw) or True)
    assert w._instalar_frame_nativo(cor='#00060a') is True
    assert w.installado == [{'cor': '#00060a'}]
    assert w.window() is w  # mixin não altera hierarquia Qt
```

- [ ] **Step 2: Rodar os testes e confirmar a falha**

Run: `pytest tests/test_frame_nativo_secundarias.py -v`
Expected: FAIL com `ModuleNotFoundError: core.frame_nativo`.

- [ ] **Step 3: Implementar `core/frame_nativo.py`**

`aplicar_frame_nativo(janela, *, cor=None) -> bool`: se `QApplication.platformName() != "windows"` retornar `False`; resolver `cor` como o argumento ou `janela.palette().color(QPalette.ColorRole.Window)`; importar `WindowsFrame` de `core.windows_frame` dentro da função; criar uma única instância em `janela._frame_nativo` (reutilizar se já existir) e retornar `install()`. `FrameNativoMixin`: método `_instalar_frame_nativo(self, *, cor=None)` chama o helper; `event(self, event)` chama `super().event(event)` e, se o frame estiver ativo e o evento for `QEvent.Type.UpdateRequest` ou `CAPTION_PAINT_EVENT`, chama `frame.paint_caption()`; `nativeEvent(self, event_type, message)` delega para `frame.native_event(message)` e devolve `(True, resultado)` se não for `None`, senão `super().nativeEvent(...)`. Documentar no docstring do módulo a convenção para janelas futuras: herdar `FrameNativoMixin` e chamar `_instalar_frame_nativo(cor=...)` no fim de `__init__`.

- [ ] **Step 4: Rodar os testes e confirmar a passagem**

Run: `pytest tests/test_frame_nativo_secundarias.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/frame_nativo.py tests/test_frame_nativo_secundarias.py
git commit -m "feat(frame): helper e mixin reutilizáveis para barra nativa sem titulo"
```

---

### Task 3: Aplicar o frame em Configurações, Agenda e Planos

**Files:**
- Modify: `core/config_dashboard.py:777-841`
- Modify: `core/interface_agenda.py:59-76`
- Modify: `core/interface_planos.py:369-394`
- Test: `tests/test_frame_nativo_secundarias.py`

**Interfaces:**
- Consumes: `FrameNativoMixin._instalar_frame_nativo(cor=None)` de Task 2.
- Produces: as três janelas com `windowTitle()` preservado e frame instalado; cores `self._paleta["bg"]` (Configurações), `#061524` (Agenda) e `#081527` (Planos).

- [ ] **Step 1: Escrever os testes que falham**

```python
def construir_janela(chave):
    if chave == 'config':
        return ConfigDashboardWindow(servico_falso())
    if chave == 'agenda':
        return AgendaWindow()
    return PlanosWindow()

@pytest.mark.parametrize('chave, cor', [
    ('config', None),          # cor conferida depois, via janela._paleta['bg']
    ('agenda', '#061524'),
    ('planos', '#081527'),
])
def test_janelas_secundarias_instalam_frame(monkeypatch, chave, cor):
    chamados = []
    monkeypatch.setattr('core.frame_nativo.aplicar_frame_nativo',
                        lambda janela, *, cor=None: chamados.append(cor) or True)
    janela = construir_janela(chave)
    esperado = janela._paleta['bg'] if chave == 'config' else cor
    assert chamados == [esperado]
    assert janela.windowTitle()  # rótulo da barra de tarefas preservado
```

`servico_falso()` usa o mesmo padrão de mock de `ConfigService` dos testes existentes em `tests/test_config_dashboard.py`.

- [ ] **Step 2: Rodar os testes e confirmar a falha**

Run: `pytest tests/test_frame_nativo_secundarias.py -v`
Expected: FAIL com `chamados == []` (nenhuma janela instala o frame).

- [ ] **Step 3: Implementar nas três janelas**

Em cada arquivo, importar `FrameNativoMixin` de `core.frame_nativo` e trocar a classe para herdar o mixin **antes** do QWidget: `class ConfigDashboardWindow(FrameNativoMixin, QWidget)`, `class AgendaWindow(FrameNativoMixin, QWidget)`, `class PlanosWindow(FrameNativoMixin, QWidget)`. Chamar `self._instalar_frame_nativo(cor=self._paleta["bg"])` no fim de `ConfigDashboardWindow.__init__` (após a linha 840, onde `_aplicar_estilo()` já rodou), `self._instalar_frame_nativo(cor=COR_FUNDO)` no fim de `AgendaWindow.__init__` (após `self.recarregar()`, linha 76) e o mesmo em `PlanosWindow.__init__` (após `self._construir()`, linha 394). Não alterar títulos, ícones, estilos nem flags dessas janelas.

- [ ] **Step 4: Rodar os testes e confirmar a passagem**

Run: `pytest tests/test_frame_nativo_secundarias.py tests/test_config_dashboard.py tests/test_interface_agenda.py tests/test_interface_planos.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/config_dashboard.py core/interface_agenda.py core/interface_planos.py tests/test_frame_nativo_secundarias.py
git commit -m "feat(janelas): barra nativa sem titulo em Configuracoes, Agenda e Planos"
```

---

### Task 4: Aplicar o frame no Globo (processo separado)

**Files:**
- Modify: `globo/janela.py:127-200`
- Test: `tests/test_frame_nativo_secundarias.py`

**Interfaces:**
- Consumes: `FrameNativoMixin` de Task 2.
- Produces: `JanelaGlobo(FrameNativoMixin, QMainWindow)` e `_abrir_com_qt()` usando essa classe com `_instalar_frame_nativo(cor="#00060a")`.

- [ ] **Step 1: Escrever o teste que falha**

```python
def test_globo_usa_mixin_e_cor_propria(monkeypatch):
    import globo.janela as gj
    assert issubclass(gj.JanelaGlobo, FrameNativoMixin)
    chamados = []
    monkeypatch.setattr('core.frame_nativo.aplicar_frame_nativo',
                        lambda janela, *, cor=None: chamados.append(cor) or True)
    janela = gj.JanelaGlobo()
    janela._instalar_frame_nativo(cor='#00060a')
    assert chamados == ['#00060a']
    assert isinstance(janela, QMainWindow)
```

- [ ] **Step 2: Rodar o teste e confirmar a falha**

Run: `pytest tests/test_frame_nativo_secundarias.py::test_globo_usa_mixin_e_cor_propria -v`
Expected: FAIL com `AttributeError: module 'globo.janela' has no attribute 'JanelaGlobo'`.

- [ ] **Step 3: Implementar em `globo/janela.py`**

Definir `class JanelaGlobo(FrameNativoMixin, QMainWindow): pass` no módulo (importar `FrameNativoMixin` de `core.frame_nativo`). Em `_abrir_com_qt()`, trocar `janela = QMainWindow()` (linha 188) por `janela = JanelaGlobo()`. Manter `setWindowTitle("NIA — Globo")`, ícone e `setStyleSheet("QMainWindow { background: #00060a; }")` como estão. Chamar `janela._instalar_frame_nativo(cor="#00060a")` depois do `setStyleSheet()` (linha 196), antes do `setMinimumSize()`.

- [ ] **Step 4: Rodar o teste e confirmar a passagem**

Run: `pytest tests/test_frame_nativo_secundarias.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add globo/janela.py tests/test_frame_nativo_secundarias.py
git commit -m "feat(globo): barra nativa sem titulo na janela do globo"
```

---

### Task 5: Verificação final e registro

**Files:**
- Modify: `Documentos.Md/HOMOLOGACAO_CANVAS_FINAL.md`

**Interfaces:**
- Consumes: tudo das Tasks 1-4.
- Produces: suíte verde, `git diff --check` limpo e convenção documentada para janelas futuras.

- [ ] **Step 1: Rodar a suíte completa**

Run: `pytest -q`
Expected: PASS em toda a suíte (sem regressões em `tests/test_barra_nativa.py`, `test_controles_nativos.py`, `test_windows_frame.py`, `test_janela_maximizada.py`, `test_janela_tela_cheia.py`).

- [ ] **Step 2: Verificar o diff**

Run: `git diff --check`
Expected: nenhuma saída.

- [ ] **Step 3: Registrar a convenção no documento de homologação**

Acrescentar seção curta em `Documentos.Md/HOMOLOGACAO_CANVAS_FINAL.md` com: janelas incluídas (Configurações, Agenda, Planos, Globo), WhatsApp explicitamente fora, e a regra para janelas futuras (herdar `FrameNativoMixin` e chamar `_instalar_frame_nativo(cor=...)` no fim de `__init__`).

- [ ] **Step 4: Commit**

```bash
git add Documentos.Md/HOMOLOGACAO_CANVAS_FINAL.md
git commit -m "docs: registrar barra nativa nas janelas secundarias"
```
