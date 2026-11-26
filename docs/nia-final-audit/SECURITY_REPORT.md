# Relatório de segurança

## Varredura estática (2026-11-26)
- 274 arquivos Python analisados por AST; **0 erros de sintaxe**.
- `eval(`: 1 ocorrência, apenas em comentário (`actions/desktop.py:129`).
- `exec(compile(...))`: 1 ocorrência real em `actions/desktop.py:91`, com
  `sandbox` de builtins limitados; ferramentas que a acionam passam por
  `permissoes_ferramentas` e exigem confirmação. Risco residual documentado.
- `shell=True`: 9 ocorrências em ferramentas privilegiadas
  (`computer_settings`, `cowork`, `dev_agent`, `open_app`, `dashboard/server`),
  todas em código existente com política de permissão; nenhuma alteração.
- `pickle.load`, `yaml.load`, `os.system`: 0 ocorrências.
- Literais de credencial: 9 ocorrências, todas em testes com valores fictícios
  (`ficticia`, `segredo-de-teste`). Nenhuma credencial real em código/estado.
- 40 ferramentas declaradas em `TOOL_DECLARATIONS`; 41 escopos em
  `ESCOPOS_LEGADOS` (extra: `executar_comando`); nenhuma ferramenta declarada
  sem política e nenhuma sem referência no corpo de `main.py`.
- 109 marcações TODO/FIXME/XXX (comentários), não tratadas como falha sem
  comprovação de funcionalidade ausente.

## Testes negativos existentes
`test_politica_confianca.py`, `test_permissoes_legadas.py`, `test_niateck.py`,
`test_gateway_integrado.py`, `test_prontidao_niateck.py`: origem negada,
segredo em argumentos, travessia, ZIP malicioso, IPC e assinatura pendente.

## Limitações
Nenhuma credencial real, rede externa, dispositivo ou produção foi acessado.
Injeção de prompt em conteúdo externo é mitigada por regras existentes, sem
validação com provedor real nesta auditoria.

## Correção de compatibilidade com segurança
`core/entrada_uinput.py` agora importa `fcntl` condicionalmente e
`disponivel()` exige `fcntl is not None`. Nenhuma permissão foi relaxada;
o módulo continua inerte fora do Linux.
