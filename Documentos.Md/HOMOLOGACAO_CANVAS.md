# Homologação do Canvas Infinito — NIA

Data: 20/11/2026 · Branch `CANVAS-INFINITO` · Perfil isolado: `NIA_PLANOS_DIR` em
temp · Dados fictícios · Nenhuma alteração na pasta de dados do usuário.

## Ambiente e pré-testes

- Windows 11 (10.0.26200), Python 3.12.14, PyQt6 6.12.1, pytest 9.2.0.
- `QT_QPA_PLATFORM=offscreen`; `NIA_PLANOS_DIR` apontado para diretório temporário.
- Árvore limpa antes da homologação; 12 commits locais; nada enviado ou mesclado.
- Suíte antes de qualquer alteração: **334 testes passaram**. Nenhuma falha pré-existente.
- Abertura real: `python main.py` com perfil isolado iniciou dashboard, microfone e
  interface e foi encerrada após 12 s. Log mostrou tentativas de voz com HTTP 404
  nos modelos externos configurados — transcritor real não foi validado.

## Resultado por área

| Área | Status | Cenário executado | Evidência |
|---|---|---|---|
| Gerenciador de Planos | **Aprovado** (interface Qt + disco) | Criar, buscar por título/objetivo, renomear, arquivar, restaurar, recarregar após "reinício" | `tests/test_planos.py`, `tests/test_interface_planos.py`; ID preservado e última gravação válida |
| Canvas manual | **Aprovado** (interface Qt) | Cards/conexões, mover, progresso, zoom, excluir conectado, desfazer/refazer, câmera, dock/núcleo | `tests/test_canvas_mapa.py`, `tests/test_integracao_canvas.py` |
| Voz e texto | **Aprovado** com transcrição simulada | Criar/retomar, títulos parecidos, escolha por ordinal, reentrega, cancelamento, negação, pergunta informativa | `tests/test_comandos_planos.py`, `tests/test_habilidades_chat_voz.py` |
| Edição assistida | **Aprovado** (lógica + interface simulada) | "O que falta agora?" após conclusão manual, lote de 3 soluções, conflito em memória, troca de plano com resposta atrasada | `tests/test_assistencia_planos.py`, `tests/test_interface_assistida.py` |
| Cinco modelos | **Aprovado** (dados + interface Qt) | Estruturas locais, combinação de ramos, progresso por ramo, venda/divulgação separadas, finanças exatas | `tests/test_modelos_planos.py` |
| Lembretes | **Aprovado** (relógio simulado + interface Qt) | Agendamento por comando/card, vencimento único, adiar/concluir/cancelar, suspensão ao excluir/arquivar e restauração, abertura do card correto | `tests/test_lembretes.py`, `tests/test_interface_lembretes.py` |
| Privacidade/publicação | **Aprovado** com destino simulado | Card restrito, resumo derivado, anexo interno, segredo, prévia alterada, reenvio; saída real desativada | `tests/test_publicacao_segura.py`, `tests/test_assistencia_planos.py` |
| Persistência | **Aprovado** | Falha de escrita, conflito de revisão, arquivo inválido isolado, plano sem mapa, salvamento ao fechar | `tests/test_planos.py`, `tests/test_plano_mapa.py`, `tests/test_integracao_canvas.py` |
| Offline | **Aprovado** com rede bloqueada | Busca, edição, progresso, cálculos e lembretes sem `requests.get/post` | `tests/test_homologacao.py` (monkeypatch de rede) |
| Interface visual/desktop | **Pendente** | Abertura real foi `offscreen`; aparência do dock/núcleo não foi inspecionada em desktop | Smoke launch com log; sem captura visual |

## Correções realizadas

1. **Troca de plano com alterações pendentes perdia trabalho.** Em `_abrir_canvas_do_plano`,
   ao trocar de plano com mudanças não salvas, o editor era substituído sem salvar nem
   perguntar. Causa: ausência de guarda de pendência no ponto de entrada usado também por
   voz/lembretes. Correção: salvar antes da troca; se falhar, perguntar
   *Salvar e sair / Sair sem salvar / Cancelar*; Cancelar mantém o plano atual. Arquivo:
   `ui.py`. Verificação: `test_troca_de_plano_com_pendencia_nao_perde_trabalho` — RED antes,
   GREEN depois.
2. **Timer de autosave podia disparar depois da saída do Canvas.** O `QTimer` de 600 ms do
   `EditorMapa` permanecia agendado ao voltar ou ao carregar outro plano. Correção: parar o
   timer em `_voltar_dos_planos`, em `carregar()` e no caminho de troca. Arquivos: `ui.py`,
   `core/interface_mapa.py`. Verificação: `test_fechamento_do_canvas_nao_deixa_timer_de_autosave_ativo`.
3. Nenhuma remoção de código foi necessária; nenhuma função, sinal, atalho ou registro do
   dock foi retirado.

## Medições de desempenho

Condições idênticas antes/depois das correções não foram possíveis porque as correções
foram feitas durante a homologação; a medição abaixo é a versão final homologada.

