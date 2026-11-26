# Agenda — CRUD completo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completar o CRUD da Agenda com edição e exclusão pela janela e comandos de voz/chat para renomear, mudar tipo/notas e reabrir.

**Architecture:** Extensão dos três módulos existentes — `core/agenda.py` (dados e validação), `core/comandos_agenda.py` (parser puro), `core/interface_agenda.py` (janela PyQt6) — com integração pontual em `main.py`. Nenhum módulo novo de persistência ou janela.

**Tech Stack:** Python 3.12, PyQt6, pytest, padrões de `CanvasStage.hoje_host`, `VerticalDock` e `NiaUI`.

**Spec:** `docs/superpowers/specs/2026-11-23-agenda-crud-design.md`

## Global Constraints

- Tipos: `reuniao`, `chamada`, `tarefa`, `entrega`, `viagem`, `aniversario`, `outro`.
- Estados: `pendente`, `concluido`, `cancelado`.
- Alvo de comando sem ID: título/data ditos → próximo → perguntar se ambíguo.
- Frases com "card" (exceto "card da agenda") pertencem ao Canvas dos planos.
- Persistência atômica por perfil em `~/.nia/agenda.json`, override `NIA_AGENDA`.
- Nenhuma mudança em formato de dados, planos, lembretes, clima ou fala.
- Nenhuma afirmação de validação visual sem captura da interface executada.
- Somente serviços gratuitos.

## Review Focus

1. Campo "Notas" editado pela janela sobrevive a reabrir a janela — teste em Task 4.
2. Exclusão pela janela pede confirmação com padrão seguro — teste em Task 4.
3. Renomear para título vazio não apaga o título antigo — teste em Task 1.
4. "mude o tipo da reunião para tarefa" muda o tipo sem alterar data — teste em Task 2.
5. "reabra a consulta" volta para pendente e o card do Canvas reaparece — teste em Task 3.

---

### Task 1: Validação e reabrir no modelo

**Files:**
- Modify: `core/agenda.py`
- Test: `tests/test_agenda_crud.py`

**Interfaces:**
- Consumes: `AG.editar`, `AG.criar` (rodada 11).
- Produces: `reabrir(item_id)->dict`; `editar()` valida titulo/tipo/inicio/estado.

- [ ] **Step 1: Escrever testes RED**

```python
def test_editar_rejeita_titulo_vazio():
    item = agenda.criar("Consulta", "2026-11-24T09:00:00-03:00")
    with pytest.raises(ValueError):
        agenda.editar(item["id"], {"titulo": "   "})
    assert agenda.listar()[0]["titulo"] == "Consulta"

def test_editar_rejeita_tipo_e_data_invalidos():
    item = agenda.criar("Consulta", "2026-11-24T09:00:00-03:00")
    with pytest.raises(ValueError): agenda.editar(item["id"], {"tipo": "invalido"})
    with pytest.raises(ValueError): agenda.editar(item["id"], {"inicio": "xyz"})

def test_reabrir_volta_para_pendente():
    item = agenda.criar("Consulta", "2026-11-24T09:00:00-03:00")
    agenda.concluir(item["id"])
    assert agenda.reabrir(item["id"])["estado"] == "pendente"
```

- [ ] **Step 2: Rodar e confirmar falha** — `pytest tests/test_agenda_crud.py -v` → FAIL.
- [ ] **Step 3: Implementar validação em `editar()`/`criar()` e `reabrir()`.**
- [ ] **Step 4: Rodar e confirmar passa** — `pytest tests/test_agenda_crud.py -v` → PASS.
- [ ] **Step 5: Commit** — `git add core/agenda.py tests/test_agenda_crud.py && git commit -m "feat(agenda): validacao e reabrir no modelo"`

---

### Task 2: Novos comandos de edição no parser

**Files:**
- Modify: `core/comandos_agenda.py`
- Test: `tests/test_agenda_crud.py`

**Interfaces:**
- Consumes: `AG.reabrir` (Task 1), `CAG.resolver_alvo` (rodada 12).
- Produces: `processar()` devolve `acao="editar"` com `campos={"titulo"|"tipo"|"notas"|"estado": ...}`.

- [ ] **Step 1: Escrever testes RED**

```python
def test_renomear():
    r = CA.processar("renomeie a consulta para Consulta particular")
    assert r["acao"] == "editar" and r["campos"] == {"titulo": "Consulta particular"}

def test_mudar_tipo():
    r = CA.processar("mude o tipo da reunião para tarefa")
    assert r["campos"] == {"tipo": "tarefa"}

def test_mudar_notas():
    r = CA.processar("mude as notas da consulta para levar exames")
    assert r["campos"] == {"notas": "levar exames"}

def test_reabrir():
    assert CA.processar("reabra a consulta")["campos"] == {"estado": "pendente"}
```

