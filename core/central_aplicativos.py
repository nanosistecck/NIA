# -*- coding: utf-8 -*-
"""Central de Aplicativos da NIA — launchpad integrado à janela principal.

 QWidget leve, sem WebEngine/Electron, sem serviço residente e sem polling.
 Usa o registro central como única fonte de aplicativos e o GerenciadorJanelas
 para abrir interfaces. Ações de ferramentas são solicitadas ao motor pela
 ponte existente — a Central nunca executa uma operação protegida sozinha.
"""
from __future__ import annotations

from collections import OrderedDict
import html

from PyQt6.QtCore import QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from core.interface_canvas import icon
from core.registro_aplicativos import buscar, categorias, disponibilidade, por_id

# Paleta da especificação, em tons próximos do `ui.C` existente.
FUNDO = '#0B101A'
SUPERFICIE = '#141C2A'
TEXTO = '#F1F5F9'
TEXTO_SEC = '#94A3B8'
BORDA = 'rgba(255,255,255,0.10)'


class _Icones:
    """Cache limitado e FIFO; nada é carregado até o app aparecer na grade."""
    def __init__(self, limite=64):
        self.limite = limite
        self._dados: OrderedDict[tuple[str, str], QIcon] = OrderedDict()

    def obter(self, nome: str, cor: str) -> QIcon:
        chave = (nome, cor)
        if chave in self._dados:
            self._dados.move_to_end(chave)
            return self._dados[chave]
        try:
            item = icon(nome, cor)
        except Exception:
            item = icon('system', cor)
        self._dados[chave] = item
        if len(self._dados) > self.limite:
            self._dados.popitem(last=False)
        return item


class AppTile(QWidget):
    acionado = pyqtSignal(str)
    contextual = pyqtSignal(str, str)

    def __init__(self, descritor, icones: _Icones, tamanho=64):
        super().__init__()
        self.id = descritor.id
        self.descritor = descritor
        self._tamanho = tamanho
        self.setObjectName('AppTile')
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(f'{descritor.nome}\n{descritor.descricao}')
        self.setAccessibleName(descritor.nome)
        self.setAccessibleDescription(descritor.descricao)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(6)
        self.icone = QLabel()
        self.icone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icone.setFixedSize(tamanho, tamanho)
        self.icone.setPixmap(icones.obter(descritor.icone, descritor.cor)
                             .pixmap(tamanho, tamanho))
        self.nome = QLabel(descritor.nome)
        self.nome.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.nome.setWordWrap(False)
        self.nome.setFont(QFont('Segoe UI', 9))
        self.nome.setStyleSheet(f'color:{TEXTO}; background:transparent;')
        layout.addWidget(self.icone, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.nome, 0, Qt.AlignmentFlag.AlignHCenter)
        self.setStyleSheet(
            'QWidget#AppTile { background: rgba(255,255,255,0.02);'
            f'border:1px solid transparent; border-radius:{max(14, tamanho//4)}px; }}'
            'QWidget#AppTile:hover { background: rgba(0,212,255,0.10);'
            'border-color: rgba(0,212,255,0.35); }'
            'QWidget#AppTile:focus { outline:2px solid #00d4ff; '
            'border-color:#00d4ff; }')

    def mouseDoubleClickEvent(self, event):
        self.acionado.emit(self.id)
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.acionado.emit(self.id)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        acoes = (
            ('Abrir aplicativo', 'abrir'),
            ('Adicionar aos favoritos', 'favorito_adicionar'),
            ('Remover dos favoritos', 'favorito_remover'),
            ('Fixar no dock', 'dock_fixar'),
            ('Remover do dock', 'dock_remover'),
            ('Informações', 'informacoes'),
            ('Configurar', 'configurar'),
            ('Usar com a NIA', 'usar'),
        )
        for rotulo, chave in acoes:
            acao = menu.addAction(rotulo)
            acao.triggered.connect(
                lambda _=False, c=chave: self.contextual.emit(self.id, c))
        menu.exec(event.globalPos())

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.acionado.emit(self.id)
            return
        super().keyPressEvent(event)


