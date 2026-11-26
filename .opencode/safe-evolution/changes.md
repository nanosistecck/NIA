# Historico incremental

Para cada etapa registre: data, tarefa, arquivos, motivo, testes executados, resultados, riscos, decisao e proxima etapa. Nao registre tokens, senhas ou credenciais.

## 22/11/2026 — Diagnostico e baseline
- Tarefa: mapear roteamento de Planos/Canvas, reproduzir a confusao "card vs plano" e registrar estado.
- Arquivos lidos: `core/comandos_planos.py`, `core/assistencia_planos.py`, `core/controle_canvas.py`, `core/interface_canvas_planos.py`, `core/interface_mapa.py`, `main.py`, `ui.py`, testes de Canvas/Planos.
- Testes: 63 testes de controle passaram; 137/138 de Planos/Canvas passaram.
- Falha preexistente: `test_dock_delega_a_aparencia_e_aplica_preferencias` (layout do composer), nao relacionada.
- Causa confirmada: `CP.reconhecer("criar um novo card") == CRIAR`; gramatica local gera titulos ruins ou falha sem titulo.
- Riscos: alterar `reconhecer` pode afetar criacao de planos legitimos; coberto por testes.
- Proxima etapa: escrever testes RED e implementar.

## 22/11/2026 — Etapa 1: roteamento de intencao e consulta de planos
- Arquivos: `core/comandos_planos.py`, `main.py`, `tests/test_cards_contexto_planos.py` (novo).
- Motivo: "criar um novo card" casava `criar (um|...)` e virava criacao de plano.
- Implementado: `_CRIACAO_DE_CARD`/`_QUERO_CARD` exigem objeto `card`; `LISTAR_PLANOS`
  responde "quais planos eu tenho"/"liste meus planos"; "gerenciar planos" abre o gerenciador;
  titulo explicito `chamado/com titulo` tambem e lido na criacao de plano.
- Testes: 17 novos testes de roteamento/listagem passaram.
- Riscos: criacao legitima de plano preservada por testes (`test_criacao_voz.py`).

## 22/11/2026 — Etapa 2: gramatica local de cards e ideias
- Arquivos: `core/controle_canvas.py`, `main.py`, `tests/test_cards_contexto_planos.py`.
- Motivo: criacao local gerava titulos ruins ("sobre X", "com ideias...") e falhava sem titulo.
- Implementado: parser com titulo explicito/topico, tipo, status, descricao, posicao,
  conexao, varios cards em um lote, anexar ideias a card nomeado/selecionado e
  renomear rotulo de conexao. Mensagem sem plano orienta abrir o Canvas.
- Testes: 34 novos testes passaram; 146 testes dasAreas afetadas passaram.
- Correcoes no caminho: nome de funcao no import do `main.py` (`ImportError` silencioso)
  e extracao de valor das clauses (grupos de captura, nao intervalo apos o match).
- Riscos: parser intercepta pedidos generativos; provedor continua disponivel para
  pedidos que nao casam a gramatica local.
- Proxima etapa: suite completa, revisao de diff e captura offscreen.

## 22/11/2026 — Etapa 3: distribuicao de cards e validacao final
- Arquivos: `core/controle_canvas.py`.
- Motivo: cards criados em pedidos seguintes ficavam na mesma posicao (270,110) e
  ficavam escondidos uns atr dos outros na captura.
- Implementado: `_posicao_livre` procura a primeira posicao sem sobreposicao,
  mantendo as coordenadas explicitas intactas.
- Testes: 95 testes de Canvas/Planos passaram apos a mudanca.
- Suite completa: 543 passed, 4 failed. Todas as 4 falhas eram preexistentes
  (`test_botao_salvar`, `test_dock_delega_a_aparencia...`, `test_excluir_card_suspende...`,
  `test_topo_compacto` por ordem de testes). Nenhuma area alterada por esta etapa.
- `compileall` e `git diff --check`: limpos.
- Evidencia visual: interface executada offscreen, seis comandos aplicados e
  captura inspecionada em `logs/captura_controle_cards.png`.
