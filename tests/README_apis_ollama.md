# Regressão de APIs e Ollama

Implementação na branch `multi-provedores`. A suíte usa somente credenciais fictícias,
SQLite e JSON temporários, rede simulada e Qt em modo offscreen. As verificações
reais são separadas da suíte e estão registradas ao final deste documento.

## Resolução e compatibilidade

- Credenciais: SQLite primeiro; chaves adicionais de `llm_routing.json` depois;
  `api_keys.json` como recurso legado. Uma identidade presente no SQLite não pode
  ser reintroduzida pelos JSON, inclusive quando está pausada, pendente ou em
  cooldown. A exclusão/substituição guarda apenas o hash da identidade bloqueada.
  Recadastro explícito ou reteste conclusivo da entrada existente permite recuperação.
- Conversa sem nova preferência: preserva a escada efetiva do checkout,
  Codex → Gemini → OpenAI → genéricos. Genéricos configurados como preferidos
  continuam antes do Codex. Estratégias, ranks, padrões, apelidos e estatísticas
  existentes permanecem nos formatos anteriores.
- Texto longo/comandos: preserva as escadas próprias do checkout. Os motores
  nativos Gemini/OpenAI continuam com seus modelos próprios; o formulário informa
  que uma preferência de modelo externo não muda esses modelos nativos.
- Voz e consumidores com endpoint fixo: continuam usando `resolver()`, que não
  entrega segredos vinculados a outro endpoint. Clientes que aceitam URL e modelo
  usam a conexão completa. A renovação de credenciais de voz ocorre antes de novas
  chamadas; uma sessão Gemini persistente é fechada quando sua chave muda.
- Ativação local: `conversation_provider=ollama` é uma escolha explícita nova.
  O modelo instalado e a URL são persistidos de forma aditiva e atômica. A conversa
  usa Ollama; falha local não autoriza a escada externa. O botão de preferência
  externa exige confirmação. Configurações antigas sem essa preferência mantêm
  seu comportamento. Geração e streaming consultam o modelo persistido.

## Comportamentos intencionais

- Chaves novas com teste inconclusivo ficam pendentes, fora da seleção automática.
  Gemini, OpenAI e Groq usam seus catálogos autenticados. OpenRouter usa `/key`
  para autenticação, separadamente de `/models`. Para outros endpoints compatíveis,
  compara-se a resposta autenticada com uma consulta sem autenticação. Um catálogo
  público não comprova a validade da chave. Integrações legadas não são desativadas
  por teste inconclusivo.
- HTTP e códigos do corpo são interpretados em conjunto: credencial recusada é
  **Inválido**; autenticação confirmada é **Validado**; falta de créditos/cota é
  **Esgotado**. Rate limit é **Limite temporário**. Rede, timeout, bloqueio de acesso
  ou falta de permissão não são confundidos com chave inválida. O diagnóstico
  armazena data, HTTP, código normalizado e mensagem segura; pausa é independente.
- O catálogo é descoberto por conexão, com paginação limitada a 50 páginas e
  indicação explícita de resultados parciais. Modelos são filtráveis na interface;
  listagem/atualização não troca o modelo escolhido. Trocar segredo ou endpoint
  invalida o catálogo anterior. Falha de rede conserva o último catálogo em cache.
- **Validar todas** processa as conexões sequencialmente fora da thread Qt, com
  progresso e cancelamento. Resultados de registros editados/excluídos são ignorados.
- A validação comum e em lote não gera texto. **Testar uso do modelo** é uma ação
  separada, com confirmação de possível consumo de cota/créditos: envia somente
  um prompt fixo curto, sem histórico de conversa. O teste não muda a preferência
  de modelo. Isto permite comprovar uso quando o catálogo é público.
- Credencial recusada exige reteste conclusivo ou substituição; esperar não a
  reativa. Pausa manual permanece separada do resultado dos testes.
- Falhas de modelo não castigam a chave inteira. O cliente genérico memoriza
  temporariamente a falha por conexão, endpoint, modelo e operação.
- A configuração F2 mantém a chave legada anterior até confirmar a nova. Opções
  OpenRouter antes removidas por esse formulário agora são preservadas.
