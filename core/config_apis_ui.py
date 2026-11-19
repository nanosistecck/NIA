"""Provedores e modelos: APIs externas e Ollama em um componente reutilizável.

O conteúdo nasceu do antigo ``ConfigAPIsDialog``. Agora vive em
``ConfigAPIsPanel``, uma única implementação usada pelo dashboard de
Configurações — a engrenagem clássica e o painel apontam para a mesma página.
A rede roda em ``QThreadPool``; a gravação e os widgets ficam na thread Qt.

Regras preservadas do painel anterior:

- múltiplas chaves por provedor, com cadastro, edição, substituição, teste,
  pausa e exclusão;
- consulta, filtro e seleção de modelos por conexão;
- descoberta, seleção e ativação de modelos do Ollama;
- chaves sempre mascaradas na lista e fora de mensagens de erro;
- resultados atrasados descartados por token/versão;
- ``config/nia.db`` e ``config/api_keys.json`` continuam sendo a fonte de
  verdade. Nada aqui inventa um armazenamento paralelo.
"""
from PyQt6.QtCore import Qt, QObject, QRunnable, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import (QAbstractButton, QButtonGroup, QComboBox,
                             QFormLayout, QFrame,
                             QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                             QProgressBar, QPushButton, QSizePolicy,
                             QStackedWidget, QVBoxLayout, QWidget)
import json
from datetime import datetime, timezone, timedelta

from core import db_chaves, llm_router, valida_chave
from core import llm_client
from core.provedores import PROVEDORES, nome_do_provedor


class _Sinais(QObject):
    pronto = pyqtSignal(object)


class _Trabalho(QRunnable):
    def __init__(self, funcao):
        super().__init__()
        self.funcao = funcao
        self.sinais = _Sinais()

    def run(self):
        try:
            resultado = self.funcao()
        except Exception:
            resultado = None
        self.sinais.pronto.emit(resultado)


def _mascarar_chave(chave) -> str:
    """Nunca devolve a credencial inteira; curtas ficam só com o cadeado."""
    texto = str(chave or '')
    if len(texto) < 8:
        return '••••'
    return '••••' + texto[-4:]