- Riscos restantes: `.gitignore` preexistente ignora `.opencode/` e `tests/*`,
  entao os novos testes/estado nao aparecem como untracked no Git (nao alterado).
- Decisao: nao commitar, nao criar branch e nao tocar nas mudancas locais do usuario.

## 22/11/2026 — Rodada 2: prioridade da conversa e resumo legivel
- Tarefa: no chat do Canvas, priorizar conversa sobre o plano e parar de revelar IDs.
- Diagnostico (antes de editar): reproduzido com `%TEMP%\diag_prioridade.py`.
  - Causa 1: frases sobre o plano nao casavam reconhecedor local; `_on_text_command`
    seguia para `_responder_texto_local`, que usa OpenRouter com ferramentas.
  - Causa 2: `ui.py` montava a confirmacao com `card_id`/`origem`/`titulo` crus.
- Arquivos: `core/assistencia_planos.py`, `main.py`, `ui.py`,
  `tests/test_prioridade_conversa_plano.py` (novo).
- Implementado: `conversa_sobre_plano`, `resumo_conversa_plano`, `resumo_lote`,
  `_responder_conversa_plano` na rota antes de `CH.reconhecer`, e confirmacao
  via `resumo_lote` no lugar da lista de IDs.
- Testes: 17 RED → 18 GREEN; 190 testes da area passaram; suite completa
  561 passed, 4 failed (mesmas preexistentes da rodada 1).
- `compileall` e `git diff --check`: limpos.
- Evidencia: captura `logs/captura_prioridade_plano.png` e mensagens verificadas
  sem nenhum hash de 32 caracteres.
- Riscos: reconhecedor e deliberadamente restrito a termos de plano/card e a
  titulos de cards; hora, clima e busca local explicita foram testados a parte.
- Proxima etapa: aprovacao do dono antes de qualquer commit ou nova area.

## 22/11/2026 — Rodada 3: interacao completa com o Canvas
- Tarefa: corrigir falso "O plano mudou", retomada de pedido e cards sobre a NIA.
- Diagnostico: tres reproducoes em `%TEMP%` antes de editar (ver `baseline.md`).
- Arquivos: `core/controle_canvas.py`, `core/assistencia_planos.py` (inalterado nesta
  rodada), `main.py`, `ui.py`, `tests/test_interacao_canvas_pedido.py` (novo).
- Implementado:
  - `_CARDS_FUNCIONAMENTO_NIA`, `pedido_funcionamento_nia`, `pedido_retomada` e
    `_pedido_funcionamento_nia` em `core/controle_canvas.py`;
  - `NiaUI.plano_canvas_vivo` em `ui.py` como fonte de verdade quando o espelho
    de sinal esta vazio;
  - `vivo_atual()` no `main.py`, preservando o descarte quando a ponte existe e
    o plano realmente troca;
  - `_retomar_pedido_canvas` e `_ultimo_pedido_canvas` (5 minutos, mesmo plano/sessao).
- Testes: 13 RED → 14 GREEN; 196 testes da area passaram; suite completa
  575 passed, 4 failed (mesmas preexistentes).
- Correcoes no caminho: pontes ausentes em testes com `SimpleNamespace` exigiram
  `getattr` para `_retomar_pedido_canvas` e `tem_ponte` antes de descartar.
- `compileall` e `git diff --check`: limpos.
- Evidencia: `logs/captura_interacao_canvas.png` e mensagens sem "O plano mudou".
- Riscos: a retomada repete o pedido (pode duplicar cards se o primeiro ja
  tiver sido aplicado); comportamento intencional de "faz de novo".
- Decisao: sem commit, sem branch, sem tocar nas mudancas locais preexistentes.

## 22/11/2026 — Commit e rodada 4: interrupcao conversacional
- Commit solicitado pelo usuario: `e170e6b` (11 arquivos, 749 insercoes).
- Tarefa: nova mensagem (chat ou voz) interrompe fala/tarefa corrente; "faz ate
  o final" impede a interrupcao.
