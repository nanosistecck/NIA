# Nova interface principal da NIA

## Ajuste posterior: aparência personalizável

As configurações do dock agora têm as abas **Ferramentas**, **Fundo** e **Dock**.
O fundo permite escolher a cor principal com prévia e luminosidade de 40% a 160%.
O padrão de 90% deixa a composição aproximadamente 10% mais escura em relação
ao ajuste anterior, mantendo suas luzes, posições, proporções e suavidade.
A transformação da paleta preserva a ordem dos tons, sem recortar a luminosidade.

O tamanho dos ícones varia de 18 a 40 px e a altura preferida do dock de 240 a
900 px, limitada pelo espaço disponível na janela. A largura acompanha os ícones;
a rolagem e o botão de recolher permanecem acessíveis. Os controles receberam
ícones vetoriais de engrenagem, ajustes, grade e setas. O campo de conversa
continua transparente e sem borda ao receber foco.

As escolhas ficam em `appearance` dentro de `config/interface.json`. Salvar
aplica e persiste; cancelar descarta a prévia. Há uma ação para restaurar a
aparência padrão, sem alterar a seleção e a ordem das ferramentas.

Validação mais recente: **100 testes passaram**, incluindo dois testes novos
para escurecimento, troca de paleta, cache, salvar/cancelar, persistência e
adaptação do dock com ícones grandes em 820 × 580. As abas foram renderizadas
e inspecionadas. Compilação Python e `git diff --check` passaram.

Implementação em `INTERFACE-NIA`, baseada no commit `18be981`, em 19/11/2026.
O repositório estava limpo ao iniciar. Não houve commit, push ou PR.

## Entrega

- `ui.py`: janela real usada por `main.py → NiaUI → MainWindow`, cabeçalho discreto, Canvas inicialmente vazio, Reator existente, conversa no rodapé e histórico recolhido.
- `core/interface_canvas.py`: fundo estático em cache por tamanho/escala/tema, vidro, ícones vetoriais, composição do Reator, cards e personalização do dock.
- `tests/test_interface_canvas.py`: seis testes de integração Qt, sem rede ou dispositivos físicos.
- Preferências em `config/interface.json`, no mesmo diretório e com o padrão de gravação atômica das preferências de tema. Nenhuma credencial foi incluída no código ou nas capturas.

O dock permite selecionar ícones, arrastar a ordem, usar os botões Subir/Descer pelo teclado e adicionar/remover aplicativos. O menu Todas as ferramentas mantém disponíveis as ações ocultas, inclusive palavra de ativação, interrupção, WhatsApp, remoto, Computer Use e segundo plano. O recolhimento permanece acessível em janelas baixas; os ícones rolam quando necessário. Caminhos inexistentes ficam desabilitados e a abertura usa URL local da plataforma, sem montar comandos de shell.

O histórico usa o `LogWidget` existente. Respostas com a gaveta fechada entram sem abrir o painel, alterar o rascunho ou iniciar digitação animada fora de vista. O campo mantém Enter, botão Enviar, anexos e microfone com indicação de estado. F2, F4, F6, F9, F11 e Esc conservam os vínculos existentes.

Resultados continuam pelo contrato `NiaUI.show_content(título, texto)` e pelo sinal da thread Qt. Os cards permitem seleção, cópia, fixação e fechamento. Resultados novos substituem somente os não fixados; resultados com o mesmo título atualizam o card não fixado. O Reator ocupa a direita com conteúdo e volta ao centro ao fechar o último card. Seu menu de contexto permite outras âncoras quando o Canvas está livre. A gaveta e o dock ficam protegidos pela composição. Sistema, visão e Cowork são acessíveis sob demanda, sem cards de clima ou agenda fictícios.

Foram removidos o splitter e o painel antigo de resultados, o chat lateral, o dock horizontal e sua rolagem, o rodapé antigo, o relógio e seu temporizador, o fundo antigo do HUD, os textos de estado duplicados sob o Reator e o medidor antigo com suas atualizações por quadro. Os núcleos, assets, reações e mecanismos de voz permanecem existentes.