def _repolir(widget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _rotulo(texto: str, parent=None) -> QLabel:
    lab = QLabel(texto, parent)
    lab.setObjectName('FieldLabel')
    lab.setWordWrap(True)
    return lab


def _secao(titulo: str, subtitulo: str = '', parent=None) -> QFrame:
    caixa = QFrame(parent)
    caixa.setObjectName('PanelSection')
    v = QVBoxLayout(caixa)
    v.setContentsMargins(16, 14, 16, 16)
    v.setSpacing(9)
    titulo_lbl = QLabel(titulo, caixa)
    titulo_lbl.setObjectName('SectionTitle')
    v.addWidget(titulo_lbl)
    if subtitulo:
        sub = QLabel(subtitulo, caixa)
        sub.setObjectName('SectionHint')
        sub.setWordWrap(True)
        v.addWidget(sub)
    corpo = QVBoxLayout()
    corpo.setSpacing(10)
    v.addLayout(corpo)
    caixa.body = corpo
    return caixa


def testar_configuracao_legada(parent, provedor, chave, feedback):
    """F2 mantém seu contrato, mas uma chave nova aguarda validação assíncrona."""
    db_chaves.adicionar_chave(provedor, chave, label='configuracao', status='pendente')
    row = next(r for r in db_chaves.listar_chaves(provedor) if r['key'] == chave)
    trabalho = _Trabalho(lambda: valida_chave.testar(provedor, chave, row['base_url']))
    if not hasattr(parent, '_testes_credenciais'):
        parent._testes_credenciais = set()
    parent._testes_credenciais.add(trabalho)

    def concluir(resultado):
        parent._testes_credenciais.discard(trabalho)
        if resultado is None:
            feedback('CHAVE: teste indisponível; use APIs externas para testar novamente.')
            return
        atualizada = db_chaves.aplicar_validacao(row['id'], row['revision'], resultado)
        if resultado.apta and atualizada:
            try:
                llm_client.salvar_config_local({'gemini_api_key': chave})
            except Exception:
                feedback('CHAVE: validada no banco; não foi possível atualizar a cópia legada.')
        llm_router.recarregar()
        feedback('CHAVE: ' + resultado.mensagem)
    trabalho.sinais.pronto.connect(concluir)
    QThreadPool.globalInstance().start(trabalho)
    llm_router.recarregar()


class ConfigAPIsPanel(QWidget):
    """Página compartilhada de Provedores e modelos.

    ``mostrar_area('apis'|'ollama')`` escolhe a área visível. O dashboard monta
    este componente sob demanda; a primeira abertura lê apenas o banco e o JSON
    locais — nenhuma consulta de rede é disparada sozinha.
    """

    AREAS = ('apis', 'ollama')
    credencial_pronta = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('ProvidersPanel')
        self._versao = 0
        self._local_versao = 0
        self._registro = None
        self._fechado = False
        self._trabalhos = set()
        self._tentativas = {}
        self._sequencia_teste = 0
        self._lote = 0
        self._conexao_modelos_id = None
        self._modelos_disponiveis = []
        self._area = 'apis'

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(12)

        self.efetivo = QLabel(self)
        self.efetivo.setObjectName('EffectiveState')
        self.efetivo.setWordWrap(True)
        self.efetivo.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        raiz.addWidget(self.efetivo)

        troca = QHBoxLayout()
        troca.setSpacing(6)
        self._grupo_areas = QButtonGroup(self)
        self._grupo_areas.setExclusive(True)
        self._botoes_area: dict[str, QPushButton] = {}
        for nome, rotulo in (('apis', 'APIs externas'), ('ollama', 'Ollama')):
            botao = QPushButton(rotulo, self)
            botao.setObjectName('Segment')
            botao.setCheckable(True)
            botao.setCursor(Qt.CursorShape.PointingHandCursor)
            botao.setAccessibleName(f'Área {rotulo}')
            botao.clicked.connect(lambda _=False, n=nome: self.mostrar_area(n))
            self._grupo_areas.addButton(botao)
            self._botoes_area[nome] = botao
            troca.addWidget(botao)
        troca.addStretch(1)
        raiz.addLayout(troca)

        self._stack = QStackedWidget(self)
        self._stack.setObjectName('ProviderStack')
        self._pagina_apis = self._construir_apis()
        self._pagina_ollama = self._construir_ollama()
        self._stack.addWidget(self._pagina_apis)
        self._stack.addWidget(self._pagina_ollama)
        raiz.addWidget(self._stack, 1)

        self.mostrar_area('apis')
        self._achatar_controles()
        politica = self.sizePolicy()
        politica.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        self.setSizePolicy(politica)
        self._atualizar()

    def _achatar_controles(self) -> None:
        """Deixa botões e campos encolherem antes de surgir rolagem horizontal."""
        for controle in self.findChildren((QAbstractButton, QComboBox, QLineEdit)):
            minimo = 56 if isinstance(controle, QAbstractButton) else 84
            controle.setMinimumWidth(minimo)
            politica = controle.sizePolicy()
            politica.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
            controle.setSizePolicy(politica)

    # ── construção ─────────────────────────────────────────────────────────
    def _construir_apis(self) -> QWidget:
        pagina = QWidget(self)
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        barra = QHBoxLayout()
        barra.setSpacing(6)
        self.resumo = QLabel(pagina)
        self.resumo.setObjectName('SectionHint')
        self.resumo.setWordWrap(True)
        barra.addWidget(self.resumo, 1)
        self.filtro_status = QComboBox(pagina)
        self.filtro_status.setAccessibleName('Filtrar APIs por estado')
        for rotulo, estado in [('Todas as APIs', ''), ('Validadas', 'validado'),
                               ('Inválidas', 'invalido'), ('Esgotadas', 'esgotado'),
                               ('Limite temporário', 'limitado'),
                               ('Inconclusivas', 'inconclusivo'),
                               ('Não verificadas', 'nao_verificada'),
                               ('Pausadas', 'pausadas')]:
            self.filtro_status.addItem(rotulo, estado)
        self.filtro_status.currentIndexChanged.connect(self._atualizar)
        barra.addWidget(self.filtro_status)
        self.validar_todas = QPushButton('Validar todas', pagina)
        self.validar_todas.setObjectName('Secondary')
        self.validar_todas.setAccessibleName('Validar todas as APIs cadastradas')
        self.validar_todas.clicked.connect(self._validar_todas)
        self.cancelar_lote = QPushButton('Cancelar', pagina)
        self.cancelar_lote.setObjectName('Secondary')
        self.cancelar_lote.setAccessibleName('Cancelar a verificação em lote')
        self.cancelar_lote.clicked.connect(self._cancelar_validacao)
        self.cancelar_lote.setEnabled(False)
        barra.addWidget(self.validar_todas)
        barra.addWidget(self.cancelar_lote)
        lay.addLayout(barra)
        self.progresso = QProgressBar(pagina)
        self.progresso.setObjectName('PanelProgress')
        self.progresso.setTextVisible(False)
        self.progresso.setVisible(False)
        lay.addWidget(self.progresso)

        formulario = _secao(
            'Nova conexão ou edição',
            'A credencial é testada antes de substituir uma conexão existente. '
            'Chaves já salvas aparecem mascaradas na lista.',
            pagina)
        self.provedor = QComboBox(formulario)
        self.provedor.setAccessibleName('Provedor da conexão')
        for pid, spec in sorted(PROVEDORES.items(), key=lambda p: p[1].get('nome', p[0])):
            self.provedor.addItem(spec.get('nome', pid), pid)
        self.chave = QLineEdit(formulario)
        self.chave.setEchoMode(QLineEdit.EchoMode.Password)
        self.chave.setPlaceholderText('Cole a chave; ao editar, vazio conserva a atual')
        self.chave.setAccessibleName('Chave da conexão')
        self.apelido = QLineEdit(formulario)
        self.apelido.setPlaceholderText('Ex.: conta principal')
        self.apelido.setAccessibleName('Apelido da conexão')
        form = QFormLayout()
        form.setSpacing(8)
        form.addRow(_rotulo('Provedor', formulario), self.provedor)
        form.addRow(_rotulo('Chave', formulario), self.chave)
        form.addRow(_rotulo('Apelido (opcional)', formulario), self.apelido)
        formulario.body.addLayout(form)

        self.avancado_botao = QPushButton(
            'Avançado — modelo externo e URL personalizada', formulario)
        self.avancado_botao.setObjectName('Secondary')
        self.avancado_botao.setCheckable(True)
        self.avancado_botao.setChecked(False)
        self.avancado_botao.setAccessibleName('Mostrar modelo e URL personalizados')
        self.avancado_corpo = QWidget(formulario)
        av = QFormLayout(self.avancado_corpo)
        av.setContentsMargins(0, 0, 0, 0)
        av.setSpacing(8)
        self.modelo = QLineEdit(self.avancado_corpo)
        self.modelo.setPlaceholderText(
            'Padrão do catálogo; motores nativos mantêm seus modelos próprios')
        self.modelo.setAccessibleName('Modelo externo da conexão')
        self.url = QLineEdit(self.avancado_corpo)
        self.url.setPlaceholderText('Endpoint da conexão; vazio usa o catálogo')
        self.url.setAccessibleName('URL personalizada da conexão')
        av.addRow(_rotulo('Modelo', self.avancado_corpo), self.modelo)
        av.addRow(_rotulo('URL', self.avancado_corpo), self.url)
        self.avancado_corpo.setVisible(False)
        self.avancado_botao.toggled.connect(self.avancado_corpo.setVisible)
        formulario.body.addWidget(self.avancado_botao)
        formulario.body.addWidget(self.avancado_corpo)

        botoes = QHBoxLayout()
        botoes.setSpacing(6)
        self.novo_botao = QPushButton('Adicionar chave', formulario)
        self.novo_botao.setObjectName('Secondary')
        self.novo_botao.setAccessibleName('Limpar o formulário para adicionar uma chave')
        self.novo_botao.clicked.connect(self._novo)
        self.metadados_botao = QPushButton('Salvar apelido e modelo', formulario)
        self.metadados_botao.setObjectName('Secondary')
        self.metadados_botao.clicked.connect(self._metadados)
        self.salvar = QPushButton('Testar e salvar', formulario)
        self.salvar.setObjectName('Primary')
        self.salvar.clicked.connect(self._salvar)
        for botao in (self.novo_botao, self.metadados_botao, self.salvar):
            botoes.addWidget(botao)
        botoes.addStretch(1)
        formulario.body.addLayout(botoes)
        self.recado = QLabel(
            'Testes consultam autenticação ou catálogo, sem geração de texto.', formulario)
        self.recado.setObjectName('PanelStatus')
        self.recado.setProperty('estado', 'info')
        self.recado.setWordWrap(True)
        formulario.body.addWidget(self.recado)
        lay.addWidget(formulario)

        lista = _secao(
            'Conexões cadastradas',
            'O estado vem da última validação. Pausar ou excluir não apaga as '
            'outras chaves do mesmo provedor.', pagina)
        self.lista = QWidget(lista)
        self.lista.setObjectName('ApiList')
        self.linhas = QVBoxLayout(self.lista)
        self.linhas.setContentsMargins(0, 0, 0, 0)
        self.linhas.setSpacing(8)
        lista.body.addWidget(self.lista)
        lay.addWidget(lista)

        modelos = _secao(
            'Modelos desta conexão',
            'A listagem pertence ao catálogo da conexão; ela não comprova saldo '
            'nem permissão de geração.', pagina)
        self.info_modelos = QLabel('Use “Ver modelos” em uma API cadastrada.', modelos)
        self.info_modelos.setObjectName('SectionHint')
        self.info_modelos.setWordWrap(True)
        self.busca_modelos = QLineEdit(modelos)
        self.busca_modelos.setPlaceholderText('Filtrar modelos por nome ou identificador')
        self.busca_modelos.setAccessibleName('Filtrar modelos desta conexão')
        self.busca_modelos.textChanged.connect(self._filtrar_modelos)
        self.modelos_api = QComboBox(modelos)
        self.modelos_api.setAccessibleName('Modelos disponíveis nesta conexão')
        mbarra = QHBoxLayout()
        mbarra.setSpacing(6)
        mbarra.addWidget(self.modelos_api, 1)
        usar_modelo = QPushButton('Usar seleção no formulário', modelos)
        usar_modelo.setObjectName('Secondary')
        usar_modelo.clicked.connect(self._usar_modelo)
        mbarra.addWidget(usar_modelo)
        atualizar_modelos = QPushButton('Atualizar modelos', modelos)
        atualizar_modelos.setObjectName('Secondary')
        atualizar_modelos.clicked.connect(self._atualizar_modelos_api)
        mbarra.addWidget(atualizar_modelos)
        testar_uso = QPushButton('Testar uso do modelo', modelos)
        testar_uso.setObjectName('Secondary')
        testar_uso.clicked.connect(self._testar_uso)
        mbarra.addWidget(testar_uso)
        modelos.body.addWidget(self.info_modelos)
        modelos.body.addWidget(self.busca_modelos)
        modelos.body.addLayout(mbarra)
        lay.addWidget(modelos)
        lay.addStretch(1)

        for campo in (self.chave, self.apelido, self.modelo, self.url):
            campo.textChanged.connect(self._invalidar)
        self.provedor.currentIndexChanged.connect(self._invalidar)
        return pagina

    def _construir_ollama(self) -> QWidget:
        pagina = QWidget(self)
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        cartao = _secao(
            'Ollama (modelos locais)',
            'A descoberta consulta /api/tags sem iniciar o serviço nem baixar '
            'modelos. Ativar um modelo grava a preferência de conversa.', pagina)
        self.preferencia_local = QLabel(cartao)
        self.preferencia_local.setObjectName('PreferenceState')
        self.preferencia_local.setWordWrap(True)
        self.em_uso_local = QLabel(cartao)
        self.em_uso_local.setObjectName('PreferenceState')
        self.em_uso_local.setWordWrap(True)
        cartao.body.addWidget(self.preferencia_local)
        cartao.body.addWidget(self.em_uso_local)

        self.estado_local = QLabel('Atualize a lista para consultar o Ollama.', cartao)
        self.estado_local.setObjectName('PanelStatus')
        self.estado_local.setProperty('estado', 'info')
        self.estado_local.setWordWrap(True)
        cartao.body.addWidget(self.estado_local)

        self.url_local = QLineEdit(llm_client.get_llm_settings()[0], cartao)
        self.url_local.setPlaceholderText('http://localhost:11434')
        self.url_local.setAccessibleName('URL do serviço Ollama')
        cartao.body.addWidget(_rotulo('URL do serviço', cartao))
        cartao.body.addWidget(self.url_local)

        self.modelos = QComboBox(cartao)
        self.modelos.setAccessibleName('Modelos instalados no Ollama')
        cartao.body.addWidget(_rotulo('Modelos instalados', cartao))
        cartao.body.addWidget(self.modelos)

        acoes = QHBoxLayout()
        acoes.setSpacing(6)
        atualizar = QPushButton('Atualizar lista', cartao)
        atualizar.setObjectName('Secondary')
        atualizar.clicked.connect(self._descobrir)
        ativar = QPushButton('Selecionar e ativar', cartao)
        ativar.setObjectName('Primary')
        ativar.clicked.connect(self._ativar)
        legado = QPushButton('Usar preferência externa legada', cartao)
        legado.setObjectName('Secondary')
        legado.clicked.connect(self._legado)
        for botao in (atualizar, ativar):
            acoes.addWidget(botao)
        acoes.addStretch(1)
        cartao.body.addLayout(acoes)
        cartao.body.addWidget(legado)

        politica = QLabel(
            'Com Ollama ativo, falhas locais não enviam a conversa a serviços '
            'externos. A escada externa só volta quando você escolhe a preferência '
            'legada ou ativa outra conexão.', cartao)
        politica.setObjectName('SectionHint')
        politica.setWordWrap(True)
        cartao.body.addWidget(politica)
        lay.addWidget(cartao)
        lay.addStretch(1)

        self.url_local.textChanged.connect(self._invalidar_local)
        self.modelos.currentIndexChanged.connect(self._invalidar_local)
        return pagina

    # ── áreas ──────────────────────────────────────────────────────────────
    @property
    def area_atual(self) -> str:
        return self._area

    def mostrar_area(self, nome: str = 'apis') -> str:
        texto = str(nome or '').strip().lower()
        area = 'ollama' if texto in ('ollama', 'local', 'modelos locais') else 'apis'
        self._area = area
        self._stack.setCurrentWidget(
            self._pagina_ollama if area == 'ollama' else self._pagina_apis)
        for chave, botao in self._botoes_area.items():
            botao.setChecked(chave == area)
        self._atualizar_estado()
        return area

    # ── ciclo de vida ──────────────────────────────────────────────────────
    def encerrar(self) -> None:
        if self._fechado:
            return
        self._fechado = True
        self._cancelar_validacao()
        self._invalidar()
        self._invalidar_local()

    def closeEvent(self, event) -> None:
        self.encerrar()
        super().closeEvent(event)

    def _invalidar(self, *_):
        self._versao += 1
        self.salvar.setEnabled(True)

    def _invalidar_local(self, *_):
        self._local_versao += 1

    def _executar(self, funcao, retorno):
        trabalho = _Trabalho(funcao)
        self._trabalhos.add(trabalho)

        def pronto(valor):
            self._trabalhos.discard(trabalho)
            if not self._fechado:
                retorno(valor)
        trabalho.sinais.pronto.connect(pronto)
        QThreadPool.globalInstance().start(trabalho)

    def _dizer(self, texto: str, estado: str = 'info') -> None:
        self.recado.setText(texto)
        self.recado.setProperty('estado', estado)
        _repolir(self.recado)

    def _dizer_estado_local(self, texto: str, estado: str = 'info') -> None:
        self.estado_local.setText(texto)
        self.estado_local.setProperty('estado', estado)
        _repolir(self.estado_local)

    # ── estado local e preferência × uso ───────────────────────────────────
    @staticmethod
    def _familia_do_motor(motor: str) -> str:
        texto = str(motor or '').strip().lower()
        if not texto or 'nenhuma chamada' in texto:
            return 'nenhuma'
        if texto.startswith('ollama'):
            return 'ollama'
        return 'externo'

    def _comparar_preferencia(self, pref: str, motor: str) -> tuple[str, str]:
        familia = self._familia_do_motor(motor)
        if familia == 'nenhuma':
            return 'info', 'Ainda não houve chamada de conversa nesta sessão.'
        if familia == 'ollama' and 'indispon' in str(motor).lower():
            return 'warning', ('A última conversa não encontrou o Ollama; a '
                               'preferência gravada continua valendo para a próxima.')
        esperado = 'ollama' if pref == 'ollama' else 'externo'
        if familia == esperado:
            return 'success', ''
        return 'warning', (f'O último motor em uso foi {motor}, diferente da '
                           'preferência gravada. A próxima conversa usa a preferência salva.')

    def _atualizar_estado(self) -> None:
        pref = llm_client.preferencia_conversa()
        modelo = llm_client.get_llm_settings()[1]
        motor = llm_client.motor_conversa_em_uso()
        salvo = (f'Ollama · {modelo} (sem fallback externo automático)'
                 if pref == 'ollama'
                 else 'escada externa legada (Codex e reservas configuradas)')
        estado, nota = self._comparar_preferencia(pref, motor)
        texto = (f'Preferência gravada: {salvo}\n'
                 f'Último motor de conversa: {motor}')
        if nota:
            texto += '\n' + nota
        self.efetivo.setText(texto)
        self.efetivo.setProperty('estado', estado)
        _repolir(self.efetivo)
        self.preferencia_local.setText(f'Preferência gravada: {salvo}')
        self.em_uso_local.setText(f'Último motor de conversa: {motor}')
        self.em_uso_local.setProperty('estado', estado)
        _repolir(self.em_uso_local)

    # ── APIs externas ──────────────────────────────────────────────────────
    def _atualizar(self):
        llm_router.recarregar()
        self._atualizar_estado()
        while self.linhas.count():
            item = self.linhas.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        rows = db_chaves.listar_chaves()
        contagens = {k: sum(valida_chave.status_registro(r) == k for r in rows)
                     for k in ('validado', 'invalido', 'esgotado')}
        self.resumo.setText(f"{len(rows)} APIs · {contagens['validado']} validadas · "
                            f"{contagens['invalido']} inválidas · {contagens['esgotado']} esgotadas"
                            f" · {len(rows) - sum(contagens.values())} a verificar")
        for row in rows:
            filtro = self.filtro_status.currentData()
            if filtro == 'pausadas' and row['enabled']:
                continue
            if filtro and filtro != 'pausadas' and valida_chave.status_registro(row) != filtro:
                continue
            box = QFrame()
            box.setObjectName('ApiCard')
            coluna = QVBoxLayout(box)
            coluna.setContentsMargins(10, 8, 10, 10)
            coluna.setSpacing(6)
            cabecalho = QHBoxLayout()
            cabecalho.setSpacing(6)
            texto = QLabel(
                f"{nome_do_provedor(row['platform'])} · {_mascarar_chave(row['key'])}"
                f" · {row['label']}", box)
            texto.setWordWrap(True)
            cabecalho.addWidget(texto, 1)
            estado = valida_chave.status_registro(row)
            badge = QLabel(
                valida_chave.ROTULOS_STATUS.get(estado, 'Inconclusivo')
                + (' · Pausada' if not row['enabled'] else ''), box)
            badge.setObjectName('ApiBadge')
            badge.setProperty('estado', 'pausada' if not row['enabled'] else estado)
            cabecalho.addWidget(badge)
            coluna.addLayout(cabecalho)
            detalhe = row.get('validacao_mensagem') or (
                'Ainda não houve uma verificação conclusiva nesta instalação.')
            if row.get('validacao_http'):
                detalhe += f" · HTTP {row['validacao_http']}"
            if row.get('validacao_em'):
                detalhe += ' · ' + self._quando(row['validacao_em'])
            diagnostico = QLabel(detalhe, box)
            diagnostico.setObjectName('SectionHint')
            diagnostico.setWordWrap(True)
            coluna.addWidget(diagnostico)

            acoes = QFormLayout()
            acoes.setContentsMargins(0, 0, 0, 0)
            acoes.setSpacing(4)
            grade = QHBoxLayout()
            grade.setSpacing(4)
            por_linha = 2
            for indice, (titulo, acao) in enumerate((
                    ('Editar', lambda _, r=row: self._editar(r)),
                    ('Substituir chave', lambda _, r=row: self._editar(r, True)),
                    ('Testar novamente', lambda _, r=row: self._retestar(r)),
                    ('Ver modelos', lambda _, r=row: self._ver_modelos(r)),
                    ('Pausar' if row['enabled'] else 'Retomar',
                     lambda _, r=row: self._pausar(r)),
                    ('Excluir', lambda _, r=row: self._excluir(r)),
            )):
                botao = QPushButton(titulo, box)
                botao.setObjectName('CardAction')
                botao.setAccessibleName(f'{titulo} — {nome_do_provedor(row["platform"])} '
                                        f'{_mascarar_chave(row["key"])}')
                botao.clicked.connect(acao)
                grade.addWidget(botao)
                if indice % por_linha == por_linha - 1:
                    coluna.addLayout(grade)
                    grade = QHBoxLayout()
                    grade.setSpacing(4)
            if grade.count():
                coluna.addLayout(grade)
            self.linhas.addWidget(box)
        self.linhas.addStretch()

    @staticmethod
    def _quando(ts):
        zona = timezone(timedelta(hours=-3))
        return datetime.fromtimestamp(ts, zona).strftime('%d/%m %H:%M (Brasília)')

    def _ver_modelos(self, row):
        self._conexao_modelos_id = row['id']
        try:
            self._modelos_disponiveis = json.loads(row.get('modelos_json') or '[]')
        except ValueError:
            self._modelos_disponiveis = []
        origem = ('catálogo público; não comprova acesso da chave'
                  if row.get('modelos_publico') else 'catálogo remoto da conexão')
        completo = ('completo' if row.get('modelos_completo')
                    else 'parcial ou ainda não consultado')
        texto = (f"{nome_do_provedor(row['platform'])} · "
                 f"{len(self._modelos_disponiveis)} modelos · {origem} · {completo}.")
        if row.get('modelos_em'):
            texto += ' Atualização: ' + self._quando(row['modelos_em']) + '.'
        if row.get('modelos_mensagem'):
            texto += ' ' + row['modelos_mensagem']
        self.info_modelos.setText(
            texto + '\nA listagem não garante saldo ou permissão de geração. '
            'Motores nativos mantêm seus modelos próprios.')
        self._filtrar_modelos()

    def _filtrar_modelos(self, *_):
        anterior = self.modelos_api.currentText()
        termo = self.busca_modelos.text().strip().casefold()
        self.modelos_api.clear()
        self.modelos_api.addItems(
            [m for m in self._modelos_disponiveis if termo in m.casefold()])
        indice = self.modelos_api.findText(anterior)
        if indice >= 0:
            self.modelos_api.setCurrentIndex(indice)

    def _usar_modelo(self):
        if not self._registro or self._registro['id'] != self._conexao_modelos_id:
            self._dizer('Use Editar nessa API antes de alterar a preferência de modelo.',
                        'warning')
            return
        if self.modelos_api.currentText():
            self.modelo.setText(self.modelos_api.currentText())
            self._dizer('Modelo copiado para o formulário. '
                        'Confirme em Salvar apelido e modelo.', 'info')

    def _atualizar_modelos_api(self):
        row = next((r for r in db_chaves.listar_chaves()
                    if r['id'] == self._conexao_modelos_id), None)
        if row:
            self._testar_registro(row)
        else:
            self.info_modelos.setText('Escolha Ver modelos em uma API cadastrada.')

    def _testar_uso(self):
        row = next((r for r in db_chaves.listar_chaves()
                    if r['id'] == self._conexao_modelos_id), None)
        modelo = self.modelos_api.currentText()
        if not row or not modelo:
            self._dizer('Selecione uma API e um modelo para testar o uso.', 'warning')
            return
        if QMessageBox.question(
                self, 'Teste de uso do modelo',
                f"Enviar um prompt fixo de teste a {nome_do_provedor(row['platform'])}, "
                f"no modelo {modelo}?\nNão envia histórico de conversa. Esta chamada "
                'pode consumir cota ou créditos.') != QMessageBox.StandardButton.Yes:
            return
        self._testar_registro(row, geracao_modelo=modelo)

    def _cancelar_validacao(self):
        self._lote += 1
        self._tentativas.clear()
        self.validar_todas.setEnabled(True)
        self.cancelar_lote.setEnabled(False)

    def _validar_todas(self):
        self._cancelar_validacao()
        lote = self._lote
        filas = list(db_chaves.listar_chaves())
        total = len(filas)
        self.progresso.setRange(0, max(1, total))
        self.progresso.setValue(0)
        self.progresso.setVisible(True)
        self.validar_todas.setEnabled(False)
        self.cancelar_lote.setEnabled(True)

        def proxima():
            if lote != self._lote or self._fechado:
                return
            self.progresso.setValue(total - len(filas))
            if not filas:
                self.validar_todas.setEnabled(True)
                self.cancelar_lote.setEnabled(False)
                self._dizer(
                    f'Verificação concluída: {total} APIs processadas. '
                    'Registros alterados durante o teste são ignorados.', 'success')
                return
            self._testar_registro(filas.pop(0), proxima, lote)
        proxima()

    def _testar_registro(self, row, ao_terminar=None, lote=None, geracao_modelo=None):
        chave_id = row['id']
        atual = next((r for r in db_chaves.listar_chaves() if r['id'] == chave_id), None)
        if atual is None or atual['revision'] != row['revision']:
            if ao_terminar:
                ao_terminar()
            return
        self._sequencia_teste += 1
        token = self._sequencia_teste
        self._tentativas[chave_id] = token
        editor = self._versao if self._registro and self._registro['id'] == chave_id else None
        self._dizer(f"Consultando {nome_do_provedor(row['platform'])}…", 'info')

        def concluir(resultado):
            atual = (self._tentativas.get(chave_id) == token
                     and (lote is None or lote == self._lote))
            editado = editor is not None and editor != self._versao
            if atual and not editado and resultado is not None:
                ok = db_chaves.aplicar_validacao(chave_id, row['revision'], resultado)
                self._dizer(
                    resultado.mensagem if ok
                    else 'Resultado antigo ignorado: a API mudou durante o teste.',
                    'success' if ok else 'warning')
                if ok:
                    nova = next((r for r in db_chaves.listar_chaves() if r['id'] == chave_id), None)
                    if nova and self._registro and self._registro['id'] == chave_id:
                        self._registro = nova
                    if nova and self._conexao_modelos_id == chave_id:
                        self._ver_modelos(nova)
                    self._atualizar()
            elif atual:
                self._dizer(
                    'Teste inconclusivo ou resultado ignorado para preservar a edição '
                    'em curso.', 'warning')
            if ao_terminar:
                ao_terminar()

        def testar():
            if geracao_modelo:
                return valida_chave.testar_geracao(
                    row['platform'], row['key'], geracao_modelo, row['base_url'])
            return valida_chave.testar(row['platform'], row['key'], row['base_url'])
        self._executar(testar, concluir)

    def _novo(self):
        self._registro = None
        self.provedor.setEnabled(True)
        for campo in (self.chave, self.apelido, self.modelo, self.url):
            campo.clear()
        self._invalidar()

    def _editar(self, row, substituir=False):
        self._registro = dict(row)
        canon = llm_router.provedor_canonico(row['platform'])
        indice = next((i for i in range(self.provedor.count())
                       if llm_router.provedor_canonico(self.provedor.itemData(i)) == canon), -1)
        if indice < 0:
            self.provedor.addItem(row['platform'], row['platform'])
            indice = self.provedor.count() - 1
        self.provedor.setCurrentIndex(indice)
        self.provedor.setEnabled(False)
        self.chave.clear()
        self.apelido.setText(row['label'])
        self.modelo.setText(row['modelo'])
        self.url.setText(row['base_url'])
        self._invalidar()
        self._ver_modelos(row)
        self._dizer('Edição carregada. Troca de chave ou endpoint exige teste conclusivo.',
                    'info')
        if substituir:
            self.chave.setFocus()

    def _metadados(self):
        row = self._registro
        if not row:
            return
        self._invalidar()
        ok = db_chaves.atualizar_chave(
            row['id'], row['revision'],
            label=self.apelido.text().strip(), modelo=self.modelo.text().strip())
        self._dizer('Metadados salvos.' if ok
                    else 'Registro alterado; carregue novamente.',
                    'success' if ok else 'warning')
        if ok:
            self._registro = next(r for r in db_chaves.listar_chaves() if r['id'] == row['id'])
        self._atualizar()

    def _salvar(self):
        row = dict(self._registro) if self._registro else None
        provedor = row['platform'] if row else self.provedor.currentData()
        chave = self.chave.text().strip() or (row['key'] if row else '')
        if not chave:
            self._dizer('Informe uma chave.', 'warning')
            return
        if not row and any(r['key'] == chave for r in db_chaves.listar_chaves(provedor)):
            self._dizer('Chave já cadastrada. Use Editar ou Testar novamente na '
                        'entrada existente.', 'warning')
            return
        url = self.url.text().strip()
        modelo = self.modelo.text().strip()
        label = self.apelido.text().strip()
        self._invalidar()
        versao = self._versao
        self.salvar.setEnabled(False)
        self._dizer('Testando…', 'info')

        def concluir(resultado):
            if versao != self._versao:
                return
            self.salvar.setEnabled(True)
            if resultado is None:
                self._dizer('Não foi possível testar; registro anterior preservado.',
                            'error')
                return
            try:
                if row:
                    substituicao = chave != row['key'] or url != row['base_url']
                    if substituicao and not resultado.apta:
                        self._dizer(resultado.mensagem + ' Registro anterior preservado.',
                                    'warning')
                        return
                    chave_id = row['id']
                    ok = db_chaves.aplicar_validacao(
                        chave_id, row['revision'], resultado,
                        key=chave, base_url=url, modelo=modelo, label=label)
                else:
                    chave_id = db_chaves.adicionar_chave(
                        provedor, chave, label, modelo, url, status='pendente')
                    ok = chave_id is not None and db_chaves.aplicar_validacao(
                        chave_id, 0, resultado)
                self._dizer(resultado.mensagem if ok
                            else 'Entrada alterada ou duplicada; carregue novamente.',
                            'success' if ok else 'warning')
                if ok:
                    self._novo()
                    self._ver_modelos(
                        next(r for r in db_chaves.listar_chaves() if r['id'] == chave_id))
                    self.credencial_pronta.emit()
                self._atualizar()
            except ValueError as exc:
                self._dizer(str(exc), 'warning')
        self._executar(lambda: valida_chave.testar(provedor, chave, url), concluir)

    def _retestar(self, row):
        self._testar_registro(row)

    def _confirmar_indisponibilidade(self, row):
        outras = [r for r in db_chaves.listar_chaves(row['platform'])
                  if r['id'] != row['id'] and r['enabled'] and r['status'] == 'ativo']
        if outras or not row['enabled']:
            return True
        return QMessageBox.question(
            self, 'Disponibilidade',
            'Esta é a última chave ativa deste provedor. Conversa, voz ou outras '
            'funções que dependem dela podem ficar indisponíveis. Continuar?'
        ) == QMessageBox.StandardButton.Yes

    def _pausar(self, row):
        if row['enabled'] and not self._confirmar_indisponibilidade(row):
            return
        self._invalidar()
        db_chaves.atualizar_chave(row['id'], row['revision'], enabled=int(not row['enabled']))
        self._dizer('Credencial pausada.' if row['enabled']
                    else 'Credencial retomada.', 'success')
        self._atualizar()
        self._sincronizar_registro(row['id'])
        self._atualizar_estado()

    def _sincronizar_registro(self, chave_id) -> None:
        """Evita salvar metadados com a revisão anterior a uma pausa/reteste."""
        if not self._registro or self._registro['id'] != chave_id:
            return
        atual = next((r for r in db_chaves.listar_chaves()
                      if r['id'] == chave_id), None)
        if atual is not None:
            self._registro = atual

    def _excluir(self, row):
        if QMessageBox.question(
                self, 'Excluir credencial',
                'Excluir esta credencial? A exclusão também bloqueia cópias legadas '
                'para novas chamadas.') != QMessageBox.StandardButton.Yes:
            return
        if not self._confirmar_indisponibilidade(row):
            return
        self._invalidar()
        db_chaves.remover_chave(row['id'])
        if self._registro and self._registro['id'] == row['id']:
            self._novo()
        self._dizer('Credencial excluída.', 'success')
        self._atualizar()
        self._atualizar_estado()

    # ── Ollama ─────────────────────────────────────────────────────────────
    def _descobrir(self):
        self._invalidar_local()
        url = self.url_local.text().strip()
        versao = self._local_versao
        self._dizer_estado_local('Consultando Ollama…', 'info')

        def concluir(estado):
            if self._fechado or versao != self._local_versao:
                return
            if not estado or estado.get('estado') == 'inacessivel':
                self.modelos.blockSignals(True)
                self.modelos.clear()
                self.modelos.blockSignals(False)
                self._dizer_estado_local(
                    'Ollama inacessível. Inicie o serviço e atualize a lista.', 'error')
                return
            modelos = list(estado.get('modelos') or [])
            selecionado = self.modelos.currentText() or llm_client.get_llm_settings()[1]
            self.modelos.blockSignals(True)
            self.modelos.clear()
            self.modelos.addItems(modelos)
            self.modelos.setCurrentIndex(self.modelos.findText(selecionado))
            self.modelos.blockSignals(False)
            if estado.get('estado') == 'sem_modelos' or not modelos:
                self._dizer_estado_local(
                    'Nenhum modelo instalado. Instale um modelo no Ollama.', 'warning')
                return
            if selecionado and not llm_client._modelo_instalado(selecionado, modelos):
                self._dizer_estado_local(
                    f'O modelo salvo ({selecionado}) não está instalado. '
                    'Selecione outro e ative.', 'warning')
                return
            self._dizer_estado_local(
                f'Ollama disponível. {len(modelos)} modelo(s) instalado(s).', 'success')
        self._executar(lambda: llm_client.descobrir_modelos(url), concluir)

    def _ativar(self):
        self._invalidar_local()
        modelo = self.modelos.currentText()
        url = self.url_local.text().strip()
        versao = self._local_versao
        if not modelo:
            self._dizer_estado_local(
                'Atualize a lista e selecione um modelo instalado.', 'warning')
            return
        self._dizer_estado_local('Ativando modelo…', 'info')

        def concluir(estado):
            if self._fechado or versao != self._local_versao:
                return
            if (not estado or estado.get('estado') != 'disponivel'
                    or not llm_client._modelo_instalado(modelo, estado['modelos'])):
                self._dizer_estado_local(
                    'Modelo ausente ou serviço inacessível; seleção anterior '
                    'preservada.', 'error')
                return
            try:
                llm_client.ativar_modelo(modelo, url, modelos_instalados=estado['modelos'])
            except Exception:
                self._dizer_estado_local(
                    'Não foi possível salvar; configuração anterior preservada.', 'error')
                return
            self._invalidar_local()
            self._dizer_estado_local(
                f'Modelo {modelo} ativado. Falhas locais não enviam a conversa a '
                'serviços externos.', 'success')
            self._atualizar()
        self._executar(lambda: llm_client.descobrir_modelos(url), concluir)

    def _legado(self):
        if QMessageBox.question(
                self, 'Preferência de conversa',
                'Usar a escada externa configurada para novas conversas?'
        ) != QMessageBox.StandardButton.Yes:
            return
        self._invalidar_local()
        try:
            llm_client.salvar_config_local({'conversation_provider': 'legado'})
        except Exception:
            self._dizer_estado_local(
                'Falha ao salvar a preferência; configuração anterior preservada.',
                'error')
            return
        self._dizer_estado_local(
            'Preferência externa legada ativada para novas conversas.', 'success')
        self._atualizar()