- Diagnostico: `ui._send` nao chamava `on_interrupt`; `interrupt` nao cancelava
  ferramenta em voo nem descartava TTS em geracao; nao havia excecao "ate o final".
- Arquivos: `main.py`, `ui.py`, `tests/test_interrupcao_conversa.py` (novo).
- Implementado: `pedido_ate_o_final`, `atividade_em_andamento`,
  `_tratar_interrupcao`, `interrupt(silencioso=False)` com `_fala_seq` e
  cancelamento de `_ferramenta_futuro`; `on_atividade` no `MainWindow` e
  chamada em `_send`.
- Testes: 17 RED → 18 GREEN; 214 testes da area; suite completa 593 passed,
  4 failed (mesmas preexistentes).
- Correcoes no caminho: esqueletos de teste sem `_interrupted`/`_speaking_lock`
  exigiram `getattr` nas verificacoes.
- `compileall` e `git diff --check`: limpos.
- Evidencia: `logs/captura_interrupcao.png` e probe com turno/fala_seq avancados.
- Decisao: esta rodada NAO foi commitada; aguardando aprovacao explicita.

## 22/11/2026 — Rodada 5: troca rapida de assunto
- Tarefa: clima seguido de horas nao deve esperar a fala anterior terminar.
- Diagnostico: `_trava_boca` presa pela geracao TTS do clima; `interrupt()` avancava
  `_fala_seq` mas nao sinalizava que a proxima fala podia ignorar a espera.
- Arquivos: `main.py`, `tests/test_troca_assunto_rapida.py` (novo).
- Implementado: `_boca_bypass`, `_timeout_boca`, `_adquirir_boca`; `interrupt()`
  marca o bypass; os tres pontos de `acquire(timeout=10/25)` passaram a usar
  `_adquirir_boca`, que consome o bypass na primeira tentativa.
- Testes: 6 RED → 6 GREEN; 312 testes da area; suite completa 599 passed,
  4 failed (mesmas preexistentes).
- `compileall` e `git diff --check`: limpos.
- Evidencia: acquire apos interrupcao em 0,0001 s (contra 10 s sem bypass).
- Decisao: sem commit nesta rodada; aguardando aprovacao.

## 22/11/2026 — Rodada 6: fala completa
- Tarefa: parar de cortar frases no meio; falar tudo que for necessario sem
  perder respostas curtas quando a conversa pede.
- Diagnostico: teto de 45 palavras em `_fechar_resposta` (dois pontos), prompts
  "doze palavras"/"ate quarenta e cinco" e `max_tokens=150` no cliente LLM.
- Arquivos: `core/cerebro_openrouter.py`, `core/personas.py`, `core/llm_client.py`,
  `main.py`, `tests/test_fala_completa.py` (novo),
  `tests/test_planejamento_provedor_canvas.py` (default dinamico de tokens).
- Implementado: `_pedido_quer_texto_completo` isenta explicacoes/dicas/listas do
  teto; teto de seguranca subiu de 45 para 90 apenas para conversa de rotina;
  `max_tokens`/`num_predict` padrao 1024; prompts orientam tamanho conforme a
  pergunta e "fale ate o fim".
- Testes: 8 RED → 10 GREEN; 322 testes da area; suite completa 625 passed,
  4 failed (mesmas preexistentes).
- Correcoes no caminho: `unicodedata` importado dentro do helper; teste de prompt
  passou a ler `REGRAS_FIXAS` (as regras globais), nao `PERSONALIDADES`.
- `compileall` e `git diff --check`: limpos.
- Evidencia: explicacao com 120 palavras preservada; "oi" com 90; tokens 1024.
- Decisao: sem commit nesta rodada; aguardando aprovacao.

## 22/11/2026 — Rodada 7: fala cortada no meio da frase
- Tarefa: frase do clima parava em "92%" sem dizer "de chance de chuva. Agora faz 31 graus".
- Diagnostico: `SILENCIO_MAX_S=8s` fazia `_corrida` desistir no meio do turno;
  a régua de 65% aceitava o audio cortado como completo.
