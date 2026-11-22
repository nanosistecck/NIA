# Criterios de aceite e evidencias — rodada 3

| Requisito | Teste | Evidencia | Estado |
|---|---|---|---|
| Pedido sobre funcionamento gera cards uteis | `test_interacao_canvas_pedido.py` (14 testes) | 5 cards com titulos e descricoes locais, conectados ao central | OK |
| Frase real do usuario e reconhecida | `test_frase_real_e_reconhecida_como_funcionamento` | `CC.pedido_funcionamento_nia` True | OK |
| Espelho vazio nao descarta lote valido | `test_espelho_vazio_nao_descarta_lote_valido` | card aplicado; sem "O plano mudou" | OK |
| Plano realmente trocado ainda descarta | `test_plano_real_trocado_ainda_descarta` | mensagem de mudanca preservada | OK |
| "tenta fazer meu pedido" reprocessa | `test_retomada_reprocessa_ultimo_pedido` | `CH.reconhecer` nao chamado; cards criados | OK |
| Variantes de retomada reconhecidas | parametro com 5 frases | todas True | OK |
| Sem pedido anterior responde localmente | `test_retomada_sem_pedido_responde_localmente` | sem queda no cerebro comum | OK |
| Sem regressao das rodadas 1 e 2 | 196 tests da area | 196 passed | OK |
| Suite completa | `pytest -q` | **575 passed, 4 failed** (mesmas preexistentes) | OK |
| Sintaxe e diff | `compileall` / `git diff --check` | limpos | OK |

## Evidencia funcional e visual

- Antes: `diag_provedor2.py` reproduziu "SIS: O plano mudou desde o pedido;
  nada foi aplicado." e `diag_pedido.py` mostrou titulos crus e retomada caindo
  no cerebro comum.
- Depois (`%TEMP%\gerar_evidencia3.py`), com as frases exatas do usuario:
  - "vc consegue criar cards relacionados ao seu funcionamento e inserir nesse plano?" → OK;
  - "tenta fazer meu pedido" → OK;
  - titulos: Como a NIA funciona, Canvas Infinito, Planos e memória,
    Ferramentas e integrações, Evolução proposta;
  - verificacao automatica: `TEM "O plano mudou"? False`.
- Captura inspecionada: `logs/captura_interacao_canvas.png` (272.672 bytes),
  com o card central conectado aos cards de funcionamento da NIA.
- Ressalva: sem microfone, provedor real ou tela fisica. A interface e o Canvas
  foram executados de fato; provedor e voz foram simulados.
