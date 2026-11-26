# NIA Gesture Control — Orquestrador autônomo
Objetivo: integrar AirMouse como ferramenta nativa Windows, local e leve, sem reescrever a NIA. O código local é a fonte de verdade. Este pacote é um plano executável por agente, não um instalador binário.

## Inicialização e retomada
Localize a raiz NIA e esta pasta. Leia STATUS.json e CONTINUAR.md. Se novo, execute fase 01. Se retomada, confira git status/diff sem modificar histórico, fingerprints dos arquivos relevantes e último teste; reconcilie mudanças externas e retome a unidade incompleta. Não repita auditoria global salvo mudança arquitetural comprovada. Não confie cegamente em registros antigos.

## Regras de autonomia
Execute sequencialmente as fases abaixo, sem pedir aprovação a cada edição rotineira. Use permissões concedidas pelo ambiente; não altere políticas do agente nem contorne bloqueios. Instale somente dependências necessárias em ambiente isolado. Não copie AirMouse se licença não estiver confirmada; registre bloqueio e solicite resolução, sem trocar de repositório automaticamente. Não acesse webcam nem injete entrada real sem autorização explícita para o teste/ativação. Testes automatizados usam backend falso. Não faça alterações destrutivas, elevação, publicação, commit/push ou transmissão de imagens. Preserve mudanças locais. Se falhar, diagnostique, faça até três tentativas fundamentadas, registre e continue apenas trabalho independente. Não repita tentativas idênticas.

## Sequência
01. `01_AUDITORIA.md` — Auditoria e compatibilidade
02. `02_INSTALACAO.md` — Instalação isolada
03. `03_MOTOR.md` — Gerenciamento do motor
04. `04_WEBCAM.md` — Integração da webcam
05. `05_RASTREAMENTO.md` — Reconhecimento das mãos
06. `06_MOUSE.md` — Mouse virtual
07. `07_WINDOWS.md` — Controle do Windows
08. `08_SEGURANCA.md` — Segurança operacional
09. `09_INTERFACE.md` — Interface principal
10. `10_CALIBRACAO.md` — Calibração e treinamento
11. `11_PERFIS.md` — Perfis e personalização
12. `12_MENU_TECLADO.md` — Menu radial e teclado
13. `13_DOCK.md` — Dock e Central de Aplicativos
14. `14_INTELIGENCIA.md` — Integração com inteligência e Canvas
15. `15_OTIMIZACAO.md` — Otimização e diagnóstico
16. `16_VALIDACAO.md` — Validação e entrega

## Checkpoints
Antes de cada unidade, grave fase, tarefa, estado em andamento, arquivos previstos e baseline. Após cada edição relevante e teste, registre alterações e evidências; use arquivo temporário e substituição atômica para STATUS e CONTINUAR. Guarde hashes dos arquivos relevantes, comandos de teste e resultados, decisões, dependências e rollback específico que preserve alterações alheias. Nunca registre segredos, frames ou texto digitado. Se o agente for interrompido, a próxima sessão verifica a unidade em andamento antes de repetir ações. Use o sistema de continuidade existente da NIA quando houver, mantendo neste diretório um ponteiro explícito e checkpoint mínimo.

## Gates
Licença antes de incorporar código; instalação isolada antes do motor; segurança fase 08 antes de entrada real; testes de integração antes da entrega. Estados: pendente, em_andamento, parcial, bloqueada, concluida. Só marque concluida com evidência. Testes físicos não realizados permanecem pendentes. A entrega final informa alterações, resultados, limitações, como ativar/desativar e retomar.
