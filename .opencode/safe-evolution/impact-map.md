# Mapa de impacto — rodada 2

| Modulo/arquivo | Contrato existente | Mudanca necessaria | Risco | Teste de compatibilidade |
|---|---|---|---|---|
| `core/assistencia_planos.py` | Intenções e contexto do Canvas | Adicionar `conversa_sobre_plano`, `resumo_conversa_plano` e `resumo_lote` | Medio: reconhecedor pode capturar hora/clima | `tests/test_prioridade_conversa_plano.py` |
| `main.py` | `_executar_frase_habilidade` decide rota local x ferramenta | Responder pelo plano antes de `CH.reconhecer` | Medio: pode roubar comandos de sistema | testes de rota + suíte de habilidades |
| `ui.py` | `aplicar_lote_assistido` informa IDs e títulos crus | Usar `resumo_lote` com títulos e limite | Baixo | testes existentes exigem "concluída" |
| `tests/test_prioridade_conversa_plano.py` | — | Novo arquivo RED→GREEN | Nenhum | — |