## Validação executada

```powershell
$env:QT_QPA_PLATFORM='offscreen'
& .venv-apis/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=cache/pytest-interface
```

Resultado: **98 testes passaram**, incluindo os 92 testes anteriores de APIs/Ollama.

Os seis testes novos verificam:

1. Abertura vazia, mínimo de 820 × 580, gaveta acima do campo, preservação de rascunho/anexo e tela cheia.
2. Envio por Enter ao callback existente, resposta de outra thread, foco preservado, histórico fechado sem temporizador de digitação e interrupção por Esc.
3. Entrega de resultados pela thread Qt, conteúdo tratado como texto, atualização, cópia, fixação, rolagem de vários cards e retorno do Reator ao centro.
4. Edição e gravação do dock, ordem, visibilidade, recarga das preferências, aplicativo ausente desabilitado e despacho de abertura somente ao clicar. A chamada ao sistema operacional foi interceptada neste teste.
5. Preferências inválidas, estados da interface, mudo e pausa/retomada do temporizador do Reator quando a janela está coberta.
6. Entrega de frames simulados pelos contratos públicos de câmera/visão, painel de Cowork e composição com a gaveta aberta.

Foram renderizadas e inspecionadas a abertura, uma pesquisa real com o Reator à direita e a janela mínima. Também foram geradas cenas com `QT_SCALE_FACTOR=1.5` e `2`. Compilação Python e `git diff --check` passaram.

A pesquisa real usou `_ddg_search` e `_format_ddg` de `actions/web_search.py`, retornou duas fontes e foi entregue por `NiaUI.show_content` a partir de outra thread. O chamador existente de `web_search` em `main.py` continua intacto.

As dependências declaradas em `requirements.txt` foram instaladas no `.venv-apis`. O `main.py` foi executado: iniciou a interface, o servidor remoto, a entrada de microfone e a saída WASAPI. O log registrou tentativas de voz recusadas com HTTP 404 e a passagem aos modelos de reserva; não se afirma uma conversa de voz completa validada.

## Capturas

- [Abertura sem conteúdo](interface-nia/abertura.png)
- [Pesquisa real no Canvas](interface-nia/pesquisa.png)
- [Janela mínima](interface-nia/minima.png)

## Perfil de renderização

Foi reconstruída a versão de `ui.py` do commit de base e comparada à nova em processos separados, sequencialmente, no mesmo ambiente, em 1280 × 820. Amostras de aproximadamente 2,2 s por estado, com aquecimento. Estados de escuta, pensamento e fala foram simulados no HUD; os motores de áudio não participaram. CPU é a medida do processo pelo psutil, em que 100% corresponde a um núcleo lógico.

| Estado simulado | CPU base | CPU nova | RAM base | RAM nova |
|---|---:|---:|---:|---:|
| Escuta em repouso | 20,6% | 33,3% | 73,9 MB | 74,1 MB |
| Pensamento | 14,8% | 16,3% | 78,9 MB | 79,0 MB |
| Fala | 43,2% | 52,8% | 79,8 MB | 80,0 MB |

As amostras curtas variaram entre execuções. Não demonstram redução de CPU: o Reator maior aumenta a área de renderização. A memória ficou próxima da base nesta comparação. O fundo fica em cache, não há blur em tempo real e a pausa dos temporizadores quando a janela está coberta foi testada. Estes números não substituem uma medição com áudio real em uso contínuo.

## Limites da validação

A janela nativa também foi aberta isoladamente com `NiaUI`. A aprovação automática do controle do computador rejeitou a inspeção/automação porque o aplicativo Python não estava autorizado. Portanto, a interação manual por automação do Windows, a abertura efetiva de um aplicativo externo pelo dock e o ciclo completo da bandeja não foram validados por esse caminho. Os testes Qt verificam os contratos e a persistência descritos acima.

Captura de câmera física, conversa real de voz, conexão de WhatsApp/remoto, Globo e execução real de tarefas Cowork/Computer Use não foram exercitados de ponta a ponta. Seus handlers e contratos foram preservados; câmera, visão e Cowork receberam validação com dados simulados. As configurações de APIs, provedores e motores ficaram fora da reforma visual.

