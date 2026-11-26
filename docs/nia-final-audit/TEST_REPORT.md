# Relatório final de testes (atualizado)

Comando | Exit | Resultado | Evidência
`pytest tests -q` | 0 | **1036 passed, 0 failed** em 310,25 s | `docs/nia-final-audit/MODO_LIVRE_FINAL_PYTEST.log`
`pytest tests/test_modo_livre.py -q` | 0 | 5 passed | saída do shell
`pytest tests/test_preflight.py -q --durations=3` | 0 | 7 passed; preflight 0,08 s | saída do shell
`compileall` / `git diff --check` | 0 | limpos | saída do shell
