# -*- coding: utf-8 -*-
"""Overlay do editor de mapa dentro da janela principal da NIA.

O overlay cobre o ``centralWidget`` e recebe o núcleo real durante a sessão. Toda mudança de
layout (dock e núcleo) é de sessão: nada é gravado em preferências.
"""
from __future__ import annotations

from uuid import uuid4

from PyQt6.QtCore import Qt, QRect, QEvent, QTimer, QSize, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout, QInputDialog, QLabel, QMenu, QPushButton, QVBoxLayout, QWidget, QCheckBox, QFrame, QComboBox, QApplication,
)

from core import assistencia_planos as AP
from core import lembretes as LEM
from core.comandos_lembretes import assunto_de
from core import modelos_planos as MP
from core.interface_canvas import icon
from core.interface_mapa import EditorMapa

_PRI = "#00d4ff"
_TEXT = "#d8f8ff"

# Glass escuro estático: gradientes e bordas de 1 px sem blur em tempo real.
_ESTILO = f"""
QWidget#CanvasEditorOverlay {{
    background: transparent; border: none;
}}
QLabel {{ color: {_TEXT}; background: transparent; }}
QPushButton[canvasControl="true"] {{
    color: {_TEXT};
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(38,84,110,180), stop:1 rgba(12,40,58,190));
    border: 1px solid rgba(150,215,240,70); border-radius: 9px;
    padding: 7px 13px; min-height: 32px; font-size:14px;
}}
QPushButton[canvasControl="true"]:hover {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(52,112,142,205), stop:1 rgba(18,54,76,210));
    border: 1px solid rgba(160,230,255,120);
}}
QPushButton[canvasControl="true"]:focus {{ border: 2px solid {_PRI}; outline: none; }}
QPushButton[canvasControl="true"]:checked {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(24,150,175,220), stop:1 rgba(8,70,92,225));
    border: 2px solid #80f6fc;
}}
"""