class CentralAplicativos(QWidget):
    """Launchpad dentro da janela principal; uma instância por MainWindow."""

    app_aberto = pyqtSignal(str)
    ferramenta_solicitada = pyqtSignal(str, str, dict)
    acao_interface = pyqtSignal(str, str)
    dock_acao_solicitada = pyqtSignal(str)
    fechada = pyqtSignal()

    def __init__(self, parent=None, *, registro=None, gerenciador=None,
                 tamanho_icone=64, animacoes=True):
        super().__init__(parent)
        self.setObjectName('CentralAplicativos')
        self._registro = registro
        self._gerenciador = gerenciador
        self._tamanho = tamanho_icone
        self._animacoes = bool(animacoes)
        self._icones = _Icones()
        self._categoria = 'todos'
        self._favoritos: set[str] = set()
        self._fixados: set[str] = set()
        self._acoes_dock: set[str] = set()
        self._visiveis: list = []
        self._tiles: dict[str, AppTile] = {}
        self._colunas = 0
        self._sincronizado = False
        self._aberta = False
        self._construir()

    # ── construção ─────────────────────────────────────────────────────────
    def _construir(self):
        self.setStyleSheet(
            f'QWidget#CentralAplicativos {{ background: {FUNDO}; }}'
            'QWidget#CentralFundo { background: qlineargradient('
            'x1:0,y1:0,x2:0,y2:1, stop:0 rgba(11,16,26,250),'
            'stop:1 rgba(8,20,32,248)); border:1px solid rgba(255,255,255,0.10);'
            'border-radius:20px; }'
            f'QLineEdit#CentralBusca {{ background: {SUPERFICIE}; '
            'color:#F1F5F9; border:1px solid rgba(255,255,255,0.12);'
            'border-radius:14px; padding:0 12px; selection-background-color:#00d4ff; }'
            'QPushButton#CentralCat { background: rgba(255,255,255,0.03); '
            'color:#94A3B8; border:1px solid transparent; border-radius:12px;'
            'padding:6px 12px; } QPushButton#CentralCat:checked { '
            'background: rgba(0,212,255,0.16); color:#F1F5F9;'
            'border-color: rgba(0,212,255,0.45); }'
            'QPushButton#CentralFechar { background:rgba(255,255,255,0.04);'
            'color:#F1F5F9; border-radius:12px; }'
            'QLabel#CentralVazio { color:#94A3B8; font-size:15px; }')
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        self._fundo = QFrame()
        self._fundo.setObjectName('CentralFundo')
        externo.addWidget(self._fundo)
        col = QVBoxLayout(self._fundo)
        col.setContentsMargins(28, 20, 28, 20)
        col.setSpacing(14)

        topo = QHBoxLayout()
        titulo = QLabel('Central de Aplicativos')
        titulo.setStyleSheet(f'color:{TEXTO}; font-size:20px; font-weight:600;')
        fechar = QPushButton('✕')
        fechar.setObjectName('CentralFechar')
        fechar.setFixedSize(38, 38)
        fechar.setToolTip('Fechar a Central (Esc)')
        fechar.setAccessibleName('Fechar Central de Aplicativos')
        fechar.clicked.connect(self.fechar)
        topo.addWidget(titulo)
        topo.addStretch(1)
        topo.addWidget(fechar)
        col.addLayout(topo)

        busca = QHBoxLayout()
        self._campo = QLineEdit()
        self._campo.setObjectName('CentralBusca')
        self._campo.setPlaceholderText('Pesquisar aplicativos e habilidades...')
        self._campo.setAccessibleName('Pesquisar aplicativos e habilidades')
        self._campo.setFixedHeight(44)
        self._campo.setMaximumWidth(520)
        self._campo.setMinimumWidth(320)
        self._campo.textChanged.connect(self._agendar_busca)
        self._limpar = QPushButton('✕')
        self._limpar.setFixedSize(36, 36)
        self._limpar.setToolTip('Limpar pesquisa')
        self._limpar.clicked.connect(lambda: self._campo.setText(''))
        self._limpar.setVisible(False)
        busca.addStretch(1); busca.addWidget(self._campo, 0)
        busca.addWidget(self._limpar); busca.addStretch(1)
        col.addLayout(busca)
        self._tmr_busca = QTimer(self)
        self._tmr_busca.setSingleShot(True)
        self._tmr_busca.setInterval(80)
        self._tmr_busca.timeout.connect(self._aplicar_filtro)

        self._categorias = QHBoxLayout()
        self._botoes_categoria: dict[str, QPushButton] = {}
        for nome in (categorias() if self._registro else ('todos',)):
            botao = QPushButton(nome.title())
            botao.setObjectName('CentralCat')
            botao.setCheckable(True)
            botao.setChecked(nome == 'todos')
            botao.clicked.connect(lambda _=False, c=nome: self.definir_categoria(c))
            self._botoes_categoria[nome] = botao
            self._categorias.addWidget(botao)
        self._categorias.addStretch(1)
        col.addLayout(self._categorias)

        self._area = QScrollArea()
        self._area.setWidgetResizable(True)
        self._area.setFrameShape(QFrame.Shape.NoFrame)
        self._area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._area.setStyleSheet('QScrollArea { background:transparent; }'
                                 'QWidget#CentralGrid { background:transparent; }'
                                 'QScrollBar:vertical { width:6px; }')
        self._area.viewport().setStyleSheet('background:transparent;')
        self._grelha_widget = QWidget()
        self._grelha_widget.setObjectName('CentralGrid')
        self._grelha_widget.setStyleSheet('background:transparent;')
        self._grelha = QGridLayout(self._grelha_widget)
        self._grelha.setContentsMargins(4, 4, 4, 4)
        self._grelha.setHorizontalSpacing(28)
        self._grelha.setVerticalSpacing(26)
        self._area.setWidget(self._grelha_widget)
        col.addWidget(self._area, 1)

        self._vazio = QLabel('Nenhum aplicativo corresponde à pesquisa.')
        self._vazio.setObjectName('CentralVazio')
        self._vazio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._vazio.setVisible(False)
        col.addWidget(self._vazio)

        self._atalho_esc = QShortcut(QKeySequence('Escape'), self)
        self._atalho_esc.activated.connect(self.fechar)

    # ── dados ──────────────────────────────────────────────────────────────
    def definir_favoritos(self, identificadores):
        self._favoritos = set(identificadores or ())
        self._aplicar_filtro()

    def definir_fixados(self, identificadores):
        self._fixados = set(identificadores or ())

    def definir_acoes_dock(self, identificadores) -> None:
        """Ids que devem acionar o botão real do dock, não abrir janela."""
        self._acoes_dock = {str(x) for x in (identificadores or ())}

    def definir_categoria(self, categoria: str):
        if categoria not in self._botoes_categoria:
            return
        self._categoria = categoria
        for nome, botao in self._botoes_categoria.items():
            botao.setChecked(nome == categoria)
        self._aplicar_filtro()

    def refresh(self):
        """Recarrega metadados compactos; chamado só ao abrir/fechar dock."""
        if self._registro is not None:
            if not self._sincronizado:
                self._registro.sincronizar_habilidades()
                self._registro.sincronizar_ferramentas()
                self._sincronizado = True
            for nome in self._registro.categorias():
                if nome not in self._botoes_categoria:
                    botao = QPushButton(nome.title())
                    botao.setObjectName('CentralCat')
                    botao.setCheckable(True)
                    botao.clicked.connect(
                        lambda _=False, c=nome: self.definir_categoria(c))
                    self._botoes_categoria[nome] = botao
                    self._categorias.insertWidget(
                        max(0, self._categorias.count() - 1), botao)
        self._aplicar_filtro()

    def _agendar_busca(self, texto):
        self._limpar.setVisible(bool(texto))
        if self._animacoes:
            self._tmr_busca.start()
        else:
            self._aplicar_filtro()

    def _aplicar_filtro(self):
        if self._registro is None:
            return
        itens = buscar(self._campo.text(), self._categoria,
                       favoritos=self._favoritos)
        largura = max(self._grelha_widget.width(), self.width() - 80, 320)
        minimo = self._tamanho + 44
        # Faixas da especificação (referências, não limites rígidos).
        if largura <= 480:
            maximo = 3
        elif largura <= 768:
            maximo = 4
        elif largura <= 1024:
            maximo = 5
        elif largura <= 1440:
            maximo = 7
        else:
            maximo = 9
        colunas = max(2, min(maximo, largura // minimo))
        ids = tuple(i.id for i in itens)
        if ids == tuple(i.id for i in self._visiveis) \
                and colunas == self._colunas and self._tiles:
            self._vazio.setVisible(not itens)
            self._area.setVisible(bool(itens))
            return  # nada mudou: não recria widgets nem ícones
        for widget in list(self._grelha_widget.findChildren(AppTile)):
            widget.setParent(None)
            widget.deleteLater()
        while self._grelha.count():
            item = self._grelha.takeAt(0)
            if item.layout() is not None:
                item.layout().deleteLater()
        self._tiles.clear()
        self._visiveis = list(itens)
        self._colunas = colunas
        for indice, descritor in enumerate(itens):
            tile = AppTile(descritor, self._icones, self._tamanho)
            tile.acionado.connect(self.abrir_app)
            tile.contextual.connect(self._contextual)
            self._grelha.addWidget(tile, indice // colunas, indice % colunas)
            self._tiles[descritor.id] = tile
        self._vazio.setVisible(not itens)
        self._area.setVisible(bool(itens))
    # ── ciclo ──────────────────────────────────────────────────────────────
    def abrir(self, regiao: QRect | None = None):
        if regiao is not None:
            self.setGeometry(regiao)
        self.refresh()
        self.show()
        self.raise_()
        self._aberta = True
        self._campo.setFocus()
        return self

    def fechar(self):
        if not self._aberta:
            return
        self._aberta = False
        self.hide()
        self.fechada.emit()

    def alternar(self, regiao: QRect | None = None):
        if self._aberta:
            self.fechar()
            return False
        self.abrir(regiao)
        return True

    @property
    def aberta(self) -> bool:
        return self._aberta

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._visiveis:
            self._aplicar_filtro()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.fechar()
            return
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right,
                           Qt.Key.Key_Up, Qt.Key.Key_Down):
            self._navegar(event.key())
            return
        super().keyPressEvent(event)

    def _navegar(self, tecla):
        ids = [i.id for i in self._visiveis]
        if not ids:
            return
        atual = next((i for i, w in self._tiles.items() if w.hasFocus()), None)
        indice = ids.index(atual) if atual in ids else 0
        colunas = max(1, self._grelha.columnCount())
        if tecla == Qt.Key.Key_Right:
            indice += 1
        elif tecla == Qt.Key.Key_Left:
            indice -= 1
        elif tecla == Qt.Key.Key_Down:
            indice += colunas
        else:
            indice -= colunas
        indice %= len(ids)
        self._tiles[ids[indice]].setFocus()

    # ── ações ──────────────────────────────────────────────────────────────
    def abrir_app(self, identificador: str):
        if identificador in self._acoes_dock:
            self.dock_acao_solicitada.emit(identificador)
            return
        descritor = por_id(identificador) if self._registro is None \
            else self._registro.por_id(identificador)
        if descritor is None:
            return
        estado = disponibilidade(identificador) if self._registro is None \
            else self._registro.disponibilidade(identificador)
        if not estado.pronta:
            self.acao_interface.emit('erro', estado.motivo)
            return
        if descritor.possui_interface and self._gerenciador is not None:
            chave = descritor.janela or descritor.id
            if chave in self._gerenciador.registradas():
                self._gerenciador.abrir(chave)
                self.app_aberto.emit(identificador)
                return
        if descritor.executavel_por_nia:
            self.ferramenta_solicitada.emit(
                descritor.dominio_ferramenta, 'usar', {'app': identificador})
        else:
            self.acao_interface.emit('erro', 'Ferramenta sem execução disponível.')

    def _contextual(self, identificador: str, acao: str):
        if acao in ('favorito_adicionar', 'favorito_remover', 'dock_fixar', 'dock_remover'):
            self.acao_interface.emit(acao, identificador)
            return
        if acao == 'informacoes':
            descritor = self._registro.por_id(identificador) if self._registro else None
            self.acao_interface.emit('informacoes',
                                     descritor.descricao if descritor else identificador)
            return
        self.abrir_app(identificador)