## Canvas Infinito — Etapas 1, 2 e 3 (20/11/2026)

Entrega combinada: base local versionada de planos, Gerenciador no dock, editor visual de mapa e comandos de planejamento por chat/voz.

**Componentes novos**
- `core/planos.py`: um JSON UTF-8 por plano em `NIA-CyberBot/planos` (fora da árvore de trabalho), `formato` separado de `revisao`, gravação atômica `.tmp` + `os.replace`, conflito de revisão, isolamento de arquivos corrompidos e mapa versionado no mesmo documento.
- `core/interface_planos.py` + botão `planos` em `ui.py`: busca sem acento/caixa, filtros de tipo/status, criar/visualizar/editar/arquivar/restaurar.
- `core/interface_mapa.py` + `core/interface_canvas_planos.py`: `QGraphicsView`/`QGraphicsScene`, cards e conexões desenhados com `QPainter`, `QUndoStack`, pan/zoom, câmera persistida, autosave com estados e novo botão de migração `dock_planos_v1`.
- `core/comandos_planos.py`: reconhecedor local de intenções, sessão com pergunta pendente/opções/contexto/dedup, ligado a `_executar_frase_habilidade` — o mesmo caminho de chat, voz local e Gemini Live.

**Reaproveitados**: gravação atômica de `config_preferencias.py`/`DockPreferences`, `GLASS`/ícones vetoriais e `arrange()`/`set_anchor()` do Canvas, padrão de janela não modal de `ConfigDashboardWindow`, `StatusLabel`/paletas do dashboard, `_transcript_key`, `_voice_diag` e o marcador de migração `skill_atalhos_v1`.

**Remoções**: nenhuma funcionalidade existente foi removida; apenas imports e constantes sem uso detectados na auditoria final. Catálogo de habilidades, F2/F4/F6/F9/F11/ESC, cards de hora/data/clima e fluxos de chat/voz permanecem intactos.

**Verificações executadas**
```
$env:QT_QPA_PLATFORM='offscreen'
& .venv-apis/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=cache/pytest-canvas
```
Resultado: **289 testes passaram** (Python 3.12.14, PyQt6 6.12.1, pytest 9.2.0). Também: `compileall -q core ui.py main.py` e `git diff --check` sem erros.

Cobertura acrescentada: persistência após reinício, revisão/conflito/falha de escrita, arquivo corrompido isolado, formato antigo sem mapa, card central idempotente, exclusão com conexões desfeita e refeita junta, restauração de câmera/posições, falha de gravação, recolhimento de dock e retorno do núcleo sem persistir preferência, intenções do Prompt 03, escolha por ordinal, negação e reentrega de transcrição.

**Limitações**: a voz foi validada com transcrição final simulada, não com microfone/STT reais; pan/zoom e edição foram exercitados em testes Qt offscreen, não em sessão manual com núcleo falando. Movimento reduzido é lido de `appearance.movimento_reducido` (padrão `false`), ainda sem controle de UI dedicado. Nenhuma chamada de rede, API externa ou Ollama foi feita nesta entrega.

## Edição assistida e memória local do Canvas — Etapa 4 (20/11/2026)

- `core/assistencia_planos.py`: contexto mínimo do plano (objetivo, card selecionado e vizinhos), intenções local/sugestão/edição/desfazer, operações estruturadas validadas contra o **estado atual do editor**, aplicação em um único `QUndoCommand` e filtro de saída antes de qualquer provedor.
- Gerenciador ganhou **Editar com a NIA**; o Canvas tem alternância **Manual / Com a NIA** que preserva mapa, seleção, câmera e mudanças pendentes.
- Os campos `restrito` e `financeiro` passaram a fazer parte do card. `filtrar_contexto` remove esses cards de chamadas externas — inclusive no fallback local → externo — e o provedor configurado da NIA é chamado pelo mesmo ponto de entrada de chat/voz (`_executar_frase_habilidade`).
- Lotes inválidos, conflito com edição manual e troca/fechamento do plano são recusados antes de qualquer alteração; o desfazer do lote só age quando ele é a última operação.

