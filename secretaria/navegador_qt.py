# -*- coding: utf-8 -*-
"""SECRETARIA DO WHATSAPP — o navegador INTERNO (05/11/2026, pedido do Diego:
"ao inves de abrir toda vez o navegador, coloca um interno dentro do proprio NIA").

E' o Chromium do Qt (PyQt6-WebEngine), o mesmo do globo. O WhatsApp Web roda numa
janela do proprio NIA que fica FORA DA TELA e fora da barra de tarefas: o dono
nao ve navegador nenhum. A pagina continua "visivel" para o Chromium (ligacao,
som e tela funcionam igual). O QR Code vai para o cartao do NIA; a janela so'
aparece quando o dono pede ("abrir o WhatsApp dela") e o X so' a esconde de novo.

Linhas: tudo do Qt roda na linha principal do processo do motor; a conversa
(asyncio) roda em outra. `ExecutorQt.no_qt(fn)` leva uma funcao para o Qt;
`PaginaQt` e' o que o motor usa (evaluate, executar, clicar, janela), igual para
o Edge e para este navegador.
"""
from __future__ import annotations

import asyncio
import itertools
import json
import os
from pathlib import Path

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
FORA_DA_TELA = (-32000, -32000)

PRELUDIO = r"""
(() => {
  if (window.__secPreludio) return;
  window.__secPreludio = true;
  const fila = [];
  let canal = null;
  window.__secretaria = (s) => { if (canal) canal.enviar(s); else fila.push(s); };
  window.__secResposta = (id, s) => {
    if (canal) canal.resposta(id, s); else fila.push(JSON.stringify({ tipo: '__resposta', id, s }));
  };
  const ligar = () => {
    try {
      new QWebChannel(qt.webChannelTransport, (c) => {
        canal = c.objects.motor;
        while (fila.length) canal.enviar(fila.shift());
      });
    } catch (e) { setTimeout(ligar, 200); }
  };
  ligar();
})();
"""


def preparar_ambiente(teste: bool = False) -> None:
    """Antes do QApplication: as opcoes do Chromium do Qt."""
    flags = ["--autoplay-policy=no-user-gesture-required", "--disable-background-timer-throttling",
             "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows",
             "--disable-features=CalculateNativeWinOcclusion,Translate"]
    if teste:
        # Bancada: microfone FALSO do navegador. O de verdade nunca abre no teste.
        flags += ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"]
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "") + " "
                                                + " ".join(flags)).strip()


