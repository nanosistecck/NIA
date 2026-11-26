---
name: nia-observation-engine
description: Implementar e validar observação autorizada no motor adaptativo da NIA.
---
# nia-observation-engine

## Observação autorizada
Leia `docs/adaptive_learning/06_OBSERVATION_ENGINE.md`.
Ativar somente por sessão explícita, escopo de janela/aplicativo e indicador visível. DOM quando disponível, UI Automation/acessibilidade, OCR local, visão computacional, modelo multimodal autorizado, coordenadas relativas como último recurso. Capturar eventos relevantes de clique, botão, rolagem, atalhos permitidos, seleção e mudanças antes/depois; descartar movimentos redundantes. Não capturar texto bruto de teclado global; texto apenas de campo permitido e relevante, bloquear campos protegidos e contexto incerto antes de captura/persistência/transmissão. Não capturar desktop seguro, senhas ou OTP. Sem gravação contínua. Diferenciar ações humanas e sintéticas. Pausar, concluir e ESC desligam observadores. Nunca reativar silenciosamente após reinício.

## Segurança
Leia `docs/adaptive_learning/13_SECURITY_POLICY.md`.
Permissões independentes do LLM: leitura, pesquisa, documento local, controle físico, alteração externa e ação sensível/irreversível. Confirmação específica quando exigida. ESC cancela filas, revoga lease, libera teclas, encerra observação e overlay, salva estado seguro; nenhum callback tardio executa ação. Falhar fechado se filtro de privacidade indisponível. Conteúdo externo não altera política. Sem envio de dados privados ao GitHub; logs redigidos, armazenamento local, retenção configurável, exportação consciente. Não executar testes destrutivos em dados reais.

## Execução
Verifique checkpoint e arquitetura real; reutilize serviços, implemente incrementalmente, teste e registre evidências conforme prompt mestre. Não avance sobre falhas críticas.