class CanvasEditor(QWidget):
    """Editor do mapa mais toolbar de retorno, encaixado no Canvas."""

    voltar = pyqtSignal()
    contexto_mudou = pyqtSignal(dict)
    modo_mudou = pyqtSignal(bool)

    def __init__(self, stage, parent=None):
        super().__init__(stage if parent is None else parent)
        self._stage = stage
        self._mounted = False
        self._chat_aberto = False
        self.setObjectName('CanvasEditorOverlay')
        self.setStyleSheet(_ESTILO)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.modo_assistido = False
        self._geracao_modo = 0
        self._sessao_id = uuid4().hex
        self.header = QWidget(self)
        topo = QHBoxLayout(self.header)
        topo.setContentsMargins(8, 0, 8, 0)
        botao = QPushButton('←', self.header)
        botao.setObjectName('voltar_planos')
        botao.setToolTip('Voltar aos planos · salva as edições pendentes')
        botao.clicked.connect(self.voltar.emit)
        topo.addWidget(botao)
        self.titulo = QLabel('Plano', self.header)
        self.titulo.setStyleSheet('font-size:18px;font-weight:600;')
        topo.addWidget(self.titulo, 1)
        self.status = QLabel('Salvo', self.header)
        self.status.setObjectName('status_canvas_editor')
        topo.addWidget(self.status)
        self.botao_detalhes = QPushButton('Detalhes', self.header)
        self.botao_detalhes.clicked.connect(lambda: self.editor_internal.detalhes())
        topo.addWidget(self.botao_detalhes)
        self.gear = QPushButton('⚙', self.header)
        self.gear.setToolTip('Configurações deste canvas')
        self.gear.clicked.connect(self._configuracoes)
        topo.addWidget(self.gear)
        self.editor_internal = EditorMapa(self)
        self.editor_internal.estado_salvamento.connect(self.status.setText)
        self.editor_internal.estado_editado.connect(lambda: self.contexto_mudou.emit(self.contexto()))
        self.editor_internal.selecao_mudou.connect(lambda: self.contexto_mudou.emit(self.contexto()))
        self.editor_internal.acoes_extras = self._acoes_extras
        # Secondary actions retain the existing slots and object names.
        for attr, name, label, slot in (
            ('botao_modo', 'alternar_modo', 'Modo: Com a NIA', lambda: self.definir_modo(not self.modo_assistido)),
            ('botao_modelo', 'adicionar_modelo', 'Adicionar modelo como ramo', self._mostrar_menu_modelos),
            ('botao_lembrete', 'definir_lembrete', 'Definir lembrete', lambda: self.definir_lembrete()),
            ('botao_perguntar', 'perguntar_nia_card', 'Perguntar à NIA sobre este card', self._perguntar_nia),
            ('botao_salvar', 'salvar_canvas', 'Salvar · Ctrl+S', self._salvar),
        ):
            button = QPushButton(label, self)
            button.setObjectName(name)
            button.clicked.connect(slot)
            button.hide()
            setattr(self, attr, button)
        self.botao_salvar.setIcon(icon('save'))
        self.botao_salvar.setIconSize(QSize(20, 20))
        self.botao_salvar.setToolTip('Salvar · Ctrl+S')
        self.botao_modo.setCheckable(True)
        self.estado_nia = QLabel('NIA  |  ● Iniciando', self)
        self.estado_nia.setStyleSheet('font-size:14px;color:#bcebf5;')
        self.chat_toggle = QPushButton('Conversa', self)
        self.chat_toggle.setCheckable(True)
        self.chat_toggle.setStyleSheet(
            'QPushButton { min-height: 22px; padding: 3px 12px; font-size: 11px; }')
        self.chat_toggle.setFixedHeight(32)
        self.chat_toggle.setToolTip('Recolher/abrir chat sem perder o texto')
        self.chat_toggle.clicked.connect(self._alternar_chat)
        self.navegar = QPushButton('☰', self)
        self.navegar.setToolTip('Ferramentas e navegação da NIA')
        self.navegar.setStyleSheet('QPushButton { min-height: 20px; padding: 4px; }')
        self.navegar.setFixedSize(40, 36)
        self.navegar.clicked.connect(lambda: self.window()._right_panel.show_tools())
        self.editor_internal.zoom_bar.setParent(self)
        for button in self.findChildren(QPushButton):
            button.setProperty('canvasControl', True)
            button.style().unpolish(button)
            button.style().polish(button)
        self._config_panel = None
        self.parentWidget().installEventFilter(self)
        QApplication.instance().installEventFilter(self)
        self._reposicionar()

    def _acoes_extras(self, menu):
        menu.addSeparator()
        modelos = menu.addMenu('Adicionar modelo como ramo')
        modelos.setEnabled(bool(self.card_selecionado_id))
        for tipo in MP.TIPOS_MODELO:
            modelos.addAction(tipo, lambda checked=False, t=tipo: self.adicionar_modelo(t))
        modelos.addAction('Complementar ramo', self._complementar_ramo)
        for button in (self.botao_lembrete, self.botao_perguntar, self.botao_modo):
            action = menu.addAction(button.text(), button.click)
            if button is not self.botao_modo:
                action.setEnabled(bool(self.card_selecionado_id))

    def montar_janela(self):
        if self._mounted:
            return
        window = self.window()
        self._mounted = True
        self._chat_aberto = False
        self.chat_toggle.setChecked(False)
        self._botao_conversa_visivel = window._btn_chat_abajo.isVisible()
        window._btn_chat_abajo.hide()
        self._composer = window._composer
        self._composer_limits = (self._composer.minimumSize(), self._composer.maximumSize())
        self._composer_visivel = self._composer.isVisible()
        self._composer.setParent(self)
        self._composer.setMinimumWidth(0)
        self._composer.setMaximumWidth(16777215)
        self._composer.show()
        self._stage.motion.stop()
        self._stage.hud_stack.setParent(self)
        self._stage.hud_stack.show()
        self.atualizar_estado()
        self._reposicionar()

    def desmontar_janela(self):
        if not self._mounted:
            return
        self._mounted = False
        window = self.window()
        self._composer.setParent(window.centralWidget())
        self._composer.setMinimumSize(self._composer_limits[0])
        self._composer.setMaximumSize(self._composer_limits[1])
        window._composer_layout.insertWidget(1, self._composer, 1)
        self._composer.setVisible(self._composer_visivel)
        window._btn_chat_abajo.setVisible(self._botao_conversa_visivel)
        self._stage.hud_stack.setParent(self._stage)
        self._stage.hud_stack.show()
        self._stage.arrange(False)

    def atualizar_estado(self, *_):
        window = self.window()
        label = getattr(window, '_rail_state_lbl', None)
        self.estado_nia.setText('NIA  |  ' + (label.text() if label else '● Iniciando'))

    def _alternar_chat(self):
        self._chat_aberto = not self._chat_aberto
        self.chat_toggle.setChecked(self._chat_aberto)
        self._reposicionar()
        (self.window()._input if self._chat_aberto else self.chat_toggle).setFocus()

    def _configuracoes(self):
        if self._config_panel is None:
            panel = QFrame(self)
            panel.setStyleSheet('QFrame {background:#092637;border:1px solid #35617a;border-radius:12px;} QLabel,QCheckBox {color:#d8f8ff;}')
            layout = QVBoxLayout(panel)
            layout.addWidget(QLabel('Visualização'))
            grade = QCheckBox('Exibir grade pontilhada')
            grade.setChecked(self.editor_internal.cena.grade)
            layout.addWidget(grade)
            layout.addWidget(QLabel('Interação'))
            roda = QComboBox()
            roda.addItems(['Roda aproxima o mapa', 'Roda navega · Ctrl+roda aproxima'])
            roda.setCurrentIndex(1 if getattr(self.editor_internal._view,'roda_navega',False) else 0)
            layout.addWidget(roda)
            fechar = QPushButton('Fechar · Esc')
            fechar.clicked.connect(lambda: (panel.hide(), self.gear.setFocus()))
            layout.addWidget(fechar)
            def salvar():
                self.editor_internal.cena.grade = grade.isChecked()
                self.editor_internal._view.roda_navega = bool(roda.currentIndex())
                self.editor_internal._view.viewport().update()
                from core.interface_canvas import DockPreferences
                from pathlib import Path
                prefs = DockPreferences(self.window()._prefs.path)
                prefs.data['canvas'] = dict(grade=grade.isChecked(), roda_navega=bool(roda.currentIndex()))
                try:
                    prefs.save()
                except OSError:
                    self.status.setText('Não foi possível salvar as preferências.')
            grade.toggled.connect(salvar)
            roda.currentIndexChanged.connect(salvar)
            self._config_panel = panel
        panel = self._config_panel
        panel.setGeometry(max(12, self.width()-330), self.header.geometry().bottom()+4, 310, 240)
        panel.setVisible(not panel.isVisible())
        panel.raise_()
        if panel.isVisible():
            panel.findChild(QCheckBox).setFocus()

    def eventFilter(self, obj, event):
        if self.isVisible() and event.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress) and event.key() == Qt.Key.Key_Escape:
            if event.type() == QEvent.Type.KeyPress:
                if self._config_panel is not None and self._config_panel.isVisible():
                    self._config_panel.hide()
                    self.gear.setFocus()
                else:
                    self.editor_internal.cancelar_conexao()
                    self.editor_internal.detalhes(False)
                    self.botao_detalhes.setFocus()
            event.accept()
            return True
        if obj is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self._reposicionar()
        return super().eventFilter(obj, event)

    def definir_modo(self, assistido: bool) -> None:
        """Alterna Manual/Com a NIA sem tocar no mapa, seleção ou câmera."""
        if self.modo_assistido != bool(assistido):
            self._geracao_modo += 1
        self.modo_assistido = bool(assistido)
        self.botao_modo.setChecked(self.modo_assistido)
        self.botao_modo.setText(
            "Modo: Com a NIA" if self.modo_assistido else "Modo: Manual")
        self.modo_mudou.emit(self.modo_assistido)
        if self.editor_internal._plano is not None:
            self.contexto_mudou.emit(self.contexto())

    @property
    def card_selecionado_id(self) -> str | None:
        return self.editor_internal.card_selecionado_id

    @property
    def mudancas_pendentes(self) -> bool:
        return self.editor_internal.mudancas_pendentes

    def abrir(self, plano) -> None:
        self._sessao_id = uuid4().hex
        self.editor_internal.carregar(plano)
        self.titulo.setText(f'{plano.tipo} / {plano.titulo}')
        self.status.setText('✓ Salvo')
        from core.interface_canvas import DockPreferences
        from pathlib import Path
        prefs = DockPreferences(self.window()._prefs.path).data.get('canvas', {})
        self.editor_internal.cena.grade = prefs.get('grade', True)
        self.editor_internal._view.roda_navega = prefs.get('roda_navega', False)
        self.editor_internal.detalhes(self.width() >= 1400)
        # Enquadrar só depois de o overlay e seu viewport terem o tamanho final.
        QTimer.singleShot(0, self._centralizar_abertura)
        self.contexto_mudou.emit(self.contexto())

    def _centralizar_abertura(self):
        if self.isVisible() and not self.editor_internal.mudancas_pendentes:
            self._reposicionar()
            self.editor_internal.enquadrar()

    def contexto(self) -> dict:
        plano = self.editor_internal.plano_atual()
        self.titulo.setText(f'{plano.tipo} / {plano.titulo}')
        return {
            "plano_id": plano.id,
            "card_id": self.editor_internal.card_selecionado_id,
            "plano": plano,
            "modo_assistido": self.modo_assistido,
            "geracao_modo": self._geracao_modo,
            "sessao_id": self._sessao_id,
            "camera": dict(self.editor_internal._camera),
        }

    def selecionar_card(self, card_id: str | None) -> None:
        self.editor_internal.selecionar(card_id)
        self.contexto_mudou.emit(self.contexto())

    def adicionar_modelo(self, tipo: str) -> bool:
        """Adiciona um modelo como ramo do card selecionado, em um só undo."""
        if tipo not in MP.TIPOS_MODELO:
            return False
        card_id = self.card_selecionado_id
        if not card_id:
            self.status.setText("Selecione um card para receber o ramo.")
            return False
        plano = self.editor_internal.plano_atual()
        origem = next((c for c in plano.mapa.get("cards", [])
                       if c.get("id") == card_id), None)
        if origem is None:
            self.status.setText("O card de origem não existe mais.")
            return False
        ops = MP.ramo_modelo(tipo, card_id, origem)
        contexto = AP.montar_contexto(plano, card_id)
        validas, erros = AP.validar_lote(ops, plano, contexto)
        if erros or not validas:
            self.status.setText(erros[0] if erros else "Ramo inválido.")
            return False
        AP.aplicar_lote(self.editor_internal, validas, f"Modelo {tipo}")
        self.status.setText(f"Modelo {tipo} adicionado como ramo.")
        self.contexto_mudou.emit(self.contexto())
        return True

    def definir_lembrete(self, card_id: str | None = None) -> bool:
        """Cria lembrete local para o card selecionado (ou para o plano)."""
        texto, ok = QInputDialog.getText(
            self, "Definir lembrete", "Quando? Ex.: amanhã às 19h revisar exercício")
        if not ok or not str(texto or "").strip():
            return False
        horario, mensagem = LEM.interpretar(texto)
        if not horario:
            self.status.setText(mensagem)
            return False
        plano = self.editor_internal.plano_atual()
        alvo = card_id if card_id is not None else self.card_selecionado_id
        if self.editor_internal.mudancas_pendentes and not self.editor_internal.salvar()[0]:
            self.status.setText('Salve as alterações do mapa antes de criar o lembrete.')
            return False
        LEM.criar(plano.id, assunto_de(texto), horario, 'America/Sao_Paulo', alvo)
        from core import planos as BP
        disco = BP.carregar(plano.id)
        self.editor_internal._plano = BP.replace(self.editor_internal._plano,
            revisao=disco.revisao, lembretes=disco.lembretes)
        self.status.setText(mensagem)
        return True

    def _salvar(self) -> None:
        """Salva pelo mesmo fluxo do editor, com retorno visível no Canvas."""
        ok, mensagem = self.editor_internal.salvar()
        self.status.setText(mensagem)
        if not ok:
            self.status.setText(f"{mensagem}. Tente novamente.")

    def _perguntar_nia(self) -> None:
        janela = self.window()
        casca = getattr(janela, "_ui", None)
        if casca is not None:
            casca.perguntar_sobre_card(self.card_selecionado_id)
        else:
            self.status.setText("Abra a conversa para perguntar sobre o card.")

    def fechar_com_seguranca(self) -> bool:
        return self.editor_internal.fechar_com_seguranca()

    def _mostrar_menu_modelos(self) -> None:
        menu = QMenu(self)
        for tipo in MP.TIPOS_MODELO:
            menu.addAction(tipo, lambda checked=False, t=tipo: self.adicionar_modelo(t))
        menu.addSeparator()
        menu.addAction("Complementar ramo selecionado",
                       self._complementar_ramo)
        menu.exec(self.botao_modelo.mapToGlobal(
            self.botao_modelo.rect().bottomLeft()))

    def _complementar_ramo(self) -> None:
        """Adiciona cards ao ramo já existente sem duplicar sua raiz."""
        card_id = self.card_selecionado_id
        if not card_id:
            self.status.setText("Selecione um card para complementar.")
            return
        plano = self.editor_internal.plano_atual()
        existentes = {c.get("modelo") for c in plano.mapa.get("cards", [])
                      if c.get("modelo")}
        if not existentes:
            self.status.setText("Ainda não há ramo para complementar.")
            return
        self.adicionar_modelo(next(iter(existentes)))

    def _reposicionar(self):
        pai = self.parentWidget()
        if pai is None or not hasattr(self, 'editor_internal'):
            return
        if self.geometry() != pai.rect():
            self.setGeometry(pai.rect())
        w, h = self.width(), self.height()
        frame = getattr(self.window(), '_dwm_frame', None)
        top = int(frame.caption_height / self.devicePixelRatioF()) if frame and frame.active else 0
        compacto = w < 1450
        self.layout_compacto = compacto
        # Reserve o espaço do chat mesmo recolhido para manter o rodapé e o
        # viewport estáveis ao alternar a conversa.
        footer = 148
        self.header.setGeometry(14, top+8, max(100,w-28), 48)
        self.editor_internal.setGeometry(0, top+62, w, max(100,h-top-62-footer))
        self.editor_internal._dispor()
        zoom = self.editor_internal.zoom_bar
        zoom.adjustSize()
        zoom.move(max(4,w-zoom.width()-18), h-zoom.height()-16)
        self.navegar.setGeometry(150, h-46, 40, 36)
        self.estado_nia.setGeometry(156, h-144, min(200, max(80, w-500)), 28)
        self.chat_toggle.setGeometry((w-110)//2, h-42, 110, 32)
        self.chat_toggle.show()
        if self._mounted:
            # O núcleo tem tamanho mínimo de 120 px: reserve-o integralmente.
            size = max(120, self._stage.hud_stack.minimumWidth(),
                       self._stage.hud_stack.minimumHeight())
            self._stage.hud_stack.setGeometry(16, h-size-12, size, size)
            self._stage.hud_stack.raise_()
            # O chat ocupa só o vão central entre núcleo/navegação e zoom.
            lateral = max(200, zoom.width()+30)
            width = min(620, max(240, w-2*lateral))
            x = (w-width)//2
            y = self.chat_toggle.y()-56-10
            self._composer.setGeometry(x, y, width, 56)
            self._composer.setVisible(self._chat_aberto)
            self._composer.raise_()
        self.editor_internal.zoom_bar.show()
        self.header.raise_()
        self.estado_nia.raise_()
        self.navegar.raise_()
        self.chat_toggle.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposicionar()
