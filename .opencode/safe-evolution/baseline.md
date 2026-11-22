# Estado inicial e regressao

- Branch/commit: `CANVAS-INFINITO` @ `32f774d`
- Data do diagnostico: 22/11/2026
- Alteracoes locais preexistentes (nao commitadas, preservadas):
  - Modificados: `Documentos.Md/HOMOLOGACAO_CANVAS_FINAL.md`, `core/assistencia_planos.py`, `core/comandos_planos.py`, `core/interface_canvas.py`, `core/interface_canvas_planos.py`, `core/interface_mapa.py`, `core/interface_planos.py`, `core/llm_client.py`, `main.py`, `tests/*` (8 arquivos), `ui.py`.
  - Removidos no worktree: `README.md`, `requirements.txt` (nao restaurar).
  - Novos: `core/controle_canvas.py`, `tests/test_controle_canvas.py`, `tests/test_planejamento_provedor_canvas.py`, `tests/test_simulacao_controle_canvas.py`.
- Testes seguros executados antes das mudancas (offscreen, dados temporarios):
  - `tests/test_controle_canvas.py` + `test_planejamento_provedor_canvas.py` + `test_simulacao_controle_canvas.py`: **63 passed**.
  - Suite de Planos/Canvas: **137 passed, 1 failed**.
    - Falha preexistente e nao relacionada: `tests/test_interface_canvas.py::test_dock_delega_a_aparencia_e_aplica_preferencias`
      (`assert dock.geometry().bottom() < w._composer.geometry().top()`; layout do chat/composer, nao do controle do Canvas).
- Comportamentos a preservar:
  - `CP.reconhecer`: "Vamos planejar um produto...", "Quero criar um projeto..." continuam `CRIAR`.
  - Edicao assistida exige modo "Editar com a NIA" e autorizacao explicita.
  - Lotes atomicos: uma operacao de undo; lote invalido nao aplica parte valida.
  - Conflito de revisao, resposta atrasada e troca de plano descartam o lote.
  - Contexto externo filtra cards `restrito`/`financeiro`.
  - Nenhum comando destrutivo de planos (arquivar/excluir) por voz nesta etapa.
- Ambiente e limitacoes:
  - Windows, Python 3.12, PyQt6, `QT_QPA_PLATFORM=offscreen` nos testes.
  - Sem credenciais/provedor real e sem microfone; validacao visual por captura offscreen.
