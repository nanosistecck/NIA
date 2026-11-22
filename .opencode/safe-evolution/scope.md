# Escopo e requisitos

## Ideia solicitada
Deixar o sistema de Planos e o Canvas Infinito completamente controlaveis pela NIA
(chat e voz), sem confundir criacao de card com criacao de plano, cobrindo criacao,
edicao e organizacao de cards/ideias e o contexto de gerenciamento de planos.

## Funcionalidades existentes a preservar
- Criacao de plano por linguagem natural (`CRIAR`) e perguntas pendentes.
- Abertura/fechamento do Canvas, Gerenciador de Planos e consulta do plano atual.
- Edicao assistida com autorizacao (`Editar com a NIA`), lotes atomicos e undo/redo.
- Operacoes estruturadas: criar/editar/mover/excluir card, conectar/desconectar,
  progresso, anexar texto, editar plano, zoom, enquadrar, centralizar, salvar,
  detalhes, grade e selecionar card.
- Filtro de contexto externo e descarte de respostas atrasadas.

## Requisitos novos e criterios de aceite
1. "criar um novo card", "criar um card" e "quero criar um card" NAO criam plano;
   criam card no plano aberto.
2. Criacao local de card com titulo explicito (`chamado/com titulo`), topico
   (`sobre/para/de`), tipo, status, descricao, posicao e conexao opcional.
3. Criacao de varios cards em um unico lote quando o pedido nomeia uma lista.
4. "com ideias sobre/para X" cria o card com titulo significativo e descricao
   inicial; ideias podem ser anexadas por comando local.
5. Comando local para anexar ideias a um card nomeado.
6. Comando local para renomear o rotulo de uma conexao.
7. Contexto de gerenciamento: listar planos, abrir/fechar/criar plano e abrir o
   gerenciador continuam distintos de criar card.
8. Sem plano aberto, pedido de card responde "abra um plano" e nao pergunta
   "qual plano" para criar outro plano.
9. Testes automatizados cobrem chat e voz; nenhuma regressao nos 63 testes atuais.

## Fora de escopo
- Arquivar/restaurar/excluir planos por voz (operacao destrutiva; exige etapa propria).
- Criar card em plano diferente do aberto sem abrir o plano.
- Validacao com provedor real, STT real ou deploy.
- Alterar formato de dados, migrar planos ou tocar em credenciais.

## Plano sequencial
- [x] Diagnosticar arquitetura e baseline
- [x] Mapear dependencias e pontos de integracao
- [x] Escrever testes RED para roteamento e gramatica de cards
- [x] Implementar correcao de intencao e gramatica local
- [x] Implementar contexto de gerenciamento (listar planos)
- [x] Executar testes de regressao e revisar diferencas
- [x] Capturar evidencia offscreen e entregar relatorio