**Verificação**: **304 testes passaram** com o mesmo comando acima; `compileall` e `git diff --check` limpos. Cobertura nova: contexto com vizinhos, filtro externo/local/fallback, lote de três soluções com desfazer em uma ação, lote inválido, conflito em memória, resposta atrasada após troca de plano e roteamento idêntico por texto e voz.

**Limitações da Etapa 4**: os testes de edição assistida usam provedor simulado e interface Qt offscreen; nenhuma chamada real a API externa ou Ollama foi feita. Lembretes e publicação ficam para etapas seguintes.

## Modelos de planejamento — Etapa 5 (20/11/2026)

- `core/modelos_planos.py`: estruturas locais para Produto, Projeto, Conteúdo, Estudos e Finanças; inferência do tipo pelo tema; ramos conectados ao card escolhido sem mover cards existentes; progresso por ramo e cálculo financeiro em centavos inteiros, preservando campo vazio (`None`) versus zero.
- **Novo plano** usa o modelo escolhido no tipo e já semeia a estrutura local. No Canvas, **Adicionar modelo como ramo** oferece os cinco modelos e **Complementar ramo** evita duplicar a raiz. Pedidos como “monte o planejamento completo” usam o mesmo caminho.
- Campos novos do card (`modelo`, `estado`, `valor`, `acumulado`) são preenchidos na leitura de planos antigos, preservando conteúdo, conexões e posições. O tipo principal do plano não muda ao combinar ramos.
- Cada geração é um único `QUndoCommand` (macro), validada antes de aplicar; conflitos, falha do provedor ou resposta atrasada preservam o mapa.

**Verificação**: **315 testes passaram**; `compileall` e `git diff --check` limpos. Cobertura nova: cinco estruturas locais, reconhecimento de tipo, combinação de ramos, progresso por ramo, publicação de Conteúdo, cálculo monetário exato, lote único de desfazer/refazer e criação de plano com modelo pelo gerenciador.

**Limitações da Etapa 5**: personalização por IA, explicações e exercícios de Estudos usam provedor simulado em testes; nenhuma chamada real a API externa/Ollama foi feita. Geração de exercícios com feedback e “Salvar no mapa” ainda dependem do provedor configurado.

## Lembretes, proteção de publicação e validação final — Etapa 6 (20/11/2026)

- `core/lembretes.py`: lembretes no mesmo JSON versionado do plano (ID do plano/card, assunto, horário UTC, fuso, estado, ocorrências avisadas). Datas em linguagem natural com relógio simulado, vencimentos, aviso por ocorrência, adiar/concluir/cancelar e suspensão ao arquivar ou excluir card — com restauração no desfazer.
- Interface: **Definir lembrete** no Card, consulta no Gerenciador, notificação com **Abrir plano/card** pelo fluxo normal do Canvas e rearmamento de um único timer para o próximo vencimento. Chat e voz compartilham `core/comandos_lembretes.py`.
- `core/publicacao_segura.py`: prepara só a seleção, bloqueia card restrito/financeiro, resumo derivado, anexo interno e segredos; exige confirmação da prévia exata e revalida em cada envio/reenvio. Destinos fora do simulado são bloqueados — não há publicação real conectada ao Canvas.

**Verificação**: **334 testes passaram**; `compileall` e `git diff --check` limpos. Relógio e destino simulados tornam datas/fusos e bloqueios reproduzíveis. Pela interface Qt offscreen: botões do gerenciador e do Canvas e abertura do card correto pelo lembrete. Por simulação: transcrição de voz, provedor de IA e publicação.

**Limitações finais**: entrega de notificações com a NIA totalmente fechada depende de integração com o sistema operacional (fora desta etapa); avisos vencidos aparecem na próxima abertura. A comparação de CPU/memória/responsividade com núcleo falando e mapas grandes não foi executada neste ambiente — os testes cobrem contratos e persistência, não medição de desempenho. Chamadas reais a API/Ollama, microfone/STT reais e publicação real não foram exercitados.
