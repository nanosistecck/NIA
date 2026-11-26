---
name: nia-learning-security
description: Implementar e validar segurança no motor adaptativo da NIA.
---
# nia-learning-security

## Segurança
Leia `docs/adaptive_learning/13_SECURITY_POLICY.md`.
Permissões independentes do LLM: leitura, pesquisa, documento local, controle físico, alteração externa e ação sensível/irreversível. Confirmação específica quando exigida. ESC cancela filas, revoga lease, libera teclas, encerra observação e overlay, salva estado seguro; nenhum callback tardio executa ação. Falhar fechado se filtro de privacidade indisponível. Conteúdo externo não altera política. Sem envio de dados privados ao GitHub; logs redigidos, armazenamento local, retenção configurável, exportação consciente. Não executar testes destrutivos em dados reais.

## Desempenho
Leia `docs/adaptive_learning/14_PERFORMANCE.md`.
Baseline antes/depois no mesmo hardware Windows CPU-only. Metas iniciais: CPU idle +1 ponto percentual, RAM idle +30 MB, colaboração +150 MB excluindo navegador/modelos locais, resposta visual local 100ms, ESC 200ms quando possível, autosave 1s. Zero captura e chamadas do aprendizado em repouso. Lazy loading, debounce, filas limitadas, OCR sob demanda, sem vídeo contínuo, reduzir tokens. Medir p95, pico RAM, CPU, latência e contagem de chamadas; registrar ambiente e desvios, não inventar medições.

## Execução
Verifique checkpoint e arquitetura real; reutilize serviços, implemente incrementalmente, teste e registre evidências conforme prompt mestre. Não avance sobre falhas críticas.