def _criar_classes():
    """As classes do Qt so' existem depois do import (o motor no modo Edge nao precisa delas)."""
    from PyQt6.QtCore import QFile, QIODevice, QObject, QPointF, Qt, QUrl, pyqtSignal, pyqtSlot  # noqa: PLC0415
    from PyQt6.QtGui import QIcon, QMouseEvent  # noqa: PLC0415
    from PyQt6.QtWebChannel import QWebChannel  # noqa: PLC0415
    from PyQt6.QtWebEngineCore import (QWebEnginePage, QWebEngineProfile, QWebEngineScript,  # noqa: PLC0415
                                       QWebEngineSettings)
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: PLC0415
    from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget  # noqa: PLC0415

    class ExecutorQt(QObject):
        """Leva funcoes da linha da conversa para a linha do Qt."""
        _pedido = pyqtSignal(object)

        def __init__(self):
            super().__init__()
            self._pedido.connect(self._rodar)

        def no_qt(self, fn) -> None:
            self._pedido.emit(fn)

        def _rodar(self, fn) -> None:
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                print(f"[navegador_qt] {exc}", flush=True)

    class Canal(QObject):
        def __init__(self, pagina_qt):
            super().__init__()
            self._p = pagina_qt

        @pyqtSlot(str)
        def enviar(self, s):
            self._p._chegou(s)

        @pyqtSlot(int, str)
        def resposta(self, i, s):
            self._p._resposta(i, s)

    class Janela(QWidget):
        """A janela do WhatsApp da secretaria. Fechar = esconder (fora da tela)."""

        def __init__(self, nav, principal: bool):
            super().__init__(None, Qt.WindowType.Tool)
            self._nav = nav
            self._principal = principal
            self.setWindowTitle("NIA — WhatsApp da secretária")
            icone = Path(__file__).resolve().parents[1] / "assets" / "icons" / "nia.ico"
            if icone.exists():
                self.setWindowIcon(QIcon(str(icone)))
            self.setStyleSheet("QWidget { background: #00060a; }")
            lay = QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            self.visao = QWebEngineView(self)
            self.visao.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
            lay.addWidget(self.visao)
            self.resize(1060, 780)
            self.esconder()
            self.show()

        def esconder(self):
            self.move(*FORA_DA_TELA)

        def mostrar(self):
            tela = QApplication.primaryScreen()
            if tela is not None:
                g = tela.availableGeometry()
                self.move(g.center().x() - self.width() // 2, g.center().y() - self.height() // 2)
            self.show()
            self.raise_()
            self.activateWindow()

        def closeEvent(self, ev):
            # O X nao fecha: so' esconde. Fechada, a secretaria ficaria surda.
            ev.ignore()
            self.esconder()

    class PaginaWeb(QWebEnginePage):
        def __init__(self, perfil, visao, nav):
            super().__init__(perfil, visao)
            self._nav = nav
            try:
                self.permissionRequested.connect(self._permissao)          # Qt 6.8+
            except AttributeError:
                self.featurePermissionRequested.connect(self._permissao_antiga)

        def _permissao(self, perm):
            try:
                host = perm.origin().host()
                if host.endswith("whatsapp.com") or host in ("127.0.0.1", "localhost"):
                    perm.grant()
                else:
                    perm.deny()
            except Exception as exc:  # noqa: BLE001
                print(f"[navegador_qt] permissao: {exc}", flush=True)

        def _permissao_antiga(self, url, recurso):
            host = url.host()
            politica = (QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
                        if host.endswith("whatsapp.com") or host in ("127.0.0.1", "localhost")
                        else QWebEnginePage.PermissionPolicy.PermissionDeniedByUser)
            self.setFeaturePermission(url, recurso, politica)

        def createWindow(self, _tipo):
            # A ligacao pode abrir outra janela: nasce escondida, com os mesmos ganchos.
            return self._nav._nova_janela(principal=False).page

        def javaScriptConsoleMessage(self, nivel, msg, linha, origem):
            # O que o proprio WhatsApp diz sobre ligacao (voip, call, webrtc) vai para o registro.
            texto = str(msg)
            baixo = texto.lower()
            if any(k in baixo for k in ("voip", "webrtc", "incoming call", "call offer", "rtc", "secretaria")):
                self._nav.registrar(f"console: {texto[:300]}")

        _ = None

    class NavegadorQt:
        """Vive na linha do Qt. O motor fala com ele pelas PaginaQt."""

        def __init__(self, executor, laco, ao_evento, perfil_dir: Path, pagina_js: Path, registrar=None):
            self.executor = executor
            self.laco = laco
            self.ao_evento = ao_evento
            self.registrar = registrar or (lambda texto: None)
            self.janelas: list = []
            self.paginas: list[PaginaQt] = []
            perfil_dir.mkdir(parents=True, exist_ok=True)
            self.perfil = QWebEngineProfile("jarvis_secretaria", QApplication.instance())
            self.perfil.setPersistentStoragePath(str(perfil_dir / "dados"))
            self.perfil.setCachePath(str(perfil_dir / "cache"))
            self.perfil.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
            self.perfil.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
            self.perfil.setHttpUserAgent(UA)
            try:
                self.perfil.setNotificationPresenter(lambda notificacao: None)
            except Exception:
                pass
            # MICROFONE E NOTIFICACAO JA LIBERADOS para o WhatsApp (05/11, primeira ligacao
            # real nao tocou: `permissions.query('microphone')` dava "prompt" e as notificacoes
            # de ligacao estavam desligadas; o WhatsApp so' faz tocar com o microfone liberado).
            try:
                from PyQt6.QtWebEngineCore import QWebEnginePermission  # noqa: PLC0415
                tipos = [QWebEnginePermission.PermissionType.MediaAudioCapture,
                         QWebEnginePermission.PermissionType.MediaAudioVideoCapture,
                         QWebEnginePermission.PermissionType.MediaVideoCapture,
                         QWebEnginePermission.PermissionType.Notifications]
                for origem in ("https://web.whatsapp.com", "http://127.0.0.1"):
                    for tipo in tipos:
                        try:
                            self.perfil.queryPermission(QUrl(origem), tipo).grant()
                        except Exception as exc:  # noqa: BLE001
                            print(f"[navegador_qt] permissao {tipo}: {exc}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"[navegador_qt] permissoes adiantadas: {exc}", flush=True)
            f = QFile(":/qtwebchannel/qwebchannel.js")
            f.open(QIODevice.OpenModeFlag.ReadOnly)
            qwc = bytes(f.readAll()).decode("utf-8")
            f.close()
            for nome, codigo in (("qwebchannel", qwc), ("preludio", PRELUDIO),
                                 ("secretaria", pagina_js.read_text(encoding="utf-8"))):
                s = QWebEngineScript()
                s.setName(f"nia_{nome}")
                s.setSourceCode(codigo)
                s.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
                s.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
                s.setRunsOnSubFrames(False)
                self.perfil.scripts().insert(s)
            self.principal = self._nova_janela(principal=True)

        def _nova_janela(self, principal: bool):
            j = Janela(self, principal)
            pagina = PaginaWeb(self.perfil, j.visao, self)
            ajustes = pagina.settings()
            for atributo, valor in ((QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False),
                                    (QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True),
                                    (QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)):
                try:
                    ajustes.setAttribute(atributo, valor)
                except Exception:
                    pass
            j.visao.setPage(pagina)
            pq = PaginaQt(self, pagina, j)
            canal = QWebChannel(pagina)
            pq._canal_obj = Canal(pq)
            canal.registerObject("motor", pq._canal_obj)
            pagina.setWebChannel(canal, QWebEngineScript.ScriptWorldId.MainWorld)
            pq._canal = canal
            self.janelas.append(j)
            self.paginas.append(pq)
            return pq

        def carregar(self, url: str) -> None:
            self.principal.page.load(QUrl(url))

        def fechar(self) -> None:
            for p in list(self.paginas):
                try:
                    p.page.setWebChannel(None)
                except Exception:
                    pass
            for j in list(self.janelas):
                try:
                    j.visao.setPage(None)
                    j.hide()
                    j.deleteLater()
                except Exception:
                    pass
            self.janelas.clear()
            self.paginas.clear()

    class PaginaQt:
        """O que o motor usa (linha da conversa). Mesma cara da pagina do Edge."""

        def __init__(self, nav, page, janela):
            self.nav = nav
            self.page = page
            self.janela_qt = janela
            self._pend: dict[int, asyncio.Future] = {}
            self._cont = itertools.count(1)

        @property
        def url(self) -> str:
            try:
                return self.page.url().toString()
            except Exception:
                return ""

        # -- da pagina para o motor (linha do Qt) --
        def _chegou(self, s: str) -> None:
            try:
                if s.startswith('{"tipo":"__resposta"') or s.startswith('{"tipo": "__resposta"'):
                    d = json.loads(s)
                    self._resposta(int(d.get("id") or 0), str(d.get("s") or "null"))
                    return
            except ValueError:
                pass
            self.nav.laco.call_soon_threadsafe(self.nav.ao_evento, self, s)

        def _resposta(self, i: int, s: str) -> None:
            self.nav.laco.call_soon_threadsafe(self._resolver, i, s)

        def _resolver(self, i: int, s: str) -> None:
            fut = self._pend.get(i)
            if fut is None or fut.done():
                return
            try:
                r = json.loads(s)
            except ValueError:
                r = None
            if isinstance(r, dict) and "__erro" in r and len(r) == 1:
                fut.set_exception(RuntimeError(str(r["__erro"])))
            else:
                fut.set_result(r)

        # -- do motor para a pagina (linha da conversa) --
        async def evaluate(self, fn: str, arg=None, espera: float = 10.0):
            i = next(self._cont)
            fut = asyncio.get_running_loop().create_future()
            self._pend[i] = fut
            chamada = f"({fn})({json.dumps(arg)})" if arg is not None else f"({fn})()"
            codigo = ("(async () => { let r; try { r = await " + chamada + "; } catch (e) { r = { __erro: String(e) }; }"
                      f" window.__secResposta({i}, JSON.stringify(r === undefined ? null : r)); }})();")
            self.nav.executor.no_qt(lambda: self.page.runJavaScript(codigo))
            try:
                return await asyncio.wait_for(fut, espera)
            finally:
                self._pend.pop(i, None)

        def executar(self, codigo: str) -> None:
            """Sem esperar resposta (a voz da secretaria, de 60 em 60 ms)."""
            self.nav.executor.no_qt(lambda: self.page.runJavaScript(codigo))

        async def clicar(self, alvo: str) -> bool:
            pos = await self.evaluate(
                "(a) => { const el = document.querySelector('[data-sec-alvo=\"' + a + '\"]'); if (!el) return null;"
                " el.scrollIntoView({block: 'center', inline: 'center'}); const b = el.getBoundingClientRect();"
                " return {x: b.left + b.width / 2, y: b.top + b.height / 2}; }", alvo)
            if not pos:
                return False
            laco = asyncio.get_running_loop()
            fut = laco.create_future()

            def _no_qt() -> None:
                ok = False
                try:
                    visao = self.janela_qt.visao
                    z = visao.zoomFactor() or 1.0
                    ponto = QPointF(float(pos["x"]) * z, float(pos["y"]) * z)
                    alvo_w = visao.focusProxy() or visao
                    glob = QPointF(alvo_w.mapToGlobal(ponto.toPoint()))
                    for tipo, botao, botoes in (
                            (QMouseEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.NoButton),
                            (QMouseEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton),
                            (QMouseEvent.Type.MouseButtonRelease, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton)):
                        ev = QMouseEvent(tipo, ponto, glob, botao, botoes, Qt.KeyboardModifier.NoModifier)
                        QApplication.sendEvent(alvo_w, ev)
                    ok = True
                except Exception as exc:  # noqa: BLE001
                    print(f"[navegador_qt] clique: {exc}", flush=True)
                laco.call_soon_threadsafe(lambda: fut.done() or fut.set_result(ok))

            self.nav.executor.no_qt(_no_qt)
            try:
                return bool(await asyncio.wait_for(fut, 5.0))
            except asyncio.TimeoutError:
                return False

        async def janela(self, estado: str) -> None:
            j = self.janela_qt
            self.nav.executor.no_qt(j.mostrar if estado == "normal" else j.esconder)

    return ExecutorQt, NavegadorQt, PaginaQt


_classes = None


def classes():
    global _classes
    if _classes is None:
        _classes = _criar_classes()
    return _classes
