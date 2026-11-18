# -*- coding: utf-8 -*-
"""SECRETARIA DO WHATSAPP — a parte da TELA (05/11/2026).

Duas coisas:
  * `pagina(janela)`: a aba SECRETARIA da engrenagem (liga/desliga, como ela
    atende, a voz, o recado do momento, as listas, o TXT das informacoes).
  * o CARTAO da ligacao: aparece no canto da tela quando alguem liga, quando
    ela esta falando, quando ela te pergunta algo e quando a ligacao acaba.
    Fica por cima das outras janelas e nao rouba o foco.

Thread-safe: `mostrar(dados)` pode ser chamado de qualquer linha; quem mexe nos
widgets e' sempre o Qt (sinal da `_Ponte`, criada no `instalar`).
As acoes (botoes do cartao e mudancas na aba) chegam ao JARVIS pelos ganchos
`on_secretaria_acao(acao, dados)` e `on_secretaria_mudou(cfg, ligou_ou_desligou)`
da casca (JarvisUI), postos pelo main.py.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QGuiApplication
from PyQt6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from core import secretaria as SEC


def _t(pt: str, en: str) -> str:
    """O texto na lingua do JARVIS (v1.0.39: a tela da secretaria tambem em ingles)."""
    return SEC.txt(pt, en)

_E: dict = {}            # C (cores) e fx (fonte) da interface, entregues no instalar
_ponte = None
_cartao = None
_casca = None
_ultimo_login = ""       # carregando | qr | conectado (vem dos eventos do motor)
_ultimo_qr = ""          # o codigo das LIGACOES (data:image/png), mostrado na janela do CONECTAR WHATSAPP


def whatsapp_conectado() -> bool:
    """v1.0.40: o WhatsApp do botao CONECTAR WHATSAPP (a ponte) esta' conectado?

    Le o status.json que a propria ponte grava (rapido, sem rede: roda no Qt de 1,5 em 1,5 s).
    So' vale se foi o node que gravou e o pid dele esta' vivo."""
    try:
        d = json.loads((SEC.RAIZ / "whatsapp_bridge" / "status.json").read_text(encoding="utf-8", errors="ignore"))
        if str(d.get("writer") or "") != "node" or not d.get("connected"):
            return False
        pid = int(d.get("pid") or 0)
        import psutil  # noqa: PLC0415
        return pid > 0 and psutil.pid_exists(pid)
    except Exception:
        return False


def estado_ligacoes() -> dict:
    """Para a janela do CONECTAR WHATSAPP: a secretaria esta ligada? conectada? qual o codigo?"""
    try:
        ligada = bool(SEC.carregar().get("ligada"))
    except Exception:
        ligada = False
    return {"ligada": ligada, "rodando": SEC.motor_rodando(), "login": _ultimo_login,
            "qr": _ultimo_qr if _ultimo_login == "qr" else ""}


def _mudar(casca, mudancas: dict) -> dict:
    """Grava a opcao e avisa o JARVIS (liga/desliga sobe ou derruba o motor)."""
    antes = SEC.carregar()
    novo = SEC.salvar(mudancas)
    ligou_desligou = ("ligada" in mudancas) and bool(antes.get("ligada")) != bool(novo.get("ligada"))
    cb = getattr(casca, "on_secretaria_mudou", None) if casca is not None else None
    if cb:
        _em_thread(cb, novo, ligou_desligou)
    return novo


def _c(nome: str, padrao: str = "#00d4ff") -> str:
    return getattr(_E.get("C"), nome, padrao)


def _fx(tam: float, peso=None) -> QFont:
    fx = _E.get("fx")
    if fx:
        return fx(tam, peso)
    f = QFont()
    f.setPointSizeF(float(tam))
    if peso is not None:
        f.setWeight(peso)
    return f


def _em_thread(fn, *args) -> None:
    threading.Thread(target=fn, args=args, daemon=True, name="secretaria-tela").start()


def _acao(acao: str, dados: dict | None = None) -> None:
    cb = getattr(_casca, "on_secretaria_acao", None) if _casca is not None else None
    if cb:
        _em_thread(cb, acao, dict(dados or {}))


class _Ponte(QObject):
    pedido = pyqtSignal(object)


def instalar(casca, C, fx) -> None:
    """Chamado pelo JarvisUI no Qt, logo que a janela existe."""
    global _ponte, _casca
    _casca = casca
    _E.update(C=C, fx=fx)
    _ponte = _Ponte()
    _ponte.pedido.connect(_no_qt)


def mostrar(dados: dict) -> None:
    if _ponte is not None:
        try:
            _ponte.pedido.emit(dict(dados or {}))
        except RuntimeError:
            pass


def _no_qt(d: dict) -> None:
    global _cartao, _ultimo_login, _ultimo_qr
    try:
        estado = d.get("estado")
        if estado == "login":
            _ultimo_login = str(d.get("login") or "")
            if _ultimo_login == "conectado":
                _ultimo_qr = ""
            return
        if estado == "qr":
            # So' guarda: quem mostra e' a janela do CONECTAR WHATSAPP (nada pula na tela).
            _ultimo_qr = str(d.get("img") or "")
            return
        if estado == "mudo":
            # O dono na ligacao pelo PC: o JARVIS para de ouvir a sala (e volta no fim).
            if _casca is not None:
                try:
                    _casca.muted = bool(d.get("valor"))
                except Exception as exc:  # noqa: BLE001
                    print(f"[secretaria_tela] mudo: {exc}")
            return
        if _cartao is None:
            _cartao = Cartao()
        _cartao.aplicar(d)
    except Exception as exc:  # noqa: BLE001
        print(f"[secretaria_tela] {exc}")


def _botao(texto: str, cor: str | None = None, cheio: bool = False) -> QPushButton:
    b = QPushButton(texto)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFont(_fx(8, QFont.Weight.Bold))
    b.setFixedHeight(30)
    cor = cor or _c("PRI")
    fundo = "rgba(0,229,255,0.10)" if cheio else "transparent"
    b.setStyleSheet(
        f"QPushButton {{ color: {cor}; background: {fundo}; border: 1px solid {cor};"
        f" border-radius: 4px; padding: 0 12px; }}"
        f"QPushButton:hover {{ color: {_c('TEXT')}; border-color: {_c('TEXT')}; }}")
    return b


# ─────────────────────────────────────────────────────────────────────────────
# O CARTAO DA LIGACAO
# ─────────────────────────────────────────────────────────────────────────────
class Cartao(QWidget):
    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedWidth(400)
        self._dados: dict = {}
        self._falas: list[str] = []
        self._contagem_ate = 0.0
        self._relogio = QTimer(self)
        self._relogio.timeout.connect(self._tic)
        self._some = QTimer(self)
        self._some.setSingleShot(True)
        self._some.timeout.connect(self.hide)

        moldura = QFrame(self)
        moldura.setObjectName("moldura")
        moldura.setStyleSheet(
            f"#moldura {{ background: {_c('PANEL', '#010d14')}; border: 1px solid {_c('PRI')}; border-radius: 8px; }}")
        fora = QVBoxLayout(self)
        fora.setContentsMargins(0, 0, 0, 0)
        fora.addWidget(moldura)
        lay = QVBoxLayout(moldura)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)
        topo = QHBoxLayout()
        self.titulo = QLabel("")
        self.titulo.setFont(_fx(10, QFont.Weight.Bold))
        self.titulo.setStyleSheet(f"color: {_c('TEXT')}; background: transparent;")
        self.titulo.setWordWrap(True)
        topo.addWidget(self.titulo, 1)
        fechar = QPushButton("✕")
        fechar.setCursor(Qt.CursorShape.PointingHandCursor)
        fechar.setFixedSize(24, 24)
        fechar.setStyleSheet(f"QPushButton {{ color: {_c('TEXT_DIM')}; background: transparent; border: 0; }}"
                             f"QPushButton:hover {{ color: {_c('TEXT')}; }}")
        fechar.clicked.connect(self.hide)
        topo.addWidget(fechar)
        lay.addLayout(topo)
        self.sub = QLabel("")
        self.sub.setFont(_fx(8))
        self.sub.setStyleSheet(f"color: {_c('TEXT_DIM')}; background: transparent;")
        self.sub.setWordWrap(True)
        lay.addWidget(self.sub)
        self.corpo = QLabel("")
        self.corpo.setFont(_fx(9))
        self.corpo.setStyleSheet(f"color: {_c('TEXT_MED')}; background: transparent;")
        self.corpo.setWordWrap(True)
        self.corpo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.corpo)
        # O QR CODE do WhatsApp da secretaria (o navegador dela fica escondido).
        self.imagem = QLabel("")
        self.imagem.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.imagem.setStyleSheet("background: #ffffff; border-radius: 6px; padding: 8px;")
        self.imagem.hide()
        lay.addWidget(self.imagem, 0, Qt.AlignmentFlag.AlignHCenter)
        self.campo = QLineEdit()
        self.campo.setFont(_fx(9))
        self.campo.setPlaceholderText(_t("Responda aqui (ou fale com o JARVIS)", "Answer here (or talk to JARVIS)"))
        self.campo.setStyleSheet(
            f"QLineEdit {{ color: {_c('TEXT')}; background: transparent; border: 1px solid {_c('BORDER_B')};"
            f" border-radius: 4px; padding: 4px 6px; }} QLineEdit:focus {{ border-color: {_c('PRI')}; }}")
        self.campo.returnPressed.connect(self._responder_digitado)
        lay.addWidget(self.campo)
        self.linha_botoes = QHBoxLayout()
        self.linha_botoes.setSpacing(6)
        lay.addLayout(self.linha_botoes)

    # -- montagem ---------------------------------------------------------------
    def _botoes(self, lista: list[tuple[str, str, str | None]]) -> None:
        while self.linha_botoes.count():
            w = self.linha_botoes.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        for texto, acao, cor in lista:
            b = _botao(texto, cor, cheio=True)
            b.clicked.connect(lambda _=False, a=acao: self._clicou(a))
            self.linha_botoes.addWidget(b)

    def _posicionar(self) -> None:
        self.adjustSize()
        tela = QGuiApplication.primaryScreen()
        if tela is None:
            return
        g = tela.availableGeometry()
        self.move(g.right() - self.width() - 18, g.bottom() - self.height() - 18)

    def _mostrar(self, esconder_em: float = 0.0) -> None:
        self._some.stop()
        self._posicionar()
        self.show()
        self.raise_()
        if esconder_em > 0:
            self._some.start(int(esconder_em * 1000))

    def _tic(self) -> None:
        resta = int(round(self._contagem_ate - time.monotonic()))
        if resta <= 0:
            self._relogio.stop()
            return
        base = self._dados.get("_sub_base", "")
        self.sub.setText(base.replace("{s}", str(resta)))

    def aplicar(self, d: dict) -> None:
        estado = d.get("estado")
        nome = str(d.get("nome") or _t("um contato", "a contact"))
        if estado == "esconder":
            self.hide()
            return
        if estado == "fala":
            quem = nome if d.get("quem") == "pessoa" else _t("Secretária", "Assistant")
            self._falas.append(f"{quem}: {d.get('texto', '')}")
            self._falas = self._falas[-5:]
            if self._dados.get("estado") in ("atendeu",):
                self.corpo.setText("\n".join(self._falas))
                self._posicionar()
            return
        self._relogio.stop()
        self._dados = dict(d)
        self.campo.hide()
        self.campo.clear()
        if estado != "qr":
            self.imagem.hide()
        if estado == "qr":
            self.titulo.setText(_t("📱  Conecte o WhatsApp da secretária", "📱  Connect the assistant's WhatsApp"))
            self.sub.setText(_t("No celular: WhatsApp  →  Aparelhos conectados  →  Conectar aparelho, "
                                "e aponte a câmera para este código. É só uma vez.",
                                "On your phone: WhatsApp  →  Linked devices  →  Link a device, "
                                "and point the camera at this code. Only once."))
            self.corpo.setText("")
            try:
                import base64  # noqa: PLC0415
                from PyQt6.QtGui import QPixmap  # noqa: PLC0415
                bruto = str(d.get("img") or "")
                dados = base64.b64decode(bruto.split(",", 1)[-1]) if bruto else b""
                mapa = QPixmap()
                if dados and mapa.loadFromData(dados):
                    self.imagem.setPixmap(mapa.scaled(250, 250, Qt.AspectRatioMode.KeepAspectRatio,
                                                      Qt.TransformationMode.SmoothTransformation))
                    self.imagem.show()
            except Exception as exc:  # noqa: BLE001
                print(f"[secretaria_tela] qr: {exc}")
            self._botoes([(_t("FECHAR", "CLOSE"), "fechar_cartao", None)])
            self._mostrar()
            return
        if estado == "tocando":
            self._falas = []
            self.titulo.setText(_t(f"📞  {nome} está ligando no WhatsApp", f"📞  {nome} is calling on WhatsApp"))
            auto = d.get("auto")
            if auto:
                self._dados["_sub_base"] = _t("Se você não decidir, a secretária atende em {s} s.",
                                              "If you don't decide, the assistant answers in {s} s.")
                self._contagem_ate = time.monotonic() + float(auto)
                self._tic()
                self._relogio.start(500)
            else:
                self.sub.setText(_t("Ela só está te avisando: decida aqui ou fale com o JARVIS.",
                                    "She is just letting you know: decide here or talk to JARVIS."))
            self.corpo.setText("")
            self._botoes([(_t("SECRETÁRIA ATENDE", "ASSISTANT ANSWERS"), "secretaria", _c("GREEN", "#00ff88")),
                          (_t("EU ATENDO", "I'LL ANSWER"), "dono", None),
                          (_t("RECUSAR", "DECLINE"), "recusar", _c("RED", "#ff3355"))])
            self._mostrar(esconder_em=60)
        elif estado == "atendeu":
            if d.get("quem") == "dono":
                self.titulo.setText(_t(f"📞  Você está na ligação com {nome}", f"📞  You are on the call with {nome}"))
                self.sub.setText(_t("Fale normalmente pelo microfone do PC. O JARVIS fica sem ouvir até a ligação acabar.",
                                    "Talk normally through the PC microphone. JARVIS stops listening until the call ends."))
                self.corpo.setText("")
                self._botoes([(_t("DESLIGAR", "HANG UP"), "encerrar", _c("RED", "#ff3355")),
                              (_t("VER A LIGAÇÃO", "SHOW THE CALL"), "mostrar", None)])
                self._mostrar()
            else:
                self.titulo.setText(_t(f"🎧  A secretária está falando com {nome}", f"🎧  The assistant is talking to {nome}"))
                self.sub.setText(_t(f"Voz {d.get('voz') or ''}. Você pode assumir a ligação a qualquer momento.",
                                    f"Voice {d.get('voz') or ''}. You can take over the call at any time."))
                self.corpo.setText("\n".join(self._falas))
                self._botoes([(_t("PASSAR PRA MIM", "PASS IT TO ME"), "transferir", _c("GREEN", "#00ff88")),
                              (_t("ENCERRAR", "END CALL"), "encerrar", _c("RED", "#ff3355"))])
                self._mostrar()
        elif estado == "pergunta":
            self.titulo.setText(_t(f"❓  {nome} quer saber", f"❓  {nome} wants to know"))
            self._dados["_sub_base"] = _t("Ela está esperando sua resposta ({s} s). Fale ou digite.",
                                          "She is waiting for your answer ({s} s). Speak or type.")
            self._contagem_ate = time.monotonic() + float(d.get("espera") or 30)
            self._tic()
            self._relogio.start(500)
            self.corpo.setText(str(d.get("pergunta") or ""))
            self.campo.show()
            self._botoes([(_t("RESPONDER", "ANSWER"), "responder", _c("GREEN", "#00ff88")),
                          (_t("NÃO POSSO AGORA", "I CAN'T NOW"), "nao_posso", None),
                          (_t("ANOTA O RECADO", "TAKE A MESSAGE"), "anota", None)])
            self._mostrar()
            self.activateWindow()
            self.campo.setFocus()
        elif estado == "pergunta_fim":
            self._dados = dict(self._dados, estado="atendeu")
            self.aplicar({"estado": "atendeu", "nome": nome, "quem": "secretaria", "voz": d.get("voz", "")})
        elif estado == "fim":
            # O QUE IMPORTA EM DESTAQUE (05/11): recado, compromisso, retorno. Com algum deles o
            # cartao FICA ate o dono fechar; sem nada importante, some sozinho.
            recados = [r for r in (d.get("recados") or []) if isinstance(r, dict) and r.get("recado")]
            compromissos = [str(c) for c in (d.get("compromissos") or []) if str(c).strip()]
            importante = bool(recados or compromissos or d.get("retornar") or d.get("urgente"))
            self.titulo.setText(("⚠  " if d.get("urgente") else "📌  " if importante else "✔  ")
                                + _t(f"Ligação de {nome}", f"Call from {nome}")
                                + (_t(" — URGENTE", " — URGENT") if d.get("urgente") else ""))
            self.sub.setText(str(d.get("sub") or ""))
            linhas = [str(d.get("resumo") or "")]
            for r in recados:
                linhas.append(_t("✉  Recado: ", "✉  Message: ") + str(r.get('recado'))
                              + ((_t("  (retorno: ", "  (call back: ") + f"{r.get('retorno')})") if r.get("retorno") else ""))
            for c in compromissos:
                linhas.append(_t("📅  Compromisso: ", "📅  Appointment: ") + c)
            if d.get("retornar"):
                linhas.append(_t("☎  Você precisa retornar.", "☎  You need to call back."))
            self.corpo.setText("\n".join(l for l in linhas if l))
            botoes = []
            if d.get("arquivo"):
                botoes.append((_t("VER A CONVERSA", "SEE THE CONVERSATION"), "abrir_arquivo", None))
            botoes.append((_t("FECHAR", "CLOSE"), "fechar_cartao", None))
            self._botoes(botoes)
            self._mostrar(esconder_em=0 if importante else 40)
        elif estado == "aviso":
            self.titulo.setText(str(d.get("titulo") or _t("Secretária", "Assistant")))
            self.sub.setText("")
            self.corpo.setText(str(d.get("texto") or ""))
            botoes = []
            if d.get("botao_abrir"):
                botoes.append((_t("ABRIR O WHATSAPP DELA", "OPEN HER WHATSAPP"), "mostrar", None))
            botoes.append((_t("FECHAR", "CLOSE"), "fechar_cartao", None))
            self._botoes(botoes)
            self._mostrar(esconder_em=float(d.get("some_em") or 0))

    # -- cliques ------------------------------------------------------------------
    def _responder_digitado(self) -> None:
        self._clicou("responder")

    def _clicou(self, acao: str) -> None:
        d = self._dados
        if acao == "fechar_cartao":
            self.hide()
            return
        if acao == "abrir_arquivo":
            _abrir(d.get("arquivo") or "")
            return
        if acao == "mostrar":
            _acao("mostrar")
            if self._dados.get("estado") != "atendeu":
                self.hide()
            return
        if acao in ("secretaria", "dono", "recusar"):
            _acao("decidir", {"id": d.get("id"), "decisao": acao})
            self.sub.setText(_t("Certo...", "Okay..."))
            self._relogio.stop()
            return
        if acao in ("transferir", "encerrar"):
            _acao(acao, {"id": d.get("id")})
            self.sub.setText(_t("Certo...", "Okay..."))
            return
        if acao in ("responder", "nao_posso", "anota"):
            texto = {"nao_posso": _t("Ele não pode responder agora.", "I can't answer right now."),
                     "anota": _t("Anota o recado que eu retorno depois.", "Take a message, I'll call back later."),
                     }.get(acao) or self.campo.text().strip()
            if not texto:
                self.campo.setFocus()
                return
            _acao("responder", {"pid": d.get("pid"), "texto": texto, "id": d.get("id")})
            self.campo.hide()
            self.sub.setText(_t("Resposta enviada para ela.", "Answer sent to her."))
            self._relogio.stop()


def _abrir(caminho: str) -> None:
    if not caminho:
        return
    try:
        if sys.platform == "win32":
            os.startfile(caminho)  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", caminho])
    except OSError:
        pass


def _abrir_no_bloco(caminho: str) -> None:
    try:
        if sys.platform == "win32":
            subprocess.Popen(["notepad.exe", caminho])
        else:
            subprocess.Popen(["xdg-open", caminho])
    except OSError:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# A ABA DA ENGRENAGEM
# ─────────────────────────────────────────────────────────────────────────────
def pagina(janela) -> QWidget:
    if not _E:
        try:
            import ui as _ui_mod  # noqa: PLC0415
            _E.update(C=_ui_mod.C, fx=_ui_mod._fx)  # noqa: SLF001
        except Exception:
            pass
    cfg = SEC.carregar()
    casca = getattr(janela, "_ui", None) or _casca

    def _mudou(mudancas: dict) -> None:
        _mudar(casca, mudancas)
        _atualizar_estado()

    externa = QWidget()
    lay_ext = QVBoxLayout(externa)
    lay_ext.setContentsMargins(0, 0, 0, 0)
    rolagem = QScrollArea()
    rolagem.setWidgetResizable(True)
    rolagem.setFrameShape(QFrame.Shape.NoFrame)
    rolagem.setStyleSheet("QScrollArea { background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }")
    lay_ext.addWidget(rolagem)
    pag = QWidget()
    rolagem.setWidget(pag)
    lay = QVBoxLayout(pag)
    lay.setContentsMargins(0, 8, 8, 8)
    lay.setSpacing(8)

    def _rot(texto: str, tam: float = 8, cor: str = "TEXT_DIM", negrito: bool = False) -> QLabel:
        lab = QLabel(texto)
        lab.setWordWrap(True)
        lab.setFont(_fx(tam, QFont.Weight.Bold if negrito else None))
        lab.setStyleSheet(f"color: {_c(cor)}; background: transparent;")
        return lab

    lay.addWidget(_rot(_t("SECRETÁRIA DO WHATSAPP  ·  ela atende as suas ligações e responde as suas mensagens",
                          "WHATSAPP ASSISTANT  ·  she answers your calls and replies to your messages"), 9, "PRI", True))
    lay.addWidget(_rot(_t("Quando alguém te liga no WhatsApp, ela atende com a voz que você escolher, conversa ao vivo, "
                          "te pergunta o que precisar e anota o recado. Quem ligou e o que ficou combinado aparecem "
                          "escritos no chat do JARVIS (ele não fala nada em voz alta). Ela sempre se apresenta como "
                          "assistente virtual.",
                          "When someone calls you on WhatsApp, she answers with the voice you choose, talks live, asks "
                          "you whatever she needs and takes a message. Who called and what was agreed show up written "
                          "in the JARVIS chat (JARVIS says nothing out loud). She always introduces herself as a "
                          "virtual assistant.")))
    lay.addWidget(_rot(_t("LIGAÇÕES", "CALLS"), 8, "PRI", True))

    # -- liga / desliga + estado
    linha = QHBoxLayout()
    b_liga = _botao("")
    b_liga.setFixedHeight(34)
    estado_lab = _rot("", 8, "TEXT_MED")

    def _pintar_liga() -> None:
        ligada = SEC.carregar().get("ligada")
        b_liga.setText(_t("ATENDENDO LIGAÇÕES  ·  clique para desligar", "ANSWERING CALLS  ·  click to turn off") if ligada
                       else _t("LIGAÇÕES DESLIGADAS  ·  clique para ligar", "CALLS OFF  ·  click to turn on"))
        cor = _c("GREEN", "#00ff88") if ligada else _c("TEXT_DIM")
        b_liga.setStyleSheet(
            f"QPushButton {{ color: {cor}; background: {'rgba(0,255,136,0.08)' if ligada else 'transparent'};"
            f" border: 1px solid {cor}; border-radius: 4px; padding: 0 16px; }}"
            f"QPushButton:hover {{ color: {_c('TEXT')}; border-color: {_c('TEXT')}; }}")

    def _atualizar_estado() -> None:
        _pintar_liga()
        if not SEC.carregar().get("ligada"):
            estado_lab.setText(_t("Desligada: ninguém atende as ligações por você.", "Off: nobody answers calls for you."))
        elif not SEC.motor_rodando():
            estado_lab.setText(_t("Ligando...", "Starting..."))
        elif _ultimo_login == "conectado":
            estado_lab.setText(_t("Pronta: as ligações estão conectadas.", "Ready: calls are connected."))
        elif _ultimo_login == "qr":
            estado_lab.setText(_t("Falta conectar as ligações: clique em CONECTAR WHATSAPP e leia o segundo código.",
                                  "Calls are not connected yet: click CONNECT WHATSAPP and scan the second code."))
        else:
            estado_lab.setText(_t("Ligando...", "Starting..."))

    def _alternar() -> None:
        _mudou({"ligada": not SEC.carregar().get("ligada")})

    b_liga.clicked.connect(_alternar)
    linha.addWidget(b_liga)
    b_ver = _botao(_t("ABRIR O WHATSAPP DELA", "OPEN HER WHATSAPP"))
    b_ver.clicked.connect(lambda: _acao("mostrar"))
    linha.addWidget(b_ver)
    linha.addStretch()
    lay.addLayout(linha)
    lay.addWidget(estado_lab)
    relogio = QTimer(pag)
    relogio.timeout.connect(_atualizar_estado)
    relogio.start(1500)
    _atualizar_estado()

    # -- v1.0.40: as MENSAGENS (a secretaria no chat, core/secretaria_chat.py)
    lay.addWidget(_rot(_t("MENSAGENS  ·  ela responde quem te manda mensagem no WhatsApp (texto e áudio)",
                          "MESSAGES  ·  she replies to whoever messages you on WhatsApp (text and audio)"), 8, "PRI", True))
    lay.addWidget(_rot(_t("Usa as mesmas informações das ligações e a voz escolhida mais abaixo, e ouve os áudios que "
                          "mandarem. Nunca responde grupo e fica quieta na conversa em que você mesmo escreveu nos "
                          "últimos 30 minutos. Usa o WhatsApp do botão CONECTAR WHATSAPP. Tudo fica salvo na pasta "
                          "dela, em \"mensagens\".",
                          "She uses the same information as the calls and the voice chosen below, and listens to the "
                          "audio people send. She never replies in groups and stays quiet in a chat where you wrote "
                          "yourself in the last 30 minutes. She uses the WhatsApp from the CONNECT WHATSAPP button. "
                          "Everything is saved in her folder, under \"mensagens\".")))
    linha_chat = QHBoxLayout()
    b_chat = _botao("")
    b_chat.setFixedHeight(34)
    estado_chat = _rot("", 8, "TEXT_MED")
    botoes_fmt: dict[str, QPushButton] = {}

    def _pintar_chat() -> None:
        c = SEC.carregar()
        ligado = bool(c.get("chat_ligado"))
        b_chat.setText(_t("RESPONDENDO MENSAGENS  ·  clique para desligar", "REPLYING TO MESSAGES  ·  click to turn off")
                       if ligado else _t("MENSAGENS DESLIGADAS  ·  clique para ligar", "MESSAGES OFF  ·  click to turn on"))
        cor = _c("GREEN", "#00ff88") if ligado else _c("TEXT_DIM")
        b_chat.setStyleSheet(
            f"QPushButton {{ color: {cor}; background: {'rgba(0,255,136,0.08)' if ligado else 'transparent'};"
            f" border: 1px solid {cor}; border-radius: 4px; padding: 0 16px; }}"
            f"QPushButton:hover {{ color: {_c('TEXT')}; border-color: {_c('TEXT')}; }}")
        atual = str(c.get("chat_formato") or "texto")
        for chave, b in botoes_fmt.items():
            ativo = chave == atual
            b.setStyleSheet(
                f"QPushButton {{ padding: 5px 10px; border: 1px solid {_c('PRI') if ativo else _c('BORDER')};"
                f" border-radius: 4px; background: {_c('PRI_GHO') if ativo else 'transparent'};"
                f" color: {_c('TEXT') if ativo else _c('TEXT_MED')}; }}")
        if not ligado:
            estado_chat.setText(_t("Desligada: ninguém responde as mensagens por você.",
                                   "Off: nobody replies to messages for you."))
        elif whatsapp_conectado():
            estado_chat.setText(_t("Pronta: respondendo as mensagens  ·  ", "Ready: replying to messages  ·  ")
                                + SEC.formatos_chat().get(atual, ("", ""))[1])
        else:
            estado_chat.setText(_t("Falta conectar o WhatsApp: clique em CONECTAR WHATSAPP.",
                                   "WhatsApp is not connected: click CONNECT WHATSAPP."))

    b_chat.clicked.connect(lambda: (_mudou({"chat_ligado": not SEC.carregar().get("chat_ligado")}), _pintar_chat()))
    linha_chat.addWidget(b_chat)
    linha_chat.addStretch()
    lay.addLayout(linha_chat)
    linha_fmt = QHBoxLayout()
    linha_fmt.setSpacing(6)
    lay_fmt_rot = _rot(_t("Responder com:", "Reply with:"), 8, "TEXT_MED")
    linha_fmt.addWidget(lay_fmt_rot)
    for chave, (rotulo, explica) in SEC.formatos_chat().items():
        b = QPushButton(rotulo)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFont(_fx(8))
        b.setToolTip(explica)
        b.clicked.connect(lambda _=False, k=chave: (_mudou({"chat_formato": k}), _pintar_chat()))
        botoes_fmt[chave] = b
        linha_fmt.addWidget(b)
    linha_fmt.addStretch()
    lay.addLayout(linha_fmt)
    lay.addWidget(estado_chat)
    cx_audio = QCheckBox(_t("Ouvir os áudios que mandarem e responder (desligado: ela só te avisa que chegou áudio)",
                            "Listen to the audio people send and reply (off: she only tells you an audio arrived)"))
    cx_audio.setFont(_fx(8))
    cx_audio.setStyleSheet(f"QCheckBox {{ color: {_c('TEXT_MED')}; background: transparent; }}")
    cx_audio.setChecked(bool(cfg.get("chat_ouvir_audios", True)))
    cx_audio.toggled.connect(lambda v: _mudou({"chat_ouvir_audios": bool(v)}))
    lay.addWidget(cx_audio)
    relogio.timeout.connect(_pintar_chat)
    _pintar_chat()

    # -- como ela atende
    lay.addWidget(_rot(_t("COMO ELA ATENDE", "HOW SHE ANSWERS"), 8, "PRI", True))
    botoes_modo: dict[str, QPushButton] = {}

    def _realcar_modo(atual: str) -> None:
        for chave, b in botoes_modo.items():
            ativo = chave == atual
            b.setStyleSheet(
                f"QPushButton {{ text-align: left; padding: 6px 10px; border: 1px solid {_c('PRI') if ativo else _c('BORDER')};"
                f" border-radius: 4px; background: {_c('PRI_GHO') if ativo else 'transparent'};"
                f" color: {_c('TEXT') if ativo else _c('TEXT_MED')}; }}")

    for chave, texto in SEC.modos().items():
        b = QPushButton(texto)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFont(_fx(8))
        b.clicked.connect(lambda _=False, k=chave: (_mudou({"modo": k}), _realcar_modo(k)))
        botoes_modo[chave] = b
        lay.addWidget(b)
    _realcar_modo(cfg.get("modo", "perguntar"))

    # -- a voz
    lay.addWidget(_rot(_t("A VOZ DELA", "HER VOICE"), 8, "PRI", True))
    grade_voz = QGridLayout()
    grade_voz.setHorizontalSpacing(6)
    grade_voz.setVerticalSpacing(6)
    botoes_voz: dict[str, QPushButton] = {}

    def _realcar_voz(atual: str) -> None:
        for chave, b in botoes_voz.items():
            ativo = chave == atual
            b.setStyleSheet(
                f"QPushButton {{ padding: 5px 8px; border: 1px solid {_c('PRI') if ativo else _c('BORDER')};"
                f" border-radius: 4px; background: {_c('PRI_GHO') if ativo else 'transparent'};"
                f" color: {_c('TEXT') if ativo else _c('TEXT_MED')}; }}")

    for i, (chave, nome, _timbre) in enumerate(SEC.vozes()):
        b = QPushButton(nome)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFont(_fx(8))
        b.clicked.connect(lambda _=False, k=chave: (_mudou({"voz": k}), _realcar_voz(k)))
        botoes_voz[chave] = b
        grade_voz.addWidget(b, i // 4, i % 4)
    lay.addLayout(grade_voz)
    _realcar_voz(str(cfg.get("voz") or "leda"))

    # -- o recado do momento
    lay.addWidget(_rot(_t("O QUE ELA DIZ SOBRE VOCÊ AGORA", "WHAT SHE SAYS ABOUT YOU RIGHT NOW"), 8, "PRI", True))
    campo_sit = QLineEdit(str(cfg.get("situacao") or ""))
    campo_sit.setFont(_fx(8))
    campo_sit.setPlaceholderText(_t("ex.: estou em reunião até as 16h   (vazio = 'ocupado, sem previsão')",
                                    "e.g.: I'm in a meeting until 4 pm   (empty = 'busy, no forecast')"))
    estilo_campo = (f"QLineEdit {{ color: {_c('TEXT')}; background: transparent; border: 1px solid {_c('BORDER_B')};"
                    f" border-radius: 4px; padding: 4px 6px; }} QLineEdit:focus {{ border-color: {_c('PRI')}; }}")
    campo_sit.setStyleSheet(estilo_campo)
    campo_sit.editingFinished.connect(lambda: _mudou({"situacao": campo_sit.text().strip()}))
    lay.addWidget(campo_sit)

    # -- tempos e escolhas
    lay.addWidget(_rot(_t("TEMPOS E ESCOLHAS", "TIMES AND CHOICES"), 8, "PRI", True))
    grade = QGridLayout()
    grade.setHorizontalSpacing(10)
    grade.setVerticalSpacing(4)
    estilo_spin = (f"QSpinBox {{ color: {_c('TEXT')}; background: transparent; border: 1px solid {_c('BORDER_B')};"
                   f" border-radius: 4px; padding: 2px 4px; }}")
    numeros = [
        ("espera_decisao_s", _t("Esperar a minha decisão por (segundos)", "Wait for my decision for (seconds)"), 4, 40),
        ("espera_toques_s", _t("Deixar tocar antes de ela atender sozinha (segundos)",
                               "Let it ring before she answers by herself (seconds)"), 2, 30),
        ("espera_resposta_dono_s", _t("Esperar a minha resposta numa pergunta (segundos)",
                                      "Wait for my answer to a question (seconds)"), 10, 60),
        ("duracao_max_min", _t("Duração máxima da ligação dela (minutos)", "Maximum length of her call (minutes)"), 1, 15),
        # v1.0.40: o chat
        ("chat_espera_s", _t("Mensagens: esperar a pessoa terminar de mandar (segundos)",
                             "Messages: wait for the person to finish sending (seconds)"), 3, 60),
        ("chat_espera_dono_s", _t("Mensagens no modo ME PERGUNTA: esperar eu responder primeiro (segundos)",
                                  "Messages in ASK ME mode: wait for me to reply first (seconds)"), 15, 900),
    ]
    for i, (chave, texto, minimo, maximo) in enumerate(numeros):
        grade.addWidget(_rot(texto), i, 0)
        sp = QSpinBox()
        sp.setRange(minimo, maximo)
        try:
            sp.setValue(int(cfg.get(chave) or SEC.PADRAO[chave]))
        except (TypeError, ValueError):
            sp.setValue(int(SEC.PADRAO[chave]))
        sp.setFont(_fx(8))
        sp.setStyleSheet(estilo_spin)
        sp.setFixedWidth(70)
        sp.valueChanged.connect(lambda v, k=chave: _mudou({k: int(v)}))
        grade.addWidget(sp, i, 1)
    lay.addLayout(grade)
    marcas = [
        ("atender_se_nao_responder", _t("Se eu não decidir a tempo, ela atende", "If I don't decide in time, she answers")),
        ("consultar_dono", _t("Ela pode me perguntar coisas no meio da ligação (só no modo ME PERGUNTA)",
                              "She can ask me things during the call (only in ASK ME mode)")),
        ("atender_em_segundo_plano", _t("Atender também com o JARVIS em segundo plano (eu fora)",
                                        "Also answer with JARVIS in the background (I'm away)")),
        ("minimizar_navegador", _t("Deixar o WhatsApp dela escondido (só aparece quando eu pedir)",
                                   "Keep her WhatsApp hidden (it only shows when I ask)")),
        ("ouvir_no_pc", _t("Tocar a voz dela nas caixas do PC (só a dela, bom para gravar vídeo)",
                           "Play her voice on the PC speakers (only hers, good for recording videos)")),
    ]
    for chave, texto in marcas:
        cx = QCheckBox(texto)
        cx.setFont(_fx(8))
        cx.setStyleSheet(f"QCheckBox {{ color: {_c('TEXT_MED')}; background: transparent; }}")
        cx.setChecked(bool(cfg.get(chave, SEC.PADRAO[chave])))
        cx.toggled.connect(lambda v, k=chave: _mudou({k: bool(v)}))
        lay.addWidget(cx)

    # -- listas
    lay.addWidget(_rot(_t("CONTATOS ESPECIAIS  ·  nomes como estão no seu WhatsApp, separados por vírgula",
                          "SPECIAL CONTACTS  ·  names as they are in your WhatsApp, separated by commas"), 8, "PRI", True))
    for chave, texto, dica in (
        ("nunca_atender_sozinha", _t("Só me avisar (ela nunca atende sozinha):", "Just tell me (she never answers by herself):"),
         _t("ex.: Mãe, Amor, Chefe", "e.g.: Mom, Honey, Boss")),
        ("sempre_recusar", _t("Sempre recusar:", "Always decline:"), _t("ex.: Telemarketing, 0800", "e.g.: Telemarketing, 1-800")),
    ):
        lay.addWidget(_rot(texto))
        campo = QLineEdit(", ".join(cfg.get(chave) or []))
        campo.setFont(_fx(8))
        campo.setPlaceholderText(dica)
        campo.setStyleSheet(estilo_campo)
        campo.editingFinished.connect(lambda c=campo, k=chave: _mudou(
            {k: [s.strip() for s in c.text().split(",") if s.strip()]}))
        lay.addWidget(campo)
    lay.addWidget(_rot(_t("Mensagem ao recusar (vai pelo WhatsApp do JARVIS, se ele estiver conectado):",
                          "Message when declining (sent through JARVIS's WhatsApp, if it is connected):")))
    campo_msg = QLineEdit(str(cfg.get("mensagem_recusa") or ""))
    campo_msg.setFont(_fx(8))
    campo_msg.setStyleSheet(estilo_campo)
    campo_msg.editingFinished.connect(lambda: _mudou({"mensagem_recusa": campo_msg.text().strip()}))
    lay.addWidget(campo_msg)

    # -- o que ela sabe
    lay.addWidget(_rot(_t("O QUE ELA SABE SOBRE VOCÊ", "WHAT SHE KNOWS ABOUT YOU"), 8, "PRI", True))
    lay.addWidget(_rot(_t("Ela só fala o que estiver nos arquivos .txt da pasta \"JARVIS Secretaria\" (em Documentos): "
                          "horário, serviços, preços, o que dizer para cada pessoa. No modo 100% AUTOMÁTICA ela responde "
                          "SÓ por eles e, o que não estiver lá, vira recado. Ela lê os arquivos de novo a cada ligação: "
                          "mudou o TXT, já vale na próxima. Tudo que ela atender fica salvo lá também.",
                          "She only says what is in the .txt files of the \"JARVIS Secretaria\" folder (in Documents): "
                          "hours, services, prices, what to tell each person. In 100% AUTOMATIC mode she answers ONLY "
                          "from them, and whatever is not there becomes a message. She reads the files again on every "
                          "call: change the TXT and it counts on the next one. Everything she answers is saved there too.")))
    arquivos_lab = _rot("", 8, "TEXT_MED")

    def _mostrar_arquivos() -> None:
        try:
            nomes = SEC.arquivos_da_base()
        except Exception:
            nomes = []
        arquivos_lab.setText((_t("Arquivos que ela usa: ", "Files she uses: ") + ", ".join(nomes)) if nomes
                             else _t("Ainda não tem nenhum arquivo: clique em EDITAR AS INFORMAÇÕES ou ADICIONAR ARQUIVO.",
                                     "No files yet: click EDIT THE INFORMATION or ADD FILE."))

    linha_add = QHBoxLayout()
    b_add = _botao(_t("ADICIONAR ARQUIVO (TXT)", "ADD FILE (TXT)"))

    def _adicionar() -> None:
        from PyQt6.QtWidgets import QFileDialog  # noqa: PLC0415
        escolhidos, _f = QFileDialog.getOpenFileNames(
            pag, _t("Arquivos com as informações para a secretária", "Files with information for the assistant"),
            str(Path.home()), _t("Textos (*.txt *.md *.csv)", "Text files (*.txt *.md *.csv)"))
        novos = []
        for caminho in escolhidos:
            try:
                novos.append(SEC.adicionar_arquivo(caminho))
            except Exception as exc:  # noqa: BLE001
                print(f"[secretaria_tela] adicionar {caminho}: {exc}")
        _mostrar_arquivos()
        if novos:
            arquivos_lab.setText(arquivos_lab.text() + _t("   ✓ adicionado: ", "   ✓ added: ") + ", ".join(novos))

    b_add.clicked.connect(_adicionar)
    linha_add.addWidget(b_add)
    linha_add.addStretch()
    lay.addLayout(linha_add)
    lay.addWidget(arquivos_lab)
    _mostrar_arquivos()
    linha2 = QHBoxLayout()
    b_info = _botao(_t("EDITAR AS INFORMAÇÕES (TXT)", "EDIT THE INFORMATION (TXT)"))

    def _editar() -> None:
        try:
            SEC.garantir_pastas()
        except OSError:
            pass
        _abrir_no_bloco(str(SEC.arq_informacoes()))

    b_info.clicked.connect(_editar)
    linha2.addWidget(b_info)
    b_pasta = _botao(_t("ABRIR A PASTA (RECADOS E LIGAÇÕES)", "OPEN THE FOLDER (MESSAGES AND CALLS)"))

    def _pasta() -> None:
        try:
            SEC.garantir_pastas()
        except OSError:
            pass
        _abrir(str(SEC.pasta_do_dono()))

    b_pasta.clicked.connect(_pasta)
    linha2.addWidget(b_pasta)
    linha2.addStretch()
    lay.addLayout(linha2)
    recados = SEC.ultimos_recados(3)
    if recados:
        lay.addWidget(_rot(_t("Últimos recados:", "Latest messages:"), 8, "TEXT_MED", True))
        for r in recados:
            lay.addWidget(_rot("•  " + r))
    lay.addStretch()
    return externa


# ─────────────────────────────────────────────────────────────────────────────
# O PEDACO DA SECRETARIA DENTRO DA JANELA "CONECTAR WHATSAPP" (05/11/2026)
# ─────────────────────────────────────────────────────────────────────────────
def secao_no_whatsapp(abrir_opcoes=None) -> QWidget:
    """Liga/desliga, como ela atende e o estado das ligacoes, no mesmo lugar do WhatsApp.

    Pedido do Diego: "vincula ela com o WhatsApp que ja tem o botaozinho". O codigo
    das ligacoes aparece no mesmo quadro do QR, logo depois do WhatsApp de sempre
    (quem faz isso e' o WhatsAppQrOverlay do ui.py, com `estado_ligacoes()`)."""
    verde = _c("GREEN", "#00ff88")
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 4, 0, 0)
    lay.setSpacing(5)
    sep = QFrame()
    sep.setFixedHeight(1)
    sep.setStyleSheet(f"background: {_c('GREEN_D', '#00aa55')};")
    lay.addWidget(sep)
    titulo = QLabel(_t("SECRETÁRIA  ·  atende as ligações e responde as mensagens do WhatsApp",
                       "ASSISTANT  ·  answers WhatsApp calls and replies to messages"))
    titulo.setWordWrap(True)
    titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    titulo.setFont(_fx(8, QFont.Weight.Bold))
    titulo.setStyleSheet(f"color: {verde}; background: transparent;")
    lay.addWidget(titulo)

    topo = QHBoxLayout()
    topo.setSpacing(6)
    b_liga = QPushButton("")
    b_liga.setCursor(Qt.CursorShape.PointingHandCursor)
    b_liga.setFont(_fx(8, QFont.Weight.Bold))
    b_liga.setFixedHeight(28)
    topo.addWidget(b_liga, 1)
    b_mais = QPushButton(_t("MAIS OPÇÕES", "MORE OPTIONS"))
    b_mais.setCursor(Qt.CursorShape.PointingHandCursor)
    b_mais.setFont(_fx(8, QFont.Weight.Bold))
    b_mais.setFixedHeight(28)
    b_mais.setStyleSheet(
        f"QPushButton {{ color: {_c('TEXT_MED')}; background: transparent; border: 1px solid {_c('BORDER')};"
        f" border-radius: 5px; padding: 0 10px; }} QPushButton:hover {{ color: {verde}; border-color: {verde}; }}")
    if abrir_opcoes:
        b_mais.clicked.connect(lambda: abrir_opcoes())
    else:
        b_mais.hide()
    topo.addWidget(b_mais)
    lay.addLayout(topo)

    linha_modos = QHBoxLayout()
    linha_modos.setSpacing(5)
    botoes_modo: dict[str, QPushButton] = {}
    for chave, texto in SEC.modos_curtos().items():
        b = QPushButton(texto)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFont(_fx(7, QFont.Weight.Bold))
        b.setFixedHeight(26)
        b.setToolTip(SEC.modos().get(chave, ""))
        botoes_modo[chave] = b
        linha_modos.addWidget(b)
    lay.addLayout(linha_modos)

    # v1.0.40: as MENSAGENS (a secretaria no chat): liga/desliga + como ela responde.
    linha_chat = QHBoxLayout()
    linha_chat.setSpacing(5)
    b_chat = QPushButton("")
    b_chat.setCursor(Qt.CursorShape.PointingHandCursor)
    b_chat.setFont(_fx(7, QFont.Weight.Bold))
    b_chat.setFixedHeight(26)
    b_chat.setToolTip(_t("Ela responde quem te manda mensagem no WhatsApp (texto e áudio), com as mesmas informações.",
                         "She replies to whoever messages you on WhatsApp (text and audio), with the same information."))
    linha_chat.addWidget(b_chat, 1)
    botoes_fmt: dict[str, QPushButton] = {}
    curtos = {"texto": _t("SÓ TEXTO", "TEXT ONLY"), "audio": _t("SÓ ÁUDIO", "AUDIO ONLY"), "misto": _t("OS DOIS", "BOTH")}
    for chave, (_rot_fmt, explica) in SEC.formatos_chat().items():
        b = QPushButton(curtos.get(chave, chave.upper()))
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFont(_fx(7, QFont.Weight.Bold))
        b.setFixedHeight(26)
        b.setToolTip(explica)
        botoes_fmt[chave] = b
        linha_chat.addWidget(b)
    lay.addLayout(linha_chat)

    estado = QLabel("")
    estado.setAlignment(Qt.AlignmentFlag.AlignCenter)
    estado.setWordWrap(True)
    estado.setFont(_fx(7))
    estado.setStyleSheet(f"color: {_c('TEXT_MED')}; background: transparent;")
    lay.addWidget(estado)

    def _pintar() -> None:
        cfg = SEC.carregar()
        ligada = bool(cfg.get("ligada"))
        b_liga.setText(_t("LIGAÇÕES: ATENDENDO", "CALLS: ANSWERING") if ligada
                       else _t("LIGAÇÕES: DESLIGADO  ·  ligar", "CALLS: OFF  ·  turn on"))
        cor = verde if ligada else _c("TEXT_DIM")
        b_liga.setStyleSheet(
            f"QPushButton {{ color: {cor}; background: {'#00140a' if ligada else 'transparent'};"
            f" border: 1px solid {cor}; border-radius: 5px; }} QPushButton:hover {{ border-color: {verde}; }}")
        atual = cfg.get("modo", "perguntar")
        for chave, b in botoes_modo.items():
            ativo = ligada and chave == atual
            b.setEnabled(ligada)
            b.setStyleSheet(
                f"QPushButton {{ color: {verde if ativo else _c('TEXT_MED')}; background: {'#00140a' if ativo else 'transparent'};"
                f" border: 1px solid {verde if ativo else _c('BORDER')}; border-radius: 5px; }}"
                f"QPushButton:hover {{ border-color: {verde}; }} QPushButton:disabled {{ color: {_c('TEXT_DIM')}; }}")
        chat = bool(cfg.get("chat_ligado"))
        b_chat.setText(_t("MENSAGENS: RESPONDENDO", "MESSAGES: REPLYING") if chat
                       else _t("MENSAGENS: DESLIGADO  ·  ligar", "MESSAGES: OFF  ·  turn on"))
        cor_chat = verde if chat else _c("TEXT_DIM")
        b_chat.setStyleSheet(
            f"QPushButton {{ color: {cor_chat}; background: {'#00140a' if chat else 'transparent'};"
            f" border: 1px solid {cor_chat}; border-radius: 5px; }} QPushButton:hover {{ border-color: {verde}; }}")
        fmt = str(cfg.get("chat_formato") or "texto")
        for chave, b in botoes_fmt.items():
            # A escolha fica sempre clicavel e marcada (com as mensagens desligadas, marcada em cinza).
            ativo = chave == fmt
            cor_b = (verde if chat else _c("TEXT")) if ativo else _c("TEXT_MED")
            borda = (verde if chat else _c("TEXT_MED")) if ativo else _c("BORDER")
            fundo = ("#00140a" if chat else "rgba(255,255,255,0.05)") if ativo else "transparent"
            b.setStyleSheet(
                f"QPushButton {{ color: {cor_b}; background: {fundo};"
                f" border: 1px solid {borda}; border-radius: 5px; padding: 0 8px; }}"
                f"QPushButton:hover {{ border-color: {verde}; }}")
        if not ligada:
            estado.setText(_t("Ligações desligadas: ninguém atende por você.", "Calls off: nobody answers for you."))
        elif _ultimo_login == "conectado":
            estado.setText(_t("Ligações conectadas ✓  ·  voz ", "Calls connected ✓  ·  voice ")
                           + SEC.nome_da_voz(cfg.get('voz') or 'leda'))
        elif _ultimo_login == "qr":
            estado.setText(_t("Falta o código das ligações (aparece aqui em cima depois do WhatsApp).",
                              "The calls code is missing (it shows up above, after WhatsApp)."))
        else:
            estado.setText(_t("Ligando as ligações...", "Connecting calls..."))

    b_liga.clicked.connect(lambda: (_mudar(_casca, {"ligada": not SEC.carregar().get("ligada")}), _pintar()))
    for chave, b in botoes_modo.items():
        b.clicked.connect(lambda _=False, k=chave: (_mudar(_casca, {"modo": k}), _pintar()))
    b_chat.clicked.connect(lambda: (_mudar(_casca, {"chat_ligado": not SEC.carregar().get("chat_ligado")}), _pintar()))
    for chave, b in botoes_fmt.items():
        b.clicked.connect(lambda _=False, k=chave: (_mudar(_casca, {"chat_formato": k}), _pintar()))
    relogio = QTimer(w)
    relogio.timeout.connect(_pintar)
    relogio.start(1500)
    _pintar()
    return w
