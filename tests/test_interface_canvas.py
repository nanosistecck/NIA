"""Contratos de UI sem rede, câmera, microfone ou preferências do usuário."""
import json
import os
import threading
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

import pytest
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton, QDialog, QListWidget

import ui
from core.interface_canvas import DockPreferences, VerticalDock


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app,tmp_path,monkeypatch):
    monkeypatch.setattr(ui,'CONFIG_DIR',tmp_path)
    monkeypatch.setattr(ui.MainWindow,'_check_config',lambda self:True)
    w=ui.MainWindow('face.png'); w.resize(1280,820); w.show(); app.processEvents()
    yield w
    for timer in w.findChildren(QTimer): timer.stop()
    w.hide(); w.deleteLater(); app.processEvents()


def settle(app):
    QTest.qWait(260); app.processEvents()


def test_open_empty_minimum_history_and_fullscreen(window,app):
    w=window
    assert not w._stage.cards and not w._drawer.isVisible()
    assert not w._left_panel.isVisible()
    w.resize(820,580); settle(app)
    assert (w.width(),w.height())==(820,580)
    for widget in (w._composer,w._right_panel,w._stage):
        assert w.centralWidget().rect().contains(widget.geometry())
    w._input.setText('rascunho')
    w._current_file='anexo-preservado.txt'
    w._toggle_history(); settle(app)
    assert w._drawer.isVisible()
    assert w._drawer.geometry().bottom()<w._composer.geometry().top()
    w._toggle_history()
    assert w._input.text()=='rascunho' and w._current_file=='anexo-preservado.txt'
    w._toggle_fullscreen(); app.processEvents(); assert w.isFullScreen()
    w._toggle_fullscreen(); app.processEvents(); assert not w.isFullScreen()


def test_text_enter_hidden_log_and_interrupt(window,app):
    w=window; received=[]; delivered=threading.Event()
    def send(text): received.append(text); delivered.set()
    w.on_text_command=send
    w._input.setFocus(); w._input.setText('Olá NIA')
    QTest.keyClick(w._input,Qt.Key.Key_Return)
    assert delivered.wait(2) and received==['Olá NIA']
    w._input.setText('próximo rascunho')
    def reply(): w._log_sig.emit('NIA: resposta recebida')
    t=threading.Thread(target=reply); t.start(); t.join(); settle(app)
    assert not w._drawer.isVisible() and not w._log._tmr.isActive()
    assert w._input.text()=='próximo rascunho'
    assert w._input.hasFocus()
    stopped=[]; w.on_interrupt=lambda:stopped.append(True)
    QTest.keyClick(w._input,Qt.Key.Key_Escape); app.processEvents()
    assert stopped==[True]
    w._toggle_history(); app.processEvents()
    assert any('resposta recebida' in label.text() for label in w._log.findChildren(ui.QLabel))


def test_results_thread_pin_update_copy_close_and_scroll(window,app):
    w=window
    center=w._hud_cam_stack.geometry().center().x()
    worker=threading.Thread(target=lambda:w._content_sig.emit('<b>Pesquisa</b>','<script>texto é dado</script>'))
    worker.start(); worker.join(); settle(app)
    first=w._stage.cards[0]
    assert first.label.textFormat()==Qt.TextFormat.PlainText
    assert first.text.toPlainText()=='<script>texto é dado</script>'
    assert w._hud_cam_stack.geometry().center().x()>center
    w._show_content(first.title,'atualizado'); assert w._stage.cards==[first]
    assert first.text.toPlainText()=='atualizado'
    next(b for b in first.findChildren(QPushButton) if b.text()=='Copiar').click()
    assert app.clipboard().text()=='atualizado'
    next(b for b in first.findChildren(QPushButton) if b.text()=='Fixar').click()
    for i in range(6):
        w._show_content(str(i),str(i)); w._stage.cards[-1]._pin(True)
    assert first in w._stage.cards
    w.resize(820,580); settle(app)
    assert w._stage.results.verticalScrollBar().maximum()>0
    for card in list(w._stage.cards): w._stage.close_card(card)
    settle(app)
    assert not w._stage.results.isVisible()
    assert abs(w._hud_cam_stack.geometry().center().x()-w._stage.width()/2)<2


def test_dock_edit_save_restart_missing_app_and_explicit_launch(app,tmp_path,monkeypatch):
    path=tmp_path/'interface.json'; executable=tmp_path/'app.exe'; executable.write_text('fixture')
    buttons=[('mic',QPushButton('Microfone')),('camera',QPushButton('Câmera'))]
    dock=VerticalDock(buttons,path); dock.show(); app.processEvents()
    def edit():
        dlg=dock.findChild(QDialog)
        listing=dlg.findChild(QListWidget)
        listing.item(0).setCheckState(Qt.CheckState.Unchecked)
        listing.item(1).setCheckState(Qt.CheckState.Checked)
        listing.insertItem(0,listing.takeItem(1))
        dlg.accept()
    QTimer.singleShot(0,edit); dock.edit_dock()
    stored=json.loads(path.read_text(encoding='utf-8'))
    assert stored['order']==['camera','mic'] and stored['hidden']==['mic']
    dock.preferences.data['apps']=[str(executable),str(tmp_path/'missing.exe')]
    dock.apply(); dock.persist()
    launches=[]
    monkeypatch.setattr('core.interface_canvas.QDesktopServices.openUrl',lambda url:launches.append(url.toLocalFile()))
    assert not launches
    dock.shortcuts[0].click(); assert [Path(p) for p in launches]==[executable]
    assert not dock.shortcuts[1].isEnabled()
    dock.toggle_dock(); assert not dock.scroll.isVisible() and dock.toggle.isVisible()
    reloaded=VerticalDock([('mic',QPushButton()),('camera',QPushButton())],path)
    assert not reloaded.expanded and reloaded.preferences.data['hidden']==['mic']
    dock.deleteLater(); reloaded.deleteLater(); app.processEvents()


