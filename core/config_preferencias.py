# -*- coding: utf-8 -*-
"""Persistência do dashboard experimental de Configurações (sem PyQt).

A engrenagem clássica e o novo dashboard leem e gravam os MESMOS arquivos:

- ``config/persona.json``    voz, personalidade, microfone e saída de áudio;
- ``config/dashboard_config.json``  tema próprio do dashboard (Claro/Escuro).

Este módulo é a fonte de verdade da gravação. As páginas Qt não montam JSON
nem chamam sounddevice diretamente: pedem ao ``ConfigService``. Assim a janela
clássica (que continua usando ``main._carregar_persona``/``_salvar_persona``)
enxerga imediatamente o que o dashboard gravou.

Os apelidos das vozes continuam em ``config/apelidos_voz.json``, através de
``core.personas.definir_apelido``. Nada aqui toca em ``config/cores.json``: as
cores personalizadas do núcleo são independentes deste tema.
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

from core.personas import (ESCOLHA_PADRAO, PERSONAGENS, PERSONALIDADES,
                           apelidos, nome_da_ia, nome_original,
                           validar_apelido)

TEMA_PADRAO = "escuro"
TEMAS = ("claro", "escuro")

_TRAVA = threading.RLock()


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[1]


CONFIG_DIR = _base_dir() / "config"
PERSONA_PADRAO_PATH = CONFIG_DIR / "persona.json"
DASHBOARD_PADRAO_PATH = CONFIG_DIR / "dashboard_config.json"


class PreferenciaInvalida(ValueError):
    """O valor pedido não é aceito pelo formato atual."""


def _ler_json(caminho: Path) -> dict:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _gravar_json(caminho: Path, dados: dict) -> None:
    """Gravação atômica no mesmo diretório, preservando o formato existente."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    temporario.replace(caminho)


def carregar_persona(caminho: Path | str | None = None) -> dict:
    """A escolha atual, com os padrões do motor e as chaves desconhecidas à parte."""
    caminho = Path(caminho) if caminho else PERSONA_PADRAO_PATH
    with _TRAVA:
        dados = _ler_json(caminho)
    resultado = dict(ESCOLHA_PADRAO)
    resultado.update({k: v for k, v in dados.items() if k in ESCOLHA_PADRAO})
    resultado["microfone"] = normalizar_dispositivo(resultado.get("microfone"))
    resultado["saida"] = normalizar_dispositivo(resultado.get("saida"))
    return resultado


def salvar_persona(mudancas: dict, caminho: Path | str | None = None) -> dict:
    """Faz merge com o arquivo existente e grava. Devolve o resultado lido.

    Chaves que o motor ainda não conhece (ou de versões futuras) são mantidas.
    """
    if not isinstance(mudancas, dict):
        raise PreferenciaInvalida("as mudanças precisam ser um dicionário")
    caminho = Path(caminho) if caminho else PERSONA_PADRAO_PATH
    with _TRAVA:
        atual = _ler_json(caminho)
        atual.update({k: v for k, v in mudancas.items() if k in ESCOLHA_PADRAO})
        _gravar_json(caminho, atual)
        dados = _ler_json(caminho)
    resultado = dict(ESCOLHA_PADRAO)
    resultado.update({k: v for k, v in dados.items() if k in ESCOLHA_PADRAO})
    resultado["microfone"] = normalizar_dispositivo(resultado.get("microfone"))
    resultado["saida"] = normalizar_dispositivo(resultado.get("saida"))
    return resultado


def carregar_tema(caminho: Path | str | None = None) -> str:
    caminho = Path(caminho) if caminho else DASHBOARD_PADRAO_PATH
    with _TRAVA:
        dados = _ler_json(caminho)
    tema = str(dados.get("tema") or "").strip().lower()
    return tema if tema in TEMAS else TEMA_PADRAO


def salvar_tema(tema: str, caminho: Path | str | None = None) -> str:
    """Grava só a preferência do dashboard; não mexe em cores.json."""
    tema = str(tema or "").strip().lower()
    if tema not in TEMAS:
        raise PreferenciaInvalida("tema precisa ser 'claro' ou 'escuro'")
    caminho = Path(caminho) if caminho else DASHBOARD_PADRAO_PATH
    with _TRAVA:
        dados = _ler_json(caminho)
        dados["tema"] = tema
        _gravar_json(caminho, dados)
    return tema


def normalizar_dispositivo(valor) -> int | None:
    """None/padrão/``nao-definido`` -> None; índice inteiro -> inteiro.

    O formato antigo grava ``"nao-definido"`` quando ninguém escolheu nada e
    ``None`` quando o cliente escolheu o padrão de propósito. Para a tela os
    dois são a mesma opção; para o motor o comportamento também é equivalente.
    """
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor if valor >= 0 else None
    texto = str(valor).strip().lower()
    if texto in ("", "nao-definido", "não-definido", "padrao", "padrão", "default"):
        return None
    try:
        numero = int(texto)
    except (TypeError, ValueError):
        return None
    return numero if numero >= 0 else None


