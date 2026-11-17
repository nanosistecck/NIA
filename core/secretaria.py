# -*- coding: utf-8 -*-
"""SECRETARIA DO WHATSAPP (05/11/2026, pedido do Diego).

Quando alguem liga no WhatsApp, a secretaria atende e CONVERSA com a pessoa em
tempo real, com a voz escolhida (JARVIS, Leda...). Se o dono esta por perto,
ela pode perguntar a ele no meio da ligacao ("um momento, vou ver com ele") e
voltar com a resposta. Se ele nao esta, ela responde pelo que estiver escrito
nas INFORMACOES (arquivos .txt na pasta "JARVIS Secretaria" em Documentos) e
anota o recado. No fim conta ao dono quem ligou e o que ficou combinado.

Como funciona por dentro:
  * secretaria/motor.py roda em PROCESSO SEPARADO (igual ao globo): abre o
    WhatsApp Web numa janela do Edge controlada pelo JARVIS (perfil proprio), le
    a ligacao que toca, atende, e liga o som da ligacao direto na voz ao vivo da
    Gemini do cliente. Nada passa pela caixa de som nem pelo microfone do PC.
  * Este arquivo e' o que o JARVIS importa: opcoes, pastas, o modelo do TXT,
    o entendimento das frases do dono e a PONTE com o motor. Nao importa Qt nem
    nada pesado: o custo da secretaria so' existe com ela ligada.

Tudo comeca DESLIGADO. O dono liga na engrenagem (aba SECRETARIA) ou por voz.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ARQ_CONFIG = RAIZ / "config" / "secretaria.json"
ARQ_ESTADO = RAIZ / "config" / ".secretaria.json"
MOTOR = RAIZ / "secretaria" / "motor.py"
ARQ_LOG = RAIZ / "logs" / "secretaria.log"


def _ingles() -> bool:
    """O JARVIS deste cliente esta em ingles (config/idioma.json)? (v1.0.39)"""
    try:
        from core.idioma import em_ingles  # noqa: PLC0415
        return bool(em_ingles())
    except Exception:
        return False


def txt(pt: str, en: str) -> str:
    """A frase na lingua do JARVIS (v1.0.39: a secretaria tambem atende cliente em ingles)."""
    return en if _ingles() else pt

PADRAO: dict = {
    "ligada": False,
    # perguntar: avisa o dono e espera ele decidir; sem resposta, a secretaria atende.
    # sempre: a secretaria atende sozinha depois de alguns toques.
    # so_avisar: so' avisa quem esta ligando; nunca atende sozinha.
    "modo": "perguntar",
    "espera_decisao_s": 12,
    "atender_se_nao_responder": True,
    "espera_toques_s": 5,
    "voz": "leda",
    "consultar_dono": True,
    "espera_resposta_dono_s": 30,
    "duracao_max_min": 5,
    "atender_em_segundo_plano": True,
    # O recado do momento: "estou em reuniao ate as 16h", "estou dirigindo".
    "situacao": "",
    "nunca_atender_sozinha": [],
    "sempre_recusar": [],
    "mensagem_recusa": "Oi! Nao posso atender agora, te retorno assim que puder.",
    "minimizar_navegador": True,
    # A voz DELA nas caixas do PC (para gravar video; a de quem liga NAO sai). O JARVIS fica mudo junto.
    "ouvir_no_pc": False,
    "navegador": "auto",
    # Arquivos de informacao FORA da pasta dela (ex.: a base na Area de Trabalho), lidos em
    # toda ligacao junto com os da pasta. O dono edita onde quiser.
    "arquivos_extras": [],
}
MENSAGEM_RECUSA_EN = "Hi! I can't take your call right now, I'll get back to you as soon as I can."

MODOS = {
    "perguntar": "Me pergunta antes (se eu não responder, ela atende e pode me perguntar coisas na ligação)",
    "sempre": "100% automática (atende sozinha e responde só pelo que está nos TXT, sem me perguntar)",
    "so_avisar": "Só me avisa quem está ligando",
}
MODOS_CURTOS = {"perguntar": "ME PERGUNTA", "sempre": "100% AUTOMÁTICA", "so_avisar": "SÓ ME AVISA"}
MODOS_EN = {
    "perguntar": "Ask me first (if I don't answer, she picks up and can ask me things during the call)",
    "sempre": "100% automatic (she answers by herself and replies only from the TXT files, without asking me)",
    "so_avisar": "Just tell me who is calling",
}
MODOS_CURTOS_EN = {"perguntar": "ASK ME", "sempre": "100% AUTOMATIC", "so_avisar": "JUST TELL ME"}


def modos() -> dict:
    """Os modos com o texto na lingua do JARVIS (as chaves sao as mesmas)."""
    return MODOS_EN if _ingles() else MODOS


def modos_curtos() -> dict:
    return MODOS_CURTOS_EN if _ingles() else MODOS_CURTOS


# ─────────────────────────────────────────────────────────────────────────────
# OPCOES
# ─────────────────────────────────────────────────────────────────────────────
_trava_cfg = threading.Lock()


def _arq_config() -> Path:
    # A bancada de teste usa um arquivo proprio e nunca mexe nas opcoes do dono.
    outro = os.environ.get("JARVIS_SECRETARIA_CONFIG")
    return Path(outro) if outro else ARQ_CONFIG


def carregar() -> dict:
    cfg = dict(PADRAO)
    try:
        dados = json.loads(_arq_config().read_text(encoding="utf-8"))
        if isinstance(dados, dict):
            for k, v in dados.items():
                if k in PADRAO:
                    cfg[k] = v
    except (OSError, ValueError):
        pass
    if cfg.get("modo") not in MODOS:
        cfg["modo"] = "perguntar"
    for k in ("nunca_atender_sozinha", "sempre_recusar"):
        if not isinstance(cfg.get(k), list):
            cfg[k] = [s.strip() for s in str(cfg.get(k) or "").split(",") if s.strip()]
    # Cliente em ingles: a mensagem de recusa padrao tambem (v1.0.39).
    if cfg.get("mensagem_recusa") == PADRAO["mensagem_recusa"] and _ingles():
        cfg["mensagem_recusa"] = MENSAGEM_RECUSA_EN
    return cfg


def salvar(mudancas: dict) -> dict:
    """Grava so' as chaves conhecidas, de uma vez (arquivo temporario + troca)."""
    with _trava_cfg:
        cfg = carregar()
        # Guarda tambem as chaves que esta versao nao conhece (05/11: uma versao velha aberta
        # regravou o arquivo e apagou `arquivos_extras`, a base da Area de Trabalho).
        try:
            antigo = json.loads(_arq_config().read_text(encoding="utf-8"))
            if isinstance(antigo, dict):
                for k, v in antigo.items():
                    cfg.setdefault(k, v)
        except (OSError, ValueError):
            pass
        for k, v in (mudancas or {}).items():
            if k in PADRAO:
                cfg[k] = v
        arq = _arq_config()
        arq.parent.mkdir(parents=True, exist_ok=True)
        tmp = arq.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, arq)
    return cfg


