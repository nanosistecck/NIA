# Mapa de impacto

| Modulo/arquivo | Contrato existente | Mudanca necessaria | Risco | Teste de compatibilidade |
|---|---|---|---|---|
| `core/comandos_planos.py` | `reconhecer` classifica CRIAR/ABRIR/FECHAR/etc. | Nao classificar criacao de card como CRIAR; adicionar LISTAR_PLANOS e "gerenciar planos" | Medio: pode deixar de criar planos legitimos | `tests/test_comandos_planos.py`, `tests/test_criacao_voz.py` |
| `core/controle_canvas.py` | `pedido_controle` resolve comandos locais | Parser de criacao de card(s), ideias e rotulo de conexao | Medio: titulos/ops errados | `tests/test_controle_canvas.py`, novo teste de gramatica |
| `core/assistencia_planos.py` | `intencao_para_lote` chama controle/estruturado | Nenhuma mudanca de contrato; usa os novos comandos locais | Baixo | `tests/test_edicao_assistida_revisao.py` |
| `main.py` | `_executar_frase_habilidade` roteia navegacao vs Canvas | Mensagem clara sem plano; manter autorizacao e provedor | Baixo | `tests/test_simulacao_controle_canvas.py` |
| `ui.py` | Ponte Qt `aplicar_lote_assistido` | Sem mudanca | Nenhum | Testes existentes |
| `.opencode/safe-evolution/*.md` | Estado persistente | Registrar baseline, escopo, impacto e evidencias | Nenhum | Revisao manual |
