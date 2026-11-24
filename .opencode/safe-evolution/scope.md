# Escopo — rodada 14 (frase real de criacao na Agenda)

## Solicitado
Corrigir "adicione na agenda buscar a maria as 21:06", que caiu no Canvas.

## Causas
1. `processar` exige termo de tipo; "adicione na agenda" nao casa.
2. `interpretar` sem data devolve None mesmo com hora explicita.

## Correcoes
1. Reconhecer "adicione na agenda/à agenda/minha agenda" como criacao, com
   titulo extrativo do resto da frase.
2. Inferir data quando ha hora mas nao ha data: hoje se a hora for futura,
   amanha se ja passou. Sem hora continua perguntando.

## Preservado
Criacao de card no Canvas, demais comandos da Agenda e rota de plano.

## Plano
- [x] Diagnosticar e reproduzir
- [x] Testes RED
- [x] Corrigir parser e interpretar
- [x] Suite completa e evidencia

## Resultado
- 6 testes novos; suite **730 passed, 0 failed** (duas execucoes).
- Frase real verificada na NIA: cria e fala do proximo compromisso.
