import copy
import json
import logging
import sys
import tempfile
import threading
from pathlib import Path
from PySide6.QtCore import QObject, QThread, Signal, Qt, QUrl, QTimer, Slot
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QInputDialog, QMessageBox, QLabel, QPlainTextEdit, QLineEdit,
    QComboBox, QTableWidget, QTableWidgetItem, QSlider, QSplitter, QDialog, QFormLayout,
    QDialogButtonBox, QScrollArea, QSpinBox, QDoubleSpinBox, QCheckBox)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtTextToSpeech import QTextToSpeech
from .project import Project, Cue, seconds, stamp, import_subtitles,response_json
from .services import Settings, generate, download, export_audio, synthesize
from .i18n import LANGUAGES,apply_language


class Worker(QObject):
    done=Signal(object);failed=Signal(str);log=Signal(str);finished=Signal()
    def __init__(self, fn, cancel): super().__init__();self.fn=fn;self.cancel=cancel
    def run(self):
        try:
            result=self.fn(self.cancel,self.log.emit)
            if self.cancel.is_set():raise InterruptedError('Operation cancelled.')
            self.done.emit(result)
        except Exception as e: self.failed.emit(f'{type(e).__name__}: {e}')
        finally: self.finished.emit()


class SceneExplorer(QDialog):
    def __init__(self, data, speech, parent):
        super().__init__(parent);self.setWindowTitle('Scene Explorer');self.resize(650,450)
        from .project import scene_data
        self.data=scene_data(data);data=self.data;self.speech=speech;self.x=5;self.y=5
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel('Arrow keys: move · D: layout · L: objects · Shift+L: jump · Enter: nearest object'))
        self.view=QPlainTextEdit();self.view.setReadOnly(True);self.view.setFocusPolicy(Qt.FocusPolicy.NoFocus);layout.addWidget(self.view)
        from .desktop import LayoutGrid
        self.grid=LayoutGrid(self);layout.insertWidget(1,self.grid)
        self.describe(data.get('layout','No layout returned.'))
    def describe(self,text): self.view.appendPlainText(text);self.speech.say(text)
    def keyPressEvent(self,e):
        k=e.key();objects=self.data.get('objects',[])
        if k in [Qt.Key.Key_Left,Qt.Key.Key_Right,Qt.Key.Key_Up,Qt.Key.Key_Down]:
            self.x=max(0,min(10,self.x+(k==Qt.Key.Key_Right)-(k==Qt.Key.Key_Left)))
            self.y=max(0,min(10,self.y+(k==Qt.Key.Key_Down)-(k==Qt.Key.Key_Up)))
            self.describe(f'Position {self.x}, {self.y}')
        elif k==Qt.Key.Key_D: self.describe(self.data.get('layout',''))
        elif k==Qt.Key.Key_L:
            names=[str(o.get('name','Object')) for o in objects]
            if e.modifiers() & Qt.KeyboardModifier.ShiftModifier and names:
                name,ok=QInputDialog.getItem(self,'Jump to object','Object',names,0,False)
                if ok:
                    o=objects[names.index(name)];self.x=float(o.get('x',5));self.y=float(o.get('y',5));self.describe(str(o.get('description',name)))
            else: self.describe(', '.join(names) or 'No objects.')
        elif k in [Qt.Key.Key_Return,Qt.Key.Key_Enter] and objects:
            o=min(objects,key=lambda o:(float(o.get('x',5))-self.x)**2+(float(o.get('y',5))-self.y)**2)
            self.describe(str(o.get('name','Object'))+': '+str(o.get('description','')))
        else: super().keyPressEvent(e)
        self.grid.update()


from .desktop import DesktopInterface


