# -*- coding: utf-8 -*-
"""INICIAR COM O WINDOWS — o liga/desliga da engrenagem (24/10/2026).

Pedido do Diego: o cliente marca a opcao e, dali em diante, toda vez que o PC
liga o NIA abre sozinho.

O jeito escolhido e o mesmo dos programas comuns: um valor na chave `Run` do
USUARIO (HKCU). Nao pede administrador — o instalador e `lowest` —, vale so para
quem marcou, e aparece em Gerenciador de Tarefas > Aplicativos de inicializacao
com o nome "NIA CyberBot", onde o cliente tambem consegue desligar.

O ESTADO E LIDO DO PROPRIO WINDOWS, nunca de um arquivo nosso: se o cliente
desligar pelo Gerenciador de Tarefas (que grava em `StartupApproved`, sem apagar
o `Run`), a engrenagem tem de mostrar DESLIGADA, e um .json ficaria mentindo.

No Linux a mesma opcao vira o `.desktop` de `~/.config/autostart`, que GNOME,
KDE, XFCE e Cinnamon leem ao entrar. No Mac a opcao nao aparece.

O desinstalador apaga o valor (`[Registry]` com `uninsdeletevalue` no .iss), e o
`desinstalar.sh` do Linux apaga o `.desktop`: ninguem fica com o Windows tentando
abrir um NIA que nao existe mais.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PASTA_APP = Path(__file__).resolve().parents[1]
NOME = "NIA CyberBot"
# Nome gravado no Registro (e no .desktop) pelas versoes com o nome antigo.
# Continua sendo reconhecido para que quem ja tinha marcado "abrir com o
# Windows" nao fique com um valor perdido apontando para o exe velho.
NOME_ANTIGO = "JARVIS CyberBot"

_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APROVADO = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"

_E_WINDOWS = sys.platform.startswith("win")
_E_LINUX = sys.platform.startswith("linux")

# Linux: o nia.sh fica um nivel acima da pasta app (ver instalar.sh).
_AUTOSTART = Path(os.path.expanduser("~/.config/autostart/nia-cyberbot.desktop"))
_AUTOSTART_ANTIGO = Path(os.path.expanduser("~/.config/autostart/jarvis-cyberbot.desktop"))


def _lancadores() -> tuple[Path | None, Path | None]:
    """(script, icone): nome novo first; instante antigo continua valendo."""
    sh = next((p for p in (PASTA_APP.parent / "nia.sh", PASTA_APP.parent / "jarvis.sh")
               if p.is_file()), None)
    ico = next((p for p in (PASTA_APP.parent / "nia.png", PASTA_APP.parent / "jarvis.png")
                if p.is_file()), None)
    return sh, ico


def disponivel() -> bool:
    """A opcao aparece na engrenagem? (Windows e Linux; no Mac, nao.)"""
    if _E_WINDOWS:
        return _comando_windows() is not None
    if _E_LINUX:
        return _lancadores()[0] is not None
    return False


def _comando_windows() -> str | None:
    """O que o Windows roda ao ligar: o mesmo lancador do atalho da area de
    trabalho, que ja entra na pasta certa e chama o pythonw."""
    for exe in (PASTA_APP / "NIA-CyberBot.exe", PASTA_APP / "JARVIS-CyberBot.exe"):
        if exe.is_file():
            return f'"{exe}"'
    return None


def esta_ligado() -> bool:
    try:
        if _E_WINDOWS:
            import winreg  # noqa: PLC0415
            for nome in (NOME, NOME_ANTIGO):
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN) as k:
                        winreg.QueryValueEx(k, nome)
                except FileNotFoundError:
                    continue
                # Desligado pelo Gerenciador de Tarefas: o primeiro byte e impar
                # (03 = desativado, 02 = ativado). Sem valor = ativado.
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _APROVADO) as k:
                        dado, _ = winreg.QueryValueEx(k, nome)
                    if isinstance(dado, bytes) and dado and dado[0] % 2 == 1:
                        continue
                except FileNotFoundError:
                    pass
                return True
            return False
        if _E_LINUX:
            return _AUTOSTART.is_file() or _AUTOSTART_ANTIGO.is_file()
    except Exception:
        pass
    return False


def ligar(querer: bool) -> tuple[bool, str]:
    """Liga ou desliga. Devolve (deu_certo, motivo_se_falhou)."""
    try:
        if _E_WINDOWS:
            return _ligar_windows(querer)
        if _E_LINUX:
            return _ligar_linux(querer)
        return False, "so existe no Windows e no Linux"
    except Exception as exc:
        return False, str(exc)[:120]


def _ligar_windows(querer: bool) -> tuple[bool, str]:
    import winreg  # noqa: PLC0415
    if querer:
        comando = _comando_windows()
        if comando is None:
            return False, "nao achei o NIA-CyberBot.exe"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN) as k:
            winreg.SetValueEx(k, NOME, 0, winreg.REG_SZ, comando)
    else:
        for nome in (NOME, NOME_ANTIGO):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN, 0, winreg.KEY_SET_VALUE) as k:
                    winreg.DeleteValue(k, nome)
            except FileNotFoundError:
                pass
    # Nos dois casos a marca do Gerenciador de Tarefas sai: ao ligar, porque um
    # "desativado" antigo calaria a opcao; ao desligar, para nao sobrar lixo.
    for nome in (NOME, NOME_ANTIGO):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _APROVADO, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, nome)
        except FileNotFoundError:
            pass
    if esta_ligado() != querer:
        return False, "o Windows nao gravou"
    return True, ""


def _ligar_linux(querer: bool) -> tuple[bool, str]:
    if not querer:
        _AUTOSTART.unlink(missing_ok=True)
        _AUTOSTART_ANTIGO.unlink(missing_ok=True)
        return True, ""
    sh, icone = _lancadores()
    if sh is None:
        return False, "nao achei o nia.sh"
    icone = icone or (PASTA_APP.parent / "nia.png")
    _AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
    _AUTOSTART_ANTIGO.unlink(missing_ok=True)   # so um .desktop, senao abre dois
    _AUTOSTART.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={NOME}\n"
        f'Exec="{sh}"\n'
        f"Path={PASTA_APP}\n"
        f"Icon={icone}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n", encoding="utf-8")
    return True, ""


def conferir_caminho() -> None:
    """Chamado ao abrir: se a opcao esta ligada mas aponta para outra pasta
    (o cliente reinstalou em outro lugar), aponta de novo para esta."""
    try:
        if _E_WINDOWS:
            import winreg  # noqa: PLC0415
            comando = _comando_windows()
            if comando is None:
                return
            for nome in (NOME, NOME_ANTIGO):
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN) as k:
                        atual, _ = winreg.QueryValueEx(k, nome)
                except FileNotFoundError:
                    continue
                if str(atual).strip().lower() != comando.lower() or nome != NOME:
                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN) as k:
                        winreg.SetValueEx(k, NOME, 0, winreg.REG_SZ, comando)
                    if nome != NOME:
                        try:
                            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN, 0,
                                                winreg.KEY_SET_VALUE) as k:
                                winreg.DeleteValue(k, nome)
                        except FileNotFoundError:
                            pass
                break
        elif _E_LINUX and (_AUTOSTART.is_file() or _AUTOSTART_ANTIGO.is_file()):
            sh, icone = _lancadores()
            if sh is None:
                return
            if (str(sh) not in _AUTOSTART.read_text(encoding="utf-8")
                    if _AUTOSTART.is_file() else True):
                _ligar_linux(True)
    except Exception:
        pass
