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

## Rodada 2 — baseline antes das mudancas (22/11/2026)
- Rodada 1 concluida: 543 passed, 4 falhas preexistentes na suite completa;
  146 testes das areas afetadas passaram; `compileall` e `git diff --check` limpos.
- Reproducao das duas causas (`%TEMP%\diag_prioridade.py`):
  - `me fala sobre o plano que estamos criando` → `tratado_local=False`,
    `AP=NENHUMA`, `CP=EXPLICAR`; cai em `_responder_texto_local` com ferramentas.
  - Mensagem atual reproduzida exatamente:
    `SIS: Alteração concluída em sobre inteligencia artificial: 665ddc..., Fundamentos, 665ddc..., 665ddc..., 665ddc....`
- Causa raiz 1: nenhum reconhecedor local cobre conversa aberta sobre o plano;
  `_on_text_command` segue para busca local/cerebro com `TOOL_DECLARATIONS`.
- Causa raiz 2: `ui.py:7109-7110` monta a mensagem com `card_id`/`origem`/`titulo`
  sem converter IDs em nomes e sem limite.
- Comportamentos a preservar nesta rodada: hora/clima/abrir programa, busca local
  explicita e mensagens com "Alteração concluída".

## Rodada 3 — baseline antes das mudancas (22/11/2026)
- Suite anterior: 561 passed, 4 falhas preexistentes.
- Reproducao 1 (`%TEMP%\diag_pedido.py`): "vc consegue criar cards relacionados
  ao seu funcionamento e inserir nesse plano?" gerou 2 cards com titulos crus
  ("Relacionados ao seu funcionamento", "Inserir nesse plano").
- Reproducao 2 (`%TEMP%\diag_provedor2.py`): com provedor e espelho
  `estado_canvas_vivo()` retornando None durante a geracao, a frase generativa
  respondeu exatamente "SIS: O plano mudou desde o pedido; nada foi aplicado."
- Reproducao 3: "tenta fazer meu pedido" retornou False e caiu no cerebro comum,
  produzindo a resposta generica relatada pelo usuario.
- Causa raiz 1: `main.py:7338-7342` confia somente no espelho de contexto apos a
  chamada do provedor; se ele estiver temporariamente vazio, descarta um lote valido.
- Causa raiz 2: nao existe memoria do ultimo pedido do Canvas para frases de retomada.
- Causa raiz 3: a gramatica local nao tem conteudo proprio sobre a NIA, gerando
  titulos a partir de preposicoes do pedido.
- A preservar: descarte de resposta atrasada quando o plano realmente troca
  (`test_resposta_atrasada_nao_altera_outro_estado`).