- Arquivos: `core/gemini_voice.py`, `main.py`, `tests/test_fala_sem_corte.py` (novo).
- Implementado: `SILENCIO_MAX_S=20s`; `_INTEIRA_PARA_TOCAR=0.85` e
  `_INTEIRA_PARA_GRAVAR=0.90`; `_gerar_inteiro` devolve `b""` quando nenhuma
  tentativa atinge a régua, fazendo o chamador cair no caminho que fala
  conforme o audio chega em vez de tocar uma frase pela metade.
- Testes: 4 RED → 5 GREEN; 343 testes da area; suite completa 630 passed,
  4 failed (mesmas preexistentes).
- `compileall` e `git diff --check`: limpos.
- Evidencia: frase de 122 caracteres com corte em 67% rejeitada; completa aceita.
- Decisao: sem commit nesta rodada; aguardando aprovacao.

## 22/11/2026 — Rodada 8: clima "agora a tarde"
- Aprovacao explicita do usuario para a melhoria proposta na resposta anterior.
- Arquivos: `actions/weather_report.py`, `main.py`,
  `tests/test_clima_agora.py` (novo; testes de clima do usuario intactos).
- Implementado:
  - `current=time` acrescentado a URL do Open-Meteo (com `timezone=auto`);
  - `_hora_local_atual` le a hora da cidade sem depender do relogio do PC;
  - `_filtrar_horas(..., desde=None)` limita as horas restantes do turno;
  - `weather_action` aplica o limite so quando o pedido contem "agora";
  - descricao da ferramenta `weather_report` orienta a preservar "agora" em `time`.
- Regras: turno ja comecado → so horas restantes; antes do turno → turno
  completo; sem `current.time` → turno completo; sem horas restantes → turno
  completo (nunca resposta vazia).
- Testes: 5 RED → 11 GREEN; 352 testes da area; suite completa 639 passed,
  4 failed (mesmas preexistentes); 14 testes de clima do usuario passaram.
- `compileall` e `git diff --check`: limpos.
- Evidencia: 16h "agora a tarde" → 0%; 16h "hoje à tarde" → 80%; 10h → 80%;
  sem hora local → 80%.
- Decisao: sem commit nesta rodada; aguardando aprovacao.

## 22/11/2026 — Rodada 9: fim das 4 falhas persistentes
- Pergunta do usuario: dava para resolver as falhas?
- Resposta: sim, todas. Diagnostico por reproducao antes de editar.
- Arquivos: `core/interface_canvas_planos.py`, `core/interface_mapa.py`,
  `tests/test_interface_canvas.py`, `tests/test_config_dashboard.py`.
- Correcoes: botao Salvar mostrado e posicionado; composer mostrado no teste de
  layout (widget oculto nao recebe geometria do Qt); guarda de revisao removida
  em `ExcluirCardCommand._lembretes`; cache de `nomes_tela` limpo no fixture.
- Testes: os 4 testes passaram isolados e na suite completa.
- **Suite completa: 643 passed, 0 failed** — primeira vez sem falhas.
- `compileall` e `git diff --check`: limpos.
- Decisao: sem commit nesta rodada; aguardando aprovacao.

## 22/11/2026 — Rodada 10: acao no PC deixou de ser confundida com plano
- Relato: "abra o youtube e toque uma musica" listou 23 planos.
- Causa: regex final de `CP.reconhecer` classificava qualquer "abra" como ABRIR.
- Arquivos: `core/comandos_planos.py`, `tests/test_contexto_acao_pc.py` (novo).
- Correcao: regex final agora so aceita `continua|continue|retoma|retome`;
  abertura de plano por nome continua no regex especifico anterior.
- Testes: 7 RED → 11 GREEN; suite completa 654 passed, 0 failed.
- `compileall` e `git diff --check`: limpos.
- Evidencia: frase chega em `CH.reconhecer`, log "Tocando música no YouTube",
  nenhuma listagem de planos.