class Window(DesktopInterface, QMainWindow):
    def __init__(self, settings_path=None):
        super().__init__();from . import __version__;self.setWindowTitle('Describer Workbench '+__version__);self.resize(1180,850)
        self.settings=Settings(settings_path);self.project=Project();self.project_path=None;self.dirty=False
        from .diagnostics import make_logger
        self.logger=make_logger(self.settings)
        self.thread=None;self.cancel=threading.Event();self.last_spoken=None;self.history=[]
        self.played_pauses=set();self.pause_active=False;self.api_server=None;self.api_thread=None
        self.player=QMediaPlayer(self);self.audio=QAudioOutput(self);self.player.setAudioOutput(self.audio)
        self.speech=QTextToSpeech(self);self.original_volume=self.settings.data['player_volume']/100;self.audio.setVolume(self.original_volume)
        from .playback_speech import PlaybackSpeech
        self.playback_speech=PlaybackSpeech(self.speech,self.settings.data,self.log)
        self.speech.setVolume(self.settings.data['speech_volume']/100)
        self.video=QVideoWidget();self.video.setMinimumHeight(200);self.player.setVideoOutput(self.video)
        self.player.positionChanged.connect(self.position_changed);self.player.durationChanged.connect(self.duration_changed)
        self.player.errorOccurred.connect(lambda e,msg:self.log('Playback: '+msg))
        self.speech.stateChanged.connect(self.speech_state)
        self.preview=QMediaPlayer(self);self.preview_audio=QAudioOutput(self);self.preview.setAudioOutput(self.preview_audio)
        self.pause_player=QMediaPlayer(self);self.pause_audio=QAudioOutput(self);self.pause_player.setAudioOutput(self.pause_audio)
        self.pause_player.mediaStatusChanged.connect(self.pause_status)
        self.pause_player.errorOccurred.connect(lambda error,message:self.pause_failed(message))
        self.narration=QMediaPlayer(self);self.narration_audio=QAudioOutput(self);self.narration.setAudioOutput(self.narration_audio)
        self.narration.playbackStateChanged.connect(lambda state:self.audio.setVolume(self.original_volume*10**(self.settings.data['duck_db']/20) if state==QMediaPlayer.PlaybackState.PlayingState else self.original_volume))
        self.preview_tmp=tempfile.TemporaryDirectory(prefix='describer-preview-')
        for v in self.speech.availableVoices():
            if v.name()==self.settings.data.get('playback_voice'):self.speech.setVoice(v)
        central=QWidget();self.setCentralWidget(central);layout=QVBoxLayout(central)
        row=QHBoxLayout();layout.addLayout(row)
        for name,fn in [('Open video',self.open_video),('Open URL',self.open_url),('Analyze video',self.analyze),('Settings',self.edit_settings)]: self.button(row,name,fn)
        self.cancel_button=self.button(row,'Cancel operation',lambda:self.cancel.set());self.cancel_button.setEnabled(False)
        self.file_label=QLabel('Open a video to begin.');layout.addWidget(self.file_label)
        from .model_picker import ModelPicker
        self.model_picker=ModelPicker(self);layout.addWidget(self.model_picker)
        split=QSplitter(Qt.Orientation.Vertical);layout.addWidget(split,1);split.addWidget(self.video)
        editor=QWidget();el=QVBoxLayout(editor);split.addWidget(editor)
        controls=QHBoxLayout();el.addLayout(controls)
        self.button(controls,'−10 s',lambda:self.seek(self.player.position()-10000));self.button(controls,'Play / Pause',self.toggle)
        self.button(controls,'+10 s',lambda:self.seek(self.player.position()+10000));self.clock=QLabel('00:00:00');controls.addWidget(self.clock)
        self.slider=QSlider(Qt.Orientation.Horizontal);self.slider.setAccessibleName('Video position');self.slider.valueChanged.connect(self.seek);controls.addWidget(self.slider,1)
        self.volume=QSlider(Qt.Orientation.Horizontal);self.volume.setRange(0,100);self.volume.setValue(self.settings.data['player_volume']);self.volume.setMaximumWidth(110);self.volume.setAccessibleName('Player volume');self.volume.valueChanged.connect(self.set_volume);controls.addWidget(QLabel('Volume'));controls.addWidget(self.volume)
        self.speak_check=QCheckBox('Speak descriptions');self.speak_check.setChecked(True);controls.addWidget(self.speak_check)
        self.current=QLabel('');self.current.setWordWrap(True);self.current.setAccessibleName('Current description');el.addWidget(self.current)
        self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['Start','End','Description','Placement']);self.table.setColumnWidth(2,650)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.select_cue);el.addWidget(self.table,1)
        form=QHBoxLayout();el.addLayout(form);self.start=QLineEdit('0');self.end=QLineEdit('3')
        form.addWidget(QLabel('Start'));form.addWidget(self.start);form.addWidget(QLabel('End'));form.addWidget(self.end)
        self.start.setAccessibleName('Description start time');self.end.setAccessibleName('Description end time');self.start.editingFinished.connect(self.update_fit)
        self.text=QPlainTextEdit();self.text.setAccessibleName('Description text');self.text.setMaximumHeight(95);el.addWidget(self.text)
        self.text.textChanged.connect(self.editor_changed);self.start.textChanged.connect(self.editor_changed);self.end.textChanged.connect(self.editor_changed)
        editrow=QHBoxLayout();el.addLayout(editrow)
        for name,fn in [('Add',self.add_cue),('Apply edit',self.apply_edit),('Delete',self.delete_cue),('Ask about scene',self.ask),('Explore scene',self.explore),('Export',self.export)]:self.button(editrow,name,fn)
        prompts=QHBoxLayout();layout.addLayout(prompts);prompts.addWidget(QLabel('Prompt preset'));self.preset=QComboBox();prompts.addWidget(self.preset)
        self.button(prompts,'Manage presets',self.presets);self.prompt=QPlainTextEdit();self.prompt.setFixedHeight(74);self.prompt.setAccessibleName('Editorial prompt');prompts.addWidget(self.prompt,1)
        self.preset.currentTextChanged.connect(self.preset_changed);self.reload_presets()
        self.log_view=QPlainTextEdit();self.log_view.setReadOnly(True);self.log_view.setMaximumHeight(95);self.log_view.setAccessibleName('Status and token usage log');layout.addWidget(self.log_view)
        menu=self.menuBar().addMenu('&File')
        for label,key,fn in [('Open video','Ctrl+O',self.open_video),('Open URL','Ctrl+U',self.open_url),('Open YouTube','Ctrl+Y',self.open_url),
                             ('Open project','Ctrl+Shift+O',self.load_project),('Save project','Ctrl+S',self.save_project),
                             ('Import SRT / VTT','Ctrl+I',self.import_cues),('Settings','Ctrl+,',self.edit_settings),('Export','Ctrl+E',self.export)]:
            action=QAction(label,self);action.setShortcut(QKeySequence(key));action.triggered.connect(fn);menu.addAction(action)
        glossary=QAction('Character glossary',self);glossary.triggered.connect(self.edit_glossary);menu.addAction(glossary)
        for label,fn in [('Recover interrupted jobs',self.recover_jobs),('Repair narration',self.repair_narration),('Install speech detector',self.install_detector),('Start developer API / MCP',self.start_api),('Stop developer API / MCP',self.stop_api)]:
            action=QAction(label,self);action.triggered.connect(fn);menu.addAction(action)
        for label,fn in [('Manage voice presets',self.manage_voices),('Test selected export voice',self.test_voice),('Select Windows export voice',self.select_windows_voice),('Import original data',self.import_original),('Check for updates',self.check_updates)]:
            action=QAction(label,self);action.triggered.connect(fn);menu.addAction(action)
        apply_language(self,self.settings.data['ui_language'])
        from .i18n import DialogLanguage
        self.dialog_language=DialogLanguage(self);QApplication.instance().installEventFilter(self.dialog_language)
        QTimer.singleShot(0,lambda:self.sound('start'))
        if self.settings.load_warning:self.log(self.settings.load_warning)
        if self.settings.data.get('auto_update_check') and self.settings.data.get('update_feed'):QTimer.singleShot(1500,self.check_updates)
        helpaction=QAction('Help',self);helpaction.setShortcut('F1');helpaction.triggered.connect(self.help);self.menuBar().addAction(helpaction);apply_language(self,self.settings.data['ui_language'])
        self.build_interface()
    def button(self,row,text,fn):
        b=QPushButton(text);b.clicked.connect(fn);row.addWidget(b);return b
    def log(self,text,level=logging.INFO):
        for key in ['gemini_key','openai_key','ollama_key']:
            if self.settings.data[key]:text=text.replace(self.settings.data[key],'[redacted]')
        if level>=logging.INFO:self.log_view.appendPlainText(text)
        if hasattr(self,'job_note') and self.thread is not None:self.job_note.setText(text);self.job_label.setText('Working · '+text[:75])
        self.logger.setLevel(getattr(logging,self.settings.data.get('logging_level','INFO'),logging.INFO));self.logger.log(level,text)
    def error(self,text): self.sound('error');QMessageBox.warning(self,'Operation failed',text);self.log(text,logging.ERROR)
    def busy(self):
        if self.thread is not None: self.error('An operation is already running. Wait or cancel it.');return True
        return False
    def job(self,fn,done):
        if self.busy():return
        self.log('Starting background operation.',logging.DEBUG)
        self.sound('start');self.cancel=threading.Event();thread=QThread(self);worker=Worker(fn,self.cancel);worker.moveToThread(thread)
        self.thread=thread;self.worker=worker;self.done_callback=done;self.cancel_button.setEnabled(True)
        if hasattr(self,'job_card'):self.job_card.show();self.job_progress.setRange(0,0)
        self.model_picker.setEnabled(False)
        thread.started.connect(worker.run);worker.log.connect(self.log);worker.failed.connect(self.error);worker.done.connect(self.on_job_done,Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(thread.quit);worker.finished.connect(worker.deleteLater);thread.finished.connect(self.job_finished);thread.finished.connect(thread.deleteLater)
        thread.start()
    @Slot(object)
    def on_job_done(self,result):
        self.completed(self.done_callback,result)
    def completed(self,done,result):
        try:done(result);self.sound('finish')
        except Exception as e:self.error(str(e))
    def job_finished(self):
        self.log('Background operation finished.',logging.DEBUG)
        self.thread=None;self.worker=None;self.cancel_button.setEnabled(False)
        self.model_picker.setEnabled(True)
        if hasattr(self,'job_card'):
            self.job_card.hide()
            if self.cancel.is_set():self.notify('Operation stopped. Completed downloads and durable checkpoints are retained.')
        pending=getattr(self,'pending_after_job',None);self.pending_after_job=None
        if pending and not self.cancel.is_set():QTimer.singleShot(0,pending)
        if getattr(self,'pending_model_test',None):
            settings=self.pending_model_test;self.pending_model_test=None
            from .models import test_connection
            QTimer.singleShot(0,lambda:self.job(lambda c,l:test_connection(settings,c,l),self.log))
        if getattr(self,'pending_update',None):
            data,folder=self.pending_update;self.pending_update=None;self.stage_update_job(data,folder)
    def guard_changes(self):
        if not self.dirty:return True
        choice=QMessageBox.question(self,'Unsaved project','Save changes before continuing?',QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel)
        if choice==QMessageBox.StandardButton.Cancel:return False
        if choice==QMessageBox.StandardButton.Save:return bool(self.save_project())
        return True
    def reset_scene(self):
        self.history=[]
        if hasattr(self,'answer'):del self.answer
        self.conversation.clear();self.answer_text.setText('No answer yet.');self.add_answer_button.setEnabled(False)
        self.question.clear()
        while self.explore_host.count():
            item=self.explore_host.takeAt(0)
            if item.widget():item.widget().deleteLater()
    def set_video(self,path):
        from .services import probe
        self.pause_active=False;self.pause_player.stop();self.narration.stop();self.played_pauses.clear()
        duration=probe(path);self.playback_speech.stop();self.player.stop();self.project=Project(str(Path(path).resolve()),duration);self.project_path=None;self.dirty=False
        self.undo_stack.clear();self._selected_cue=None
        self.reset_scene();self.player.setSource(QUrl.fromLocalFile(self.project.video));self.file_label.setText(self.project.video);self.refresh();self.last_spoken=None
    def open_video(self):
        if self.busy() or not self.guard_changes():return
        p,_=QFileDialog.getOpenFileName(self,'Open video','','Video files (*.mp4 *.mkv *.mov *.avi *.webm);;All files (*)')
        if p:
            try:self.set_video(p)
            except Exception as e:self.error(str(e))
    def open_url(self):
        if self.busy() or not self.guard_changes():return
        url,ok=QInputDialog.getText(self,'Download video','Direct video or YouTube URL')
        if not ok or not url:return
        folder=QFileDialog.getExistingDirectory(self,'Save downloaded video in')
        if folder:
            quality=self.settings.data['download_quality'];self.job(lambda c,l:download(url,folder,c,l,quality),self.download_done)
    def download_done(self,path):
        try:self.set_video(path)
        except Exception as e:self.error(str(e))
    def duration_changed(self,value):self.slider.setRange(0,value)
    def seek(self,value):
        self.pause_active=False;self.pause_player.stop();self.narration.stop();self.playback_speech.stop();self.last_spoken=None
        self.played_pauses={c.event_id for c in self.project.cues if c.event_start is not None and c.event_start<value/1000}
        self.player.setPosition(max(0,value))
    def toggle(self):
        if self.pause_active:
            self.pause_active=False;self.pause_player.stop();return
        if self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState:self.player.pause();self.narration.stop();self.playback_speech.stop()
        else:self.last_spoken=None;self.player.play()
    def position_changed(self,value):
        self.slider.blockSignals(True);self.slider.setValue(value);self.slider.blockSignals(False);self.clock.setText(stamp(value/1000)[:-4])
        found=next(((i,c) for i,c in enumerate(self.project.cues) if c.start<=value/1000<c.end),None)
        self.current.setText(found[1].text if found else '')
        if self.speak_check.isChecked() and not self.pause_active and self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState:
            pause=next((c for c in self.project.cues if c.disposition=='pause' and c.event_id not in self.played_pauses and c.event_start<=value/1000<c.event_end),None)
            if pause:
                self.start_pause(pause);return
        if found and found[1].disposition not in ('pause','unresolved') and found[0]!=self.last_spoken and self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState:
            self.last_spoken=found[0]
            if self.speak_check.isChecked():
                cue=found[1]
                if cue.disposition=='in-gap':
                    if not Path(cue.audio).is_file():self.player.pause();self.offer_narration_repair();return
                    # Media position callbacks and audio startup are not sample-accurate.
                    # If playback arrived late, pause rather than speaking past a safe slot.
                    if cue.speech_seconds/cue.speed+.2>cue.end-value/1000:
                        self.start_pause(cue);return
                    self.narration.setPlaybackRate(cue.speed);self.narration.setSource(QUrl.fromLocalFile(cue.audio));self.narration.play()
                else:self.playback_speech.say(cue.text,self.settings.data['interrupt'])
        if not found:self.last_spoken=None
    def start_pause(self,cue):
        if not Path(cue.audio).is_file():self.player.pause();self.offer_narration_repair();return
        self.played_pauses.add(cue.event_id);self.pause_active=True;self.player.pause();self.narration.stop();self.playback_speech.stop()
        self.current.setText('Pause description: '+cue.text);self.pause_player.setSource(QUrl.fromLocalFile(cue.audio));self.pause_player.play()
    def pause_status(self,status):
        if status==QMediaPlayer.MediaStatus.EndOfMedia and self.pause_active:
            # Resume after the media-status callback unwinds, avoiding backend reentry.
            self.pause_active=False;QTimer.singleShot(0,self.player.play)
    def pause_failed(self,message):
        if self.pause_active:self.pause_active=False;self.log('Pause narration failed: '+message)
    def set_volume(self,value):
        self.settings.data['player_volume']=value;self.original_volume=value/100;self.speech_state(self.speech.state())
        try:self.settings.save()
        except Exception as exc:self.log('Could not save volume: '+str(exc))
    def speech_state(self,state):
        self.audio.setVolume(self.original_volume*10**(self.settings.data['duck_db']/20) if state==QTextToSpeech.State.Speaking else self.original_volume)
    def refresh(self):
        self.table.blockSignals(True);self.table.setRowCount(len(self.project.cues))
        for i,c in enumerate(self.project.cues):
            for k,v in enumerate([stamp(c.start),stamp(c.end),c.text,c.disposition+(': '+c.uncertainty if c.uncertainty else '')]):self.table.setItem(i,k,QTableWidgetItem(v))
        self.table.blockSignals(False)
        if hasattr(self,'pages'):
            self.pages.setCurrentIndex(1 if self.project.video else 0)
            self.render_cues();self.sync_glossary();self.presentation_position(self.player.position())
            self.recents.clear()
            self.recent_empty.setVisible(not self.settings.data.get('recent_projects'));self.recents.setVisible(bool(self.settings.data.get('recent_projects')))
            self.editor_toolbar.setVisible(self.pages.currentIndex()==1)
            for path in self.settings.data.get('recent_projects',[]):
                from PySide6.QtWidgets import QListWidgetItem
                item=QListWidgetItem(Path(path).stem);item.setData(Qt.UserRole,path);item.setToolTip(path);self.recents.addItem(item)
    def select_cue(self):
        i=self.table.currentRow()
        if 0<=i<len(self.project.cues):
            self._editor_loading=True
            c=self.project.cues[i];self.start.setText(str(c.start));self.end.setText(str(c.end));self.text.setPlainText(c.text);self.seek(round(c.start*1000));self._old_start=c.start
            self._editor_loading=False
            if hasattr(self,'inline'):self._selected_cue=c;self.inline.show();self.update_fit()
    def editor_changed(self):
        if getattr(self,'_editor_loading',False) or self.busy():return
        i=self.table.currentRow()
        if not 0<=i<len(self.project.cues):return
        try:
            candidate=self.editor_cue()
        except ValueError:
            return  # Keep intermediate typing; never publish an invalid cue.
        if candidate==self.project.cues[i]:return
        before=copy.deepcopy(self.project.cues);after=copy.deepcopy(before);after[i]=candidate;after.sort(key=lambda c:c.start)
        if hasattr(self,'undo_stack'):
            from .desktop import CueEdit
            self._typing=True
            try:self.undo_stack.push(CueEdit(self,before,after,'Edit description'))
            finally:self._typing=False
            index=next(j for j,c in enumerate(self.project.cues) if c==candidate)
            self.table.blockSignals(True);self.table.setCurrentCell(index,0);self.table.blockSignals(False)
            self._selected_cue=self.project.cues[index];self.update_fit()
        else:self.project.cues=after;self.dirty=True
    def shift_end(self):
        try:
            new=seconds(self.start.text());old=getattr(self,'_old_start',new);self.end.setText(str(max(new+.1,seconds(self.end.text())+new-old)));self._old_start=new
        except ValueError:pass
    def editor_cue(self):
        if not self.project.video:raise ValueError('Open a video first.')
        candidate=Cue(seconds(self.start.text()),seconds(self.end.text()),self.text.toPlainText()).validate(self.project.duration)
        i=self.table.currentRow()
        if 0<=i<len(self.project.cues):
            old=self.project.cues[i]
            return old.edited(candidate.start,candidate.end,candidate.text,self.project.duration)
        return candidate
    def add_cue(self):
        if self.busy():return
        try:self.project.cues.append(self.editor_cue());self.changed()
        except Exception as e:self.error(str(e))
    def apply_edit(self):
        if self.busy():return
        i=self.table.currentRow()
        if i<0:return
        try:self.project.cues[i]=self.editor_cue();self.changed()
        except Exception as e:self.error(str(e))
    def delete_cue(self):
        if self.busy():return
        i=self.table.currentRow()
        if i>=0:
            if QMessageBox.question(self,'Delete description','Delete the selected description?')==QMessageBox.StandardButton.Yes:
                cues=copy.deepcopy(self.project.cues);cues.pop(i);self.commit_cues(cues,'Delete description')
    def changed(self):self.project.cues.sort(key=lambda c:c.start);self.dirty=True;self.refresh();self.last_spoken=None
    def save_project(self):
        if self.busy():return False
        i=self.table.currentRow()
        if 0<=i<len(self.project.cues):
            try:self.project.cues[i]=self.editor_cue();self.changed()
            except Exception as e:self.error(str(e));return False
        p=self.project_path
        if not p:p,_=QFileDialog.getSaveFileName(self,'Save project','','Describer project (*.adproject)')
        if not p:return False
        try:self.project.save(p);self.project_path=p;self.dirty=False;self.remember_project();self.update_status();self.log('Project saved.');return True
        except Exception as e:self.error(str(e));return False
    def load_project(self):
        if self.busy() or not self.guard_changes():return
        p=getattr(self,'_recent_path',None)
        self._recent_path=None
        if not p:p,_=QFileDialog.getOpenFileName(self,'Open project','','Describer project (*.adproject)')
        if p:
            try:
                project=Project.load(p)
                if not Path(project.video).is_file():
                    replacement,_=QFileDialog.getOpenFileName(self,'Locate project video')
                    if not replacement:return
                    project.video=replacement
                from .services import probe
                actual=probe(project.video)
                for c in project.cues:c.validate(actual)
                project.duration=actual;self.undo_stack.clear();self._selected_cue=None;self.project=project;self.project_path=p;self.dirty=False;self.reset_scene()
                self.pause_active=False;self.pause_player.stop();self.narration.stop();self.played_pauses.clear()
                self.playback_speech.stop();self.player.stop();self.last_spoken=None;self.player.setSource(QUrl.fromLocalFile(project.video));self.file_label.setText(project.video);self.refresh();self.remember_project()
                QTimer.singleShot(0,lambda:self.offer_narration_repair() if self.project is project else None)
            except Exception as e:self.error(str(e))
    def import_cues(self):
        if self.busy():return
        if not self.project.video:self.error('Open a video first.');return
        p,_=QFileDialog.getOpenFileName(self,'Import descriptions','','Subtitles (*.srt *.vtt)')
        if p:
            try:
                warnings=[];cues=import_subtitles(p,self.project.duration,warnings)
                for warning in warnings:self.log(warning)
                if self.project.cues and QMessageBox.question(self,'Replace descriptions','Replace all current descriptions with the imported captions?')!=QMessageBox.StandardButton.Yes:return
                self.project.cues=cues;self.changed()
            except Exception as e:self.error(str(e))
    def after_job(self,callback):
        if self.thread is not None:self.pending_after_job=callback
        else:QTimer.singleShot(0,callback)
    def cloud_confirm(self,settings=None,info=None,narration=False,vision=True):
        settings=settings or self.settings.data
        destinations=[]
        if not vision:pass
        elif settings.get('analysis_provider','Gemini')=='Ollama':
            from .models import is_cloud
            if is_cloud(settings,info or {}):destinations.append('Sampled video frames and prompts to the selected remote/cloud Ollama server; may use paid allowance.')
        else:destinations.append('Video segments and prompts to Google Gemini using your key; may include audio and incur charges.')
        if narration and settings.get('voice_engine')=='OpenAI':destinations.append('Generated description text to OpenAI for paid speech synthesis.')
        if not destinations:return True
        return QMessageBox.question(self,'Confirm external processing','This operation sends:\n\n'+'\n\n'.join(destinations)+'\n\nContinue?')==QMessageBox.Yes
    def confirm_ollama(self,info,settings=None):
        settings=settings or self.settings.data
        from .models import is_cloud
        if not is_cloud(settings,info):return True
        return QMessageBox.question(self,'Use Ollama cloud or remote server','This sends prompts and sampled video frames to the selected remote model and may use paid allowance. Continue?')==QMessageBox.Yes
    def operation_preflight(self,settings,done,narration=False,detector=False,vision=True):
        identity=self.project;current_settings=copy.deepcopy(self.settings.data)
        def current():return self.project is identity and self.settings.data==current_settings
        def check(cancel,log):
            from .engine.core import check_cancel
            check_cancel(cancel)
            if detector:
                from .engine.assets import validate_detector
                try:validate_detector(settings)
                except Exception as exc:return {'detector_error':str(exc)}
            if narration:
                from .services import narration_preflight
                narration_preflight(settings,cancel)
            info=None
            if vision and settings.get('analysis_provider')=='Ollama':
                from .models import model_info
                log('Checking exact Ollama model; request timeout is 10 seconds. Cancel prevents starting inference.')
                info=model_info(settings)
            elif vision and not settings.get('gemini_key'):raise ValueError('Enter your Gemini key in Settings > Keys & privacy, then retry Draft or Scene.')
            check_cancel(cancel)
            return {'info':info}
        def ready(result):
            if self.cancel.is_set() or not current():return
            if 'detector_error' in result:
                message=result['detector_error']+'\n\nDownload/repair the selected pinned detector from Hugging Face, verify it, and continue this operation?'
                if QMessageBox.question(self,'Set up speech detector',message,QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Yes:return
                def install():
                    if not current():return
                    from .engine.assets import provision
                    def installed(path):
                        self.log('Speech detector installed and verified: '+str(path))
                        self.after_job(lambda:self.operation_preflight(settings,done,narration,detector,vision) if current() else None)
                    self.job(lambda c,l:provision(settings.get('sound_model') or None,c),installed)
                self.after_job(install);return
            if vision and settings.get('analysis_provider')=='Ollama':self.verified_model=(settings.get('ollama_url'),settings.get('ollama_model'))
            if narration:self.verified_voice=(settings.get('voice_engine'),settings.get('windows_voice'))
            if not self.cloud_confirm(settings,result['info'],narration,vision):return
            self.after_job(lambda:done() if current() else None)
        self.job(check,ready)
    def analyze(self):
        if self.busy() or not self.project.video:return
        if self.project.cues and QMessageBox.question(self,'Replace descriptions','Replace existing descriptions with newly generated results?')!=QMessageBox.StandardButton.Yes:return
        snapshot=copy.deepcopy(self.project);original_settings=copy.deepcopy(self.settings.data);settings=dict(original_settings,allow_cloud=True);prompt=self.prompt.toPlainText()
        scope=self.model_picker.scope.currentIndex()
        start_at=self.player.position()/1000 if scope else 0
        duration={1:20,2:60}.get(scope)
        def task(c,l):
            cues=generate(snapshot,settings,prompt,c,l,start_at,duration);return cues,snapshot.glossary,snapshot.coverage,snapshot.analysis
        self.operation_preflight(original_settings,lambda:self.job(task,self.generated),narration=True,detector=True)
    def generated(self,result):
        cues,glossary,*metadata=result;self.project.glossary=glossary;self.project.cues=cues
        if metadata:self.project.coverage,self.project.analysis=metadata
        self.played_pauses.clear();self.changed();self.log(f'Generated {len(cues)} descriptions; placement/uncertainty shown in the table. Review visual facts before use.')
        # Refresh the editor even if row zero was already selected before regeneration.
        # Save commits the selected editor, which must not still contain the old cue.
        if cues:self.table.setCurrentCell(0,0);self.select_cue()
    def scene_request(self,instruction,done,length=10):
        if self.busy() or not self.project.video:return
        self.player.pause();pos=self.player.position()/1000;source=self.project.video;duration=self.project.duration;settings=copy.deepcopy(self.settings.data);settings['allow_cloud']=True
        def task(cancel,log):
            from .engine import get_service
            service=get_service();start=max(0,pos-length/2)
            operation='explore' if '"objects"' in instruction else 'ask'
            job=service.submit(source=source,settings=settings,prompt=instruction,start=start,duration=max(.1,min(length,duration-start)),operation=operation)
            service.wait(job['id'],cancel,log)
            return json.dumps(service.scene_result(job['id']))
        identity=self.project
        self.operation_preflight(copy.deepcopy(self.settings.data),lambda:self.job(task,lambda result:done(result) if self.project is identity else None))
    def add_scene_answer(self,answer,position,button=None):
        if self.busy():return
        try:cue=Cue(position,min(position+4,self.project.duration),answer).validate(self.project.duration)
        except (ValueError,TypeError):
            if button:button.setEnabled(False)
            self.error('Move the playhead before the end of the video and ask again before adding a description.');return
        cue.disposition='unresolved';cue.uncertainty='AI scene answer: verify visual facts.'
        if hasattr(self,'undo_stack'):self.commit_cues([*self.project.cues,cue],'Add scene answer')
        else:self.project.cues.append(cue);self.changed()
        if button:button.setEnabled(False)
    def explore(self):
        instruction=f'In {self.settings.data["language"]}, describe spatial layout of the middle frame. Return JSON {{"layout":"summary","objects":[{{"name":"object","x":5,"y":5,"description":"detail"}}]}}. Grid x and y range 0 to 10, left-to-right and top-to-bottom. Avoid duplicate coordinates. Character glossary: {self.project.glossary}'
        def done(text):
            try:
                explorer=SceneExplorer(response_json(text),self.playback_speech,self)
                while self.explore_host.count():self.explore_host.takeAt(0).widget().deleteLater()
                explorer.setWindowFlags(Qt.Widget);self.explore_host.addWidget(explorer);explorer.show()
            except Exception as e:self.error(str(e))
        self.scene_request(instruction,done,2)
    def missing_narration(self):
        return [c for c in self.project.cues if c.disposition in ('in-gap','pause') and not Path(c.audio).is_file()]
    def offer_narration_repair(self):
        missing=self.missing_narration()
        if not missing or self.thread is not None:return
        self.player.pause()
        if QMessageBox.question(self,'Narration files are missing',f'{len(missing)} descriptions refer to missing narration. Repair narration using the selected speech engine? Text, evidence and source media are preserved. You can also use File > Repair narration later.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.repair_narration()
    def repair_narration(self):
        if self.busy() or not self.project.video or not self.project.cues:return
        self.player.pause();snapshot=copy.deepcopy(self.project);settings=copy.deepcopy(self.settings.data);identity=self.project
        def launch():
            from .engine import get_service
            service=get_service();allowed=dict(settings,allow_cloud=True)
            def done(project):
                if self.project is identity:
                    self.project=project;self.undo_stack.clear();self._selected_cue=None;self.changed();self.log('Narration repaired. Save the project to keep the new audio references.')
            self.job(lambda c,l:service.repair_narration(snapshot,allowed,c,l),done)
        self.operation_preflight(settings,launch,narration=True,detector=True,vision=False)
    def recover_jobs(self):
        if self.busy() or not self.guard_changes():return
        from .engine import get_service
        try:
            service=get_service();jobs=service.list_jobs(limit=200)
            if service.damaged_jobs:
                details='\n'.join(item['path'] for item in service.damaged_jobs.values())
                QMessageBox.warning(self,'Damaged job records preserved','These records could not be read and have been left unchanged. Other jobs remain available. Restore damaged records from a backup if available.\n'+details)
            rows=[]
            for job in jobs:
                if job['state'] not in ('error','cancelled','interrupted'):continue
                try:project=service.input_project(job['id'])
                except (OSError,ValueError,KeyError) as exc:
                    self.log('Cannot recover '+job['id']+': '+str(exc));continue
                rows.append((job,project))
            if not rows:QMessageBox.information(self,'Recover interrupted jobs','No readable failed, cancelled or interrupted jobs were found in this workspace.');return
            labels=[f"{job['id']} | {job['operation']} | {job['state']} | {Path(project.video).name}" for job,project in rows]
            selected,ok=QInputDialog.getItem(self,'Recover interrupted jobs','Choose a saved job. Original project and settings are used; current credentials are supplied without changing your saved preferences.',labels,0,False)
            if not ok:return
            job,project=rows[labels.index(selected)]
            if not Path(project.video).is_file():self.error('The saved job source is missing. Restore it to its original path before resuming; existing checkpoints are preserved.');return
            if QMessageBox.question(self,'Resume saved job',f"Resume {job['operation']} for {project.video}? Completed checkpoints will be reused only when source, settings and implementation match. The result opens as an unsaved recovered project.",QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Yes:return
            settings=dict(job['settings'])
            settings.update({k:v for k,v in self.settings.data.items() if k.endswith('_key')})
            vision=job['operation'] in ('describe','ask','explore')
            narration=job['operation'] in ('describe','prepare','voice-preview') or (job['operation']=='export' and job['export_format'] in ('mp3','wav','mp4'))
            identity=self.project
            def launch():
                def task(cancel,log):
                    # Retain the original permission value in checkpoint identity;
                    # current consent was obtained above for actual destinations.
                    service.resume(job['id'],settings=settings)
                    return service.wait(job['id'],cancel,log)
                def done(result):
                    if self.project is not identity:return
                    self.project=result;self.project_path=None;self.undo_stack.clear();self._selected_cue=None;self.reset_scene();self.played_pauses.clear()
                    self.player.setSource(QUrl.fromLocalFile(result.video));self.file_label.setText(result.video);self.changed()
                    artifact=service.get_job(job['id']).get('artifact')
                    self.log('Recovered job '+job['id']+'. Save the recovered project.'+((' Artifact: '+artifact['path']) if artifact else ''))
                self.job(task,done)
            self.operation_preflight(settings,launch,narration=narration,detector=narration and job['operation']!='voice-preview',vision=vision)
        except Exception as exc:self.error(str(exc))
    def edit_glossary(self):
        self.tabs.setCurrentIndex(2)
    def validate_export_destination(self,p,extension=None,parent=None):
        import tempfile
        target=Path(p).expanduser().resolve()
        if extension and target.suffix.lower()!='.'+extension:
            raise ValueError('Save path extension must match the selected format: .'+extension)
        source=Path(self.project.video).resolve()
        if target==source or (target.exists() and source.exists() and target.samefile(source)):
            raise ValueError('Cannot overwrite original media. Choose another destination.')
        if not target.parent.is_dir():raise ValueError('Choose an existing output folder.')
        for output in (target,Path(str(target)+'.coverage.json')):
            if output.exists():
                if not output.is_file():raise ValueError('Choose a file, not a folder: '+str(output))
                if output==source or (source.exists() and output.samefile(source)):
                    raise ValueError('Cannot overwrite original media. Choose another destination.')
                if QMessageBox.question(parent or self,'Replace existing file',f'Replace {output}?',QMessageBox.Yes|QMessageBox.No|QMessageBox.Cancel,QMessageBox.No)!=QMessageBox.Yes:return False
                with output.open('r+b'):pass
        with tempfile.NamedTemporaryFile(prefix='.describer-write-',dir=target.parent):pass
        return True
    def export_to(self,p,destination_checked=False):
        if self.busy() or not self.project.cues:return
        i=self.table.currentRow()
        if i>=0:
            try:self.project.cues[i]=self.editor_cue()
            except Exception as exc:self.error(str(exc));return
        if not p:return
        if not destination_checked:
            try:
                if not self.validate_export_destination(p):return
            except (OSError,ValueError) as exc:self.error(str(exc));return
        if Path(p).suffix.lower() in ('.mp3','.wav','.mp4'):
            if self.settings.data['voice_engine']=='OpenAI' and QMessageBox.question(self,'OpenAI speech','Send description text to OpenAI for paid speech synthesis?')!=QMessageBox.StandardButton.Yes:return
            project=copy.deepcopy(self.project);settings=copy.deepcopy(self.settings.data);settings['allow_cloud']=True
            self.job(lambda c,l:export_audio(project,p,settings,c,l),lambda _:self.log('Complete narration exported: '+p))
        else:
            try:
                from .engine.exporting import export
                export(self.project,p,self.settings.data,self.cancel,self.log)
                self.log('Exported: '+p)
            except Exception as e:self.error(str(e))
    def reload_presets(self):
        self.preset.clear();self.preset.addItems(list(self.settings.data['presets'].get(self.settings.data['language'],self.settings.data['presets'].get('English',{'Standard':''}))))
    def preset_changed(self,name):self.prompt.setPlainText(self.settings.data['presets'].get(self.settings.data['language'],self.settings.data['presets'].get('English',{})).get(name,''))
    def presets(self):
        action,ok=QInputDialog.getItem(self,'Manage prompt presets','Action',['Add or edit','Delete'],0,False)
        if not ok:return
        if action=='Delete':
            presets=self.settings.data['presets'].setdefault(self.settings.data['language'],{})
            name,ok=QInputDialog.getItem(self,'Delete preset','Preset',list(presets),0,False)
            if ok:
                presets.pop(name,None)
                if not presets:presets['Standard']=''
                try:self.settings.save();self.reload_presets()
                except Exception as e:self.error(str(e))
            return
        name,ok=QInputDialog.getText(self,'Prompt presets','Preset name (existing name to edit)',text=self.preset.currentText())
        if not ok or not name:return
        presets=self.settings.data['presets'].setdefault(self.settings.data['language'],{})
        text,ok=QInputDialog.getMultiLineText(self,'Edit prompt','Editorial instructions (leave empty for standard)',presets.get(name,''))
        if ok:
            presets[name]=text
            try:self.settings.save();self.reload_presets();self.preset.setCurrentText(name)
            except Exception as e:self.error(str(e))
    def edit_settings(self, section=None):
        if self.busy():return
        from .desktop import BlueprintDialog
        d=BlueprintDialog(self);d.setWindowTitle('Settings');d.resize(780,720);outer=QVBoxLayout(d);scroll=QScrollArea();scroll.setWidgetResizable(True);content=QWidget();form=QFormLayout(content);scroll.setWidget(content);outer.addWidget(scroll);fields={}
        for key,label in [('gemini_key','Gemini API key'),('model','Gemini model'),('ollama_url','Ollama server address'),('ollama_key','Ollama server API key (optional)'),('openai_key','OpenAI API key'),('tts_model','OpenAI speech model'),('voice','OpenAI base voice'),('language','Description language'),('update_feed','Update feed (HTTPS URL or local JSON)')]:
            field=QLineEdit(str(self.settings.data[key]));field.setAccessibleName(label)
            if key.endswith('_key'):field.setEchoMode(QLineEdit.EchoMode.Password)
            form.addRow(label,field);fields[key]=field
        for key,label,lo,hi in [('chunk','Seconds per analysis chunk',15,1800),('fps','Frames per second (Gemini)',1,30),('ollama_frame_interval','Ollama seconds between frames (max 8 per request)',1,10),('ollama_timeout','Ollama request timeout (seconds)',30,1800),('duck_db','Background ducking (dB)',-40,0),('speech_rate','Windows voice rate',-10,10),('speech_volume','Speech volume',0,100)]:
            field=QSpinBox();field.setRange(lo,hi);field.setValue(self.settings.data[key]);form.addRow(label,field);fields[key]=field
        engine=QComboBox();engine.addItems(['Windows','Windows 32-bit','Windows OneCore','OpenAI']);engine.setCurrentText(self.settings.data['voice_engine']);form.addRow('Audio export speech engine',engine)
        ui_language=QComboBox();ui_language.addItems(LANGUAGES);ui_language.setCurrentText(self.settings.data['ui_language']);form.addRow('Interface language',ui_language)
        choices={}
        for key,label,items in [('verbosity','Description verbosity',['Short','Standard','Detailed']),('download_quality','YouTube download quality',['Best','360p','480p','720p','1080p']),('playback_output','Playback speech output',['Windows speech','Screen reader']),('logging_level','Diagnostic logging level',['DEBUG','INFO','WARNING','ERROR','CRITICAL'])]:
            combo=QComboBox();combo.addItems(items);combo.setCurrentText(self.settings.data[key]);form.addRow(label,combo);choices[key]=combo
        voice_preset=QComboBox();voice_preset.addItems(['']+list(self.settings.data['voice_presets']));voice_preset.setCurrentText(self.settings.data['voice_preset']);form.addRow('OpenAI voice preset',voice_preset)
        flags={}
        for key,label in [('chunking','Enable video chunking'),('auto_glossary','Recognize characters during analysis'),('silent_upload','Remove audio before uploading video'),('sounds','Notification sounds'),('auto_update_check','Check configured update feed at startup'),('safety_block_none','Request BLOCK_NONE for adjustable Gemini filters (provider core rules still apply)')]:
            flag=QCheckBox(label);flag.setChecked(bool(self.settings.data[key]));form.addRow(flag);flags[key]=flag
        temperature=QDoubleSpinBox();temperature.setRange(0,2);temperature.setSingleStep(.1);temperature.setValue(float(self.settings.data['temperature']));form.addRow('Gemini temperature',temperature)
        interrupt=QCheckBox('Allow new descriptions to interrupt speech');interrupt.setChecked(self.settings.data['interrupt']);form.addRow(interrupt)
        voices=QComboBox();available=self.speech.availableVoices();voices.addItems([v.name() for v in available]);voices.setCurrentText(self.settings.data.get('playback_voice',''));form.addRow('Playback Windows voice',voices)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);form.addRow(buttons)
        from .desktop import organize_settings
        organize_settings(self,d,outer,scroll,content,form,buttons,section)
        if d.exec():
            old=copy.deepcopy(self.settings.data)
            try:
                for key,field in fields.items():self.settings.data[key]=field.value() if isinstance(field,(QSpinBox,QDoubleSpinBox)) else field.text().strip()
                if self.settings.data['voice_engine']!=engine.currentText():self.settings.data['windows_voice']=''
                self.settings.data['voice_engine']=engine.currentText();self.settings.data['interrupt']=interrupt.isChecked()
                self.settings.data.update({key:flag.isChecked() for key,flag in flags.items()})
                self.settings.data.update(ui_language=ui_language.currentText(),voice_preset=voice_preset.currentText(),temperature=temperature.value(),playback_voice=voices.currentText())
                self.settings.data.update({key:combo.currentText() for key,combo in choices.items()})
                self.settings.save();self.playback_speech.settings=self.settings.data;self.speech.setVolume(self.settings.data['speech_volume']/100);apply_language(self,self.settings.data['ui_language'])
                if voices.currentIndex()>=0:self.speech.setVoice(available[voices.currentIndex()])
                self.reload_presets()
                self.model_picker.rows=[];self.model_picker.reload()
            except Exception as e:self.settings.data=old;self.error(str(e))
    def sound(self,name):
        if not self.settings.data.get('sounds',True):return
        from PySide6.QtMultimedia import QSoundEffect
        if not hasattr(self,'notification'):
            self.notification=QSoundEffect(self);self.notification.statusChanged.connect(self.notification_ready)
        from .services import asset_path
        source=QUrl.fromLocalFile(str(asset_path(name+'.wav')))
        if self.notification.source()==source:self.notification.play()
        else:self.notification.setSource(source);self.notification.setVolume(.25)
    def notification_ready(self):
        from PySide6.QtMultimedia import QSoundEffect
        if self.notification.status()==QSoundEffect.Status.Ready:self.notification.play()
    def select_windows_voice(self):
        if self.busy():return
        engine=self.settings.data['voice_engine']
        if engine=='OpenAI':self.error('Select a Windows engine in Settings first.');return
        from .windows_speech import windows_speech
        def done(voices):
            if not voices:self.error('No voices are installed for this engine.');return
            labels=[v['name']+' — '+v['id'] for v in voices]
            choice,ok=QInputDialog.getItem(self,'Windows export voice','Installed voices ('+engine+')',labels,0,False)
            if ok:self.settings.data['windows_voice']=voices[labels.index(choice)]['id'];self.settings.save()
        self.job(lambda c,l:windows_speech(engine,cancel=c,listing=True),done)
    def test_voice(self):
        if self.busy():return
        text,ok=QInputDialog.getText(self,'Test selected export voice','Preview text',text='A person walks into the sunlit room.')
        if not ok or not text:return
        settings=copy.deepcopy(self.settings.data)
        if settings['voice_engine']=='OpenAI' and QMessageBox.question(self,'OpenAI speech','Send preview text to OpenAI for paid synthesis?')!=QMessageBox.StandardButton.Yes:return
        self.preview.stop();self.preview.setSource(QUrl());path=Path(self.preview_tmp.name)/'preview.wav'
        def done(_):self.preview.setSource(QUrl.fromLocalFile(str(path)));self.preview.play();self.log('Voice preview synthesized.')
        self.job(lambda c,l:synthesize(text,path,settings,c),done)
    def manage_voices(self):
        if self.busy():return
        presets=self.settings.data['voice_presets']
        action,ok=QInputDialog.getItem(self,'Manage voice presets','Action',['Add','Edit','Delete','Import original voices.json'],0,False)
        if not ok:return
        if action=='Import original voices.json':
            from .compatibility import read_voice_presets
            path,_=QFileDialog.getOpenFileName(self,'Import voice presets','','JSON (*.json)')
            if not path:return
            try:presets.update(read_voice_presets(path));self.settings.save()
            except Exception as e:self.error(str(e))
            return
        current=''
        if action!='Add':
            if not presets:return
            current,ok=QInputDialog.getItem(self,'Voice preset','Preset',list(presets),0,False)
            if not ok:return
        if action=='Delete':
            if QMessageBox.question(self,'Delete voice preset','Delete '+current+'?')!=QMessageBox.StandardButton.Yes:return
            presets.pop(current)
            if self.settings.data['voice_preset']==current:self.settings.data['voice_preset']=''
            self.settings.save();return
        data=presets.get(current,{'base_voice':'alloy','speed':1,'instructions':''})
        d=QDialog(self);d.setWindowTitle('Voice preset');form=QFormLayout(d)
        name=QLineEdit(current);base=QLineEdit(data['base_voice']);speed=QDoubleSpinBox();speed.setRange(.25,4);speed.setSingleStep(.05);speed.setValue(data['speed']);instructions=QPlainTextEdit(data['instructions'])
        for label,field in [('Name',name),('Base voice',base),('Speed',speed),('Delivery instructions',instructions)]:form.addRow(label,field)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);form.addRow(buttons)
        if d.exec():
            if not name.text().strip() or not base.text().strip():self.error('Name and base voice are required.');return
            if name.text().strip()!=current and name.text().strip() in presets:self.error('That preset name already exists.');return
            if current:presets.pop(current)
            presets[name.text().strip()]={'base_voice':base.text().strip(),'speed':speed.value(),'instructions':instructions.toPlainText()}
            if self.settings.data['voice_preset']==current:self.settings.data['voice_preset']=name.text().strip()
            self.settings.save()
    def import_original(self):
        if self.busy():return
        kind,ok=QInputDialog.getItem(self,'Import original data','Import type',['Generated JSON descriptions','Settings (no API keys)','Prompt presets'],0,False)
        if not ok:return
        path,_=QFileDialog.getOpenFileName(self,'Select original export or settings','','Original data (*.json *.dat2 *.dat);;All files (*)')
        if not path:return
        try:
            if kind=='Prompt presets':
                from .compatibility import read_prompt_presets
                for language,presets in read_prompt_presets(path).items():self.settings.data['presets'].setdefault(language,{}).update(presets)
                self.settings.save();self.reload_presets()
            elif kind.startswith('Settings'):
                from .compatibility import read_original_settings
                data=read_original_settings(path)
                if QMessageBox.question(self,'Import settings','Apply these settings? '+', '.join(sorted(data)))!=QMessageBox.StandardButton.Yes:return
                old=copy.deepcopy(self.settings.data)
                try:self.settings.data.update(data);self.settings.save()
                except Exception:self.settings.data=old;raise
                self.reload_presets();self.log('Imported settings without keys. Source file unchanged.')
            else:
                from .compatibility import import_original_output
                if not self.project.video:raise ValueError('Open the matching video first.')
                project=import_original_output(path,self.project.video,self.project.duration)
                if self.project.cues and QMessageBox.question(self,'Replace descriptions','Replace the current descriptions and glossary?')!=QMessageBox.StandardButton.Yes:return
                self.project.cues=project.cues;self.project.glossary=project.glossary;self.changed()
        except Exception as e:self.error(str(e))
    def check_updates(self):
        if self.busy():return
        feed=self.settings.data.get('update_feed','')
        if not feed:
            if QMessageBox.question(self,'Update source not configured','No update feed is configured, so no version check was performed. Open the official GitHub releases page to review available downloads?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
                from PySide6.QtGui import QDesktopServices
                QDesktopServices.openUrl(QUrl('https://github.com/scottconverse/Describer-Workbench/releases'))
            return
        from .updates import read_feed
        def done(data):
            if not data['newer']:self.log('No newer version in the configured feed.');return
            if QMessageBox.question(self,'Workbench update','Version '+data['version']+' is available. Download and verify a separate portable copy?')!=QMessageBox.StandardButton.Yes:return
            folder=QFileDialog.getExistingDirectory(self,'Stage verified update in')
            # Schedule after the check worker has completed its thread teardown.
            if folder:self.pending_update=(data,folder)
        self.job(lambda c,l:read_feed(feed),done)
    def stage_update_job(self,data,folder):
        from .updates import stage_update
        self.job(lambda c,l:stage_update(data,folder,c,l),self.update_staged)
    def update_staged(self,path):
        self.log('Verified update staged: '+path)
        if not getattr(sys,'frozen',False):self.log('Source mode: launch the verified portable copy manually.');return
        if QMessageBox.question(self,'Update ready','Install this verified update and restart? The current version will be retained in a sibling rollback folder.')!=QMessageBox.StandardButton.Yes:return
        if not self.guard_changes():return
        import os,subprocess
        from .updates import prepare_apply
        from .services import CREATE_NO_WINDOW
        try:
            script,payload,receipt=prepare_apply(path,Path(sys.executable).parent,sys.executable,os.getpid(),self.settings.path.parent/'updates')
            subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script),str(payload)],creationflags=CREATE_NO_WINDOW)
            self.log('Update helper started; receipt: '+str(receipt))
            # The worker is completing; wait for teardown before allowing close.
            QTimer.singleShot(200,self.close_for_update)
        except Exception as e:self.error(str(e))
    def close_for_update(self):
        if self.thread is not None:QTimer.singleShot(100,self.close_for_update)
        else:self.close()
    def help(self):
        from . import __version__
        QMessageBox.information(self,'Describer Workbench '+__version__,
            'Local remediation candidate '+__version__+'. '
            'Open a video, then choose Draft with AI or import SRT/VTT. Select a description to seek and edit it inline. '
            'Start/end accept seconds or HH:MM:SS and change independently. Click the timeline to seek; Ctrl+wheel zooms. Space toggles playback outside text editors when the window receives it. Save with Ctrl+S. '
            'Export MP4, MP3/WAV, SRT/VTT, text or JSON. The shared engine protects measured speech, '
            'caps narration speed at 1.15x, and retains no-fit descriptions as pauses. '
            'Draft checks the selected detector and offers verified setup before inference. File also offers detector installation, Repair narration and Recover interrupted jobs. Edits preserve review evidence; Mark as checked clears review deliberately. Unresolved facts block complete media exports. '
            'File can also start the authenticated developer API/MCP server. Windows speech works offline. '
            'Cloud operations use your own keys and require confirmation. Cancel stops local jobs; an in-flight cloud request may take up to its timeout. '
            'This is an independent reconstruction. Read the maintained user manual at https://describer-workbench.sconverse.chatgpt.site/manual for controls and verification limits.')
    def install_detector(self):
        if self.busy():return
        if QMessageBox.question(self,'Install local speech detector','Download the pinned Google YAMNet speech detector from Hugging Face? Analysis stays local and the checksum is verified.')!=QMessageBox.StandardButton.Yes:return
        from .engine.assets import provision
        target=self.settings.data.get('sound_model') or None
        self.job(lambda c,l:(l('Installing selected detector; cancellation waits at most one network read timeout (10 seconds).'),str(provision(target,c)))[1],lambda path:self.log('Speech detector installed and verified: '+path))
    def start_api(self):
        if self.api_thread and self.api_thread.is_alive():self.log('Developer API is already running.');return
        try:
            import secrets,os,uvicorn
            from .engine import get_service
            from .adapters.http import create_app
            service=get_service();token=secrets.token_urlsafe(32)
            path=service.root/'api-token.txt'
            descriptor=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(descriptor,'w',encoding='utf-8') as out:out.write(token)
            self.api_server=uvicorn.Server(uvicorn.Config(create_app(service,token),host='127.0.0.1',port=8796,log_level='warning'))
            server=self.api_server;self.api_start_error=None;self.api_ready=False
            def run_server():
                try:server.run()
                except BaseException as exc:self.api_start_error=type(exc).__name__
            self.api_thread=threading.Thread(target=run_server,name='describer-api',daemon=True);self.api_thread.start()
            import time
            deadline=time.monotonic()+10
            def check_start():
                if self.api_server is not server:return
                if server.started and self.api_thread.is_alive():
                    self.api_ready=True
                    self.log('Developer API ready: http://127.0.0.1:8796 ; MCP: /mcp/ ; private bearer token: '+str(path));return
                if not self.api_thread.is_alive():
                    self.api_server=None;self.api_thread=None;self.api_ready=False
                    self.error('Developer API did not start. Port 8796 may be in use. Stop the conflicting service yourself or retry after it exits; no other process was stopped.');return
                if time.monotonic()>deadline:
                    server.should_exit=True
                    self.error('Developer API startup timed out. Stop API, then retry after checking port 8796.');return
                QTimer.singleShot(50,check_start)
            QTimer.singleShot(0,check_start)
        except Exception as exc:self.error(str(exc))
    def stop_api(self):
        if self.api_server:self.api_server.should_exit=True
        if self.api_thread:self.api_thread.join(timeout=5)
        if self.api_thread and self.api_thread.is_alive():self.log('Developer API is still stopping; active requests may need to finish.');return False
        self.api_server=None;self.api_thread=None;self.api_ready=False;return True
    def closeEvent(self,event):
        for picker in list(getattr(self,'voice_discoveries',set())):
            if picker.thread is not None and not picker.thread.isRunning():picker.finished()
        pending=[picker for picker in getattr(self,'voice_discoveries',set()) if picker.thread is not None]
        if pending:
            for picker in pending:picker.shutdown()
            self.log('Cancelling voice discovery; close again after it finishes.');event.ignore();return
        if self.thread is not None:
            self.cancel.set();self.log('Cancelling; wait for the current operation to finish before closing.');event.ignore();return
        if not self.guard_changes():event.ignore();return
        if not self.stop_api():event.ignore();return
        self.pause_active=False;self.pause_player.stop();self.narration.stop()
        self.timeline.stop_decoder()
        self.player.stop();self.player.setSource(QUrl());self.playback_speech.stop();self.preview.stop();self.preview.setSource(QUrl());self.preview_tmp.cleanup()
        for handler in self.logger.handlers:handler.close()
        event.accept()


def main():
    app=QApplication(sys.argv);app.setApplicationName('Describer Workbench')
    try:window=Window()
    except Exception as e:
        QMessageBox.critical(None,'Startup failed',f'Could not open Describer Workbench: {e}');return
    window.show()
    try:code=app.exec()
    finally:
        from .engine.service import _services
        for service in list(_services.values()):
            if not service._closed:service.close()
    sys.exit(code)


if __name__=='__main__':main()