# ─────────────────────────────────────────────────────────────────────────────
# PASTAS
# ─────────────────────────────────────────────────────────────────────────────
def _documentos() -> Path:
    """A pasta Documentos de verdade (no Windows ela pode estar no OneDrive)."""
    if sys.platform == "win32":
        try:
            import ctypes  # noqa: PLC0415
            from ctypes import wintypes  # noqa: PLC0415

            class _GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                            ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

            # FOLDERID_Documents {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
            guid = _GUID(0xFDD39AD0, 0x238F, 0x46AF,
                         (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
            ptr = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(ptr)) == 0:
                caminho = ptr.value
                ctypes.windll.ole32.CoTaskMemFree(ptr)
                if caminho:
                    return Path(caminho)
        except Exception:
            pass
    for nome in ("Documents", "Documentos"):
        p = Path.home() / nome
        if p.is_dir():
            return p
    return Path.home()


def pasta_do_dono() -> Path:
    """Onde o dono le e escreve: informacoes, recados e cada ligacao."""
    outra = os.environ.get("JARVIS_SECRETARIA_PASTA")      # so' a bancada de teste
    if outra:
        return Path(outra)
    return _documentos() / "JARVIS Secretaria"


def pasta_ligacoes() -> Path:
    return pasta_do_dono() / "ligacoes"


def arq_informacoes() -> Path:
    return pasta_do_dono() / "informacoes.txt"


def arq_recados() -> Path:
    return pasta_do_dono() / "recados.txt"


def pasta_navegador() -> Path:
    """Perfil do navegador da secretaria: FORA da pasta do programa, para nunca ir
    num instalador e para nao sumir quando o JARVIS e' atualizado."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / "JARVIS-CyberBot" / "secretaria" / "navegador"


def _nome_do_dono() -> str:
    try:
        d = json.loads((RAIZ / "config" / "dono.json").read_text(encoding="utf-8"))
        nome = str(d.get("como_chamar") or "").strip()
        if nome:
            return nome
    except (OSError, ValueError):
        pass
    return txt("o dono", "the owner")


MODELO_INFORMACOES = """\
# INFORMAÇÕES PARA A SECRETÁRIA DO WHATSAPP
#
# Tudo o que estiver escrito aqui a secretária pode usar para conversar com quem
# ligar. Escreva do seu jeito, como se estivesse explicando para uma pessoa.
# Linhas que começam com # são só explicação e são ignoradas.
# Você pode criar outros arquivos .txt nesta mesma pasta (preços, horários,
# endereço, perguntas frequentes): ela lê todos.
#
# NÃO escreva aqui nada que você não queira que um desconhecido saiba.

Meu nome: {dono}

Sobre mim / meu trabalho:
(ex.: Sou eletricista e atendo em toda a cidade.)

Horário em que costumo atender ligação:
(ex.: de segunda a sexta, das 8h às 18h.)

Quando a pessoa pedir para falar comigo:
(ex.: diga que eu retorno ainda hoje e anote o assunto.)

Endereço / onde me encontrar (só se quiser que ela diga):

Preços e serviços (só se quiser que ela diga):

Pessoas especiais (o que fazer quando elas ligarem):
(ex.: se a Maria ligar, diga que eu ligo de volta em 10 minutos.)

O que ela NUNCA deve falar:
(ex.: meu endereço, quanto eu cobro.)
"""

MODELO_INFORMACOES_EN = """\
# INFORMATION FOR THE WHATSAPP ASSISTANT
#
# Everything written here can be used by the assistant to talk to whoever
# calls. Write it your own way, as if you were explaining it to a person.
# Lines starting with # are just explanations and are ignored.
# You can create other .txt files in this same folder (prices, hours,
# address, FAQ): she reads all of them.
#
# Do NOT write anything here that you would not want a stranger to know.

My name: {dono}

About me / my work:
(e.g.: I am an electrician and I work all over town.)

Hours when I usually take calls:
(e.g.: Monday to Friday, 8 am to 6 pm.)

When someone asks to talk to me:
(e.g.: say I will call back today and write down the subject.)

Address / where to find me (only if you want her to say it):

Prices and services (only if you want her to say them):

Special people (what to do when they call):
(e.g.: if Mary calls, say I will call her back in 10 minutes.)

What she must NEVER say:
(e.g.: my address, how much I charge.)
"""


def garantir_pastas() -> Path:
    """Cria a pasta do dono e o TXT de exemplo (so' se ainda nao existir)."""
    pasta = pasta_do_dono()
    pasta.mkdir(parents=True, exist_ok=True)
    pasta_ligacoes().mkdir(parents=True, exist_ok=True)
    info = arq_informacoes()
    if not info.exists():
        modelo = MODELO_INFORMACOES_EN if _ingles() else MODELO_INFORMACOES
        info.write_text(modelo.format(dono=_nome_do_dono()), encoding="utf-8")
    return pasta


_IGNORAR_NA_BASE = {"recados.txt"}
# 05/11: 40 mil -> 120 mil letras (a base grande do Diego: CyberBot, JARVIS, planos). Cabe folgado
# na voz ao vivo (~30 mil fichas) e ela le tudo de novo a cada ligacao.
LIMITE_BASE = 120000
EXTENSOES_BASE = (".txt", ".md", ".csv")


def arquivos_da_base() -> list[str]:
    """Os arquivos que ela le em toda ligacao (nomes, informacoes.txt primeiro)."""
    pasta = pasta_do_dono()
    nomes = []
    if pasta.is_dir():
        nomes = [p.name for p in pasta.iterdir() if p.is_file() and p.suffix.lower() in EXTENSOES_BASE
                 and p.name.lower() not in _IGNORAR_NA_BASE]
    nomes = sorted(nomes, key=lambda n: (n.lower() != "informacoes.txt", n.lower()))
    return nomes + [txt(f"{p.name} (em {p.parent.name})", f"{p.name} (in {p.parent.name})") for p in _extras()]


def adicionar_arquivo(origem: str) -> str:
    """Copia um TXT de qualquer lugar para a pasta dela (sem apagar nada que ja exista)."""
    import shutil  # noqa: PLC0415
    o = Path(origem)
    if not o.is_file() or o.suffix.lower() not in EXTENSOES_BASE:
        raise ValueError("so' arquivos .txt, .md ou .csv")
    garantir_pastas()
    destino = pasta_do_dono() / o.name
    n = 2
    while destino.exists():
        destino = pasta_do_dono() / f"{o.stem} ({n}){o.suffix}"
        n += 1
    shutil.copy2(o, destino)
    return destino.name


def _extras() -> list[Path]:
    """Os arquivos de informacao fora da pasta (opcao `arquivos_extras`), so' os que existem."""
    saida = []
    for c in carregar().get("arquivos_extras") or []:
        try:
            p = Path(os.path.expandvars(str(c))).expanduser()
            if p.is_file() and p.suffix.lower() in EXTENSOES_BASE:
                saida.append(p)
        except (OSError, ValueError):
            continue
    return saida


def ler_informacoes() -> str:
    """Junta os .txt/.md/.csv da pasta do dono e os extras (sem as linhas de comentario)."""
    pasta = pasta_do_dono()
    partes: list[str] = []
    total = 0
    vistos: set[str] = set()
    arquivos = []
    if pasta.is_dir():
        arquivos = sorted(
            (p for p in pasta.iterdir() if p.is_file() and p.suffix.lower() in EXTENSOES_BASE
             and p.name.lower() not in _IGNORAR_NA_BASE),
            key=lambda p: (p.name.lower() != "informacoes.txt", p.name.lower()),
        )
    arquivos += [p for p in _extras() if p not in arquivos]
    for arq in arquivos:
        try:
            bruto = arq.read_bytes()[:LIMITE_BASE]
        except OSError:
            continue
        texto = None
        for cod in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                texto = bruto.decode(cod)
                break
            except UnicodeDecodeError:
                continue
        if not texto:
            continue
        linhas = [ln.rstrip() for ln in texto.splitlines() if not ln.lstrip().startswith("#")]
        # Os "(ex.: ...)" do modelo sao exemplo, nao informacao do dono.
        linhas = [ln for ln in linhas if not re.match(r"^\s*\((ex\.|e\.g\.):", ln)]
        corpo = "\n".join(linhas).strip()
        corpo = re.sub(r"\n{3,}", "\n\n", corpo)
        if not corpo:
            continue
        # O mesmo texto em dois arquivos (a base copiada para a pasta E ligada de fora) entra uma vez so'.
        if corpo in vistos:
            continue
        vistos.add(corpo)
        bloco = f"[{arq.name}]\n{corpo}"
        if total + len(bloco) > LIMITE_BASE:
            bloco = bloco[: max(0, LIMITE_BASE - total)]
        partes.append(bloco)
        total += len(bloco)
        if total >= LIMITE_BASE:
            break
    return "\n\n".join(partes)


def ultimos_recados(qtd: int = 5) -> list[str]:
    """As ultimas `qtd` ligacoes do recados.txt, cada uma numa linha so'.

    Desde 05/11 cada ligacao e' um BLOCO: a 1a linha (data - nome [URGENTE] [RETORNAR]) e as
    de baixo com espaco na frente (resumo, Recado:, Compromisso:)."""
    try:
        bruto = arq_recados().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    blocos: list[list[str]] = []
    for ln in bruto:
        if not ln.strip():
            continue
        if ln.startswith((" ", "\t")) and blocos:
            blocos[-1].append(ln.strip())
        else:
            blocos.append([ln.strip()])
    return [" · ".join(b) for b in blocos[-qtd:]]


# ─────────────────────────────────────────────────────────────────────────────
# VOZES (as mesmas da engrenagem: core.personas)
# ─────────────────────────────────────────────────────────────────────────────
def vozes() -> list[tuple[str, str, str]]:
    """(chave, nome na tela, nome do timbre na Gemini)."""
    saida = []
    try:
        from core.personas import PERSONAGENS  # noqa: PLC0415
        for chave, item in PERSONAGENS.items():
            timbre = item.get("voz_gemini")
            if item.get("base") == "__gemini__" and timbre:
                saida.append((chave, str(item.get("nome") or chave), str(timbre)))
    except Exception:
        pass
    if not saida:
        saida = [("charon", "JARVIS", "Charon"), ("leda", "Leda", "Leda")]
    return saida


def timbre_da_voz(chave: str) -> str:
    chave = _norm(chave)
    for k, nome, timbre in vozes():
        if chave in (_norm(k), _norm(nome), _norm(timbre)):
            return timbre
    return "Leda"


def nome_da_voz(chave: str) -> str:
    chave = _norm(chave)
    for k, nome, timbre in vozes():
        if chave in (_norm(k), _norm(nome), _norm(timbre)):
            return nome
    return "Leda"


def chave_da_voz(falado: str) -> str | None:
    falado = _norm(falado)
    if not falado:
        return None
    for k, nome, timbre in vozes():
        for alvo in (_norm(k), _norm(nome), _norm(timbre)):
            if alvo and (falado == alvo or re.search(rf"\b{re.escape(alvo)}\b", falado)):
                return k
    return None


# ─────────────────────────────────────────────────────────────────────────────
# AS FRASES DO DONO
# ─────────────────────────────────────────────────────────────────────────────
def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", str(t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return " ".join("".join(c if c.isalnum() else " " for c in t).split())


_RE_DONO = re.compile(
    r"\b(eu (mesmo )?atendo|eu (mesmo )?falo|deixa que eu|deixa comigo|passa (ela |ele |a ligacao )?(pra|para) mim|"
    r"me passa|transfere|eu vou atender|vou atender eu|eu quero atender|eu quero falar"
    # ingles (v1.0.39, cliente do Canada)
    r"|i ll (answer|take|get)( it| this| the call)?|i will (answer|take)( it| this| the call)?"
    r"|let me (answer|take|talk)|leave it to me|put (it|him|her|them|the call) through"
    r"|pass (it|him|her|them|the call) to me|transfer( it| the call)?( to me)?|i want to (answer|talk))\b")
_RE_RECUSAR = re.compile(
    r"\b(recusa|recusar|rejeita|rejeitar|nao atende|nao atenda|nao quero atender|desliga|derruba|ignora|"
    r"nao posso atender"
    r"|decline|reject|refuse|don t answer|dont answer|do not answer|hang up|ignore( it| the call)?"
    r"|i can t (answer|talk)|i cannot (answer|talk)|not now)\b")
_RE_DEIXA_TOCAR = re.compile(r"\b(deixa tocar|deixa ai|deixa quieto|nao faz nada|let it ring|leave it|do nothing)\b")
_RE_SECRETARIA = re.compile(
    r"\b(atende|atenda|atender|pode atender|atende (ai|ele|ela|pra mim|por mim)|secretaria|fala com (ele|ela)|"
    r"conversa com (ele|ela)|ve o que (ele|ela) quer|ve o que e"
    r"|answer|pick up|pick it up|you answer|you take it|take the call|go ahead|talk to (him|her|them)"
    r"|see what (he|she|they) wants?|assistant|secretary)\b")
_RE_MSG = re.compile(r"\b(manda|mande|fala|diz|diga|avisa|escreve|responde)( pra (ele|ela)| para (ele|ela))? que (.+)$")
_RE_MSG_EN = re.compile(r"\b(tell|text|message|say|let)( (him|her|them))?( know)? that (.+)$")


def interpretar_decisao(texto: str) -> dict | None:
    """Fala do dono enquanto a ligacao toca -> {'decisao': ..., 'mensagem': ...}.

    secretaria | dono | recusar | ignorar. Devolve None quando a frase nao e'
    sobre a ligacao (ai ela segue para o JARVIS normal)."""
    t = _norm(texto)
    if not t:
        return None
    if _RE_DONO.search(t):
        return {"decisao": "dono"}
    if _RE_RECUSAR.search(t):
        msg = ""
        m = _RE_MSG.search(t)
        if m:
            # Recupera o trecho com acentos da frase original, do "que" em diante.
            original = str(texto or "")
            achou = re.search(r"\bque\b(.+)$", original, re.IGNORECASE)
            msg = (achou.group(1) if achou else m.group(5)).strip(" .,!")
        else:
            m = _RE_MSG_EN.search(t)
            if m:
                achou = re.search(r"\bthat\b(.+)$", str(texto or ""), re.IGNORECASE)
                msg = (achou.group(1) if achou else m.groups()[-1]).strip(" .,!")
        if msg:
            msg = msg[0].upper() + msg[1:]
        return {"decisao": "recusar", "mensagem": msg}
    if _RE_DEIXA_TOCAR.search(t):
        return {"decisao": "ignorar"}
    if _RE_SECRETARIA.search(t) or t in ("sim", "pode", "pode sim", "ok", "beleza", "vai",
                                         "yes", "yeah", "yep", "sure", "please", "go"):
        return {"decisao": "secretaria"}
    return None


_RE_DURANTE = {
    "transferir": _RE_DONO,
    "encerrar": re.compile(r"\b(desliga|encerra|termina|finaliza)( a| essa)? (ligacao|chamada)\b|\bdesliga ai\b"
                           r"|\b(end|finish|terminate)( the| this)? call\b|\bhang up\b"),
}


def interpretar_durante_ligacao(texto: str) -> str | None:
    t = _norm(texto)
    for acao, rx in _RE_DURANTE.items():
        if rx.search(t):
            return acao
    return None


def nome_bate(nome: str, lista) -> bool:
    """O contato que liga esta' numa das listas? Sem acento, sem caixa, aceita numero."""
    n = _norm(nome)
    dig = re.sub(r"\D", "", str(nome or ""))
    for item in lista or []:
        alvo = _norm(item)
        if not alvo:
            continue
        dig_alvo = re.sub(r"\D", "", str(item))
        if len(dig_alvo) >= 8 and dig and (dig.endswith(dig_alvo[-8:]) or dig_alvo.endswith(dig[-8:])):
            return True
        if alvo == n or re.search(rf"\b{re.escape(alvo)}\b", n):
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# PONTE COM O MOTOR (processo separado)
# ─────────────────────────────────────────────────────────────────────────────
_abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _pid_vivo(pid: int) -> bool:
    try:
        import psutil  # noqa: PLC0415
        return psutil.pid_exists(int(pid))
    except Exception:
        return True


def estado_motor() -> dict | None:
    try:
        dados = json.loads(ARQ_ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not dados.get("porta") or not _pid_vivo(dados.get("pid", 0)):
        try:
            ARQ_ESTADO.unlink()
        except OSError:
            pass
        return None
    return dados


def motor_rodando() -> bool:
    return ARQ_ESTADO.exists() and estado_motor() is not None


def _pedido(metodo: str, caminho: str, corpo: dict | None, espera: float) -> dict:
    e = estado_motor()
    if not e:
        return {"ok": False, "erro": "a secretaria nao esta rodando"}
    req = urllib.request.Request(
        f"http://127.0.0.1:{e['porta']}{caminho}",
        data=json.dumps(corpo).encode("utf-8") if corpo is not None else None,
        headers={"Content-Type": "application/json", "X-Token": e["token"]},
        method=metodo,
    )
    try:
        with _abridor.open(req, timeout=espera) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"ok": False, "erro": str(exc)[:160]}


def comando(acao: str, dados: dict | None = None, espera: float = 8.0) -> dict:
    return _pedido("POST", "/api/cmd", {"acao": acao, "dados": dados or {}}, espera)


def _matar_navegador_da_secretaria() -> int:
    """Sobra de navegador com o perfil da secretaria (motor morto a forca)."""
    perfil = str(pasta_navegador()).lower()
    n = 0
    try:
        import psutil  # noqa: PLC0415
        for p in psutil.process_iter(["name", "cmdline"]):
            try:
                nome = (p.info.get("name") or "").lower()
                if nome not in ("msedge.exe", "chrome.exe", "chromium.exe", "chrome", "msedge"):
                    continue
                linha = " ".join(p.info.get("cmdline") or []).lower()
                if perfil and perfil in linha:
                    p.kill()
                    n += 1
            except Exception:
                continue
    except Exception:
        pass
    return n


def fechar_motor(espera: float = 3.0) -> bool:
    """O JARVIS fechando: o motor fecha o navegador e sai; o que sobrar, sai a forca."""
    e = estado_motor()
    if not e:
        return True
    _pedido("POST", "/api/host", {"acao": "fechar"}, 1.5)
    fim = time.monotonic() + espera
    while time.monotonic() < fim:
        if not motor_rodando():
            return True
        time.sleep(0.15)
    try:
        import psutil  # noqa: PLC0415
        psutil.Process(int(e["pid"])).kill()
    except Exception:
        pass
    _matar_navegador_da_secretaria()
    try:
        ARQ_ESTADO.unlink()
    except OSError:
        pass
    return False


class Ponte:
    """O lado do JARVIS: sobe o motor, recebe os eventos, manda as decisoes.

    `ao_evento(evento: dict)` e' chamado numa linha separada (nunca no Qt).
    """

    def __init__(self, ao_evento, log=None):
        self._ao_evento = ao_evento
        self._log = log or (lambda texto: None)
        self._parar = threading.Event()
        self._linha = None
        self._trava = threading.Lock()
        self._ultimo_abrir = 0.0

    # -- ciclo de vida ---------------------------------------------------------
    def iniciar(self) -> bool:
        """Sobe o motor (se a secretaria estiver ligada) e a escuta dos eventos."""
        if not carregar().get("ligada"):
            return False
        try:
            garantir_pastas()
        except OSError as exc:
            self._log(f"[Secretaria] nao criei a pasta das informacoes: {exc}")
        ok = self._subir_motor()
        if ok and (self._linha is None or not self._linha.is_alive()):
            self._parar.clear()
            self._linha = threading.Thread(target=self._escutar, daemon=True, name="secretaria-eventos")
            self._linha.start()
        return ok

    def _subir_motor(self) -> bool:
        if motor_rodando():
            return True
        if not MOTOR.is_file():
            self._log("[Secretaria] motor nao encontrado")
            return False
        with self._trava:
            if motor_rodando():
                return True
            if time.monotonic() - self._ultimo_abrir < 8.0:
                return True
            self._ultimo_abrir = time.monotonic()
            ARQ_LOG.parent.mkdir(parents=True, exist_ok=True)
            cmd = [sys.executable, str(MOTOR), "--pai", str(os.getpid()), "--token", secrets.token_hex(16)]
            opcoes: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                            "stderr": subprocess.DEVNULL, "cwd": str(MOTOR.parent)}
            if sys.platform == "win32":
                opcoes["creationflags"] = 0x08000000      # CREATE_NO_WINDOW
            subprocess.Popen(cmd, **opcoes)
        # O navegador leva alguns segundos; quem chama nao espera por ele.
        fim = time.monotonic() + 20.0
        while time.monotonic() < fim:
            if motor_rodando():
                return True
            time.sleep(0.2)
        self._log("[Secretaria] o motor nao respondeu ao subir")
        return False

    def parar(self) -> None:
        self._parar.set()
        if motor_rodando():
            fechar_motor(6.0)

    def rodando(self) -> bool:
        return motor_rodando()

    # -- eventos ---------------------------------------------------------------
    def _escutar(self) -> None:
        desde = 0
        falhas = 0
        while not self._parar.is_set():
            if not motor_rodando():
                if not carregar().get("ligada"):
                    time.sleep(2.0)
                    continue
                # Caiu: tenta subir de novo, com calma.
                falhas += 1
                time.sleep(min(30.0, 3.0 * falhas))
                if self._parar.is_set():
                    break
                self._subir_motor()
                desde = 0
                continue
            r = _pedido("GET", f"/api/eventos?desde={desde}", None, 30.0)
            if not r.get("ok"):
                time.sleep(1.0)
                continue
            falhas = 0
            for ev in r.get("eventos") or []:
                try:
                    desde = max(desde, int(ev.get("n") or 0))
                except (TypeError, ValueError):
                    pass
                try:
                    self._ao_evento(ev)
                except Exception as exc:
                    self._log(f"[Secretaria] erro ao tratar evento {ev.get('tipo')}: {exc}")

    # -- comandos ----------------------------------------------------------------
    def decidir(self, chamada: int, decisao: str, mensagem: str = "") -> dict:
        return comando("decidir", {"id": chamada, "decisao": decisao, "mensagem": mensagem})

    def responder(self, pergunta: int, texto: str) -> dict:
        return comando("responder", {"pid": pergunta, "texto": texto})

    def presenca(self, presente: bool) -> dict:
        return comando("presenca", {"presente": bool(presente)}, 3.0)

    def recarregar(self) -> dict:
        return comando("recarregar", {}, 3.0)

    def mostrar(self) -> dict:
        return comando("mostrar", {}, 6.0)

    def estado(self) -> dict:
        return comando("estado", {}, 4.0)