- O armazenamento continua nos formatos SQLite/JSON existentes; não há migração
  para cofre do sistema nesta alteração.

## Executar

```powershell
& '.\.venv-apis\Scripts\python.exe' -m pytest tests/test_apis_ollama.py -q -p no:cacheprovider --tb=short
```

Dependências da suíte: `pytest`, `requests` e `PyQt6`. O ambiente virtual local de
validação não é versionado. A suíte cobre migração aditiva e repetida, aliases,
duplicatas, revisões, pausa/exclusão/reinício/recadastro, fontes legadas, cooldown,
substituição, isolamento de endpoints, resultados HTTP, ausência de rede, timeout,
catálogo público e grande, transporte sem redirecionamento, remoção do segredo de
erros, clientes nativos, conversa pela entrada `perguntar`, ferramentas locais,
geração/streaming, Ollama indisponível/sem modelos/modelo removido, formulário F2,
edição em curso, testes atrasados e execução do worker fora da thread Qt.

Resultado final: **92 testes passaram**. A suíte inclui interpretação de códigos,
paginação, isolamento de catálogos, lote, cancelamento, filtros de APIs/modelos,
diagnóstico de voz e confirmação do teste de uso. Compilação Python e revisão
de whitespace com `git diff --check` concluídas. Configurações e dados reais não
foram usados pela suíte.

Na revisão de código residual, foram removidos helpers de validação sem chamadas,
imports e constantes sem uso e comentários que descreviam o motor antigo.
A resolução de conexões e a persistência da ativação Ollama compartilham os mesmos
caminhos do formulário. Migração, aliases, leitores JSON e `validar()` continuam
presentes porque atendem instalações e diagnósticos existentes.

## Verificação das conexões cadastradas

Executada separadamente com autorização, após backup SQLite local em `config/`.
As cinco conexões tiveram seus diagnósticos e modelos persistidos. Foi conferida
a preservação de segredos, provedores, apelidos, pausas, modelos escolhidos,
endpoints e estatísticas. O relatório local sem segredos fica em
`config/validacao_apis.resultado.json`; banco, backup e relatório não são versionados.

| Provedor | Resultado | HTTP | Modelos listados |
|---|---|---|---|
| Gemini | Validado | 200 | 65 |
| OpenRouter | Validado | 200 | 445 |
| Groq | Validado | 200 | 11 |
| NVIDIA | Inconclusivo: catálogo público | 200 | 32 |
| OpenCode | Inconclusivo: catálogo público | 200 | 48 |

Não houve teste de geração com chaves reais. A prova de uso das duas conexões com
catálogo público continua dependente da opção explícita **Testar uso do modelo**.
As quantidades refletem a consulta realizada e podem mudar no provedor.

O diagnóstico existente continua somente de leitura por padrão. Para persistir
uma nova verificação sem gerar texto:

```powershell
& '.\.venv-apis\Scripts\python.exe' verificar_chaves.py --atualizar
```

Referências de implementação: [autenticação OpenRouter](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key),
[listagem Gemini](https://aistudio.google.com/api-reference/models/list-models),
[catálogo Groq](https://console.groq.com/docs/api-reference),
[erros Groq](https://console.groq.com/docs/errors),
[modelos OpenCode](https://opencode.ai/docs/console/api/models/).

## Validação que exige ambiente real

- Cada provedor efetivamente utilizado: autenticação, permissões, cota, respostas
  do SDK e dos proxies, e certificados/URLs personalizados. Provedores com catálogo
  público ou sem adaptador de teste conclusivo ficam pendentes na interface.
- Ollama instalado: ativação, carregamento, uso de GPU, latência, execução de
  ferramentas e streaming com os modelos reais da máquina.
- Aplicativo completo no Windows: navegação F2/configurações, escalas de DPI,
  foco, voz ao vivo, TTS, visão e demais integrações com hardware/serviços reais.
  A renderização isolada do diálogo foi conferida em offscreen; os testes de voz
  executam métodos reais isolados, sem carregar drivers nem gerar áudio.