- Decisao: sem commit nesta rodada; aguardando aprovacao.

## 23/11/2026 — Rodada 11: Agenda (etapa de desenho)
- Tarefa: nova aplicacao de Agenda no dock e no Canvas principal.
- Diagnostico: recon do dock, `CanvasStage.hoje_host`, `resumo_dia.py`,
  `lembretes.py` e `comandos_lembretes.py`; estado Git e suíte conferidos.
- Play back aprovado pelo usuario, com duas correcoes dele:
  - o card vai no Canvas principal (clima/horas), nao no Canvas dos planos;
  - calendario parecido com o Google, porem mais moderno/elegante; com data,
    hora e sugestao de quando comecar a preparar.
- Abordagem A escolhida: modulo proprio, sem tocar em planos/lembretes.
- Arquivo criado: `docs/superpowers/specs/2026-11-23-agenda-design.md`.
- Estado atualizado: `baseline.md`, `impact-map.md`.
- Revisao de builder executada: 4 perguntas.
  - Decisoes do construtor: reexibicao do card via checkbox no dashboard + comando
    "mostrar card da agenda"; "bom dia" ganha intent propria e helper
    `resumo_proximo()`; campos `plano_id`/`card_id` removidos do registro.
  - Decisao do dono: alvo de comando sem ID = titulo/data ditos, senao proximo
    compromisso, com pergunta quando ambiguo.
- Desenho aprovado; `writing-plans` executado.
- Plano salvo em `docs/superpowers/plans/2026-11-23-agenda.md` (6 tarefas,
  RED→GREEN, capturas obrigatorias nas tasks 4 e 5).
- Self-review do plano: especificacao coberta, tipos consistentes entre tasks,
  5 inputs de risco com teste, sem TBD.
- Metodo de execucao escolhido pelo dono: Native (`executing-plans`).
- Workspace/ledger manuais (scripts bash indisponiveis no WSL sem distro).
- Tasks 1-5 completas, cada uma RED→GREEN e commitada:
  - `ad4ed95` persistencia, `200365f` comandos, `ed20174` rota,
    `a80e3bb` janela, `ba38866` card.
- Task 6: suite **685 passed, 0 failed, exit 0**; compileall e diff limpos.
- Correcoes por teste registradas em `acceptance.md`.
- Evidencias visuais inspecionadas (janela e card no Canvas principal).
- Revisao final com servico gratuito: 5 achados corrigidos (1 Critical, 3 Important,
  1 Minor), 4 testes novos, suite 689/689, commit `caa9b90`.
- Decisao registrada: somente servicos gratuitos (revisor pago falhou por credito).

## 23/11/2026 — Rodada 12: correcoes dos testes reais
- Tarefa: o dono testou a NIA e pediu correcao de 6 erros + varredura extra.
- Arquivos: `core/agenda.py`, `core/comandos_agenda.py`, `main.py`,
  `tests/test_agenda_correcoes.py` (novo, 18 testes).
- Correcoes: prioridade da Agenda sobre o Canvas, acao excluir, alvo por
  tokens (com ambiguidade), mensagens por acao, filtro de periodo nas listagens
  com citacao do proximo, saudacoes bom dia/tarde/noite, titulo sem data,
  "dia N", e "exclua todos" sem apagar em lote.
- Duas regressoes encontradas e corrigidas durante a suite: "Exclua o card
  Validação" e "Conecte o card ... Entrega" voltaram ao Canvas ao exigir que
  frases com "card" nao entrem na Agenda (exceto "card da agenda").
- Suite final 707/707, exit 0; compileall e diff limpos.
- Duas varreduras reais executadas: todas as frases do relato e as extras
  responderam corretamente.
- Nenhum commit feito nesta rodada; branch AGENDA com mudancas pendentes.

## 23/11/2026 — Rodada 13: CRUD completo da Agenda
- Usuario aprovou o desenho e autorizou alteracoes.
- Spec `docs/superpowers/specs/2026-11-23-agenda-crud-design.md` e plano
  `docs/superpowers/plans/2026-11-23-agenda-crud.md` escritos.
