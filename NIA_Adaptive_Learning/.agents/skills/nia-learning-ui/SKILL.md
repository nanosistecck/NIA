---
name: nia-learning-ui
description: Implementar e validar interface e voo visual no motor adaptativo da NIA.
---
# nia-learning-ui

## Interface e voo visual
Leia `docs/adaptive_learning/11_UI_FLIGHT_PLAN.md`.
Central no dock e catálogo de apps: 1120x740 DIP inicial, mínimo 760x520 adaptável, menu 220/56, topo 44, margens 24, gaps 16, botões 36–40, raio 12, animações 120–200ms. Dark: fundo #0B111C, painel #152235, card #1D3047, borda #344A63, ação #60A5FA, aprendizado #A78BFA, validado #4ADE80, texto #E2E8F0, secundário #94A3B8. Light usa tokens existentes e contraste. Menu visão geral, conhecimentos, procedimentos, experiências, atividades, correções, configurações; busca, filtros, detalhes, origem, versões, editar, desativar, excluir, importar/exportar com validação. Overlay reutiliza serviço existente: azul controle, violeta observação, verde colaboração, amarelo espera, vermelho falha; texto explícito, borda 2 DIP, brilho 8–14 DIP opacidade 15–30%, topo central 32 DIP, click-through, DPI/múltiplos monitores, sem roubar foco. Painel separado com pausar/concluir/ESC. Workspace documento à esquerda 38%, navegador à direita 62%, ajuste 25–65%, área útil Windows, abas/recolhimento em telas pequenas, restaurar geometria quando possível. Cards de pesquisa com fonte, estado real, cancelar, abrir e adicionar. Sem porcentagens fictícias. Glassmorphism leve sem blur contínuo. Testar dark/light, DPI, teclado, resize e ausência de cortes.

## Execução
Verifique checkpoint e arquitetura real; reutilize serviços, implemente incrementalmente, teste e registre evidências conforme prompt mestre. Não avance sobre falhas críticas.
