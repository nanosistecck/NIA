# Escopo — rodada 14 (frase real de criacao na Agenda)

## Solicitado
Corrigir "adicione na agenda buscar a maria as 21:06", que caiu no Canvas.

## Causas
1. `processar` exige termo de tipo; "adicione na agenda" nao casa.
2. `interpretar` sem data devolve None mesmo com hora explicita.

## Correcoes
1. Reconhecer "adicione na agenda/à agenda/minha agenda" como criacao, com
   titulo extrativo do resto da frase.
2. Inferir data quando ha hora mas nao ha data: hoje se a hora for futura,
   amanha se ja passou. Sem hora continua perguntando.

## Preservado
Criacao de card no Canvas, demais comandos da Agenda e rota de plano.

## Plano
- [x] Diagnosticar e reproduzir
- [x] Testes RED
- [x] Corrigir parser e interpretar
- [x] Suite completa e evidencia

## Resultado
- 6 testes novos; suite **730 passed, 0 failed** (duas execucoes).
- Frase real verificada na NIA: cria e fala do proximo compromisso.


## 2026-11-23T22:29:56.762125-03:00 — Programa EVOLUCAO-NIA

Executar prompts 01 a 16 na ordem e dependencias de EVOLUCAO-NIA/PROGRESSO.json, preservando produto e dados. Etapa 01 somente auditoria. Etapa 02 higiene minima e regressao reproduzida. Usuario autorizou retirada do indice de 206 caches e config/api_keys.json mantendo arquivos locais, sem commit/publicacao.


## 2026-11-23T22:50:56.900283-03:00 — checkpoint EVOLUCAO-NIA

Retomada do programa: ler EVOLUCAO-NIA/PROGRESSO.json e registros/RELATORIO.md; executar etapa 05 parcial. Restante 06–16 pendente. Estado local atual contém alterações de produto, novos testes e remoções somente no índice Git previamente autorizadas. Preservar tudo.

## 2026-11-24 — Avaliação da Central + falha Canvas + credenciais nas configurações

Solicitado: (1) avaliar o que foi adicionado em EVOLUCAO-NIA com testes
simulados, corrigir erros, especialmente a falha intermitente de geometria do
Canvas; (2) disponibilizar nas Configurações a configuração das integrações
externas (Penpot/Plane/Nextcloud) com links para as páginas oficiais.

Causa confirmada do Canvas: `settle()` do teste usava espera fixa de 260 ms
contra `QPropertyAnimation` de 220 ms; sob carga a geometria medida era
transitória. Correção: espera condicional pelo estado `Stopped` da animação,
mantendo a asserção original. Timers órfãos de `QTimer.singleShot` também
foram trocados por timer filho da janela.

Para credenciais: usar Windows Credential Manager (`win32cred`, já instalado)
para tokens e arquivo local apenas com campos não secretos. Sem nova migração
de banco e sem credencial em texto puro.

## Rodada 15 — limpeza de código morto (25/11/2026)

### Solicitado
Análise geral do projeto para achar código morto, funções sem uso e chamadas
sem função, limpando sem prejudicar a NIA.

### Descoberto no diagnóstico
- 225 fontes Python, 0 erros de sintaxe, 0 chamadas a funções inexistentes.
- 110 definições de produção sem referência direta, mas a maioria é viva por
  despacho dinâmico (`getattr`) ou é callback de framework (Qt/HTTP/WebEngine).
- 102 imports sem uso aparente: 101 são `from __future__ import annotations`
  (falso positivo); 1 candidato real (`QConicalGradient` em `ui.py:31`).
- 6 módulos órfãos; o diretório `EVOLUCAO-NIA/` é o maior conjunto (201 arquivos,
  ~984 KB), ignorado pelo Git e sem referência em código/testes.

### Decisões do dono
- `EVOLUCAO-NIA/` pode ser **totalmente apagado**, sem backup. Confirmado depois
  de avisado de que o diretório não está versionado e a exclusão é irreversível.
- Ainda não decidido sobre os outros módulos órfãos fora de `EVOLUCAO-NIA/`.

### Preservado
Callbacks de framework, despacho dinâmico por string/getattr, `__future__`,
todas as funções usadas por testes e todas as mudanças locais preexistentes.