- Builder check (gratuito) com 5 perguntas: respondidas no spec; a primeira
  revelou bug real (ValueError sem tratamento na rota) — corrigido com teste.
- Tasks 1-3: validacao/reabrir no modelo, novos comandos, rota com rotulos por
  campo e tratamento de erro. Commit `0936ce4`.
- Task 4: janela com lista clicavel, notas, estado, botoes Salvar/Cancelar/
  Concluir/Reabrir/Excluir e confirmacao. Commit `97ce4a8`.
- Regressao encontrada e corrigida: "Renomeie o produto..." foi capturado pela
  Agenda ao adicionar verbos genericos ao detector; removidos.
- Suite final 724/724, exit 0; compileall e diff limpos.
- Evidencia `logs/captura_agenda_crud.png` inspecionada.

## 23/11/2026 — Rodada 14: frase real de criacao na Agenda
- Relato: `adicione na agenda buscar a maria as 21:06` respondeu "Abra um plano...".
- Causa: `processar` exigia termo de tipo e nao reconhecia "adicione na agenda";
  `interpretar` devolvia None para hora sem data.
- Arquivos: `core/agenda.py`, `core/comandos_agenda.py`,
  `tests/test_agenda_frase_real.py` (novo, 6 testes).
- Correcoes: criacao direta na agenda com titulo extrativo; hora sem data
  infere hoje se futura e amanha se passou.
- Teste real: frase cria "buscar a maria" as 21:06 e fala do proximo compromisso.
- Suite 730/730, exit 0 (duas execucoes); compileall e diff limpos.
- Servidor reiniciou durante a suíte; retomado sem repetir trabalho concluido.


## 2026-11-23T22:50:56.900283-03:00 — checkpoint EVOLUCAO-NIA

Programa EVOLUCAO-NIA: etapas 01–04 completas; 05 parcial. Produto e arquivos alterados descritos em EVOLUCAO-NIA/registros/RELATORIO.md. Nenhum commit ou publicação. 167 testes combinados passaram; baseline integral anterior tinha 1 falha Canvas que não foi reproduzida isoladamente.

## 2026-11-24 — Avaliação da Central, causa do Canvas e credenciais nas Configurações

- Diagnóstico antes de editar: lidas instruções `.opencode/safe-evolution/*`,
  comparados Git/código/estado persistente e executada suíte baseline de
  **895 passed** (`EVOLUCAO-NIA/registros/avaliacao-01-baseline-pytest.log`).
- Causa raiz do Canvas reproduzida de forma determinística: criar outra
  `MainWindow` antes do teste deixa o driver de animação Qt offscreen sem
  avançar (`state=Running`, geometria intacta após 1 s). O `settle` media
  quadros transitórios. Correção apenas no helper de teste: entrega sinais
  enfileirados, espera a animação e aplica `arrange(False)` se o driver não
  progredir. Asserções inalteradas; teste passa com animação de 1500 ms.
- `ui.py`: timer de lembretes passou a ser timer filho da janela, sem
  `QTimer.singleShot` órfão (teste novo `test_timers_interface.py`).
- Novo `core/credenciais_integracoes.py`: URL/workspace/usuário em
  `config/integracoes.json` (atômico) e token no Windows Credential Manager
  (`win32cred`, sem nova dependência); sem credencial em texto puro nem
  migração de banco. Injeção de store para testes.
- `core/config_dashboard.py`: terceiro segmento "Serviços externos" em
  Configurações → Integrações, com Penpot/Plane/Nextcloud, botão "Abrir site"
  (links oficiais), Salvar/Limpar e status sem segredo. Construção lazy.
- Testes novos: 5 de credenciais + 4 de UI + 1 de timer; uma falha de
  poluição de `os.environ` no teste de credenciais foi corrigida.
- Suíte final: **905 passed, exit 0** (`avaliacao-09-integral-final-pytest.log`).
  `git diff --check` limpo e 239 fontes AST sem erros.
