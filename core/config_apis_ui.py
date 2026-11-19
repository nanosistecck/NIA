"""Configurações de conexões; rede em workers e gravação somente na thread Qt."""
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                            QPushButton, QComboBox, QGroupBox, QFormLayout,
                            QScrollArea, QWidget, QMessageBox, QTabWidget, QProgressBar)
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


class ConfigAPIsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('NIA · APIs e Ollama')
        self.resize(1000, 850)
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
        self.finished.connect(self._encerrar)
        raiz = QVBoxLayout(self)
        self.efetivo = QLabel()
        raiz.addWidget(self.efetivo)
        abas = QTabWidget()
        raiz.addWidget(abas, 1)
        grupo = QGroupBox('APIs externas')
        externo = QVBoxLayout(grupo)
        barra = QHBoxLayout()
        self.resumo = QLabel()
        self.resumo.setWordWrap(True)
        barra.addWidget(self.resumo, 1)
        self.filtro_status = QComboBox()
        for rotulo, estado in [('Todas as APIs', ''), ('Validadas', 'validado'), ('Inválidas', 'invalido'),
                               ('Esgotadas', 'esgotado'), ('Limite temporário', 'limitado'),
                               ('Inconclusivas', 'inconclusivo'), ('Não verificadas', 'nao_verificada'),
                               ('Pausadas', 'pausadas')]:
            self.filtro_status.addItem(rotulo, estado)
        self.filtro_status.currentIndexChanged.connect(self._atualizar)
        barra.addWidget(self.filtro_status)
        self.validar_todas = QPushButton('Validar todas')
        self.validar_todas.clicked.connect(self._validar_todas)
        self.cancelar_lote = QPushButton('Cancelar verificação')
        self.cancelar_lote.clicked.connect(self._cancelar_validacao)
        self.cancelar_lote.setEnabled(False)
        barra.addWidget(self.validar_todas)
        barra.addWidget(self.cancelar_lote)
        externo.addLayout(barra)
        self.progresso = QProgressBar()
        self.progresso.setVisible(False)
        externo.addWidget(self.progresso)
        self.provedor = QComboBox()
        for pid, spec in sorted(PROVEDORES.items(), key=lambda p: p[1].get('nome', p[0])):
            self.provedor.addItem(spec.get('nome', pid), pid)
        self.chave = QLineEdit()
        self.chave.setEchoMode(QLineEdit.EchoMode.Password)
        self.chave.setPlaceholderText('Cole a chave; ao editar, vazio conserva a atual')
        self.apelido = QLineEdit()
        form = QFormLayout()
        form.addRow('Provedor', self.provedor)
        form.addRow('Chave', self.chave)
        form.addRow('Apelido (opcional)', self.apelido)
        externo.addLayout(form)
        avancado = QGroupBox('Avançado — modelo externo e URL personalizada')
        avancado.setCheckable(True)
        avancado.setChecked(False)
        av = QFormLayout(avancado)
        self.modelo, self.url = QLineEdit(), QLineEdit()
        self.modelo.setPlaceholderText('Padrão do catálogo; motores nativos mantêm seus modelos próprios')
        self.url.setPlaceholderText('Endpoint da conexão; vazio usa o catálogo')
        av.addRow('Modelo', self.modelo)
        av.addRow('URL', self.url)
        externo.addWidget(avancado)
        botoes = QHBoxLayout()
        self.salvar = QPushButton('Testar e salvar')
        self.salvar.clicked.connect(self._salvar)
        novo = QPushButton('Adicionar chave')
        novo.clicked.connect(self._novo)
        metadata = QPushButton('Salvar apelido e modelo')
        metadata.clicked.connect(self._metadados)
        for b in (novo, metadata, self.salvar):
            botoes.addWidget(b)
        externo.addLayout(botoes)
        self.recado = QLabel('Testes consultam autenticação ou catálogo, sem geração de texto.')
        self.recado.setWordWrap(True)
        externo.addWidget(self.recado)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.lista = QWidget()
        self.linhas = QVBoxLayout(self.lista)
        scroll.setWidget(self.lista)
        externo.addWidget(scroll, 1)
        modelos_api = QGroupBox('Modelos desta conexão')
        ml = QVBoxLayout(modelos_api)
        self.info_modelos = QLabel('Use “Ver modelos” em uma API cadastrada.')
        self.info_modelos.setWordWrap(True)
        self.busca_modelos = QLineEdit()
        self.busca_modelos.setPlaceholderText('Filtrar modelos por nome ou identificador')
        self.busca_modelos.textChanged.connect(self._filtrar_modelos)
        self.modelos_api = QComboBox()
        mbarra = QHBoxLayout()
        mbarra.addWidget(self.modelos_api, 1)
        usar_modelo = QPushButton('Usar seleção no formulário')
        usar_modelo.clicked.connect(self._usar_modelo)
        mbarra.addWidget(usar_modelo)
        atualizar_modelos = QPushButton('Atualizar modelos')
        atualizar_modelos.clicked.connect(self._atualizar_modelos_api)
        mbarra.addWidget(atualizar_modelos)
        testar_uso = QPushButton('Testar uso do modelo')
        testar_uso.clicked.connect(self._testar_uso)
        mbarra.addWidget(testar_uso)
        ml.addWidget(self.info_modelos)
        ml.addWidget(self.busca_modelos)
        ml.addLayout(mbarra)
        externo.addWidget(modelos_api)
        abas.addTab(grupo, 'APIs externas')

        local = QGroupBox('Modelos locais')
        lay = QVBoxLayout(local)
        self.estado_local = QLabel('Atualize a lista para consultar o Ollama.')
        self.url_local = QLineEdit(llm_client.get_llm_settings()[0])
        self.modelos = QComboBox()
        lay.addWidget(self.estado_local)
        lay.addWidget(self.url_local)
        lay.addWidget(self.modelos)
        acoes = QHBoxLayout()
        atualizar = QPushButton('Atualizar lista')
        atualizar.clicked.connect(self._descobrir)
        ativar = QPushButton('Selecionar e ativar')
        ativar.clicked.connect(self._ativar)
        legado = QPushButton('Usar preferência externa legada')
        legado.clicked.connect(self._legado)
        for b in (atualizar, ativar, legado):
            acoes.addWidget(b)
        lay.addLayout(acoes)
        lay.addStretch()
        abas.addTab(local, 'Modelos locais')
        fechar = QPushButton('Fechar')
        fechar.clicked.connect(self.accept)
        raiz.addWidget(fechar)
        for campo in (self.chave, self.apelido, self.modelo, self.url):
            campo.textChanged.connect(self._invalidar)
        self.provedor.currentIndexChanged.connect(self._invalidar)
        self.url_local.textChanged.connect(self._invalidar_local)
        self.modelos.currentIndexChanged.connect(self._invalidar_local)
        self._atualizar()

    def _encerrar(self):
        self._fechado = True
        self._cancelar_validacao()
        self._invalidar()
        self._invalidar_local()

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

    def _atualizar(self):
        llm_router.recarregar()
        pref = llm_client.preferencia_conversa()
        modelo = llm_client.get_llm_settings()[1]
        self.efetivo.setWordWrap(True)
        self.efetivo.setText('Preferência de conversa: ' + (
            f'Ollama · {modelo} (sem fallback externo automático)' if pref == 'ollama'
            else 'escada externa legada (Codex e reservas configuradas)')
            + '\nÚltimo motor de conversa: ' + llm_client.motor_conversa_em_uso())
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
            box = QWidget()
            box.setObjectName('apiCard')
            box.setStyleSheet('QWidget#apiCard { border: 1px solid #24404b; border-radius: 5px; }')
            coluna = QVBoxLayout(box)
            coluna.setContentsMargins(4, 4, 4, 4)
            linha = QHBoxLayout()
            estado = valida_chave.status_registro(row)
            cabecalho = QHBoxLayout()
            texto = QLabel(f"{nome_do_provedor(row['platform'])} · ••••{row['key'][-4:]} · {row['label']}")
            cabecalho.addWidget(texto, 1)
            badge = QLabel(valida_chave.ROTULOS_STATUS.get(estado, 'Inconclusivo')
                           + (' · Pausada' if not row['enabled'] else ''))
            cor = {'validado': '#80e4ab', 'invalido': '#ff8e8e', 'esgotado': '#ffc56b'}.get(estado, '#a8c6d3')
            badge.setStyleSheet(f'color: {cor}; font-weight: bold; padding: 3px 8px;')
            cabecalho.addWidget(badge)
            coluna.addLayout(cabecalho)
            detalhe = row.get('validacao_mensagem') or 'Ainda não houve uma verificação conclusiva nesta instalação.'
            if row.get('validacao_http'):
                detalhe += f" · HTTP {row['validacao_http']}"
            if row.get('validacao_em'):
                detalhe += ' · ' + self._quando(row['validacao_em'])
            diagnostico = QLabel(detalhe)
            diagnostico.setWordWrap(True)
            coluna.addWidget(diagnostico)
            coluna.addLayout(linha)
            for titulo, acao in (
                ('Editar', lambda _, r=row: self._editar(r)),
                ('Substituir chave', lambda _, r=row: self._editar(r, True)),
                ('Testar novamente', lambda _, r=row: self._retestar(r)),
                ('Ver modelos', lambda _, r=row: self._ver_modelos(r)),
                ('Pausar' if row['enabled'] else 'Retomar', lambda _, r=row: self._pausar(r)),
                ('Excluir', lambda _, r=row: self._excluir(r)),
            ):
                botao = QPushButton(titulo)
                botao.clicked.connect(acao)
                linha.addWidget(botao)
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
        origem = 'catálogo público; não comprova acesso da chave' if row.get('modelos_publico') else 'catálogo remoto da conexão'
        completo = 'completo' if row.get('modelos_completo') else 'parcial ou ainda não consultado'
        texto = f"{nome_do_provedor(row['platform'])} · {len(self._modelos_disponiveis)} modelos · {origem} · {completo}."
        if row.get('modelos_em'):
            texto += ' Atualização: ' + self._quando(row['modelos_em']) + '.'
        if row.get('modelos_mensagem'):
            texto += ' ' + row['modelos_mensagem']
        self.info_modelos.setText(texto + '\nA listagem não garante saldo ou permissão de geração. Motores nativos mantêm seus modelos próprios.')
        self._filtrar_modelos()

    def _filtrar_modelos(self, *_):
        anterior = self.modelos_api.currentText()
        termo = self.busca_modelos.text().strip().casefold()
        self.modelos_api.clear()
        self.modelos_api.addItems([m for m in self._modelos_disponiveis if termo in m.casefold()])
        indice = self.modelos_api.findText(anterior)
        if indice >= 0:
            self.modelos_api.setCurrentIndex(indice)

    def _usar_modelo(self):
        if not self._registro or self._registro['id'] != self._conexao_modelos_id:
            self.recado.setText('Use Editar nessa API antes de alterar a preferência de modelo.')
            return
        if self.modelos_api.currentText():
            self.modelo.setText(self.modelos_api.currentText())
            self.recado.setText('Modelo copiado para o formulário. Confirme em Salvar apelido e modelo.')

    def _atualizar_modelos_api(self):
        row = next((r for r in db_chaves.listar_chaves() if r['id'] == self._conexao_modelos_id), None)
        if row:
            self._testar_registro(row)
        else:
            self.info_modelos.setText('Escolha Ver modelos em uma API cadastrada.')

    def _testar_uso(self):
        row = next((r for r in db_chaves.listar_chaves() if r['id'] == self._conexao_modelos_id), None)
        modelo = self.modelos_api.currentText()
        if not row or not modelo:
            self.info_modelos.setText('Selecione uma API e um modelo para testar o uso.')
            return
        if QMessageBox.question(self, 'Teste de uso do modelo',
                f"Enviar um prompt fixo de teste a {nome_do_provedor(row['platform'])}, no modelo {modelo}?\n"
                'Não envia histórico de conversa. Esta chamada pode consumir cota ou créditos.') != QMessageBox.StandardButton.Yes:
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
                self.recado.setText(f'Verificação concluída: {total} APIs processadas. Registros alterados durante o teste são ignorados.')
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
        self.recado.setText(f"Consultando {nome_do_provedor(row['platform'])}…")

        def concluir(resultado):
            atual = self._tentativas.get(chave_id) == token and (lote is None or lote == self._lote)
            editado = editor is not None and editor != self._versao
            if atual and not editado and resultado is not None:
                ok = db_chaves.aplicar_validacao(chave_id, row['revision'], resultado)
                self.recado.setText(resultado.mensagem if ok else 'Resultado antigo ignorado: a API mudou durante o teste.')
                if ok:
                    nova = next((r for r in db_chaves.listar_chaves() if r['id'] == chave_id), None)
                    if nova and self._registro and self._registro['id'] == chave_id:
                        self._registro = nova
                    if nova and self._conexao_modelos_id == chave_id:
                        self._ver_modelos(nova)
                    self._atualizar()
            elif atual:
                self.recado.setText('Teste inconclusivo ou resultado ignorado para preservar a edição em curso.')
            if ao_terminar:
                ao_terminar()
        def testar():
            if geracao_modelo:
                return valida_chave.testar_geracao(row['platform'], row['key'], geracao_modelo, row['base_url'])
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
        self.recado.setText('Edição carregada. Troca de chave ou endpoint exige teste conclusivo.')
        if substituir:
            self.chave.setFocus()

    def _metadados(self):
        row = self._registro
        if not row:
            return
        self._invalidar()
        ok = db_chaves.atualizar_chave(row['id'], row['revision'],
                                      label=self.apelido.text().strip(), modelo=self.modelo.text().strip())
        self.recado.setText('Metadados salvos.' if ok else 'Registro alterado; carregue novamente.')
        if ok:
            self._registro = next(r for r in db_chaves.listar_chaves() if r['id'] == row['id'])
        self._atualizar()

    def _salvar(self):
        row = dict(self._registro) if self._registro else None
        provedor = row['platform'] if row else self.provedor.currentData()
        chave = self.chave.text().strip() or (row['key'] if row else '')
        if not chave:
            self.recado.setText('Informe uma chave.')
            return
        if not row and any(r['key'] == chave for r in db_chaves.listar_chaves(provedor)):
            self.recado.setText('Chave já cadastrada. Use Editar ou Testar novamente na entrada existente.')
            return
        url, modelo, label = self.url.text().strip(), self.modelo.text().strip(), self.apelido.text().strip()
        self._invalidar()
        versao = self._versao
        self.salvar.setEnabled(False)
        self.recado.setText('Testando…')

        def concluir(resultado):
            if versao != self._versao:
                return
            self.salvar.setEnabled(True)
            if resultado is None:
                self.recado.setText('Não foi possível testar; registro anterior preservado.')
                return
            try:
                if row:
                    substituicao = chave != row['key'] or url != row['base_url']
                    if substituicao and not resultado.apta:
                        self.recado.setText(resultado.mensagem + ' Registro anterior preservado.')
                        return
                    chave_id = row['id']
                    ok = db_chaves.aplicar_validacao(chave_id, row['revision'], resultado,
                                                   key=chave, base_url=url, modelo=modelo, label=label)
                else:
                    chave_id = db_chaves.adicionar_chave(provedor, chave, label, modelo, url, status='pendente')
                    ok = chave_id is not None and db_chaves.aplicar_validacao(chave_id, 0, resultado)
                self.recado.setText(resultado.mensagem if ok else 'Entrada alterada ou duplicada; carregue novamente.')
                if ok:
                    self._novo()
                    self._ver_modelos(next(r for r in db_chaves.listar_chaves() if r['id'] == chave_id))
                self._atualizar()
            except ValueError as exc:
                self.recado.setText(str(exc))
        self._executar(lambda: valida_chave.testar(provedor, chave, url), concluir)

    def _retestar(self, row):
        self._testar_registro(row)

    def _confirmar_indisponibilidade(self, row):
        outras = [r for r in db_chaves.listar_chaves(row['platform'])
                  if r['id'] != row['id'] and r['enabled'] and r['status'] == 'ativo']
        if outras or not row['enabled']:
            return True
        return QMessageBox.question(self, 'Disponibilidade',
            'Esta é a última chave ativa deste provedor. Conversa, voz ou outras funções '
            'que dependem dela podem ficar indisponíveis. Continuar?') == QMessageBox.StandardButton.Yes

    def _pausar(self, row):
        if row['enabled'] and not self._confirmar_indisponibilidade(row):
            return
        self._invalidar()
        db_chaves.atualizar_chave(row['id'], row['revision'], enabled=int(not row['enabled']))
        self._atualizar()

    def _excluir(self, row):
        if QMessageBox.question(self, 'Excluir credencial',
                'Excluir esta credencial? A exclusão também bloqueia cópias legadas para novas chamadas.') != QMessageBox.StandardButton.Yes:
            return
        if not self._confirmar_indisponibilidade(row):
            return
        self._invalidar()
        db_chaves.remover_chave(row['id'])
        if self._registro and self._registro['id'] == row['id']:
            self._novo()
        self._atualizar()

    def _descobrir(self):
        self._invalidar_local()
        url, versao = self.url_local.text().strip(), self._local_versao
        self.estado_local.setText('Consultando Ollama…')

        def concluir(estado):
            if versao != self._local_versao:
                return
            if not estado:
                self.estado_local.setText('URL inválida ou Ollama inacessível.')
                return
            selecionado = self.modelos.currentText() or llm_client.get_llm_settings()[1]
            self.modelos.blockSignals(True)
            self.modelos.clear()
            self.modelos.addItems(estado['modelos'])
            self.modelos.setCurrentIndex(self.modelos.findText(selecionado))
            self.modelos.blockSignals(False)
            removido = selecionado and not llm_client._modelo_instalado(selecionado, estado['modelos'])
            self.estado_local.setText({'inacessivel': 'Ollama inacessível. Inicie o serviço e atualize.',
                'sem_modelos': 'Nenhum modelo instalado. Instale um modelo no Ollama.',
                'disponivel': 'Modelo anterior ausente; selecione outro.' if removido else 'Ollama disponível.'}[estado['estado']])
        self._executar(lambda: llm_client.descobrir_modelos(url), concluir)

    def _ativar(self):
        self._invalidar_local()
        modelo, url, versao = self.modelos.currentText(), self.url_local.text().strip(), self._local_versao
        if not modelo:
            self.estado_local.setText('Atualize a lista e selecione um modelo instalado.')
            return

        def concluir(estado):
            if versao != self._local_versao:
                return
            if not estado or not llm_client._modelo_instalado(modelo, estado['modelos']):
                self.estado_local.setText('Modelo ausente ou serviço inacessível; seleção anterior preservada.')
                return
            try:
                llm_client.ativar_modelo(modelo, url, modelos_instalados=estado['modelos'])
                self._invalidar_local()
                self.estado_local.setText('Modelo ativado. Falhas locais não enviam a conversa a serviços externos.')
                self._atualizar()
            except Exception:
                self.estado_local.setText('Não foi possível salvar; configuração anterior preservada.')
        self._executar(lambda: llm_client.descobrir_modelos(url), concluir)

    def _legado(self):
        if QMessageBox.question(self, 'Preferência de conversa',
                'Usar a escada externa configurada para novas conversas?') != QMessageBox.StandardButton.Yes:
            return
        self._invalidar_local()
        try:
            llm_client.salvar_config_local({'conversation_provider': 'legado'})
            self._atualizar()
        except Exception:
            self.estado_local.setText('Falha ao salvar a preferência; configuração anterior preservada.')