### Plano
- [x] Diagnosticar AST/baseline e comparar com Git/estado persistente
- [x] Confirmar impacto e aprovação da exclusão de `EVOLUCAO-NIA/`
- [x] Excluir `EVOLUCAO-NIA/` e validar (22 testes de sanidade verdes)
- [ ] Triagem individual dos candidatos restantes
- [ ] Remoções em lotes pequenos, com testes e registro


## 2026-11-25 — Programa NIA CORE EVOLUTION (20 fases)

### Solicitado
Executar os prompts 01–20 em ordem de dependência, preservando motor,
provedores, interface, agenda, Canvas, ferramentas, configurações e dados.
Usar modo Safe Evolution; não reiniciar planejamento se houver progresso.

### Estado lido
`NIA_CORE_EVOLUTION/state/CHECKPOINT.json` está `pending`, sem baseline:
iniciar Prompt 01. Git: `NiaSDK` @ `29ed677` com 40 entradas locais
preservadas. Nenhum commit/branch/push criado.

### Abordagem escolhida (reuso antes de criação)
1. **Fases 01–06 (fundação):** usar `catalogo_habilidades`,
   `registro_aplicativos`, `contexto_ferramentas`, `permissoes_ferramentas`
   e o executor único de `main.py`. Acrescentar campos opcionais e módulos
   novos, sem alterar assinaturas públicas nem duplicar serviços.
2. **Fases 07–10 (conhecimento):** adaptar `memory_manager`, `diario`,
   `indice_local` e `busca_fontes` com persistência SQLite por perfil,
   backup e migração idempotente; nunca apagar originais.
3. **Fases 11–15 (automação):** estender `core/rotinas.py` (já existe
   agendador único, SQLite e DST), `whatsapp_bridge` e `segundo_plano`
   com eventos/outbox locais, sem segundo agendador residente.
4. **Fases 16–20 (consolidação):** endurecer política de confiança e
   isolamento; reutilizar `tema`, `frame_nativo` e dock para o UI Kit;
   plugin factory, atualização e homologação dependem de código local/
   autorização e ficam marcadas como `blocked`/`pending` quando aplicável.

### Preservado (gate em toda unidade)
- `TOOL_DECLARATIONS`, roteamento multiprovedor e executor único.
- Aliases e assinaturas antigas de catálogo/registros.
- Agenda, planos/Canvas, dock, Central, clima, voz e dados de perfil.
- Tema/identidade visual, janelas nativas e atalho F9.
- Nenhuma instalação externa, rede com dados privados, credencial em log,
  commit/push ou ação de produção sem autorização explícita.

### Fora de escopo até autorização/presença de recursos
- Pilotos Casa Inteligente/TinyTuya, AirMouse e Central de Leitura (Fase 20).
- Download/execução de código upstream ou plugins desconhecidos (Fases 05, 18, 19).
- Testes reais de WhatsApp, microfone, câmera, DPI físico e dispositivos.

### Plano de execução
- [x] Diagnóstico: protocolos, skills, state, Git e código real
- [x] Fase 01: baseline de testes e desempenho; inventário; fechar gate
- [x] Fases 02–06: contrato, SDK, formato e gerenciador
- [x] Fase 03: gateway integrado à porta real de ferramentas
- [x] Fases 07–10: aprendizado, memória, consolidação, conhecimento
- [x] Fases 11–14: planos, recorrência, eventos e outbox
- [x] Fases 15–16: segundo plano e política de confiança + threat model
- [x] Fases 17–19: UI Kit, factory local e atualizador local
- [x] Fase 20: homologação automática (relatório parcial entregue)

### Resultado final (26/11/2026)
Fases **01–20 `passed`**. Suíte final: **1005 passed, 0 failed** com
`pytest tests -q`. Revisão de hardware/provedores entregue em
`REVIEW_EXISTING.md`; prontidão `.niateck`, migração SQLite, boot NiaLive e
dashboard Tab/compacto finalizados com evidências. Pilotos TinyTuya/AirMouse/
Central de Leitura e upstream licenciado são trabalho futuro com plugins,
conforme esclarecido pelo dono. Commit/push continuam proibidos.
`NIA_PLUGIN_FACTORY/` preservado. Detalhes em `NIA_CORE_EVOLUTION/state/HANDOFF.md`.