- Evidência visual inspecionada: `captura_integracoes.png` (página legível,
  cartões e botões visíveis).
- Decisão: nenhum commit, branch, publicação ou acesso a serviço externo.
- Próximo: quando o dono configurar URLs/tokens na nova página, homologar
  leituras reais; dispositivos e DPI físico seguem pendentes.

## 2026-11-24 — Remoção dos conectores com limites de uso

- Decisão do dono: só ferramentas totalmente gratuitas e de código aberto.
  Penpot/Plane/Nextcloud foram removidos (planos gratuitos com limites).
- Removidos os 3 conectores, o módulo de credenciais, 5 arquivos de teste, a
  página "Serviços externos" e todas as referências em registro/descrições.
- Preservados: laboratório HTTP local, dispositivos pareados, pesquisa,
  biblioteca, diagrama, janelas, contexto e registro central.
- Não tocados: Agenda e suas 4 falhas dependentes de data (fora do escopo).
- Validação: 118 testes da área verdes; suíte integral com 875 verdes e as
  4 falhas pré-existentes da Agenda; AST e diff limpos.
- Detalhes em `EVOLUCAO-NIA/registros/18-REMOCAO-CONECTORES.md`.

## 2026-11-24 — Correção das últimas 4 falhas (Agenda)

- Causa: `tests/test_agenda_correcoes.py` usava datas relativas a 23/11/2026
  mas dependia do relógio real para "próximo" e saudações; após a meia-noite
  os eventos de "amanhã" passaram a estar no passado.
- Correção apenas no fixture do teste: congelar `core.agenda._agora` em
  2026-11-23T13:00Z (10:00 em -03), preservando o comportamento quando um
  `agora` explícito é passado. Produto não alterado.
- Resultado: 18/18 testes da Agenda e **879 passed, exit 0** na suíte completa
  (`correcao-final-integral-pytest.log`). `git diff --check` limpo; 230 fontes
  AST sem erros. Nenhum commit/publicação.

## 2026-11-24 — Acesso completo às ferramentas restantes

- Auditoria confirmou que pesquisa/biblioteca/diagrama/integrador e globo
  estavam na Central, mas sem janela registrada; o clique gerava ação `usar`
  rejeitada. Corrigido:
  - `core/painel_ferramenta.py` (novo): painel leve sob demanda com metadados,
    ações reais e campo de argumentos JSON; emite a ação pela ponte existente.
  - `ui.py`: registro de janelas para os 4 domínios + globo; habilidades sem
    interface mostram o exemplo de uso em vez de ação inválida.
  - `core/central_aplicativos.py`: fundo da grade corrigido (antes branco com
    nomes ilegíveis) — evidência visual recapturada.
  - `core/config_dashboard.py`: botão "Abrir Central de Aplicativos" na página
    Geral (funciona quando a ponte da NIA está disponível).
- Validação: 881 passed, exit 0; AST 232 fontes sem erros; diff limpo.
- Evidências: `EVOLUCAO-NIA/registros/captura_configuracoes_geral.png`,
  `captura_integracoes.png`, `captura_central_aplicativos.png`,
  `captura_painel_biblioteca.png` (inspecionadas).

## 2026-11-24 — Manual de uso local

- Criado `docs/manual-nia/index.html`: exemplos de todas as ferramentas,
  busca, filtros e botão copiar, sem rede/CDN/WebEngine.
- Abertura por voz ("abra o manual", "quais comandos você entende?"), por
  sinal Qt e por botão em Configurações → Geral.
- 885 testes verdes; 234 fontes AST; diff limpo. Detalhes em
  `EVOLUCAO-NIA/registros/19-MANUAL-USO.md`. Sem inspeção visual do HTML em
  navegador (ferramenta indisponível nesta sessão).

## 2026-11-24 — Revisão da bandeja e formulários sem JSON

- Diagnóstico: 2 blocos não acionáveis (`microfone`, `interromper`) e, no app
  real, 44 atalhos `tool_*` inúteis apareceriam na Central; painéis exigiam JSON.