def _normalizar_mudanca(tipo: str, chave):
    if tipo == "personagem":
        if chave not in PERSONAGENS:
            raise PreferenciaInvalida("voz desconhecida")
        return chave
    if tipo == "personalidade":
        if chave not in PERSONALIDADES:
            raise PreferenciaInvalida("personalidade desconhecida")
        return chave
    if tipo in ("microfone", "saida"):
        return normalizar_dispositivo(chave)
    if tipo == "saudacao":
        return bool(chave)
    raise PreferenciaInvalida(f"tipo de configuração desconhecido: {tipo}")


class ConfigService:
    """Regras de persistência/aplicação usadas pelo dashboard e pelos testes.

    ``host`` é a casca da NIA (``NiaUI``), que expõe ``persona_atual``,
    ``on_persona_change`` e ``write_log``. Quando o motor não está disponível,
    a gravação continua valendo e a tela informa que a aplicação ao vivo falhou.
    """

    def __init__(self, host=None, persona_path: Path | str | None = None,
                 dashboard_path: Path | str | None = None,
                 interface_path: Path | str | None = None):
        self.host = host
        self.persona_path = Path(persona_path) if persona_path else PERSONA_PADRAO_PATH
        self.dashboard_path = (Path(dashboard_path) if dashboard_path
                               else DASHBOARD_PADRAO_PATH)
        # Mesmo arquivo lido por CanvasBackground e VerticalDock. O dashboard
        # atualiza só as chaves de cada controle; nunca substitui o JSON inteiro.
        self.interface_path = (Path(interface_path) if interface_path
                               else CONFIG_DIR / "interface.json")

    # ── leitura ────────────────────────────────────────────────────────────
    def carregar_persona(self) -> dict:
        return carregar_persona(self.persona_path)

    def carregar_tema(self) -> str:
        return carregar_tema(self.dashboard_path)

    def salvar_tema(self, tema: str) -> str:
        return salvar_tema(tema, self.dashboard_path)

    # ── dados que pertencem a outras telas (leitura/escrita existentes) ────
    def carregar_dono(self) -> dict:
        from core import dono  # noqa: PLC0415
        return dono.carregar()

    def salvar_dono(self, mudancas: dict) -> dict:
        from core import dono  # noqa: PLC0415
        return dono.salvar(mudancas)

    def carregar_nomes(self) -> dict:
        from core import nomes_tela  # noqa: PLC0415
        return nomes_tela.carregar()

    def salvar_nomes(self, mudancas: dict) -> dict:
        from core import nomes_tela  # noqa: PLC0415
        return nomes_tela.salvar(mudancas)

    def restaurar_nomes(self) -> None:
        from core import nomes_tela  # noqa: PLC0415
        nomes_tela.voltar_ao_padrao()

    def aplicar_nomes(self) -> None:
        janela = getattr(self.host, "_win", None)
        cb = getattr(janela, "aplicar_nomes", None) if janela is not None else None
        if cb is not None:
            cb()

    def aplicar_tema_no_nucleo(self) -> None:
        janela = getattr(self.host, "_win", None)
        cb = getattr(janela, "aplicar_tema", None) if janela is not None else None
        if cb is not None:
            cb()

    # ── dispositivos ───────────────────────────────────────────────────────
    def listar_microfones(self) -> list[dict]:
        from core.audio_dispositivos import listar  # noqa: PLC0415
        return listar()

    def listar_saidas(self) -> list[dict]:
        from core.audio_dispositivos import listar_saidas  # noqa: PLC0415
        return listar_saidas()

    def testar_microfone(self, indice: int | None) -> dict:
        from core.audio_dispositivos import testar  # noqa: PLC0415
        return testar(indice)

    def tocar_teste(self, indice: int | None) -> dict:
        from core.audio_dispositivos import tocar_teste  # noqa: PLC0415
        return tocar_teste(indice)

    # ── gravação + aplicação ───────────────────────────────────────────────
    def alterar(self, tipo: str, chave, com_amostra: bool = False,
                com_teste: bool = False, forcar: bool = False) -> dict:
        """Grava primeiro e só depois aplica ao motor.

        Devolve ``{"salvo", "aplicado", "aviso", "erro", "inalterado"}``. É
        justamente essa separação que permite dizer "Salvo" mesmo quando a
        aplicação ao vivo falhou.
        """
        resultado = {"salvo": False, "aplicado": False, "aviso": "",
                     "erro": "", "inalterado": False}
        try:
            if tipo == "apelido":
                return self._alterar_apelido(chave, resultado)
            valor = _normalizar_mudanca(tipo, chave)
            atual = self.carregar_persona()
            anterior = atual.get(tipo)
            if not forcar and anterior == valor:
                resultado.update(salvo=True, aplicado=True, inalterado=True)
                return resultado
            dados = salvar_persona({tipo: valor}, self.persona_path)
            self._sincronizar_host(dados)
            resultado["salvo"] = True
        except PreferenciaInvalida as exc:
            resultado["erro"] = str(exc)
            return resultado
        except Exception as exc:
            resultado["erro"] = f"{type(exc).__name__}: {str(exc)[:140]}"
            return resultado

        # A gravação já aconteceu. A falha daqui para baixo é só "ao vivo".
        try:
            aplicado = self._aplicar_no_motor(
                tipo, valor, com_amostra=com_amostra, com_teste=com_teste)
            resultado["aplicado"] = bool(aplicado.get("aplicado"))
            resultado["aviso"] = aplicado.get("aviso", "")
            if not resultado["aplicado"]:
                resultado["erro"] = aplicado.get("erro", "")
        except Exception as exc:
            resultado["erro"] = f"{type(exc).__name__}: {str(exc)[:140]}"
        return resultado

    def _alterar_apelido(self, chave, resultado: dict) -> dict:
        try:
            voz, texto = chave
        except (TypeError, ValueError):
            resultado["erro"] = "apelido inválido"
            return resultado
        if voz not in PERSONAGENS:
            resultado["erro"] = "voz desconhecida"
            return resultado
        ok, limpo, motivo = validar_apelido(voz, texto)
        if not ok:
            resultado["erro"] = motivo
            return resultado
        desejado = "" if limpo == nome_original(voz) else limpo
        if desejado == apelidos().get(voz, ""):
            resultado.update(salvo=True, aplicado=True, inalterado=True)
            return resultado
        from core.personas import definir_apelido  # noqa: PLC0415
        try:
            definir_apelido(voz, texto)
        except ValueError as exc:
            resultado["erro"] = str(exc)
            return resultado
        except Exception as exc:
            resultado["erro"] = f"{type(exc).__name__}: {str(exc)[:140]}"
            return resultado
        self._sincronizar_host(self.carregar_persona())
        resultado["salvo"] = True
        try:
            aplicado = self._aplicar_no_motor("apelido", (voz, texto))
            resultado["aplicado"] = bool(aplicado.get("aplicado"))
            resultado["aviso"] = aplicado.get("aviso", "")
            if not resultado["aplicado"]:
                resultado["erro"] = aplicado.get("erro", "")
        except Exception as exc:
            resultado["erro"] = f"{type(exc).__name__}: {str(exc)[:140]}"
        return resultado

    def ouvir_voz(self, voz: str) -> dict:
        """Toca a amostra real da voz já selecionada, sem regravar a escolha."""
        resultado = {"salvo": None, "aplicado": False, "aviso": "", "erro": ""}
        if voz not in PERSONAGENS:
            resultado["erro"] = "voz desconhecida"
            return resultado
        try:
            aplicado = self._aplicar_no_motor(
                "personagem", voz, com_amostra=True, com_teste=False)
            resultado["aplicado"] = bool(aplicado.get("aplicado"))
            resultado["aviso"] = aplicado.get("aviso", "")
            resultado["erro"] = aplicado.get("erro", "")
        except Exception as exc:
            resultado["erro"] = f"{type(exc).__name__}: {str(exc)[:140]}"
        return resultado

    def _sincronizar_host(self, dados: dict) -> None:
        if self.host is None:
            return
        try:
            self.host.persona_atual = dict(dados)
        except Exception:
            pass

    def _aplicar_no_motor(self, tipo: str, chave, com_amostra: bool = False,
                          com_teste: bool = False) -> dict:
        cb = getattr(self.host, "on_persona_change", None) if self.host else None
        if cb is None:
            return {"aplicado": False,
                    "erro": ("o motor de voz não está disponível nesta sessão; "
                             "a escolha será usada ao reabrir a NIA")}
        retorno = cb(tipo, chave, com_amostra=com_amostra,
                     persistir=False, com_teste=com_teste)
        if retorno is None:
            return {"aplicado": True, "aviso": "", "erro": ""}
        if isinstance(retorno, dict):
            return {
                "aplicado": bool(retorno.get("aplicado", True)),
                "aviso": str(retorno.get("aviso") or ""),
                "erro": str(retorno.get("erro") or ""),
            }
        return {"aplicado": bool(retorno), "aviso": "", "erro": ""}
