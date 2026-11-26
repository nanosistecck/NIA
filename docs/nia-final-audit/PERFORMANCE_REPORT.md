# Relatório de desempenho

## Referências
- Baseline Fase 01: import do núcleo 0,49–1,10 s; ΔRSS 16,5–16,6 MB; CPU ociosa 0,0%.
- Baseline desta auditoria: `pytest tests -q` 1005 passed em 350,24 s (não é benchmark de boot).
- Sonda atual `perf_probe.py`: import 0,4527 s; ΔRSS 16,78 MB; CPU 0,0%; 0 falhas.
- Sonda `boot_probe.py` (MainWindow offscreen): import 0,35–0,50 s,
  construção 0,25–0,48 s, RSS +56 MB.
- Sonda `nia_live_boot_probe.py`: construção de `NiaLive` 0,014–0,015 s,
  ΔRSS 0,25–0,30 MB, 0 threads novas.
- Preflight: executado em < 2 s por teste; determinístico e sem rede.

## Interpretação
Sem regressão relevante de CPU/RAM em repouso. O custo aditivo de módulos novos
é zero em repouso porque não são importados por `main`/`ui` no caminho padrão,
com exceção do gateway/preflight, que são leves e lazy.

## Limitações
Não medido: boot com provedor real, microfone, câmera, DPI físico e carga
sustentada. Nenhum benchmark foi inventado.
