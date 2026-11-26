# Desempenho

Baseline antes/depois no mesmo hardware Windows CPU-only. Metas iniciais: CPU idle +1 ponto percentual, RAM idle +30 MB, colaboração +150 MB excluindo navegador/modelos locais, resposta visual local 100ms, ESC 200ms quando possível, autosave 1s. Zero captura e chamadas do aprendizado em repouso. Lazy loading, debounce, filas limitadas, OCR sob demanda, sem vídeo contínuo, reduzir tokens. Medir p95, pico RAM, CPU, latência e contagem de chamadas; registrar ambiente e desvios, não inventar medições.

## Gate
Registrar implementação real, caminhos, testes, evidências, limitações e próximo passo no diretório progress. Não marcar concluído sem verificação.