- Ambiente: Windows 11, offscreen, Python 3.12.14 / PyQt6 6.12.1.
- Mapa: **41 cards e 40 conexões** (ramos de Produto), núcleo em repouso.
- Duração: 100 operações de pan/zoom com `processEvents()`; 10 ciclos abrir/fechar Canvas.
- Resultado: RSS 72,1 MB → 76,2 MB após pan/zoom → 79,5 MB após 10 ciclos.
- Tempo de 100 operações de pan/zoom: **0,936 s** (~9,4 ms por operação).
- Timers: 13 antes de abrir o Canvas, 14 após sair (o timer de autosave do editor reutilizado,
  parado); sem acréscimo por ciclo.
- Não foi possível medir CPU/memória com o núcleo falando nem em desktop com renderização
  real: o ambiente é offscreen e a voz tentou provedores externos sem sucesso (HTTP 404).

## Correção pós-homologação: posicionamento do núcleo (21/11/2026)

Problema relatado: ao abrir o Canvas, o núcleo nem sempre ficava no canto inferior direito.

Investigação (depuração sistemática, com instrumentação de `CanvasStage.arrange`):
- **Causa 1:** `_abrir_canvas_do_plano` chamava `set_anchor("bottom-right")` **antes** de
  esconder o card temporário (brief). Com brief visível, `arrange()` usa
  `_brief_geometries()`, que ignora a âncora e deixa o núcleo no canto direito
  centralizado (945,230 em vez de 957,461). Esconder o brief depois não disparava
  um novo `arrange()`.
- **Causa 2:** `CanvasEditor._reposicionar` reservava só ~18% da largura para o
  núcleo, mas ele ocupa até ~48% quando há cards/painéis — 324 px do mapa ficavam
  embaixo do núcleo.

Correção: esconder brief/resultados/HOJE/painéis e limpar `tools_open`/`chat_open`
**antes** de ancorar; ancorar e levantar o núcleo uma única vez; reservar a largura
real de `hud_stack` no overlay e acompanhar a animação via `valueChanged`.
Arquivos: `ui.py`, `core/interface_canvas_planos.py`.
Verificação: `tests/test_nucleo_canvas.py` (4 testes RED→GREEN) e diagnóstico com
quatro cenários — todos com `OK=True`, âncora `bottom-right` e sobreposição -17 px.
Suíte final: **342 testes passaram**; `compileall` e `git diff --check` limpos.

## Correção pós-homologação: criação por voz (21/11/2026)

Problema relatado: ao pedir a criação de um plano/produto/projeto por voz, a NIA
respondia só no chat e o Canvas não era aberto automaticamente.

Investigação: instrumentei `_executar_frase_habilidade`, `NiaUI.abrir_plano` e
`MainWindow._abrir_canvas_do_plano`. O reconhecimento e a abertura funcionavam no
caminho isolado — a causa da reclamação era que **`_aplicar_resultado_planos`
escrevia a resposta no chat, mas nunca a falava**. No Gemini Live, quando um
comando local é tratado, o bloco `turn_complete` esvazia `out_buf` e impede o
modelo de falar; o resultado era a pergunta ("Qual é o projeto?") visível apenas
no chat, sem áudio.

Correção:
- `main.py`: `_falar_resposta_comando(texto, origem)` aciona `_falar_local` em
  thread quando a origem é `voz`; `_aplicar_resultado_planos(resultado, origem)`
  passa a origem. A confirmação final ("Plano criado... Abrindo o Canvas")
  também é falada.
- `ui.py`: `NiaUI.abrir_plano` traz a janela para frente (`showNormal/raise/
  activateWindow`) após abrir o Canvas, para que a abertura por comando de voz
  fique visível sem clique do usuário.

Verificação: `tests/test_criacao_voz.py` (4 testes RED→GREEN): pergunta falada,
criação direta falada e abertura, abertura com janela em frente, texto sem
duplicar fala. Suíte final: **346 testes passaram**; `compileall` e
`git diff --check` limpos. TTS validado com `_falar_local` simulado — a síntese
real depende do motor de voz configurado.

## Pendências reais

| Pendência | Impacto | Motivo | Etapa de origem |
|---|---|---|---|
| Voz com microfone/STT reais | Não valida o reconhecimento real; comandos testados com transcrição final simulada | Sem dispositivo/transcritor configurado neste ambiente | Prompt 03 |
| Chamadas reais a API/Ollama | Não valida redação/resposta do provedor | Credenciais/serviço não disponíveis; smoke launch recebeu 404 | Prompts 04-06 |
| Entrega de notificações com NIA fechada | Avisos vencidos só aparecem na próxima abertura | Depende de integração com o sistema operacional | Prompt 06 |
| Nova integração de publicação | Saída do Canvas permanece desativada; bloqueios validados com destino simulado | Fora do escopo até esta versão | Prompt 06 |
| Inspeção visual do dock/núcleo e medição com núcleo falando | Não há confirmação visual em desktop nem perfil de CPU com fala real | Execução homologada em `offscreen` | Prompt 07 |
