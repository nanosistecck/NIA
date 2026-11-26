# Bandeja com as ferramentas do dock — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expor as 18 ferramentas do dock na Central de Aplicativos, com clique idêntico ao botão do dock, sem Canvas duplicado e sem o indicador verde dos blocos.

**Architecture:** Os 14 descritores que faltam entram no registro estático com `id` igual à chave do botão do dock. A Central recebe o conjunto de chaves do dock e, quando um bloco corresponde, emite `dock_acao_solicitada(chave)`; o MainWindow fecha a bandeja e chama `botao.click()`. Busca, categorias e favoritos continuam vindos do registro.

**Tech Stack:** Python 3, PyQt6 (sinais, QPushButton, QSignalSpy), pytest com `QT_QPA_PLATFORM=offscreen`.

**Spec:** `docs/superpowers/specs/2026-11-25-bandeja-ferramentas-dock-design.md`

## Global Constraints

- Registro declarativo: nenhum módulo é importado apenas para descrever uma ferramenta.
- As 18 chaves devem ser exatamente: `mute`, `so_nome`, `interrupt`, `whatsapp`, `remote`, `webcam`, `cowork`, `computer_use`, `segundo_plano`, `globo`, `planos`, `agenda`, `central`, `config`, `system`, `skill_secretaria`, `skill_buscar_arquivos`, `skill_resumo_dia`.
- `canvas` não pode aparecer na bandeja.
- Não alterar `hidden`/`order` do dock nem a página Aparência → Ferramentas do dock.
- Não alterar os atalhos `tool_*` nem o caminho de voz/chat das habilidades.
- Ao commitar, incluir só os arquivos da task; o repositório tem trabalho não commitado do usuário e deleções já staged no índice.

## Review Focus

- Botão oculto no dock continua acionável pela bandeja — Task 2, `test_ponte_clica_botao_oculto_do_dock`.
- Canvas não reaparece e Planos continua uma vez — Task 1, `test_bandeja_tem_as_18_entradas_do_dock_sem_duplicatas`.
- Clique em ferramenta mapeada não cai na abertura antiga de janela — Task 2, `test_clique_mapeado_nao_abre_janela_pela_via_antiga`.
- Nenhum id repetido entre descritores nativos e do dock — Task 1, `test_bandeja_tem_as_18_entradas_do_dock_sem_duplicatas`.
- Ícones novos renderizam e desconhecido cai no fallback `system` — Task 1, `test_icones_novos_das_habilidades`.

---

### Task 1: Catálogo das ferramentas do dock e ícones

**Files:**
- Modify: `core/registro_nativo.py:13-45` (`registrar_nativos`)
- Modify: `core/interface_canvas.py:35-59` (`_ICONS`)
- Test: `tests/test_catalogo_dock.py` (novo)

