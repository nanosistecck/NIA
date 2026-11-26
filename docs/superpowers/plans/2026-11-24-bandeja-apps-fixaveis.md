# Bandeja de aplicativos = apps fixáveis no dock — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer a Central de Aplicativos listar somente apps fixáveis no dock, com ícones próprios para Canvas Infinito e Agenda.

**Architecture:** O registro central passa a selecionar por `fixavel_no_dock` em vez de `visivel_na_central`; a grade já consome `buscar()`, então não muda. Os atalhos `tool_*` são marcados como não fixáveis para não voltarem para a grade. Os ícones são traços vetoriais em `_ICONS`, sem arquivos novos e sem dependências.

**Tech Stack:** Python 3, PyQt6 (QSvgRenderer/QPixmap), pytest com `QT_QPA_PLATFORM=offscreen`.

**Spec:** `docs/superpowers/specs/2026-11-24-bandeja-apps-fixaveis-design.md`

## Global Constraints

- Nenhum módulo é importado apenas para descrever um aplicativo; metadados continuam declarativos.
- Os 44 atalhos `tool_*` não devem aparecer na Central em nenhuma circunstância.
- Controles do dock (microfone, interromper, webcam, Cowork, Computer Use, WhatsApp, segundo plano) não entram na Central.
- Não alterar `hidden`, `order` ou a página Aparência → Ferramentas do dock.
- Ressalva conhecida: "Fixar no dock" em `canvas` não tem botão homônimo no dock; reportar ao usuário sem alterar o dock nesta rodada.
- Ao commitar, incluir somente os arquivos listados em cada task; o repositório tem trabalho não commitado do usuário.

## Review Focus

- App com `visivel_na_central=False` e `fixavel_no_dock=True` deve aparecer na grade — Task 1, `test_busca_inclui_fixavel_mesmo_oculto_da_central`.
- Atalho `tool_*` não pode reaparecer depois da troca de filtro — Task 1, `test_sync_de_catalogo_e_declaracoes_sem_importar_main` (asserção de `fixavel_no_dock is False`).
- Habilidade sem interface sai da grade, mas continua abrindo por `abrir_app()` — Task 1, `test_grade_e_estado_vazio` e `test_abrir_app_com_interface_e_habilidade_sem_interface`.
- Categoria sem app fixável não pode deixar botão vazio na barra da Central — Task 1, `test_busca_local_ignora_acento_e_categoria` (já asserta `'habilidades' not in RA.categorias()`).
- Nome de ícone desconhecido deve cair no fallback `system` sem quebrar a grade — Task 2, `test_icone_desconhecido_cai_no_fallback`.

---

### Task 1: Seleção da Central por `fixavel_no_dock`

**Files:**
- Modify: `core/registro_aplicativos.py:174-176` (`categorias`), `core/registro_aplicativos.py:210-244` (`sincronizar_ferramentas`), `core/registro_aplicativos.py:263-283` (`buscar`)
- Test: `tests/test_registro_aplicativos.py`
- Test: `tests/test_central_aplicativos.py`

**Interfaces:**
- Consumes: `RA.DescritorApp`, `RA.todos()`, `RA.sincronizar_ferramentas()` — existentes, sem mudança de assinatura.
- Produces:
  - `buscar(termo: str = '', categoria: str = 'todos', *, favoritos=None, apenas_disponiveis=False) -> tuple[DescritorApp, ...]` — agora seleciona `fixavel_no_dock=True`, ignorando `visivel_na_central`.
  - `categorias() -> tuple[str, ...]` — categorias presentes entre os apps fixáveis.
  - Descritores `tool_*` com `fixavel_no_dock=False`.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_registro_aplicativos.py`, acrescentar ao final de `test_sync_de_catalogo_e_declaracoes_sem_importar_main`, logo após a asserção de `visivel_na_central`:

```python
    assert RA.por_id('tool_pesquisa').fixavel_no_dock is False
```

E acrescentar um teste novo:

```python
def test_busca_inclui_fixavel_mesmo_oculto_da_central():
    RA.registrar(desc(id='oculto', nome='App Oculto',
                      visivel_na_central=False, fixavel_no_dock=True))
    RA.registrar(desc(id='habilidade', nome='Habilidade',
                      tipo='habilidade', fixavel_no_dock=False,
                      visivel_na_central=True))
    assert [i.id for i in RA.buscar()] == ['oculto']
```

Em `tests/test_central_aplicativos.py`, ajustar a grade para a nova regra:

```python
def test_grade_e_estado_vazio(central):
    w, _ = central
    assert len(w._tiles) == 2
    assert 'resumo' not in w._tiles
    w._campo.setText('nao-existe-zzz')
    w._aplicar_filtro()
    assert w._tiles == {} and w._vazio.isVisible()
    w._campo.setText('')
    w._aplicar_filtro()
    assert len(w._tiles) == 2 and not w._vazio.isVisible()