def test_bad_preferences_and_visible_states(window,tmp_path,app,monkeypatch):
    path=tmp_path/'bad.json'; path.write_text('{')
    assert DockPreferences(path).data=={}
    path.write_text('{"apps":false,"order":[null,5,"mute"]}')
    assert DockPreferences(path).data=={'apps':[],'order':['mute']}
    w=window
    for state in ('LISTENING','THINKING','SPEAKING','MUTED'):
        w._state_sig.emit(state); app.processEvents()
        assert w.hud.state==state and w._rail_state_lbl.text()
    w._toggle_mute(); assert w.hud.muted
    monkeypatch.setattr(w,'_janela_coberta',lambda:True)
    w._conferir_se_esta_a_vista()
    assert w._dormindo and not w.hud._tmr.isActive()
    monkeypatch.setattr(w,'_janela_coberta',lambda:False)
    w._conferir_se_esta_a_vista()
    assert not w._dormindo and w.hud._tmr.isActive()


def test_camera_vision_and_cowork_keep_existing_delivery(window,app):
    from PyQt6.QtCore import QByteArray, QBuffer, QIODevice
    from PyQt6.QtGui import QImage, QColor
    w=window
    frame=QImage(48,48,QImage.Format.Format_RGB32); frame.fill(QColor('#28ccde'))
    data=QByteArray(); buffer=QBuffer(data); buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert frame.save(buffer,'PNG')
    wrapper=object.__new__(ui.NiaUI); wrapper._win=w
    wrapper.set_vision_control_active(True,'ATIVA')
    wrapper.update_vision_control_frame(bytes(data),'ATIVA')
    wrapper.show_camera_frame(bytes(data)); settle(app)
    assert w._left_panel.isVisible() and w._vision_panel.isVisible()
    assert w._vision_img_lbl.pixmap() and w._cam_preview.isVisible()
    w._aplicar_cowork_estado({'pasta':'projeto','nome':'Projeto','ocupado':False})
    assert w._cw_card.isVisible()
    w._toggle_history(); settle(app)
    assert w._left_panel.height()<w._stage.height()
    w._on_cam_stream(True); app.processEvents(); assert w._cam_cont.isVisible()
    w._on_cam_stream(False); app.processEvents(); assert not w._cam_cont.isVisible()
    wrapper.set_vision_control_active(False); app.processEvents()
    assert not w._vision_panel.isVisible()


def test_background_default_darker_color_and_cache(app):
    from core.interface_canvas import CanvasBackground, appearance_settings
    bg=CanvasBackground(); bg.resize(400,260); bg._ensure_cache()
    dark=bg._cache.toImage()
    key=bg._cache.cacheKey(); bg._ensure_cache()
    assert key==bg._cache.cacheKey()
    assert bg.appearance['brightness']==90
    bg.set_appearance(dict(bg.appearance,brightness=100)); bg._ensure_cache()
    light=bg._cache.toImage()
    for x,y in ((10,10),(90,190),(340,90),(290,230)):
        a,b=dark.pixelColor(x,y),light.pixelColor(x,y)
        for channel in ('red','green','blue'):
            assert abs(getattr(a,channel)()-getattr(b,channel)()*.9)<=1.5
    bg.set_appearance(dict(bg.appearance,background_color='#42224f'))
    assert bg._palette_color('#10283e').name()=='#42224f'
    bg._ensure_cache(); assert bg._cache.toImage()!=light
    bounded=appearance_settings({'appearance':{'icon_size':500,'brightness':-5,'dock_height':True,'background_color':'invalida'}})
    assert bounded['icon_size']==40 and bounded['brightness']==40
    assert bounded['dock_height']==570 and bounded['background_color']=='#10283e'


def test_appearance_dialog_save_cancel_reload_and_small_window(window,app):
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QTabWidget, QSlider, QSpinBox
    from unittest.mock import patch
    w=window; dock=w._right_panel
    def change(save):
        dlg=dock.findChild(QDialog)
        tabs=dlg.findChild(QTabWidget)
        assert [tabs.tabText(i) for i in range(tabs.count())]==['Ferramentas','Fundo','Dock']
        dlg.findChild(QSlider,'background_brightness').setValue(120)
        dlg.findChild(QSpinBox,'dock_icon_size').setValue(40)
        dlg.findChild(QSpinBox,'dock_height').setValue(800)
        with patch('core.interface_canvas.QColorDialog.getColor',return_value=QColor('#42224f')):
            dlg.findChild(QPushButton,'background_color').click()
        assert w.centralWidget().appearance['brightness']==90
        (dlg.accept if save else dlg.reject)()
    QTimer.singleShot(0,lambda:change(False)); dock.edit_dock(); settle(app)
    assert w.centralWidget().appearance['brightness']==90
    QTimer.singleShot(0,lambda:change(True)); dock.edit_dock(); settle(app)
    expected={'background_color':'#42224f','brightness':120,'icon_size':40,'dock_height':800}
    assert w.centralWidget().appearance==expected
    assert DockPreferences(dock.preferences.path).data['appearance']==expected
    assert dock.buttons['mute'].property('dock_icon_size')==40
    assert dock.buttons['config'].iconSize().width()==40
    w.resize(820,580); settle(app)
    assert dock.geometry().bottom()<w._composer.geometry().top()
    assert dock.scroll.verticalScrollBar().maximum()>0