**Interfaces:**
- Consumes: `RA.DescritorApp`, `RA.registrar`, `RA.buscar()`, `registrar_nativos()` — existentes.
- Produces: descritores com `origem='dock'`, `dominio_ferramenta='dock'`, `possui_interface=False`, `fixavel_no_dock=True` e `id` igual à chave do botão; traços `_ICONS['secretaria']`, `_ICONS['buscar_arquivos']`, `_ICONS['resumo']`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_catalogo_dock.py`:

```python
# -*- coding: utf-8 -*-
"""Catálogo das ferramentas do dock expostas na bandeja."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtWidgets import QApplication

import core.registro_aplicativos as RA

ESPERADOS = {
    'mute', 'so_nome', 'interrupt', 'whatsapp', 'remote', 'webcam',
    'cowork', 'computer_use', 'segundo_plano', 'globo', 'planos', 'agenda',
    'central', 'config', 'system', 'skill_secretaria',
    'skill_buscar_arquivos', 'skill_resumo_dia',
}


@pytest.fixture(autouse=True)
def registro_isolado(monkeypatch):
    monkeypatch.setattr(RA, '_DESCRITORS', {})
    monkeypatch.setattr(RA, '_PROVEDOR_FERRAMENTAS', None)
    monkeypatch.setattr(RA, '_PROVEDOR_DISPONIBILIDADE', None)


def test_bandeja_tem_as_18_entradas_do_dock_sem_duplicatas():
    from core.registro_nativo import registrar_nativos
    registrar_nativos()
    ids = [i.id for i in RA.buscar()]
    assert set(ids) == ESPERADOS
    assert len(ids) == 18
    assert 'canvas' not in ids
```

```python
def test_icones_novos_das_habilidades():
    from core.interface_canvas import _ICONS, icon, vector_icon
    app = QApplication.instance() or QApplication([])
    for nome in ('secretaria', 'buscar_arquivos', 'resumo'):
        assert nome in _ICONS
        assert vector_icon(nome).isValid()
    assert not icon('inexistente-para-teste').isNull()
```

- [ ] **Step 2: Rodar os testes e confirmar a falha**

Run: `python -m pytest tests/test_catalogo_dock.py -v`
Expected: FAIL — `canvas` ainda está em `buscar()` e as 14 chaves não existem; as chaves de ícone não existem em `_ICONS`.

- [ ] **Step 3: Implementar o catálogo e os ícones**

Em `core/registro_nativo.py`:

- Remover o `DescritorApp(id='canvas', ...)` da lista `itens`.
- Acrescentar uma segunda tupla com 14 descritores, um para cada chave dos 9 controles, `central`, `system` e as 3 habilidades. Cada um com: `id` igual à chave do dock, `nome` legível, `descricao` curta, `categoria='sistema'` para controles/central/system e `'habilidades'` para as três habilidades, `icone` existente em `_ICONS` (`mute`, `so_nome`, `interrupt`, `whatsapp`, `remote`, `webcam`, `cowork`, `computer_use`, `segundo_plano`, `menu`, `system`, `secretaria`, `buscar_arquivos`, `resumo`), `cor` da paleta existente, `possui_interface=False`, `fixavel_no_dock=True`, `origem='dock'`, `dominio_ferramenta='dock'`.
- Registrá-los em `registrar_nativos()` junto com os atuais, antes das sincronizações.

Em `core/interface_canvas.py`, acrescentar em `_ICONS` os traços `secretaria` (telefone), `buscar_arquivos` (lupa sobre documento) e `resumo` (bloco de notas com linhas), no mesmo formato SVG dos traços existentes.

- [ ] **Step 4: Rodar os testes e confirmar a passagem**

Run: `python -m pytest tests/test_catalogo_dock.py -v`
Expected: PASS — os 18 ids, sem `canvas`, com ícones válidos.

- [ ] **Step 5: Commit**

```bash
git add core/registro_nativo.py core/interface_canvas.py tests/test_catalogo_dock.py
git commit --only core/registro_nativo.py core/interface_canvas.py tests/test_catalogo_dock.py -m "feat: catalogo das ferramentas do dock na bandeja"
```

### Task 2: Ponte de clique e remoção do indicador verde

**Files:**
- Modify: `core/central_aplicativos.py:53-105` (`AppTile`), `core/central_aplicativos.py:131-157` (`CentralAplicativos`), `core/central_aplicativos.py:411-431` (`abrir_app`)
- Modify: `ui.py:4064-4074` (inicialização da Central), `ui.py` (novo método `_executar_dock_pela_central`)
- Test: `tests/test_central_aplicativos.py`

**Interfaces:**
- Consumes: `dock_acao_solicitada(str)` e `definir_acoes_dock(ids)` produzidos nesta task; `self._right_panel.buttons` (dicionário `str -> QPushButton`) existente; `self._central_sig` existente.
- Produces:
  - `CentralAplicativos.dock_acao_solicitada = pyqtSignal(str)` — emitido com a chave do dock.
  - `CentralAplicativos.definir_acoes_dock(identificadores) -> None` — registra o conjunto de chaves acionáveis.
  - `MainWindow._executar_dock_pela_central(chave: str) -> None` — fecha a bandeja e chama `buttons[chave].click()`.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_central_aplicativos.py`, acrescentar:

```python
def test_clique_mapeado_nao_abre_janela_pela_via_antiga(central):
    w, ger = central
    w.definir_acoes_dock({'mute', 'central'})
    dock_acao, ferramentas, abertos = [], [], []
    w.dock_acao_solicitada.connect(dock_acao.append)
    w.ferramenta_solicitada.connect(lambda *a: ferramentas.append(a))
    w.app_aberto.connect(abertos.append)
    w.abrir_app('mute')
    assert dock_acao == ['mute']
    assert ferramentas == [] and abertos == [] and ger.abertos == []


def test_bloco_nao_tem_indicador_verde(central):
    w, _ = central
    tiles = list(w._tiles.values())
    assert tiles
    for tile in tiles:
        assert not [l for l in tile.findChildren(__import__('PyQt6.QtWidgets', fromlist=['QLabel']).QLabel)
                    if l.text() in ('●', '○')]
```

E, usando a fixture `janela_real` existente:

```python
def test_ponte_clica_botao_oculto_do_dock(janela_real, app):
    from PyQt6.QtTest import QSignalSpy
    from PyQt6.QtWidgets import QPushButton
    w = janela_real
    assert {'central', 'mute', 'webcam'}.issubset(w._central._acoes_dock)
    botao = QPushButton()
    espia = QSignalSpy(botao, botao.clicked)
    w._right_panel.buttons['fake_teste'] = botao
    try:
        w._executar_dock_pela_central('fake_teste')
        app.processEvents()
        assert espia.count() == 1
    finally:
        del w._right_panel.buttons['fake_teste']
        botao.deleteLater()
```

- [ ] **Step 2: Rodar os testes e confirmar a falha**

Run: `python -m pytest tests/test_central_aplicativos.py -k "mapeado or indicador or ponte" -v`
Expected: FAIL — `definir_acoes_dock`, `dock_acao_solicitada` e `_executar_dock_pela_central` não existem; o `QLabel` `●` ainda está nos tiles.

- [ ] **Step 3: Implementar a ponte e remover o indicador**

Em `core/central_aplicativos.py`:

- Declarar `dock_acao_solicitada = pyqtSignal(str)` em `CentralAplicativos` e inicializar `self._acoes_dock: set[str] = set()` no `__init__`.
- Implementar `definir_acoes_dock(self, identificadores) -> None` substituindo o conjunto.
- No início de `abrir_app()`, se `identificador in self._acoes_dock`, emitir `dock_acao_solicitada` e retornar.
- Em `AppTile.__init__`, remover a criação do `QLabel` de estado e o `layout.addWidget(self.estado, ...)`. As asserções de disponibilidade em `abrir_app()` continuam valendo.

Em `ui.py`:

- Depois de criar `self._central` e o dock, chamar `self._central.definir_acoes_dock(self._right_panel.buttons)` e conectar `dock_acao_solicitada` a `self._executar_dock_pela_central`.
- Implementar `def _executar_dock_pela_central(self, chave: str) -> None`: emitir `self._central_sig.emit(False)` para fechar a bandeja, buscar `self._right_panel.buttons.get(chave)` e chamar `.click()`; se não houver botão, registrar aviso pelo `_log_ferramenta` existente.

- [ ] **Step 4: Rodar os testes e confirmar a passagem**

Run: `python -m pytest tests/test_central_aplicativos.py -q`
Expected: PASS, sem regressão nos testes de grade, pesquisa, categorias e abertura de habilidades por voz/chat.

- [ ] **Step 5: Verificação final e commit**

Run: `python -m pytest -q`
Expected: suíte completa verde.

Run: `git diff --check`
Expected: nenhum erro de whitespace.

```bash
git add core/central_aplicativos.py ui.py tests/test_central_aplicativos.py
git commit --only core/central_aplicativos.py ui.py tests/test_central_aplicativos.py -m "feat: bandeja aciona ferramentas do dock sem indicador verde"
```