```

E em `test_categorias_e_favoritos`:

```python
    w.definir_favoritos({'biblioteca'})
    w.definir_categoria('favoritos')
    assert list(w._tiles) == ['biblioteca']
```

- [ ] **Step 2: Rodar os testes e confirmar a falha**

Run: `python -m pytest tests/test_registro_aplicativos.py::test_busca_inclui_fixavel_mesmo_oculto_da_central tests/test_central_aplicativos.py::test_grade_e_estado_vazio -v`
Expected: FAIL — `buscar()` ainda filtra `visivel_na_central`, então `oculto` não aparece e a grade ainda tem 3 blocos.

- [ ] **Step 3: Implementar a seleção por fixável**

Em `core/registro_aplicativos.py`:

- Em `sincronizar_ferramentas()`, ao construir o descritor do atalho, acrescentar `fixavel_no_dock=False,` ao lado de `visivel_na_central=False`.
- Em `buscar()`, trocar `itens = [i for i in todos() if i.visivel_na_central]` por `itens = [i for i in todos() if i.fixavel_no_dock]`.
- Em `categorias()`, trocar o conjunto `presentes` para considerar somente descritores com `fixavel_no_dock=True`.

- [ ] **Step 4: Rodar os testes e confirmar a passagem**

Run: `python -m pytest tests/test_registro_aplicativos.py tests/test_central_aplicativos.py -q`
Expected: PASS, sem regressão nos testes de busca, categorias, favoritos e abertura de habilidade por `abrir_app()`.

- [ ] **Step 5: Commit**

```bash
git add core/registro_aplicativos.py tests/test_registro_aplicativos.py tests/test_central_aplicativos.py
git commit -m "feat: bandeja mostra somente apps fixaveis no dock"
```

### Task 2: Ícones próprios de Canvas Infinito e Agenda

**Files:**
- Modify: `core/interface_canvas.py:35-59` (`_ICONS`)
- Modify: `core/registro_nativo.py:16-35` (descritores nativos)
- Test: `tests/test_central_icones.py` (novo)

**Interfaces:**
- Consumes: `RA.DescritorApp`, `RA.por_id()`, `registrar_nativos()` da Task 1; `core.interface_canvas.icon()` e `vector_icon()` existentes.
- Produces: `_ICONS['canvas']` e `_ICONS['agenda']` (traços SVG); descritores `canvas.icone == 'canvas'` e `agenda.icone == 'agenda'`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_central_icones.py`:

```python
# -*- coding: utf-8 -*-
"""Ícones próprios dos apps fixáveis na bandeja."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtWidgets import QApplication

import core.registro_aplicativos as RA


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_nativos_usam_icone_da_propria_ferramenta(monkeypatch):
    monkeypatch.setattr(RA, '_DESCRITORS', {})
    from core.registro_nativo import registrar_nativos
    registrar_nativos()
    assert RA.por_id('canvas').icone == 'canvas'
    assert RA.por_id('agenda').icone == 'agenda'


def test_icones_canvas_e_agenda_sao_vetoriais_e_distintos(app):
    from core.interface_canvas import _ICONS, vector_icon
    assert 'canvas' in _ICONS and 'agenda' in _ICONS
    assert _ICONS['canvas'] != _ICONS['agenda']
    assert vector_icon('canvas').isValid()
    assert vector_icon('agenda').isValid()


def test_icone_desconhecido_cai_no_fallback(app):
    from core.interface_canvas import icon
    assert not icon('inexistente').isNull()
```

- [ ] **Step 2: Rodar o teste e confirmar a falha**

Run: `python -m pytest tests/test_central_icones.py -v`
Expected: FAIL — `canvas.icone` é `planos`, `agenda.icone` é `save` e as chaves `canvas`/`agenda` não existem em `_ICONS`.

- [ ] **Step 3: Adicionar os traços e ligar aos descritores**

Em `core/interface_canvas.py`, acrescentar duas entradas em `_ICONS`:

- `'canvas'`: quadro com nós ligados (traço de canvas/mapa), distinto de `planos`.
- `'agenda'`: calendário com grade e cabeçalho, distinto de `save`.

Usar o mesmo formato SVG dos traços existentes: `viewBox="0 0 24 24"`, `fill="none"`, `stroke-width=1.6`, sem texto e sem dependência de fonte instalada.

Em `core/registro_nativo.py`, trocar `icone='planos'` do descritor `canvas` por `icone='canvas'` e `icone='save'` do descritor `agenda` por `icone='agenda'`. Não alterar os ícones de `planos`, `config` e `globo`.

- [ ] **Step 4: Rodar o teste e confirmar a passagem**

Run: `python -m pytest tests/test_central_icones.py -v`
Expected: PASS.

- [ ] **Step 5: Verificação final e commit**

Run: `python -m pytest -q`
Expected: suíte completa verde.

Run: `git diff --check`
Expected: nenhuma saída.

```bash
git add core/interface_canvas.py core/registro_nativo.py tests/test_central_icones.py
git commit -m "feat: icones proprios para Canvas e Agenda na bandeja"
```
