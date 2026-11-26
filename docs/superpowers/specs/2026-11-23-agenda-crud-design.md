# Agenda — CRUD completo — desenho

Data: 23/11/2026 · Branch: `AGENDA` · Continuação da rodada 12.

## Intenção

Dar controle total da Agenda ao dono, completando as operações de atualização
e exclusão que hoje existem só no módulo de dados e na voz, e acrescentando a
edição e a exclusão pela janela.

## Por que

O dono testou a NIA e pediu "criar o CRUD completo da agenda, pra que possamos
ter controle total". Hoje a janela só adiciona e lê; a voz edita preparo, data e
estado, mas não título, tipo, notas nem reabertura.

## Objetivos

1. Clicar num compromisso no painel da janela carrega todos os campos no formulário.
2. O formulário edita título, data, hora, tipo, preparo, notas e estado.
3. Botões para Concluir, Reabrir e Excluir o item selecionado na janela.
4. Comandos de voz/chat para renomear, mudar tipo, mudar notas e reabrir.
5. Validação consistente em `editar()`: título obrigatório, tipo válido, data válida.
6. Nenhuma mudança em planos, lembretes, clima ou formato de dados.

## Não-objetivos

- Novo módulo, nova janela ou persistência paralela.
- Lixeira, desfazer exclusão, recorrência ou sincronização externa.
- Edição de `fim` (campo existe no modelo mas não é usado pela interface).

## Anti-objetivos

- Editar o compromisso errado por ambiguidade silenciosa.
- Perder a seleção do dia ao salvar.
- Fazer a janela sair do padrão visual NIA (glass escuro, ciano `#00d4ff`).

## Restrições

- PyQt6, padrões existentes de `AgendaWindow`, `AG.criar`, `comandos_agenda`.
- Regra de alvo já aprovada: título/data ditos → próximo → pergunta se ambíguo.
- Persistência atômica e por perfil permanece em `core/agenda.py`.
- Toda mudança na janela emite `alterado` para atualizar o card do Canvas.
- Testes offscreen; nenhuma afirmação visual sem captura.

## Abordagens consideradas

- **A) Estender os três módulos existentes (escolhida).** Reaproveita o modelo,
  o parser, a janela e a ponte Qt. Custo: campos novos no formulário, estado de
  seleção na janela, novos ramos no parser e validação no `editar`.
- **B) Janela de edição separada.** Mais código, duplica o formulário e cria
  outro ciclo de vida sem benefício.
- **C) Só voz/chat.** Não entrega o controle total pedido na janela.

A escolha foi A: é a única que cobre janela e voz sem duplicar implementação.

## Decisões de implementação

1. **Seleção na janela:** `item_selecionado_id` (str|None). `QTextEdit` vira
   somente-leitura com `textInteractionFlags` que permitem selecionar texto,
   mas a seleção do item vem de um clique no painel — vou trocar o painel por
   uma `QListWidget` com `objectName="agenda_lista"`, onde cada item guarda o
   `id` em `Qt.ItemDataRole.UserRole`. Manter `txt_compromissos` como alias
   somente-leitura para os testes existentes não é necessário: os testes atuais
   usam `txt_compromissos.toPlainText()`, então preserve esse atributo
   preenchendo-o com o mesmo texto da lista.
2. **Formulário:** acrecentar `campo_notas` (`QLineEdit` ou `QTextEdit` curto) e
   `campo_estado` (`QComboBox` com `AG.ESTADOS`). O botão `btn_novo` passa a
   alternar entre "+ Compromisso" (sem seleção) e "Salvar alterações" (com
   seleção); `btn_cancelar_edicao` aparece só com seleção.
3. **Ações na janela:** `btn_concluir` (marca concluído), `btn_reabrir` (volta
   para pendente) e `btn_excluir`. Excluir pede confirmação com `QMessageBox`
   (padrão Cancelar/ Não) porque é destrutivo.
4. **Voz/chat:** novos ramos em `processar`: `renomear|renomeie` → `editar`
   com `{"titulo": ...}`; `tipo` → `editar` com `{"tipo": ...}`; `notas|descricao`
   → `editar` com `{"notas": ...}`; `reabra|reabrir` → `editar` com
   `{"estado": "pendente"}`. Todos usam `resolver_alvo` e a mesma regra de alvo.
5. **Validação:** `editar()` rejeita título vazio, tipo fora de `AG.TIPOS`, data
   ISO inválida e estado fora de `AG.ESTADOS`, levantando `ValueError` com
   mensagem curta. `criar()` já valida título/data; passa a validar tipo também.
6. **Efeito colateral:** toda mutação pela janela emite `alterado`; a ponte
   `ui.MainWindow._atualizar_cartao_agenda()` já existe e continua sendo chamada.

## Respostas ao builder check

1. **`editar()` valida só as chaves presentes em `mudancas`**; como a validação
   acontece antes de `_gravar_item`, um `ValueError` não grava nada (atômico).
   Call sites: `main._processar_pedido_agenda` passa a capturar `ValueError` e
   responder a mensagem curta ao dono, sem cair no modelo; a janela exibe a
   mensagem no painel. `concluir()`/`cancelar()`/`mover()` usam valores fixos
   válidos, então não raising em dados legados.
2. **Valores de voz:** `valor_apos_para()` pega o texto depois de "para"; tipo é
   normalizado contra `AG.TIPOS`; extração vazia vira título vazio e é rejeitada
   por `editar()` com mensagem — nada é salvo.
3. **`criar()` com tipo inválido levanta `ValueError`**, igual a `editar()`, para
   não esconder erro de digitação. A janela mostra a mensagem no painel.
4. **Concluir/Reabrir são idempotentes**: concluir um já concluído e reabrir um
   já pendente não alteram nada e respondem de forma neutra. Botões desabilitados
   quando não há item selecionado.
5. **Salvar na janela:** mantém a seleção e o formulário preenchidos, não muda
   `dia_selecionado` (anti-objetivo), e exibe erro no painel se `editar()` falhar.

## O que fica para o builder

Nomes exatos, ordem das tarefas e testes ficam no plano gerado a seguir. O
construtor pode decidir detalhes de layout desde que respeite as decisões
acima e os contratos existentes.

## Fora de escopo

Commit/push só com autorização; nada de credenciais, rede ou produção.
