# Escopo e requisitos — rodada 3 (interação completa com o Canvas)

## Ideia solicitada
Corrigir "O plano mudou desde o pedido; nada foi aplicado." e a resposta
generica a "tenta fazer meu pedido", para que a NIA crie e planeje qualquer
coisa no Canvas, inclusive cards sobre o proprio funcionamento.

## Funcionalidades existentes a preservar
- Rodadas 1 e 2: criacao de cards/ideias, prioridade da conversa e resumo sem IDs.
- Descarte de resposta atrasada quando o plano realmente troca ou e editado a mao.
- Autorizacao explicita do modo "Editar com a NIA" e lotes atomicos.
- Comandos de sistema fora do Canvas.

## Requisitos novos e criterios de aceite
1. Pedido generativo sobre o funcionamento da NIA cria cards uteis no plano,
   com titulos e descricoes locais, conectados ao card central/selecionado.
2. Se o espelho de contexto estiver vazio mas o editor real mostrar o mesmo
   plano, o lote e aplicado (nao ha falso "plano mudou").
3. Se o plano realmente trocar, o descarte continua (regressao preservada).
4. "tenta fazer meu pedido"/"faz de novo"/"repete" reprocessa o ultimo pedido
   do Canvas no mesmo plano e sessao, em ate 5 minutos.
5. Sem pedido anterior, a frase de retomada pede o pedido explicitamente.
6. Testes cobrem os tres pontos e a rota real; sem regressao nas rodadas anteriores.

## Fora de escopo
- Provedor real, microfone, rede ou deploy.
- Arquivar/excluir planos por voz.
- Alterar formato de dados ou credenciais.

## Plano sequencial
- [x] Reproduzir e diagnosticar as tres causas
- [x] Escrever testes RED
- [x] Implementar conteudo local sobre a NIA
- [x] Corrigir a ponte de contexto pos-provedor
- [x] Implementar memoria do ultimo pedido e retomada
- [x] Executar regressao e capturar evidencia