- [ ] **Step 2: Rodar e confirmar falha** → FAIL.
- [ ] **Step 3: Implementar os quatro ramos antes do ramo de preparo.**
- [ ] **Step 4: Rodar e confirmar passa** → PASS.
- [ ] **Step 5: Commit** — `git add core/comandos_agenda.py tests/test_agenda_crud.py && git commit -m "feat(agenda): comandos de renomear, tipo, notas e reabrir"`

---

### Task 3: Rota no NiaLive para os novos campos

**Files:**
- Modify: `main.py`
- Test: `tests/test_agenda_crud.py`

**Interfaces:**
- Consumes: `CAG.processar` com `campos` (Task 2), `AG.editar`, `AG.reabrir` (Task 1).
- Produces: mensagens "Compromisso renomeado", "Tipo atualizado", "Notas atualizadas", "Compromisso reaberto".

- [ ] **Step 1: Escrever teste RED de rota**

```python
def test_reabrir_pela_rota_atualiza_card(nia):
    obj, registros = nia
    item = agenda.criar("Consulta", "2026-11-24T09:00:00-03:00")
    agenda.concluir(item["id"])
    assert obj._executar_frase_habilidade("reabra a consulta", "texto")
    assert agenda.listar()[0]["estado"] == "pendente"
    assert "reaberto" in " ".join(registros).lower()
```

- [ ] **Step 2: Rodar e confirmar falha** → FAIL.
- [ ] **Step 3: Implementar `campos` no ramo de `editar` com `rotulos` por campo e mensagens corretas.**
- [ ] **Step 4: Rodar e confirmar passa** → PASS.
- [ ] **Step 5: Commit** — `git add main.py tests/test_agenda_crud.py && git commit -m "feat(agenda): rota aplica novos campos de edicao"`

---

### Task 4: Janela com edição, estado e exclusão

**Files:**
- Modify: `core/interface_agenda.py`
- Test: `tests/test_interface_agenda_crud.py`

**Interfaces:**
- Consumes: `AG.listar`, `AG.editar`, `AG.excluir`, `AG.reabrir` (Tasks 1-2).
- Produces: `AgendaWindow.item_selecionado_id`, `btn_salvar`, `btn_cancelar`, `btn_concluir`, `btn_reabrir`, `btn_excluir`, `campo_notas`, `campo_estado`, `lista` com `txt_compromissos` preenchido.

- [ ] **Step 1: Escrever testes Qt RED**

```python
def test_clicar_lista_carrega_formulario(janela):
    w = janela
    item = agenda.criar("Consulta", "2026-11-24T09:00:00-03:00", "chamada", notas="levar exames")
    w.recarregar()
    w.selecionar_item(item["id"])
    assert w.campo_titulo.text() == "Consulta"
    assert w.campo_notas.toPlainText() == "levar exames"
    assert w.btn_salvar.text() == "Salvar alterações"

def test_salvar_edicao_e_excluir(janela, monkeypatch):
    w = janela
    item = agenda.criar("Consulta", "2026-11-24T09:00:00-03:00")
    w.recarregar(); w.selecionar_item(item["id"])
    w.campo_titulo.setText("Consulta particular")
    w.btn_salvar.click()
    assert agenda.listar()[0]["titulo"] == "Consulta particular"
    monkeypatch.setattr(w, "_confirmar_exclusao", lambda: True)
    w.btn_excluir.click()
    assert agenda.listar() == []
```

- [ ] **Step 2: Rodar e confirmar falha** → FAIL.
- [ ] **Step 3: Implementar `QListWidget` com ids, `selecionar_item`, campos notas/estado, botoes e confirmacao de exclusao.**
- [ ] **Step 4: Rodar e confirmar passa** → PASS.
- [ ] **Step 5: Capturar janela offscreen e inspecionar.**
- [ ] **Step 6: Commit** — `git add core/interface_agenda.py tests/test_interface_agenda_crud.py && git commit -m "feat(agenda): edicao e exclusao na janela"`

---

### Task 5: Regressao final e documentacao

**Files:**
- Modify: `.opencode/safe-evolution/*.md`
- Test: suíte completa

**Interfaces:**
- Consumes: todas.

- [ ] **Step 1: Rodar `pytest -q`** → esperado verde.
- [ ] **Step 2: Rodar `compileall` e `git diff --check`** → limpos.
- [ ] **Step 3: Atualizar acceptance/changes/scope com os resultados.**
- [ ] **Step 4: Commit de documentacao.**

---

## Self-Review

- **Spec coverage:** validação (T1), comandos (T2), rota (T3), janela (T4), garantia (T5).
- **Step scan:** sem TBD; cada step determina uma acao.
- **Types:** `campos` dict consistente entre T2 e T3; `item_selecionado_id` str|None em T4.
- **Review Focus:** 5 cenarios com teste nas tasks 1, 2, 3 e 4.
- **Proportion:** plano proporcional ao spec; corpos de codigo apenas nos testes que fixam valores.
