# Concorrência

UI PyQt6 na thread principal; workers/async conforme arquitetura. Prioridades emergência 100, comando 90, voz 80, controle 70, documento 60, pesquisa 40, consolidação 20; evitar starvation. Até três pesquisas concorrentes inicialmente, filas limitadas, timeout, cancel tokens e geração de cancelamento. Resultados atrasados descartados. Pesquisa interna sem roubar foco, mouse ou teclado; apresentar resultados com fonte. Encerrar workers e liberar recursos.

## Gate
Registrar implementação real, caminhos, testes, evidências, limitações e próximo passo no diretório progress. Não marcar concluído sem verificação.
