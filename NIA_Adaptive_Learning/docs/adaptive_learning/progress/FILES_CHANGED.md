# FILES_CHANGED

| Caminho | Ação | Motivo | Teste |
|---|---|---|---|
| `NIA_Adaptive_Learning/docs/adaptive_learning/progress/PROJECT_MAP.md` | preenchido | F00: mapa real e classificação | leitura |
| `NIA_Adaptive_Learning/docs/adaptive_learning/progress/baseline_pytest.log` | criado | baseline 1123 passed | exit 0 |
| `core/aprendizado_adaptativo/__init__.py` | criado | pacote da camada adaptativa | import |
| `core/aprendizado_adaptativo/contratos.py` | criado | eventos/estados/cancelamento F01 | test_learning_f01_contratos |
| `core/aprendizado_adaptativo/avaliador.py` | criado | avaliação baseada em evidência | test_learning_f01_contratos |
| `core/aprendizado_adaptativo/adaptadores.py` | criado | reuso de `core.aprendizado` | test_learning_f01_adaptadores |
| `tests/test_learning_f01_contratos.py` | criado | RED→GREEN F01 | 8 passed |
| `tests/test_learning_f01_adaptadores.py` | criado | integração real F01 | 2 passed |
| `core/aprendizado_adaptativo/memoria.py` | criado | persistência procedural F02 | test_learning_f02_memoria |
| `tests/test_learning_f02_memoria.py` | criado | RED→GREEN F02 | 6 passed |
| `core/aprendizado_adaptativo/pesquisa.py` | criado | pesquisa autônoma F03 | test_learning_f03_pesquisa |
| `core/aprendizado_adaptativo/observacao.py` | criado | observação autorizada F04 | test_learning_f04_observacao |
| `core/aprendizado_adaptativo/workflows.py` | criado | procedimentos F05 | test_learning_f05_workflows |
| `core/aprendizado_adaptativo/colaboracao.py` | criado | sessões F06 | test_learning_f06_colaboracao |
| `core/aprendizado_adaptativo/documentos.py` | criado | documentos F07 | test_learning_f07_documentos |
| `core/aprendizado_adaptativo/orquestrador.py` | criado | filas F08 | test_learning_f08_orquestrador |
| `core/aprendizado_adaptativo/consolidacao.py` | criado | consolidação F09 | test_learning_f09_consolidacao |
| `core/aprendizado_adaptativo/ui.py` | criado | painel real F10 | test_learning_f10_ui |
| `core/aprendizado_adaptativo/integracao.py` | criado | catálogo/SDK F11 | test_learning_f11_integracao |
| `core/aprendizado_adaptativo/seguranca.py` | criado | política F12 | test_learning_f12_seguranca |
| `ui.py` | modificado | registrar janela `aprendizado` no GerenciadorJanelas | test_learning_f11_integracao |
| `core/registro_nativo.py` | modificado | descritor da Central | test_learning_f11_integracao |
| `main.py` | modificado | registrar capacidades no catálogo no boot | test_learning_f11_integracao |
| `core/aprendizado_adaptativo/recuperacao.py` | criado | restauração segura F14 | test_learning_f14_recuperacao |
| `NIA_Adaptive_Learning/medir_desempenho.py` | criado | medição F13 | performance.json |
