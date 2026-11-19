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