- Correções:
  - `core/registro_aplicativos.py`: `tool_*` com `visivel_na_central=False`.
  - `core/registro_nativo.py`: controles do dock removidos do registro da Central.
  - `core/ferramentas_agrupadas.py`: `CAMPOS_ACAO` + `preparar_argumentos`
    convertem campos de formulário em argumentos tipados (sem JSON do usuário).
  - `core/painel_ferramenta.py`: combo de ações e campos dinâmicos (texto,
    opções, número, confirmação), com rótulos acessíveis.
  - `ui.py`: habilidade sem interface agora preenche o exemplo no chat e foca
    o campo, em vez de apenas registrar log.
  - Manual HTML e imports mortos atualizados.
- Evidência: bandeja com 12 blocos, todos acionáveis (probe), capturas
  `captura_central_aplicativos.png` e `captura_painel_biblioteca.png`.
- Validação: 886 testes verdes, 234 fontes AST, diff limpo. Sem commit.

## 2026-11-24 — Correção final: pesquisa local por termo simples

- Simulação de ponta a ponta das 4 ferramentas revelou que `pesquisa.local`
  exigia a frase "procure nos meus arquivos por ..."; o painel pede só um termo.
- Corrigido em `core/executor_agrupado.py`: extrai o termo quando a frase é
  reconhecida e usa o texto direto quando não é, com motivo honesto quando o
  índice está vazio. Teste novo adicionado.
- Suíte final: **887 passed, exit 0**; 234 fontes AST; `git diff --check` limpo.
- Nenhuma nova arquitetura, nenhum repositório baixado, nenhum commit.

## 2026-11-24 — Remoção das 4 ferramentas insatisfatórias

- Usuário escolheu remover pesquisa nova, biblioteca, diagrama e integrador
  após diagnóstico: saídas em JSON, sem editor visual e integrador sem adaptador.
- Removidos 8 módulos, 7 arquivos de teste e todas as referências em catálogo,
  permissões, registro nativo, ui.py, main.py, frases locais e manual HTML.
- Mantidos: busca local antiga (FTS5/citações), Canvas/Planos, Agenda, dock,
  Central enxuta, gerenciador de janelas, contexto e permissões.
- Suíte: 840 passed, exit 0; 219 fontes AST; diff limpo. Sem commit.
- Detalhes em `EVOLUCAO-NIA/registros/20-REMOCAO-FERRAMENTAS.md`.

## 25/11/2026 — Rodada 15: exclusão de `EVOLUCAO-NIA/`

- Tarefa: limpeza geral de código morto; primeiro passo autorizado foi apagar o
  diretório de diagnóstico/relatórios `EVOLUCAO-NIA/`.
- Antes de apagar: 201 arquivos, ~984 KB, `.gitignore:53`, `git ls-files` vazio,
  nenhuma referência em qualquer `.py`. Avisado ao dono de que não havia backup
  no Git e que a exclusão seria irreversível; ele confirmou "Apagar agora, sem
  backup".
- Arquivos alterados até aqui: somente `.opencode/safe-evolution/*.md`
  (baseline, scope, impact-map, acceptance, changes). Nenhum arquivo de produto
  ou teste tocado; nenhum commit, push, branch ou stash.
- Motivo: o dono considera o diretório descartável e ele não participa do produto.
- Risco: perda irreversível dos relatórios históricos; aceito explicitamente.
  Referências antigas nos state files permanecem como registro histórico.
- Execução: `Remove-Item -Recurse -Force EVOLUCAO-NIA` → `exists=False`,
  `git ls-files` continua com 0 linhas. Suíte de sanidade: 22 passed em
  `test_homologacao_evolucao.py` + `test_windows_frame.py` +
  `test_frame_nativo_secundarias.py`. Nenhuma falha; nenhum arquivo de produto
  alterado; `git status` inalterado fora dos state files.
- Decisão/proxima etapa: triagem individual dos demais candidatos de código
  morto; nada será removido em bloco. Aguardando decisão sobre os outros 5
  módulos órfãos.

