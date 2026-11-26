# -*- coding: utf-8 -*-
"""Gerenciador do overlay por monitor, ligado à sessão de controle.

A criação das janelas é preguiçosa: nada existe enquanto não há sessão. O
gerenciador registra um apresentador síncrono na sessão, então quem inicia o
controle (mesmo de uma thread de trabalho) só recebe o token depois que a
interface confirmou a apresentação.
"""
from __future__ import annotations

import threading

from PyQt6.QtCore import QEventLoop, QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core import controle_sessao as CS
from core.overlay_controle import tema
from core.overlay_controle.borda import JanelaBorda
from core.overlay_controle.hud import JanelaAtividades, JanelaBanner, JanelaControles

_INSTANCIA = None


class GerenciadorOverlay(QObject):
    _evento_sig = pyqtSignal(object)
    _mostrar_sig = pyqtSignal(str)
    _ocultar_sig = pyqtSignal()

    def __init__(self, sessao_controle=None, parent=None):
        super().__init__(parent)
        global _INSTANCIA
        self._sessao = sessao_controle or CS.sessao
        self._bordas: list[JanelaBorda] = []
        self._banners: list[JanelaBanner] = []
        self._controles: JanelaControles | None = None
        self._atividades: JanelaAtividades | None = None
        self._visivel = False
        self._pausa_do_usuario = False
        self._pendente = None
        self._trava_pendente = threading.Lock()
        self._watchdog = QTimer(self)
        self._watchdog.setInterval(500)
        self._watchdog.timeout.connect(self._vigiar)
        self._ritmo_ativo = QTimer(self)
        self._ritmo_ativo.setSingleShot(True)
        self._ritmo_ativo.setInterval(9000)
        self._ritmo_ativo.timeout.connect(lambda: self._definir_ritmo('economico'))
        self._ritmo_estatico = QTimer(self)
        self._ritmo_estatico.setSingleShot(True)
        self._ritmo_estatico.setInterval(26000)
        self._ritmo_estatico.timeout.connect(lambda: self._definir_ritmo('estatico'))
        self._fade = QTimer(self)
        self._fade.setSingleShot(True)
        self._fade.setInterval(240)
        self._fade.timeout.connect(self._concluir_fade)

        self._evento_sig.connect(self._aplicar_evento)
        self._mostrar_sig.connect(self._mostrar_no_gui)
        self._ocultar_sig.connect(self._ocultar_no_gui)

        self._sessao.registrar_apresentador(self._apresentar_sincrono)
        self._sessao.registrar_ouvinte(self._ao_evento)
        app = QApplication.instance()
        if app is not None:
            app.screenAdded.connect(self._ao_mudar_tela)
            app.screenRemoved.connect(self._ao_mudar_tela)
            for tela in app.screens():
                try:
                    tela.geometryChanged.connect(self._ao_mudar_tela)
                except Exception:
                    pass
        _INSTANCIA = self

    # ── API pública ─────────────────────────────────────────────────────────
    @classmethod
    def instancia(cls):
        return _INSTANCIA

    def encerrar(self) -> None:
        global _INSTANCIA
        self._watchdog.stop()
        self._ritmo_ativo.stop()
        self._ritmo_estatico.stop()
        self._fade.stop()
        self._sessao.remover_apresentador(self._apresentar_sincrono)
        self._sessao.remover_ouvinte(self._ao_evento)
        self._destruir()
        if _INSTANCIA is self:
            _INSTANCIA = None

    @property
    def visivel(self) -> bool:
        return self._visivel

    @property
    def captura_excluida(self) -> bool:
        return all(b.captura_excluida for b in self._bordas) if self._bordas else False

    # ── apresentação síncrona ───────────────────────────────────────────────
    def _apresentar_sincrono(self, sessao_id: str, timeout: float) -> bool:
        app = QApplication.instance()
        if app is None:
            return False
        if QThread.currentThread() == app.thread():
            return self._mostrar_no_gui_sincrono(sessao_id)
        evento = threading.Event()
        resultado = [False]
        with self._trava_pendente:
            self._pendente = (sessao_id, evento, resultado)
        self._mostrar_sig.emit(sessao_id)
        if not evento.wait(max(0.2, float(timeout))):
            with self._trava_pendente:
                if self._pendente is not None and self._pendente[0] == sessao_id:
                    self._pendente = None
            return False
        return bool(resultado[0])

    def _mostrar_no_gui(self, sessao_id: str) -> None:
        ok = self._mostrar_no_gui_sincrono(sessao_id)
        with self._trava_pendente:
            pendente = self._pendente
            self._pendente = None
        if pendente is not None and pendente[0] == sessao_id:
            pendente[2][0] = ok
            pendente[1].set()

    def _mostrar_no_gui_sincrono(self, sessao_id: str) -> bool:
        self._fade.stop()
        if self._sessao.estado in (CS.EstadoControle.IDLE,
                                   CS.EstadoControle.FAILED,
                                   CS.EstadoControle.STOPPING):
            return False
        if not self._visivel:
            self._construir()
            for borda in self._bordas:
                borda.mostrar()
            for banner in self._banners:
                banner.show()
                banner.raise_()
            if self._controles is not None:
                self._controles.show()
                self._controles.raise_()
            if self._atividades is not None:
                self._atividades.show()
                self._atividades.raise_()
            self._visivel = True
        self._posicionar()
        self._processar_pintura(90)
        ok = self._tudo_apresentado()
        if not ok:
            self._ocultar_no_gui()
            return False
        self._watchdog.start()
        self._reiniciar_ritmo()
        return True

    def _tudo_apresentado(self) -> bool:
        if not self._bordas or not all(b.apresentado() for b in self._bordas):
            return False
        if not all(b.isVisible() for b in self._banners):
            return False
        if self._controles is None or not self._controles.isVisible():
            return False
        if self._atividades is None or not self._atividades.isVisible():
            return False
        return True

    @staticmethod
    def _processar_pintura(ms: int) -> None:
        laco = QEventLoop()
        QTimer.singleShot(max(1, int(ms)), laco.quit)
        laco.exec()

    def _ocultar_no_gui(self) -> None:
        self._watchdog.stop()
        self._ritmo_ativo.stop()
        self._ritmo_estatico.stop()
        self._fade.stop()
        for borda in self._bordas:
            borda.ocultar()
        for banner in self._banners:
            banner.hide()
        if self._controles is not None:
            self._controles.hide()
        if self._atividades is not None:
            self._atividades.hide()
        self._visivel = False

    # ── construção por monitor ──────────────────────────────────────────────
    def _construir(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        self._destruir()
        primaria = app.primaryScreen()
        for tela in app.screens():
            try:
                borda = JanelaBorda(tela)
                self._bordas.append(borda)
                geo = tela.geometry()
                banner = JanelaBanner(tema.metricas(geo.width(), geo.height()))
                self._banners.append(banner)
            except Exception:
                continue
        if primaria is not None:
            geo = primaria.geometry()
            m = tema.metricas(geo.width(), geo.height())
            self._controles = JanelaControles(m)
            self._controles.pausar_clicado.connect(self._alternar_pausa)
            self._controles.parar_clicado.connect(self._parar)
            self._atividades = JanelaAtividades(m)
        self._posicionar()

    def _destruir(self) -> None:
        for borda in self._bordas:
            try:
                borda.close()
                borda.deleteLater()
            except Exception:
                pass
        for banner in self._banners:
            try:
                banner.close()
                banner.deleteLater()
            except Exception:
                pass
        for painel in (self._controles, self._atividades):
            if painel is not None:
                try:
                    painel.close()
                    painel.deleteLater()
                except Exception:
                    pass
        self._bordas.clear()
        self._banners.clear()
        self._controles = None
        self._atividades = None

    def _posicionar(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        primaria = app.primaryScreen()
        for borda, banner in zip(self._bordas, self._banners):
            try:
                geo = borda.tela.geometry()
                m = tema.metricas(geo.width(), geo.height())
                banner.atualizar_metrica(m)
                banner.move(geo.x() + m.banner_x - 24, geo.y() + m.banner_y - 24)
            except Exception:
                continue
        if primaria is None:
            return
        geo = primaria.geometry()
        m = tema.metricas(geo.width(), geo.height())
        if self._controles is not None:
            self._controles.atualizar_metrica(m)
            self._controles.move(geo.x() + m.status_x - 10,
                                 geo.y() + m.status_y - 10)
        if self._atividades is not None:
            self._atividades.atualizar_metrica(m)
            self._atividades.move(geo.x() + m.atividades_x - 12,
                                  geo.y() + m.atividades_y - 12)

    # ── eventos da sessão ───────────────────────────────────────────────────
    def _ao_evento(self, evento) -> None:
        self._evento_sig.emit(evento)

    def _aplicar_evento(self, evento) -> None:
        if not isinstance(evento, CS.EventoControle):
            return
        atual = self._sessao.sessao_id
        if evento.sessao_id and atual and evento.sessao_id != atual:
            return
        tipo = evento.tipo
        if tipo in ('iniciando', 'ativo', 'reutilizada'):
            if self._controles is not None:
                self._controles.definir_estado(self._sessao.estado.value, evento.descricao)
            self._reiniciar_ritmo()
        elif tipo == 'atividade':
            if self._atividades is not None:
                self._atividades.definir_atividades(self._sessao.atividades)
                self._atividades.definir_animacao(True)
            self._reiniciar_ritmo()
        elif tipo in ('pausando', 'pausado', 'retomado', 'suspenso'):
            if tipo == 'retomado':
                self._pausa_do_usuario = False
            if self._controles is not None:
                self._controles.definir_estado(self._sessao.estado.value, evento.descricao)
            if self._atividades is not None:
                self._atividades.definir_animacao(tipo == 'retomado')
            self._definir_ritmo('estatico' if tipo != 'retomado' else 'ativo')
            if tipo == 'pausando':
                # A interface confirma que já parou de animar antes de liberar
                # o estado PAUSED (a sessão fica presa em PAUSING sem isto).
                QTimer.singleShot(120, self._sessao.confirmar_pausa)
        elif tipo in ('parada', 'encerrando'):
            if self._controles is not None:
                self._controles.definir_estado('STOPPING', evento.descricao)
            self._definir_ritmo('economico')
            if tipo == 'encerrando' and self._visivel:
                self._fade.start()
        elif tipo == 'encerrado':
            self._concluir_fade()
        elif tipo == 'falha':
            if self._controles is not None:
                self._controles.definir_estado('FAILED', evento.descricao)
            QTimer.singleShot(900, self._ocultar_no_gui)

    def _concluir_fade(self) -> None:
        # Um fade pendente da sessão anterior não pode apagar a nova sessão.
        if self._sessao.ativo() or self._sessao.estado is CS.EstadoControle.STARTING:
            return
        self._ocultar_no_gui()
        self._sessao.confirmar_encerramento()

    def _reiniciar_ritmo(self) -> None:
        self._definir_ritmo('ativo')
        self._ritmo_ativo.start()
        self._ritmo_estatico.start()

    def _definir_ritmo(self, ritmo: str) -> None:
        for borda in self._bordas:
            borda.definir_ritmo(ritmo)

    # ── controles ───────────────────────────────────────────────────────────
    def _alternar_pausa(self) -> None:
        if self._sessao.estado is CS.EstadoControle.ACTIVE:
            self._pausa_do_usuario = True
            self._sessao.pausar('botão Pausar')
        elif self._sessao.estado is CS.EstadoControle.PAUSED:
            self._pausa_do_usuario = False
            self._sessao.retomar('botão Retomar')

    def _parar(self) -> None:
        self._sessao.solicitar_parada('botão Encerrar')

    # ── monitores e watchdog ────────────────────────────────────────────────
    def _ao_mudar_tela(self, *_args) -> None:
        if not self._visivel:
            return
        self._sessao.suspender('monitores ou DPI mudaram')
        self._construir()
        for borda in self._bordas:
            borda.mostrar()
        for banner in self._banners:
            banner.show()
            banner.raise_()
        if self._controles is not None:
            self._controles.show()
            self._controles.raise_()
        if self._atividades is not None:
            self._atividades.show()
            self._atividades.raise_()
        self._posicionar()
        QTimer.singleShot(120, self._revalidar)

    def _revalidar(self) -> None:
        if not self._visivel or not self._sessao.ativo():
            return
        if self._tudo_apresentado():
            if not self._pausa_do_usuario:
                self._sessao.retomar('monitores revalidados')

    def _vigiar(self) -> None:
        if not self._visivel:
            self._watchdog.stop()
            return
        if self._sessao.estado in (CS.EstadoControle.IDLE, CS.EstadoControle.FAILED):
            self._ocultar_no_gui()
            return
        if not self._tudo_apresentado():
            self._sessao.falhar('o overlay desapareceu durante a sessão')
            self._ocultar_no_gui()
            return
        if self._sessao.parada_solicitada() and self._controles is not None:
            self._controles.definir_estado('STOPPING', 'parada solicitada')


def mascarar_captura(imagem):
    """Fallback quando o Windows não exclui o overlay da captura.

    Só age se o overlay estiver visível e a exclusão nativa tiver falhado.
    As regiões são preenchidas com o tom do fundo do overlay para que o modelo
    não confunda os painéis com conteúdo do aplicativo.
    """
    gerenciador = _INSTANCIA
    if gerenciador is None or not gerenciador.visivel or gerenciador.captura_excluida:
        return imagem
    try:
        from PIL import ImageDraw  # noqa: PLC0415
        desenho = ImageDraw.Draw(imagem)
        for widget in (*gerenciador._banners, gerenciador._controles,
                       gerenciador._atividades):
            if widget is None or not widget.isVisible():
                continue
            geo = widget.geometry()
            dpr = max(1.0, float(widget.devicePixelRatioF()))
            x1, y1 = int(geo.x() * dpr), int(geo.y() * dpr)
            x2, y2 = int((geo.x() + geo.width()) * dpr), int((geo.y() + geo.height()) * dpr)
            desenho.rectangle([x1, y1, x2, y2], fill=(4, 12, 22))
    except Exception:
        return imagem
    return imagem


def encerrar_global() -> None:
    global _INSTANCIA
    if _INSTANCIA is not None:
        try:
            _INSTANCIA.encerrar()
        finally:
            _INSTANCIA = None
