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

## Rodada 4 — baseline antes das mudancas (22/11/2026)
- Commit de referencia: `e170e6b` (11 arquivos, 749 insercoes).
- Diagnostico da interrupcao:
  - `ui.py:6521-6527` (`_send`) envia o texto ao `on_text_command` sem chamar
    `on_interrupt`; a fala/tarefa anterior continua enquanto a nova e processada.
  - `main.py:7526-7548` (`interrupt`) drena `audio_in_queue`, incrementa
    `_turno_seq` e `set_speaking(False)`, mas nao cancela a ferramenta em voo
    (`_executar_ferramenta_local`, `futuro.result(timeout=900)`) e nao tem
    excecao para "fazer ate o final".
  - `main.py:8783-8785` e `9343-9345` continuam enfileirando chunks de TTS
    mesmo depois da interrupcao, porque nao ha token de geracao.
- Comportamentos a preservar: interrupcao por ESC/_do_interrupt, barge-in de
  voz em tempo real, avisos de tarefa longa, microfone aberto apos interrupcao.
- Fora de escopo: cancelamento de processos externos ja iniciados no sistema.

## Rodada 5 — baseline antes das mudancas (22/11/2026)
- Relato: pergunta sobre clima seguida de pergunta sobre horas demorou para responder.
- Suite anterior: 593 passed, 4 falhas preexistentes.
- Diagnostico: `main.py:9001-9013` (`_trava_boca`) e os pontos de `acquire(timeout=10/25)`
  prendem a nova fala ate a geracao TTS anterior terminar. `interrupt()` (rodada 4)
  avanca `_fala_seq` e descarta os pedacos antigos, mas nao libera a trava — a
  nova resposta de horas espera ate 25 s antes de falar.
- `interrupt()` nao sinaliza explicitamente que a boca pode ser bypassada.
- A preservar: uma fala de nuvem por vez na sessao ao vivo, para nao misturar audio.
- Fora de escopo: acelerar a rede do provedor de clima ou do relogio.

## Rodada 6 — baseline antes das mudancas (22/11/2026)
- Relato: frases sendo cortadas no meio; a NIA precisa falar tudo o que for necessario.
- Suite anterior: 599 passed, 4 falhas preexistentes.
- Limites encontrados:
  - `core/cerebro_openrouter.py:1373-1385`: `_fechar_resposta` corta em 45 palavras.
  - `core/personas.py:168-190`: prompt "CONVERSA E CURTA: doze palavras" e
    "ate quarenta e cinco palavras se precisar".
  - `main.py:8791-8795`: prompt "direto e curto ... ate quarenta palavras".
  - `core/llm_client.py:324` e `:617-619`: `max_tokens`/`num_predict` = 150.
- `core/gemini_voice.py:1180` ja ajusta o prazo ao tamanho do texto (nao e a causa).
- A preservar: conversa trivial continua curta; nao introduzir respostas longas
  onde uma frase basta. Mudancas locais do usuario em `actions/weather_report.py`
  e `tests/test_clima_periodos.py` nao devem ser tocadas.

## Rodada 7 — baseline antes das mudancas (22/11/2026)
- Relato: "Hoje em Santa Maria das Barreiras: ... 92% de chance de chuva.
  Agora faz 31 graus." a NIA falou só ate "92%" e parou.
- Suite anterior: 625 passed, 4 falhas preexistentes.
- Causa raiz: `core/gemini_voice.py:297` `SILENCIO_MAX_S = 8.0` — apos 8 s sem
  audio no meio do turno, `_corrida` faz `break` (linha 1060) e descarta o resto.
- Agravante: `main.py:9071` `_INTEIRA_PARA_TOCAR = 0.65` aceita fala com so 65%
  do tempo esperado; `_gerar_inteiro` devolve o `melhor` audio mesmo cortado.
- O teto de palavras da rodada 6 NAO e a causa: o corte e no meio da frase.
- A preservar: primeiro som tem prazo proprio; falhas reais de conexao soltam
  a proxima fala; nunca repetir audio que ja tocou.

## Rodada 8 — baseline antes das mudancas (22/11/2026)
- Pedido aprovado pelo usuario: "agora a tarde" deve responder pelas horas
  restantes do turno quando ele ja comecou; antes do turno, manter 12h-17h.
- Suite anterior: 630 passed, 4 falhas preexistentes.
- Diagnostico: `_filtrar_horas` (actions/weather_report.py:175) filtra apenas
  pelo turno fixo (tarde = 12-17), sem olhar a hora atual; `_qual_dia` trata
  "agora" como hoje, mas a palavra "agora" nao e usada para limitar as horas.
- `current` da URL Open-Meteo nao pede o campo `time`, entao a hora local da
  cidade consultada nao esta disponivel (o relogio do PC pode estar em outro fuso).
- A preservar: testes de clima do usuario em `tests/test_clima_periodos.py`;
  resposta de dia inteiro e de turno sem "agora" permanecem iguais.

