# -*- coding: utf-8 -*-
"""A VOZ DO JARVIS TEM CHAVE VALIDA? — diagnostico de um comando (18/11/2026)

    python verificar_voz.py

Faz so LEITURA: consulta o catalogo de modelos dos provedores (nao gasta cota de
geracao) e diz, sem rodeios:

  1. qual chave o motor da voz esta recebendo (do banco `config/jarvis.db`);
  2. se o provedor ACEITA essa chave;
  3. quais dos modelos de fala que o JARVIS usa existem para ela.

Nunca imprime a chave inteira. Nao altera nada.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from core import db_chaves, llm_router, valida_chave  # noqa: E402
from core.gemini_voice import LIVE_MODELOS, TTS_MODELOS  # noqa: E402


def _marca(chave: str) -> str:
    if not chave:
        return "(nenhuma)"
    return f"••••{chave[-4:]} ({len(chave)} caracteres)"


def _ver_provedor(nome: str, rotulo: str) -> bool:
    print(f"\n== {rotulo} ==")
    chave = llm_router.resolver(nome)
    if not chave:
        print("  chave: NENHUMA -> a voz nao tem como falar")
        print("  acao: Configuracoes > Chaves de API e cadastre a chave")
        return False
    print(f"  chave: {_marca(chave)}")
    ok, texto = valida_chave.validar(nome, chave)
    print(f"  provedor: {'ACEITA' if ok else 'RECUSOU'} — {texto}")
    if not ok:
        print("  acao: gere outra chave no site do provedor e cadastre na tela")
        print("        de chaves (a recusada pode ficar guardada: ela sai da fila sozinha)")
    return ok


def main() -> int:
    print("JARVIS · diagnostico da voz")
    print(f"banco de chaves: {db_chaves.DB_PATH}")
    todas = db_chaves.listar_chaves()
    print(f"chaves cadastradas: {len(todas)}")
    for row in todas:
        print(f"  - {row['platform']:12s} {_marca(str(row['key']))} "
              f"status={row['status']}")

    gemini_ok = _ver_provedor("gemini", "GEMINI (voz Charon / conversa)")
    openai_ok = _ver_provedor("openai", "OPENAI (vozes onyx, ash, ...)")

    if gemini_ok:
        # O catalogo de modelos e leitura; se a chave for recusada, ja saiu acima.
        try:
            from google import genai  # noqa: PLC0415
            cliente = genai.Client(api_key=llm_router.resolver("gemini"))
            nomes = [str(getattr(m, "name", "")).replace("models/", "")
                     for m in cliente.models.list()]
            print("\n== modelos de fala vistos por esta chave ==")
            for modelo in list(LIVE_MODELOS) + list(TTS_MODELOS):
                curto = modelo.replace("models/", "")
                print(f"  {'OK     ' if curto in nomes else 'AUSENTE'} {curto}")
        except Exception as exc:
            print(f"\n  (nao consegui listar os modelos: {str(exc)[:120]})")

    print("\n== conclusao ==")
    if gemini_ok or openai_ok:
        print("  Ha pelo menos uma voz com chave aceita. Se ainda nao sair som,")
        print("  o problema nao e a chave: abra o log e procure 'voz_' ")
        print("  (voz_de_fora_falhou / voz_chave_fora / charon_trocou_de_chave).")
        return 0
    print("  NENHUMA voz tem chave valida. Enquanto isso o JARVIS fica mudo")
    print("  (a resposta continua escrita no chat).")
    print("  Gemini: pegue a chave em https://aistudio.google.com/apikey.")
    print("  Copie a chave INTEIRA. Se ela comecar com AQ. e o Google a recusar")
    print("  (401 API key not valid), gere uma chave NOVA no mesmo site e cole")
    print("  aqui de novo — nao ha o que configurar no JARVIS.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
