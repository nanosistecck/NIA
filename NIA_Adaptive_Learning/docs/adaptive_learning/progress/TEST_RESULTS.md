# TEST_RESULTS

| Fase | Comando | Resultado | Evidência |
|---|---|---|---|
| F00 | `$env:QT_QPA_PLATFORM='offscreen'; .venv-apis\Scripts\python.exe -m pytest tests -q` | **1123 passed, exit 0**, 397,27 s | `baseline_pytest.log`, `baseline_exit.txt` |
| F01 RED | `pytest tests/test_learning_f01_contratos.py -q` | ModuleNotFoundError (esperado) | `f01_red.txt` |
| F01 GREEN | `pytest tests/test_learning_f01_contratos.py tests/test_learning_f01_adaptadores.py -q` | **10 passed, exit 0** | `f01_green2.txt` |
| F02 RED | `pytest tests/test_learning_f02_memoria.py -q` | ModuleNotFoundError (esperado) | `f02_red.txt` |
| F02 GREEN | `pytest tests/test_learning_f02_memoria.py -q` | **6 passed, exit 0** | `f02_green3.txt` |
| F03 | `pytest tests/test_learning_f03_pesquisa.py -q` | **5 passed** | `f03_green.txt` |
| F04 | `pytest tests/test_learning_f04_observacao.py -q` | **5 passed** | `f04_green.txt` |
| F05 | `pytest tests/test_learning_f05_workflows.py -q` | **6 passed** | `f05_green.txt` |
| F06 | `pytest tests/test_learning_f06_colaboracao.py -q` | **4 passed** | `f06_green2.txt` |
| F07 | `pytest tests/test_learning_f07_documentos.py -q` | **4 passed** | `f07_green.txt` |
| F08 | `pytest tests/test_learning_f08_orquestrador.py -q` | **5 passed** | `f08_green.txt` |
| F09 | `pytest tests/test_learning_f09_consolidacao.py -q` | **4 passed** | `f09_green2.txt` |
| F10 | `pytest tests/test_learning_f10_ui.py -q` | **2 passed** + captura inspecionada | `f10_green3.txt`, `logs/captura_central_aprendizado.png` |
| F11 | `pytest tests/test_learning_f11_integracao.py -q` | **3 passed** | `f11_green.txt` |
| F12 | `pytest tests/test_learning_f12_seguranca.py -q` | **5 passed** | `f12_green.txt` |
| F13 | `python NIA_Adaptive_Learning/medir_desempenho.py` | CPU 0,0%, RSS +~1,1 MB, p95 0,078 ms | `performance.json` |
| F14 | `pytest tests/test_learning_f14_recuperacao.py -q` | **2 passed** | `f14_green.txt` |
| E2E local | `pytest tests/test_learning_e2e_fluxo.py tests/test_learning_f05_workflows.py -q` | **7 passed** | `f14_e2e2.txt` |
| Regressão final | `pytest tests -q` | **1185 passed, exit 0**, 488,51 s | `full_regression_final.log`, `full_regression_final_exit.txt` |

Nenhum teste físico, de rede ou com credenciais foi executado.
