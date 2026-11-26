"""Fila real e entrega Qt, sem rede, áudio ou processos externos."""
import threading
import time

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from core.config_dashboard import TaskRunner


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def esperar(app, condicao, prazo=3):
    limite = time.monotonic() + prazo
    while not condicao() and time.monotonic() < limite:
        app.processEvents()
        time.sleep(.005)
    assert condicao()


@pytest.fixture
def runner(app):
    r = TaskRunner(max_pendentes=2)
    yield r
    r.encerrar()
    assert r.aguardar_encerramento(2)
    app.processEvents()


def test_ordem_concorrencia_e_entrega_na_thread_qt(app, runner):
    resultados = []
    thread_qt = threading.get_ident()
    runner.bridge.terminou.connect(lambda token, valor: resultados.append((token, valor, threading.get_ident())))
    tokens = [runner.executar(lambda n=n: n) for n in range(2)]
    esperar(app, lambda: len(resultados) == 2)
    assert [r[0] for r in resultados] == tokens
    assert [r[1] for r in resultados] == [0, 1]
    assert all(r[2] == thread_qt for r in resultados)


def test_fila_cheia_tem_limite_e_resultado_posterior(app):
    r = TaskRunner(max_pendentes=1)
    entrou = threading.Event()
    liberar = threading.Event()
    resultados = []
    r.bridge.terminou.connect(lambda t, v: resultados.append((t, v)))
    try:
        r.executar(lambda: entrou.set() or liberar.wait(2))
        assert entrou.wait(2)
        r.executar(lambda: 'segundo')
        recusado = r.executar(lambda: pytest.fail('Tarefa excedente executada'))
        assert not resultados
        assert r._fila.qsize() == 1
        assert len(r._tarefas) == 2
        esperar(app, lambda: any(t == recusado for t, _ in resultados))
        assert next(v for t, v in resultados if t == recusado)['estado'] == 'fila_cheia'
    finally:
        liberar.set()
        r.encerrar()
        assert r.aguardar_encerramento(2)


def test_cancelamento_ativo_e_pendente(app, runner):
    entrou = threading.Event()
    resultados = []
    runner.bridge.terminou.connect(lambda t, v: resultados.append((t, v)))
    def longa(ctx):
        entrou.set()
        while True:
            ctx.verificar()
            ctx.cancelamento.wait(.005)
    ativo = runner.executar(longa, cooperativa=True)
    assert entrou.wait(2)
    pendente = runner.executar(lambda: pytest.fail('Cancelada executou'))
    assert runner.cancelar(pendente) and runner.cancelar(ativo)
    esperar(app, lambda: len(resultados) == 2)
    assert all(v['estado'] == 'cancelada' for _, v in resultados)
    assert not runner.cancelar(ativo)


def test_timeout_cooperativo_e_espera_na_fila(app, runner):
    resultados = []
    runner.bridge.terminou.connect(lambda t, v: resultados.append((t, v)))
    def longa(ctx):
        while True:
            ctx.verificar()
            time.sleep(.005)
    ativo = runner.executar(longa, cooperativa=True, timeout=.08)
    pendente = runner.executar(lambda: pytest.fail('Prazo vencido executou'), timeout=.001)
    esperar(app, lambda: len(resultados) == 2)
    assert {t for t, _ in resultados} == {ativo, pendente}
    assert all(v['estado'] == 'timeout' for _, v in resultados)


def test_erro_isolado_nao_expoe_segredos_e_worker_continua(app, runner):
    resultados = []
    runner.bridge.terminou.connect(lambda t, v: resultados.append(v))
    def erro():
        raise RuntimeError('segredo-ficticio')
    runner.executar(erro)
    runner.executar(lambda: 'recuperou')
    esperar(app, lambda: len(resultados) == 2)
    assert resultados[0]['estado'] == 'erro'
    assert 'segredo-ficticio' not in str(resultados)
    assert resultados[1] == 'recuperou'


def test_fechamento_cooperativo_sem_worker_orfao(app):
    r = TaskRunner()
    entrou = threading.Event()
    chamadas = []
    def longa(ctx):
        entrou.set()
        ctx.cancelamento.wait(2)
        ctx.verificar()
    r.executar(longa, cooperativa=True)
    assert entrou.wait(2)
    r.executar(lambda: chamadas.append('indevido'))
    r.bridge.terminou.connect(lambda *args: chamadas.append('resultado_tardio'))
    inicio = time.monotonic()
    r.encerrar()
    assert time.monotonic() - inicio < .2
    r.encerrar()
    assert r.aguardar_encerramento(2)
    app.processEvents()
    assert chamadas == [] and not r._tarefas
    assert not r._thread.is_alive()


def test_legado_bloqueante_fecha_sem_bloquear_qt_e_sai_ao_retorno(app):
    r = TaskRunner()
    entrou = threading.Event()
    liberar = threading.Event()
    try:
        r.executar(lambda: entrou.set() or liberar.wait(2))
        assert entrou.wait(2)
        r.encerrar()
        assert not r.aguardar_encerramento(0)
    finally:
        liberar.set()
        assert r.aguardar_encerramento(2)


def test_progresso_limitado_e_eventos_qt_responsivos(app, runner):
    progresso = []
    terminou = []
    qt_respondeu = []
    runner.bridge.progresso.connect(lambda t, f, m: progresso.append((f, m)))
    runner.bridge.terminou.connect(lambda *args: terminou.append(True))
    def tarefa(ctx):
        for i in range(100):
            ctx.informar_progresso(i / 100, 'Teste')
        ctx.informar_progresso(1, 'Completo')
        time.sleep(.08)
    runner.executar(tarefa, cooperativa=True)
    QTimer.singleShot(0, lambda: qt_respondeu.append(True))
    esperar(app, lambda: bool(terminou))
    assert qt_respondeu and len(progresso) <= 3
    assert progresso[-1] == (1, 'Completo')


def test_orcamento_pc_fraco_e_parametros_invalidos(app, monkeypatch):
    from core import pc_fraco
    monkeypatch.setattr(pc_fraco, 'e_fraco', lambda: True)
    r = TaskRunner()
    try:
        assert r._fila.maxsize == 8
        for prazo in (-1, 0, float('inf'), float('nan'), True):
            with pytest.raises(ValueError):
                r.executar(lambda: None, timeout=prazo)
        with pytest.raises(ValueError):
            TaskRunner(max_pendentes=0)
    finally:
        r.encerrar()
        assert r.aguardar_encerramento(2)
