# Relatório de UI

## Evidências inspecionadas
- `logs/captura_ui_kit.png` — componente isolado (cartão único, borda ciana, fundo escuro, sem recorte).
- `logs/captura_dashboard_ui_kit.png` — dashboard 1000x700 com indicador "NIA pronta".
- `logs/captura_dashboard_compacto.png` — 640x480, sem overflow, texto legível.
- `logs/audit-ui/geral-1280x720-escala1_5.png` — 150% legível após carregar fontes na sonda.
- `logs/audit-ui/geral-2560x1440-escala1_0.png` — sem recorte/sobreposição.

## Matriz de capturas
`UI_PROBE_1_0.json`, `UI_PROBE_1_25.json`, `UI_PROBE_1_5.json`: 4 resoluções
(1280x720, 1366x768, 1920x1080, 2560x1440) x 3 escalas (100%, 125%, 150%).
Todas as 12 capturas: `ok=true`, `overflow=false`.

## Correção realizada
A sonda sem `QFontDatabase.addApplicationFont` produzia glifos ausentes em
150%; corrigida e recapturada. Não era defeito do produto.

## Testes
`test_nia_ui_kit.py`, `test_integracao_ui_kit_dashboard.py` (Tab/foco,
640x480, captura) e `test_config_dashboard.py` — verdes no baseline.

## Limitações
DPI físico e tema claro não exercitados; a identidade NIA é escura por design.
