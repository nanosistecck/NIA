# -*- coding: utf-8 -*-
"""AS CHAVES DO JARVIS ESTAO CHEGANDO EM TODO LUGAR? — diagnostico (18/11/2026)

    python verificar_chaves.py

Faz so LEITURA. Responde tres perguntas, sem rodeios:

  1. Quais chaves existem no banco (`config/jarvis.db`) e em que estado estao?
  2. O provedor ACEITA cada uma? (leitura do catalogo de modelos, sem gastar cota)
  3. Cada area do JARVIS puxa a chave da fonte certa (banco/roteador) ou ficou
     presa no `config/api_keys.json` antigo?

Nunca imprime a chave inteira. Nao altera nada.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from core import db_chaves, llm_router, valida_chave  # noqa: E402

# Areas que precisam de chave e o arquivo onde a decisao mora. O 3o campo e o
# que se espera encontrar no codigo: "roteador" (banco primeiro) e o correto;
# "arquivo" seria o caminho antigo (so' `config/api_keys.json`).
CONSUMIDORES = [
    ("Voz Gemini (ao vivo, conversa e TTS)", "core/gemini_voice.py"),
    ("Voz OpenAI", "core/voz_openai.py"),
    ("Cerebro principal (escada de modelos)", "core/cerebro_openrouter.py"),
    ("Cerebro Gemini", "core/cerebro_gemini.py"),
    ("Cerebro OpenAI", "core/cerebro_openai.py"),
    ("Cerebro rapido", "core/cerebro_rapido.py"),
    ("Provedores genericos (OpenAI-compat)", "core/cerebro_generico.py"),
    ("Socorro das acoes (Gemini -> VPS)", "core/gemini_socorro.py"),
    ("Secretaria (ligacoes)", "secretaria/motor.py"),
    ("Secretaria (WhatsApp com IA)", "core/secretaria_chat.py"),
    ("Ponte WhatsApp (transcricao/visao)", "actions/whatsapp_bridge.py"),
    ("Visao de tela", "actions/screen_processor.py"),
    ("Busca na web", "actions/web_search.py"),
    ("Controle do computador", "actions/computer_control.py"),
    ("Acoes com IA (codigo, arquivos, video...)", "actions/code_helper.py"),
    ("Modo economico (script avulso)", "modo_economico.py"),
    ("main.py (motor da conversa)", "main.py"),
    ("Tela de configuracao (F2)", "ui.py"),
]


def _marca(chave: str) -> str:
    if not chave:
        return "(nenhuma)"
    return f"••••{chave[-4:]} ({len(chave)} caracteres)"


def _fonte(caminho: Path) -> str:
    """O arquivo fala com o roteador (banco) ou so' com o arquivo antigo?"""
    try:
        texto = caminho.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return "ILEGIVEL"
    usa_router = any(s in texto for s in (
        "llm_router", "carregar_router", "resolver(", "chave_ativa(",
        "router=", "CerebroGemini(", "CerebroOpenAI(", "CerebroGenerico("))
    if usa_router:
        return "ROTEADOR (banco primeiro)"
    if "api_keys.json" in texto:
        return "ARQUIVO antigo (SEM banco)"
    return "nao le chave diretamente"


def _ler_json_antigo() -> dict:
    try:
        return json.loads((RAIZ / "config" / "api_keys.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    print("JARVIS · diagnostico das chaves")
    print(f"banco: {db_chaves.DB_PATH}")
    print(f"config antigo: {RAIZ / 'config' / 'api_keys.json'}")

    todas = db_chaves.listar_chaves()
    print(f"\n== chaves no banco: {len(todas)} ==")
    if not todas:
        print("  NENHUMA. Cadastre em Configuracoes > Chaves de API.")
    for row in todas:
        status = str(row.get("status") or "ativo")
        castigo = ""
        if status != "ativo" and float(row.get("cooldown_ate") or 0):
            castigo = f" (castigo ate {_quando(float(row['cooldown_ate']))})"
        print(f"  - {str(row.get('platform')):12s} {_marca(str(row.get('key')))} "
              f"status={status}{castigo}")

    # 2. O provedor aceita? Uma leitura por chave, sem gastar cota de geracao.
    print("\n== o provedor aceita cada chave? ==")
    aceitas: dict[str, str] = {}
    alguma_aceita = False
    for row in todas:
        provedor = str(row.get("platform") or "")
        chave = str(row.get("key") or "")
        ok, texto = valida_chave.validar(provedor, chave,
                                         str(row.get("base_url") or ""))
        print(f"  {provedor:12s} {_marca(chave)}: "
              f"{'ACEITA' if ok else 'RECUSOU'} — {texto}")
        if ok and provedor not in aceitas:
            aceitas[provedor] = chave
            alguma_aceita = True

    # 3. O que cada area recebe HOJE.
    print("\n== chave que cada area recebe agora ==")
    for nome in ("gemini", "openai", "openrouter"):
        chave = llm_router.resolver(nome)
        print(f"  resolver('{nome}') -> {_marca(chave or '')}")

    # 4. Cada area puxa da fonte certa?
    print("\n== de onde cada area puxa a chave ==")
    problemas = []
    for rotulo, relativo in CONSUMIDORES:
        fonte = _fonte(RAIZ / relativo)
        print(f"  {rotulo:44s} {relativo:32s} {fonte}")
        if "ARQUIVO antigo" in fonte:
            problemas.append(rotulo)

    # 5. O arquivo antigo pode enganar? (o banco vence, mas vale avisar)
    antigo = _ler_json_antigo()
    chave_json = str(antigo.get("gemini_api_key") or "").strip()
    chave_banco = llm_router.resolver("gemini") or ""
    if chave_json and chave_banco and chave_json != chave_banco:
        print("\n  AVISO: o `api_keys.json` tem uma chave Gemini DIFERENTE da do")
        print("  banco. O JARVIS usa a do banco; a do arquivo so' serve de reserva.")

    print("\n== conclusao ==")
    if alguma_aceita:
        print("  Ha pelo menos uma chave aceita pelo provedor.")
        print("  Se alguma area ainda falhar, o problema NAO e a chave: procure no")
        print("  log por 'voz_', 'cerebro_' ou o nome do provedor.")
        if problemas:
            print("  Atencao: estas areas ainda leem o arquivo antigo:", ", ".join(problemas))
        return 0
    print("  NENHUMA chave foi aceita pelo provedor. Enquanto isso as areas que")
    print("  dependem dela respondem por escrito ou caem no socorro da VPS.")
    print("  Abra Configuracoes > Chaves de API, confira a chave (copiada inteira)")
    print("  e, se o provedor continuar recusando, gere outra no site dele.")
    return 1


def _quando(ts: float) -> str:
    import datetime as _dt
    try:
        return _dt.datetime.fromtimestamp(ts).strftime("%d/%m %H:%M")
    except Exception:
        return "?"


if __name__ == "__main__":
    raise SystemExit(main())
