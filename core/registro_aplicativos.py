# -*- coding: utf-8 -*-
"""Registro central de aplicativos, habilidades e ferramentas da NIA.

Fonte única de metadados para o dock, a Central de Aplicativos e a descoberta
de capacidades. Os descritores são **declarativos**: nenhum módulo é importado
para descrever um aplicativo, e nenhum código de metadados externos é executado.

Preferências do usuário (favoritos, ordem, ocultos, tamanho de ícone) ficam
fora daqui, em ``DockPreferences``/``ConfigService`` — ver ``preferencias()``.

O registro é alimentado por código local confiável: ``registrar()``. Para
evitar ciclo de import com ``main``, o catálogo de ferramentas é conectado por
``definir_provedor_ferramentas()`` durante a inicialização real.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import re
import threading
import unicodedata


CATEGORIAS = (
    'todos', 'favoritos', 'produtividade', 'conhecimento', 'pesquisa',
    'arquivos', 'criacao', 'automacao', 'integracoes', 'sistema', 'habilidades',
)
_ID = re.compile(r'^[a-z][a-z0-9_]{0,63}$')
# Carregador é um caminho textual "modulo:funcao", avaliado SOMENTE na abertura.
_CARREGADOR = re.compile(r'^[a-z_][a-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$')
# Nomes que nunca devem ser carregados como "aplicativo": não são serviços da
# NIA e permitiriam execução arbitrária se um dia metadados externos vazassem.
_MODULOS_PROIBIDOS = frozenset(
    ('os', 'sys', 'subprocess', 'builtins', 'importlib', 'commands', 'pty',
     'shutil', 'ctypes', 'signal', 'code', 'codeop'))


def normalizar(texto) -> str:
    bruto = unicodedata.normalize('NFKD', str(texto or '').lower())
    return ''.join(c for c in bruto if not unicodedata.combining(c)).strip()


@dataclass(frozen=True)
class DescritorApp:
    id: str
    nome: str
    descricao: str = ''
    categoria: str = 'sistema'
    tipo: str = 'aplicativo'          # aplicativo | habilidade | ferramenta | integracao
    icone: str = 'system'
    cor: str = '#00d4ff'
    disponivel: bool = True
    possui_interface: bool = False
    executavel_por_nia: bool = True
    fixavel_no_dock: bool = True
    visivel_na_central: bool = True
    carregamento_sob_demanda: bool = True
    dominio_ferramenta: str = ''
    acoes: tuple[str, ...] = ()
    permissoes: tuple[str, ...] = ()
    palavras_chave: tuple[str, ...] = ()
    exigir_config: bool = False
    chave_config: str = ''
    multiplas_instancias: bool = False
    # "modulo:funcao". Nunca é chamado durante validação/cadastro.
    carregador: str = ''
    janela: str = ''
    origem: str = 'interno'
    # Contrato universal (Fase 02): opcionais por compatibilidade.
    versao: str = '1.0.0'
    api: int = 1
    esquema_entrada: dict | None = None
    esquema_saida: dict | None = None
    agendavel: bool = False
    aliases: tuple[str, ...] = ()

    def como_dict(self) -> dict:
        return {
            'id': self.id, 'nome': self.nome, 'descricao': self.descricao,
            'categoria': self.categoria, 'tipo': self.tipo, 'icone': self.icone,
            'cor': self.cor, 'disponivel': self.disponivel,
            'possui_interface': self.possui_interface,
            'executavel_por_nia': self.executavel_por_nia,
            'fixavel_no_dock': self.fixavel_no_dock,
            'visivel_na_central': self.visivel_na_central,
            'carregamento_sob_demanda': self.carregamento_sob_demanda,
            'dominio_ferramenta': self.dominio_ferramenta,
            'acoes': list(self.acoes), 'permissoes': list(self.permissoes),
            'palavras_chave': list(self.palavras_chave),
            'exigir_config': self.exigir_config, 'chave_config': self.chave_config,
            'multiplas_instancias': self.multiplas_instancias,
            'janela': self.janela, 'origem': self.origem,
            'versao': self.versao, 'api': self.api,
            'esquema_entrada': self.esquema_entrada,
            'esquema_saida': self.esquema_saida,
            'agendavel': self.agendavel, 'aliases': list(self.aliases),
        }


@dataclass(frozen=True)
class DisponibilidadeApp:
    pronta: bool
    motivo: str = ''


_PROVEDOR_FERRAMENTAS = None
_DESCRITORS: dict[str, DescritorApp] = {}
_TRAVA = threading.RLock()
_PROVEDOR_DISPONIBILIDADE = None


def definir_provedor_ferramentas(funcao) -> None:
    """Liga as declarações reais de ``main`` sem importá-las aqui."""
    global _PROVEDOR_FERRAMENTAS
    if funcao is not None and not callable(funcao):
        raise TypeError('Provedor inválido.')
    _PROVEDOR_FERRAMENTAS = funcao


def definir_provedor_disponibilidade(funcao) -> None:
    global _PROVEDOR_DISPONIBILIDADE
    if funcao is not None and not callable(funcao):
        raise TypeError('Provedor inválido.')
    _PROVEDOR_DISPONIBILIDADE = funcao


def validar(descritor: DescritorApp) -> None:
    if not isinstance(descritor, DescritorApp):
        raise TypeError('Descritor inválido.')
    if not _ID.fullmatch(descritor.id):
        raise ValueError('Identificador inválido: ' + str(descritor.id))
    for campo in ('nome', 'descricao', 'categoria', 'tipo', 'icone', 'cor'):
        if not isinstance(getattr(descritor, campo), str):
            raise ValueError('Metadado inválido: ' + campo)
    if not descritor.nome.strip() or not descritor.descricao.strip():
        raise ValueError('Nome e descrição são obrigatórios.')
    if descritor.categoria not in CATEGORIAS:
        raise ValueError('Categoria desconhecida: ' + descritor.categoria)
    if descritor.tipo not in ('aplicativo', 'habilidade', 'ferramenta', 'integracao'):
        raise ValueError('Tipo desconhecido: ' + descritor.tipo)
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', descritor.cor):
        raise ValueError('Cor inválida: ' + descritor.cor)
    for tupla in (descritor.acoes, descritor.permissoes, descritor.palavras_chave):
        if not isinstance(tupla, tuple) or any(not isinstance(v, str) for v in tupla):
            raise ValueError('Listas de metadados devem ser tuplas de texto.')
    if descritor.carregador:
        if not _CARREGADOR.fullmatch(descritor.carregador):
            raise ValueError('Carregador deve ser "modulo:funcao".')
        if descritor.carregador.split(':', 1)[0] in _MODULOS_PROIBIDOS:
            raise ValueError('Módulo de carregador não permitido.')
    if descritor.janela and not _ID.fullmatch(descritor.janela):
        raise ValueError('Janela inválida.')
    if descritor.dominio_ferramenta and not _ID.fullmatch(descritor.dominio_ferramenta):
        raise ValueError('Domínio inválido.')
    if type(descritor.api) is not int or descritor.api != 1:
        raise ValueError('Versão de API incompatível.')
    if not isinstance(descritor.versao, str) or not re.fullmatch(r'\d+\.\d+\.\d+', descritor.versao):
        raise ValueError('Versão de manifesto inválida.')
    if type(descritor.agendavel) is not bool:
        raise ValueError('Agendabilidade deve ser booleana.')
    if (not isinstance(descritor.aliases, tuple)
            or any(not isinstance(a, str) or not a.strip() for a in descritor.aliases)):
        raise ValueError('Aliases devem ser tuplas de nomes.')
    if descritor.esquema_entrada is not None or descritor.esquema_saida is not None:
        from core.contrato_universal import validar_esquema  # importação local
        validar_esquema(descritor.esquema_entrada)
        validar_esquema(descritor.esquema_saida)


def registrar(descritor: DescritorApp, *, substituir: bool = False) -> None:
    validar(descritor)
    with _TRAVA:
        if descritor.id in _DESCRITORS and not substituir:
            raise ValueError('Identificador duplicado: ' + descritor.id)
        _DESCRITORS[descritor.id] = descritor


def registrar_varios(descritores) -> int:
    total = 0
    for descritor in descritores or ():
        registrar(descritor)
        total += 1
    return total


def todos(*, incluir_ocultos=True) -> tuple[DescritorApp, ...]:
    with _TRAVA:
        itens = tuple(_DESCRITORS.values())
    if not incluir_ocultos:
        itens = tuple(i for i in itens if i.visivel_na_central)
    return itens


def por_id(identificador: str) -> DescritorApp | None:
    with _TRAVA:
        return _DESCRITORS.get(str(identificador or ''))


def categorias() -> tuple[str, ...]:
    presentes = {i.categoria for i in todos() if i.fixavel_no_dock}
    return tuple(c for c in CATEGORIAS if c in presentes or c in ('todos', 'favoritos'))


def sincronizar_habilidades() -> int:
    """Converte o catálogo nativo em descritores, sem importar módulos extras."""
    from core import catalogo_habilidades as CH  # importação leve e local
    total = 0
    for habilidade in CH.todas():
        descritor = DescritorApp(
            id='hab_' + habilidade.id,
            nome=habilidade.nome,
            descricao=habilidade.descricao,
            categoria='habilidades',
            tipo='habilidade',
            icone='system',
            cor='#00ff88',
            possui_interface=False,
            executavel_por_nia=True,
            fixavel_no_dock=False,
            dominio_ferramenta='habilidades',
            acoes=(habilidade.acao,),
            permissoes=habilidade.permissoes,
            palavras_chave=tuple(p for p in habilidade.exemplo.split() if len(p) > 3),
            carregamento_sob_demanda=True,
            origem='catalogo',
            versao=habilidade.versao,
            api=habilidade.api,
            esquema_entrada=habilidade.esquema_entrada,
            esquema_saida=habilidade.esquema_saida,
            agendavel=habilidade.agendavel,
            aliases=habilidade.aliases,
        )
        try:
            registrar(descritor, substituir=True)
            total += 1
        except (TypeError, ValueError):
            continue
    return total


def sincronizar_ferramentas() -> int:
    """Converte declarações compactas de main, sem copiar o catálogo."""
    if _PROVEDOR_FERRAMENTAS is None:
        return 0
    try:
        declaracoes = _PROVEDOR_FERRAMENTAS() or ()
    except Exception:
        return 0
    total = 0
    for declaracao in declaracoes:
        try:
            nome = declaracao['name']
            descritor = DescritorApp(
                id='tool_' + nome,
                nome=nome.replace('_', ' ').title(),
                descricao=str(declaracao.get('description') or '')[:300],
                categoria='sistema',
                tipo='ferramenta',
                icone='system',
                cor='#00d4ff',
                possui_interface=False,
                # Atalhos para o modelo, não blocos da Central: 44 entradas
                # poluiriam a grade sem ação útil para a pessoa. Também não
                # são apps do dock, então não entram na seleção da bandeja.
                visivel_na_central=False,
                fixavel_no_dock=False,
                dominio_ferramenta=nome,
                acoes=(nome,),
                exigir_config=False,
                carregamento_sob_demanda=True,
                origem='tool_declaration',
            )
            registrar(descritor, substituir=True)
            total += 1
        except (KeyError, TypeError, ValueError):
            continue
    return total


def disponibilidade(identificador: str) -> DisponibilidadeApp:
    descritor = por_id(identificador)
    if descritor is None:
        return DisponibilidadeApp(False, 'Aplicativo não registrado.')
    if not descritor.disponivel:
        return DisponibilidadeApp(False, 'Aplicativo desabilitado.')
    if _PROVEDOR_DISPONIBILIDADE is not None:
        try:
            resultado = _PROVEDOR_DISPONIBILIDADE(descritor)
            if isinstance(resultado, DisponibilidadeApp):
                return resultado
        except Exception:
            return DisponibilidadeApp(False, 'Não foi possível verificar disponibilidade.')
    return DisponibilidadeApp(True, '')


def buscar(termo: str = '', categoria: str = 'todos', *, favoritos=None,
           apenas_disponiveis=False) -> tuple[DescritorApp, ...]:
    """Pesquisa local: nome, descrição, categoria e palavras-chave, sem acentos."""
    termo = normalizar(termo)
    itens = [i for i in todos() if i.fixavel_no_dock]
    if categoria == 'favoritos':
        favoritos = set(favoritos or ())
        itens = [i for i in itens if i.id in favoritos]
    elif categoria != 'todos':
        itens = [i for i in itens if i.categoria == categoria]
    if apenas_disponiveis:
        itens = [i for i in itens if i.disponivel]
    if termo:
        filtrados = []
        for item in itens:
            campos = ' '.join((item.nome, item.descricao, item.categoria,
                               ' '.join(item.palavras_chave), item.id))
            if termo in normalizar(campos):
                filtrados.append(item)
        itens = filtrados
    return tuple(sorted(itens, key=lambda i: (i.categoria, i.nome.casefold())))


_PADROES_CENTRAL = (
    ('abrir_central', r'^(?:nia[,:]?\s+)?(?:abra|abrir|mostre|mostrar) a central(?: de aplicativos)?\.?$'),
    ('fechar_central', r'^(?:nia[,:]?\s+)?(?:feche|fechar|esconda) a central(?: de aplicativos)?\.?$'),
    ('abrir_manual', r'^(?:nia[,:]?\s+)?(?:abra|abrir|mostre|mostrar) o manual(?: da nia| de uso| de comandos)?\??$'),
    ('ajuda', r'^(?:nia[,:]?\s+)?(?:quais comandos (?:voce|você) entende|como uso a nia|me ajude)\??$'),
    ('listar', r'^(?:nia[,:]?\s+)?(?:mostre|mostrar|quais) (?:todas as |as )?(?:suas |minhas )?(?:ferramentas|aplicativos|habilidades)(?: disponíveis| (?:que )?voce (?:possui|tem))?(?:\??)$'),
    ('config_pendente', r'^(?:nia[,:]?\s+)?quais aplicativos precisam ser configurados\??$'),
    ('ferramentas_pesquisa', r'^(?:nia[,:]?\s+)?quais ferramentas de pesquisa(?: que)?(?: você| voce)?(?: possui| tem)?\??$'),
    ('abrir_app', r'^(?:nia[,:]?\s+)?abra (?:a |o )?(?P<app>canvas infinito|agenda|configurações|configuracoes|globo)\.?$'),
    ('dock', r'^(?:nia[,:]?\s+)?(?P<acao>fixe|fixar|adicione|remova|remover) (?:a |o )?(?P<app>agenda|globo|configurações|configuracoes) (?:no|do|ao) dock\.?$'),
)


def reconhecer_comando_central(texto: str) -> tuple[str, dict]:
    """Reconhece frases curtas da Central sem IA; dados são apenas nomes."""
    limpo = normalizar(texto)
    if not limpo:
        return '', {}
    for tipo, padrao in _PADROES_CENTRAL:
        encontrado = re.match(padrao, limpo)
        if encontrado is None:
            continue
        dados = encontrado.groupdict()
        if tipo == 'dock':
            dados['acao'] = 'dock_fixar' if dados['acao'] in ('fixe', 'fixar', 'adicione') \
                else 'dock_remover'
        return tipo, dados
    return '', {}


def preferencias():
    """Preferências do usuário, carregadas sob demanda (sem dado sensível)."""
    from core.interface_canvas import DockPreferences  # noqa: PLC0415
    from core.config_preferencias import ConfigService  # noqa: PLC0415
    servico = ConfigService()
    return DockPreferences(servico.interface_path), servico


def carregar(descritor: DescritorApp):
    """Importa o módulo sob demanda. Nunca chamado por encontrar()/todos()."""
    if not descritor.carregador:
        return None
    import importlib  # noqa: PLC0415
    nome_modulo, nome_funcao = descritor.carregador.split(':', 1)
    modulo = importlib.import_module(nome_modulo)
    return getattr(modulo, nome_funcao)
