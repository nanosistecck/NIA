# Criterios de aceite e evidencias — rodada 10

| Requisito | Teste | Evidencia | Estado |
|---|---|---|---|
| "abra o youtube..." nao e ABRIR | `tests/test_contexto_acao_pc.py` (11 testes) | `CP.reconhecer` → NENHUMA | OK |
| Apps/sites nao viram plano | parametro com 6 frases | todas NENHUMA | OK |
| Abre plano por nome preservado | parametro com 3 frases | todas ABRIR | OK |
| Retomar/gerenciador preservados | `test_retomar_e_gerenciador_preservados` | RETOMAR / GERENCIADOR | OK |
| Frase chega na habilidade | `test_frase_de_pc_chega_na_habilidade_e_nao_lista_planos` | `CH.reconhecer` chamado | OK |
| Nao lista planos | mesmo teste | nenhum "Encontrei vários planos" | OK |
| Suite completa | `pytest -q` | **654 passed, 0 failed** | OK |
| Sintaxe e diff | `compileall` / `git diff --check` | limpos | OK |

## Evidencia funcional (frase exata do relato)

```
CP.reconhecer: NENHUMA
roteado: True
habilidade chamada: True
log: SIS: Tocando música no YouTube
listou planos? False
```

Ressalva: habilidade executada com stub (sem abrir o YouTube de verdade).
