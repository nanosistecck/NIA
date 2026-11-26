import json
from pathlib import Path

d = json.loads(Path('docs/nia-final-audit/STATIC_AUDIT.json').read_text(encoding='utf-8-sig'))
for chave in ('eval', 'exec', 'shell_true', 'credencial_literal'):
    v = d['seguranca'][chave]
    print('\n###', chave, v['total'])
    for x in v['amostras']:
        print(f"{x['arquivo']}:{x['linha']} {x['trecho']}")
