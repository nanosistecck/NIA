# -*- coding: utf-8 -*-
"""Central de Aprendizado Adaptativo: UI PyQt6 real, leve e responsiva (F10)."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton, QSplitter,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

# Tokens do 11_UI_FLIGHT_PLAN.md; o overlay existente mantém a paleta azul.
_TOKENS = {
    'dark': {
        'fundo': '#0B111C', 'painel': '#152235', 'card': '#1D3047',
        'borda': '#344A63', 'acao': '#60A5FA', 'aprendizado': '#A78BFA',
        'validado': '#4ADE80', 'texto': '#E2E8F0', 'secundario': '#94A3B8',
    },
    'light': {
        'fundo': '#F8FAFC', 'painel': '#FFFFFF', 'card': '#EEF2FF',
        'borda': '#CBD5E1', 'acao': '#1D4ED8', 'aprendizado': '#6D28D9',
        'validado': '#15803D', 'texto': '#0F172A', 'secundario': '#475569',
    },
}


class PainelAprendizado(QWidget):
    """Painel com listas reais da memória procedural e ações de inspeção."""

    def __init__(self, *, memoria=None, tema: str = 'dark', pai=None):
        super().__init__(pai)
        self.memoria = memoria
        self.tema_atual = 'dark'
        self.setWindowTitle('NIA — Central de Aprendizado Adaptativo')
        self.setMinimumSize(760, 520)
        self.resize(1120, 740)

        topo = QHBoxLayout()
        titulo = QLabel('Aprendizado Adaptativo')
        titulo.setObjectName('titulo')
        self.filtro = QLineEdit()
        self.filtro.setPlaceholderText('Buscar conhecimento, procedimento ou experiência')
        self.filtro.textChanged.connect(self.atualizar)
        self.btn_atualizar = QPushButton('Atualizar')
        self.btn_atualizar.clicked.connect(self.atualizar)
        self.btn_exportar = QPushButton('Exportar Markdown')
        self.btn_exportar.clicked.connect(self._exportar_para_area)
        topo.addWidget(titulo)
        topo.addWidget(self.filtro, 1)
        topo.addWidget(self.btn_atualizar)
        topo.addWidget(self.btn_exportar)

        self.abas = QTabWidget()
        self.lista_conhecimentos = QListWidget()
        self.lista_procedimentos = QListWidget()
        self.lista_experiencias = QListWidget()
        self.lista_atividades = QListWidget()
        self.lista_correcoes = QListWidget()
        visao = QLabel('Visão geral: lacunas detectadas, evidências e estado real. '
                       'Nenhuma porcentagem simulada é exibida.')
        visao.setWordWrap(True)
        configuracoes = QLabel('Configurações: retenção, privacidade e limites de '
                               'concorrência ficam na política de segurança.')
        configuracoes.setWordWrap(True)

        # Workspace colaborativo: documento à esquerda (38%), navegador de
        # resultados à direita (62%), ajustável pelo usuário entre 25% e 65%.
        self.editor_documento = QTextEdit()
        self.editor_documento.setPlaceholderText('Documento da sessão colaborativa')
        self.navegador = QListWidget()
        self.detalhe_pesquisa = QLabel('Resultados com fonte e estado real.')
        self.detalhe_pesquisa.setWordWrap(True)
        painel_direito = QWidget()
        ld = QVBoxLayout(painel_direito)
        ld.addWidget(self.navegador, 1)
        ld.addWidget(self.detalhe_pesquisa)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.editor_documento)
        self.splitter.addWidget(painel_direito)
        self.splitter.setStretchFactor(0, 38)
        self.splitter.setStretchFactor(1, 62)
        self.splitter.setSizes([380, 620])

        self.abas.addTab(visao, 'Visão geral')
        self.abas.addTab(self.splitter, 'Workspace')
        self.abas.addTab(self.lista_conhecimentos, 'Conhecimentos')
        self.abas.addTab(self.lista_procedimentos, 'Procedimentos')
        self.abas.addTab(self.lista_experiencias, 'Experiências')
        self.abas.addTab(self.lista_atividades, 'Atividades')
        self.abas.addTab(self.lista_correcoes, 'Correções')
        self.abas.addTab(configuracoes, 'Configurações')

        self.status = QLabel('Pronto')
        self.status.setObjectName('status')
        layout = QVBoxLayout(self)
        layout.addLayout(topo)
        layout.addWidget(self.abas, 1)
        layout.addWidget(self.status)
        self.set_tema(tema)
        self.atualizar()

    @staticmethod
    def estilo(tema: str = 'dark') -> str:
        t = _TOKENS.get(tema, _TOKENS['dark'])
        return f"""
        QWidget {{ background: {t['fundo']}; color: {t['texto']};
                  font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; }}
        QLabel#titulo {{ color: {t['aprendizado']}; font-size: 20px; font-weight: 600; }}
        QLabel#status {{ color: {t['secundario']}; }}
        QTabWidget::pane {{ background: {t['painel']}; border: 1px solid {t['borda']};
                            border-radius: 12px; }}
        QTabBar::tab {{ background: {t['painel']}; color: {t['secundario']};
                        padding: 8px 12px; border-radius: 8px; }}
        QTabBar::tab:selected {{ background: {t['card']}; color: {t['texto']}; }}
        QListWidget, QLineEdit {{ background: {t['card']}; color: {t['texto']};
                                  border: 1px solid {t['borda']}; border-radius: 8px;
                                  padding: 6px; }}
        QPushButton {{ background: {t['acao']}; color: #FFFFFF; border-radius: 8px;
                       padding: 8px 12px; }}
        QPushButton:hover {{ background: {t['aprendizado']}; }}
        """.strip()

    def definir_workspace(self, documento: str = '', resultados=()) -> None:
        """Preenche o workspace com documento e resultados de pesquisa reais."""
        self.editor_documento.setPlainText(str(documento or ''))
        self.navegador.clear()
        for item in (resultados or ()):
            if isinstance(item, dict):
                rotulo = f"{item.get('titulo', '')} · {item.get('url', '')}"[:160]
            else:
                rotulo = str(item)[:160]
            self.navegador.addItem(rotulo)
        self.detalhe_pesquisa.setText(
            f'{self.navegador.count()} resultado(s); cada item conserva sua fonte.')

    def set_tema(self, tema: str) -> None:
        self.tema_atual = 'light' if tema == 'light' else 'dark'
        self.setStyleSheet(self.estilo(self.tema_atual))

    def _texto_filtro(self) -> str:
        return self.filtro.text().strip().casefold()

    def _tem_filtro(self, *valores) -> bool:
        filtro = self._texto_filtro()
        return not filtro or any(filtro in str(v or '').casefold() for v in valores)

    def atualizar(self) -> None:
        for lista in (self.lista_conhecimentos, self.lista_procedimentos,
                      self.lista_experiencias, self.lista_atividades,
                      self.lista_correcoes):
            lista.clear()
        if self.memoria is None:
            self.status.setText('Sem memória procedural carregada')
            return
        for item in self.memoria.listar('knowledge'):
            if self._tem_filtro(item.get('titulo'), item.get('origem')):
                self.lista_conhecimentos.addItem(
                    f"{item.get('titulo', '')} · {item.get('origem', '')}")
        for item in self.memoria.listar('procedures'):
            if self._tem_filtro(item.get('nome'), item.get('objetivo')):
                self.lista_procedimentos.addItem(
                    f"{item.get('nome', '')} · v{item.get('versao', 1)}")
        for item in self.memoria.listar('experiences'):
            if self._tem_filtro(item.get('resultado')):
                self.lista_experiencias.addItem(str(item.get('resultado', '')))
        for item in self.memoria.listar('sessions'):
            if self._tem_filtro(item.get('objetivo')):
                self.lista_atividades.addItem(str(item.get('objetivo', '')))
        for item in self.memoria.listar('corrections'):
            if self._tem_filtro(item.get('descricao')):
                self.lista_correcoes.addItem(str(item.get('descricao', '')))
        self.status.setText(
            f"{self.lista_conhecimentos.count()} conhecimento(s), "
            f"{self.lista_procedimentos.count()} procedimento(s)")

    def exportar(self) -> str:
        linhas = ['# Aprendizado Adaptativo', '']
        if self.memoria is not None:
            for tabela, titulo in (('knowledge', 'Conhecimentos'),
                                   ('procedures', 'Procedimentos'),
                                   ('experiences', 'Experiências')):
                linhas += [f'## {titulo}', '']
                for item in self.memoria.listar(tabela):
                    linhas.append('- ' + str(item.get('titulo')
                                             or item.get('nome')
                                             or item.get('resultado')
                                             or item.get('id', ''))[:160])
                linhas.append('')
        return '\n'.join(linhas)

    def _exportar_para_area(self) -> None:
        self.status.setText('Exportação disponível via exportar()')