## Rodada 9 — baseline das 4 falhas persistentes (22/11/2026)
- Suite anterior: 639 passed, 4 failed desde a primeira rodada.
- Causas confirmadas por reproducao:
  1. `test_botao_salvar`: `core/interface_canvas_planos.py` cria `salvar_canvas`
     com `button.hide()` e `_reposicionar` nunca o mostra nem o posiciona.
  2. `test_dock_delega...`: `_composer` fica oculto por padrao e o Qt nao
     atualiza a geometria de widget oculto — fica (0,0,620,56); ao mostrar,
     passa a (100,456,620,56) e a assercao de layout e verdadeira.
  3. `test_excluir_card_suspende...`: `ExcluirCardCommand._lembretes` (interface_mapa.py:610)
     retorna quando `disco.revisao != plano.revisao and disco.mapa != plano.mapa`.
     A exclusao acabou de mudar o mapa, entao a guarda impede `suspender_por_card`.
  4. `test_topo_compacto`: `test_config_dashboard.py` monkeypatcha apenas
     `nomes_tela.ARQUIVO`, mas nao limpa `nomes_tela._cache`; "Nome de teste"
     vaza para o teste seguinte.
- Todas sao corrigiveis sem mudar contratos publicos nem dados do usuario.

## Rodada 13 — CRUD completo da Agenda (23/11/2026)
- Branch `AGENDA`, worktree com mudancas pendentes da rodada 12 (nao commitadas).
- Suite anterior: 707 passed, 0 failed; `compileall`/`git diff --check` limpos.
- Pedido do dono: "criar o crud completo da agenda, pra que possamos ter controle total".
- Recon: `AG.editar` ja aceita todos os campos, mas a janela so adiciona e le;
  a voz so edita preparo/data/estado; falta renomear, tipo, notas e reabrir;
  falta validacao em `editar()` e botoes de editar/excluir/concluir na janela.
- Desenho aprovado; spec em `docs/superpowers/specs/2026-11-23-agenda-crud-design.md`.
- Builder check em andamento (modelo gratuito).
- Nenhum codigo de produto alterado nesta etapa.

## Rodada 12 — correcoes dos testes do dono (23/11/2026)
- Teste real da NIA (interface offscreen, perfil isolado) revelou 6 falhas:
  1. "adicione/mude/exclua ..." caem no Canvas de planos ("Abra um plano...")
     porque `_processar_pedido_assistido` roda antes de `_processar_pedido_agenda`.
  2. `excluir` nao existe como acao no parser da Agenda.
  3. referencia de titulo inexistente silenciosamente cai para o proximo.
  4. mensagem "Compromisso concluir:" gramaticalmente errada.
  5. listagens nao filtram "proximo mes"/"hoje" e nao citam o proximo.
  6. "bom dia" responde sem saudacao.
- Branco: branch AGENDA, 689 testes verdes antes das mudancas.
- A preservar: comportamentos ja validados e Rulings da rodada 11.

## Rodada 11 — Agenda (23/11/2026)
- Branch: `AGENDA` (criada de `CANVAS-INFINITO`), limpa e sincronizada com `origin/AGENDA`.
- Commits na origem: `cd72528` (roteamento de acao no PC), PR #4 aberto em CANVAS-INFINITO.
- Suite anterior: **654 passed, 0 failed**; `compileall`/`git diff --check` limpos.
- Ideia aprovada no play back: modulo proprio `core/agenda.py`, janela estilo
  Google Calendar com identidade NIA, card no CANVAS PRINCIPAL (clima/horas),
  nao no Canvas dos planos; sugestao automatica de preparo por tipo, editavel.
- Recon: nao existe `autonomous-builder`; `core/lembretes.py` e atrelado a planos;
  `ui._build_dock` monta botoes; `CanvasStage.hoje_host` e o molde do card;
  `core/resumo_dia.py` define persistencia por perfil fora do Git.
- Documento de desenho: `docs/superpowers/specs/2026-11-23-agenda-design.md`.
- Nenhum codigo de produto alterado nesta etapa.

## Rodada 10 — baseline antes das mudancas (22/11/2026)
- Relato: "abra o youtube e toque uma musica" → NIA listou 23 planos.
- Suite anterior: 643 passed, 0 failed; commit/push `8c8c499`.
- Reproducao: `CP.reconhecer("abra o youtube e toque uma musica").tipo == "ABRIR"`;
  o mesmo vale para "abra a secretaria" e "abra o bloco de notas".
- Causa: `core/comandos_planos.py:137` regex final
  `^(?:nia)?(?:abra|abre|abrir|continua|...)` classifica QUALQUER "abra" como
  abertura de plano. O regex especifico da linha 113 ja cobre "abra o plano/projeto/produto".
- A preservar: "abra o plano X", "Abre o projeto Y", retomar estudo, gerenciador.
- Rotas corretas existentes: `_rede_de_abrir`, `_rede_do_site`, `CH.reconhecer`.
