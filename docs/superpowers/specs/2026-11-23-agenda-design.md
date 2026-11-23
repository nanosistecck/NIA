# Agenda da NIA — desenho

Data: 23/11/2026 · Branch: `AGENDA` · Projeto: aplicação nova, integrada ao dock e ao Canvas principal.

## Intenção

O dono quer uma Agenda dentro da NIA para registrar compromissos, tarefas e
prazos com data e hora, tanto manualmente quanto por conversa. A NIA deve ter
controle total sobre ela e lembrar do próximo compromisso na abertura, quando
perguntado e no "bom dia". Um card no **Canvas principal** (o da janela inicial,
onde aparecem clima e horas — não o Canvas dos planos) mostra o próximo
compromisso e pode ser fechado pelo usuário.

## Por que

Hoje existem apenas lembretes atrelados a planos do Canvas (`core/lembretes.py`),
que não cobrem compromissos gerais e não oferecem calendário nem acompanhamento.
A Agenda precisa ser independente, visualmente familiar (grade mensal estilo
Google Calendar) e encaixar na identidade da NIA.

## Objetivos

1. Janela Agenda com grade mensal, navegação de mês, painel do dia e formulário
   de compromisso, com a identidade visual da NIA.
2. Botão AGENDA no dock, ao lado de PLANOS/GLOBO.
3. Persistência própria, atômica, fora do repositório e isolada por perfil.
4. Comandos de chat/voz para criar, editar, mover, concluir, cancelar, listar e
   perguntar o próximo compromisso.
5. Lembrete contextual na abertura, no "bom dia" e sob demanda.
6. Card "Próximo compromisso" no Canvas principal com botão × de fechar.

## Não-objetivos

- Sincronizar com Google Calendar, Outlook ou qualquer serviço externo.
- Notificações do sistema operacional em segundo plano.
- Recorrência, convites, participantes ou anexos.
- Alterar formato de planos ou lembretes existentes.

## Anti-objetivos (o que seria uma falha)

- Compromisso sem data/hora executável.
- O card aparecer no Canvas dos planos em vez do Canvas principal.
- A NIA inventar horário quando o usuário não deu — ela deve perguntar o que falta.
- Perder a preferência de fechamento do card ao reiniciar.

## Restrições

- PyQt6, padrões existentes de `CanvasStage` (`hoje_host`, `brief_host`),
  `VerticalDock` e janelas `QWidget` com `pyqtSignal`.
- Dados do dona ficam fora do Git: mesma estratégia de `core/resumo_dia.py`
  (`~/.nia/agenda.json`, override por `NIA_AGENDA`, chave por perfil).
-thread de UI: ponte `NiaUI` usa sinais/`QTimer`, nunca chamada direta a widget.
- Nenhuma rede, chave ou dependência nova.

## Abordagens consideradas

- **A) Módulo próprio (escolhida).** `core/agenda.py` + `core/interface_agenda.py`
  + `core/comandos_agenda.py` + card novo no Canvas principal + integração
  pontual em `main.py` e `ui.py`. Não toca em planos nem lembretes. Custo: um
  módulo de dados, uma janela e três pontos de integração.
- **B) Estender `core/lembretes.py`.** Reaproveitaria código, mas prenderia a
  agenda ao plano aberto e mudaria o contrato dos lembretes — risco de regressão.
- **C) Lista simples no JSON de config.** Barato, mas não entrega calendário nem
  controle conversacional como pedido.

A escolha foi A pelo isolamento: o que já funciona continua funcionando.

## Decisões de implementação (chamadas do construtor)

1. **Registro:** `{id, titulo, inicio, fim?, tipo, preparo_minutos, estado,
   notas, criado_em, atualizado_em}`. `inicio`/`fim` em ISO com offset. Estados:
   `pendente`, `concluido`, `cancelado`. Campos `plano_id`/`card_id` foram
   removidos: a Agenda é independente de planos e eles não teriam uso (decisão
   do construtor após revisão).
2. **Preparo:** sugestão automática por tipo — reunião/chamada 15 min,
   tarefa/entrega 30 min, viagem 60 min, aniversário 120 min, outro 30 min —
   editável no formulário. Exibição: "preparar às HH:MM".
3. **Próximo compromisso:** menor `inicio` futuro entre os pendentes. Se o
   pedido não trouxer data/hora, a NIA pergunta o que falta (como em lembrete).
4. **Janela:** `AgendaWindow(QWidget)` com sinais `fechada` e `alterado`; grade
   mensal (`QGridLayout`, um botão por dia com marcador), cabeçalho `‹ Mês Ano ›`,
   botão `+ Compromisso`, painel do dia selecionado e formulário. Estilo: fundo
   escuro em gradiente estático, bordas 1 px, foco 2 px em `#00d4ff`, cantos
   arredondados, mesma família tipográfica de `canvas_brief.py`.
5. **Dock:** `_agenda_btn` em `ui._build_dock`, `objectName="agenda"`, clique em
   `MainWindow._abrir_agenda`, que cria/remostra a janela como `_abrir_planos`.
6. **Card:** `CanvasStage.agenda_host` abaixo de `hoje_host`, mesmo padrão de
   largura/altura e botão × com `objectName="AgendaFechar"`; sinal
   `agenda_visibilidade`; preferência `cards.agenda` em `interface.json` com
   padrão visível. Só aparece quando houver próximo compromisso. **Reexibição**
   (decisão do construtor): segue o mesmo molde do Hoje — checkbox
   `agenda_visivel_check` em `core/config_dashboard.py` (Aparência) e comando
   de chat/voz "mostrar card da agenda" reabilitam o card. Fechar não apaga o
   compromisso.
7. **Comandos:** `core/comandos_agenda.py` puro, no molde de
   `comandos_lembretes.py`, devolvendo ações; `main._processar_pedido_agenda`
   chama antes da prioridade de conversa sobre plano para não ser capturado.
   **Alvo sem ID (decisão do dono):** casar por título e/ou data ditos; se o
   pedido não trouxer referência, usar o próximo compromisso pendente; se mais
   de um casar com o mesmo nome, a NIA pergunta qual antes de alterar. Nunca
   mexer em vários de uma vez.
8. **Lembrete na abertura e no "bom dia" (já pedido pelo dono):** nova intenção
   em `core/comandos_agenda.py` para saudação do dono ("bom dia", "bom dia NIA")
   e helper único `agenda.resumo_proximo()` usado por `_saudar_na_abertura`, pelo
   "bom dia" e por "qual o próximo compromisso?". A fala é uma frase curta
   acrescentada, não um resumo novo de dia. Respeita mudo, segundo plano e
   interrupção.
9. **Evidência:** capturas offscreen da janela e do Canvas principal são
   obrigatórias antes de afirmar validação visual; a interface será executada.

## Aprovação

- Play back aprovado pelo dono em 23/11/2026, com as correções: card no Canvas
  principal e calendário estilo Google, mais moderno, com data/hora e preparo.
- Builder check executado; quatro perguntas resolvidas: três como decisões do
  construtor (reexibição do card, handler do "bom dia", campos vestigiais
  removidos) e uma pelo dono (regra de alvo dos comandos, acima).

## O que fica para o builder

- Nomes exatos de funções/objetos, ordem das tarefas e testes ficam no plano
  gerado a seguir. O construtor pode decidir detalhes de layout e mensagens
  desde que respeite as decisões acima e os contratos existentes.

## Fora de escopo nesta rodada

Commit/push só após aprovação do dono; nada de credenciais, rede ou produção.
