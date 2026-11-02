"""Industry desktop presentation; all media/model work remains in Window services."""
import copy
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QTimer, QProcess
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QFontDatabase, QUndoStack, QUndoCommand, QPixmap, QIcon
from PySide6.QtWidgets import (QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QTabWidget, QScrollArea, QSplitter, QDialog, QDialogButtonBox,
    QPlainTextEdit, QLineEdit, QComboBox, QCheckBox, QListWidget, QRadioButton, QButtonGroup, QProgressBar, QDockWidget,
    QFormLayout, QFileDialog, QApplication, QSlider)
from .project import Cue, seconds, response_json
from .services import asset_path


def clock(value):
    minutes, sec = divmod(max(0, value), 60)
    return f'{int(minutes):02}:{sec:04.1f}'


def button(layout, text, action, primary=False):
    widget = QPushButton(text)
    widget.setAccessibleName(text)
    icon={'Open':'folder-open','Open video':'folder-open','Draft with AI':'sparkles','Export':'download','Settings':'settings','Theme':'moon','Delete':'trash-2','Play / Pause':'play','Add at playhead':'plus'}.get(text)
    if icon:widget.setIcon(QIcon(str(asset_path('icons')/(icon+'.svg'))))
    if primary: widget.setProperty('primary', True)
    widget.clicked.connect(action)
    layout.addWidget(widget)
    return widget


class BlueprintFrame(QFrame):
    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        color = self.palette().windowText().color(); color.setAlphaF(.55)
        p.setPen(QPen(color, 1))
        for x in (6, self.width()-7):
            for y in (6, self.height()-7):
                p.drawLine(x-5, y, x+5, y); p.drawLine(x, y-5, x, y+5)


class Timeline(QWidget):
    """Real cue geometry and seeking, with native focusable cue buttons."""
    def __init__(self, window):
        super().__init__(); self.window = window; self.blocks = []; self.thumbnails=QPixmap();self.source=None;self.decoder=None
        self.setMinimumHeight(220); self.setAccessibleName('Timeline')
    def seconds_at(self, x):
        return max(0, min(self.window.project.duration, (x-96)/max(1,self.width()-106)*self.window.project.duration))
    def mousePressEvent(self, event):
        self.window.seek(round(self.seconds_at(event.position().x())*1000))
    def sync(self):
        source=self.window.project.video
        if self.source!=source:
            self.source=source;self.thumbnails=QPixmap()
            if self.decoder and self.decoder.state()!=QProcess.NotRunning:self.decoder.kill();self.decoder.waitForFinished(1000)
            if Path(source).is_file():
                from .services import tool
                try:
                    self.decoder=QProcess(self);destination=str(Path(self.window.preview_tmp.name)/'timeline.jpg')
                    self.decoder.setProgram(tool('ffmpeg'))
                    self.decoder.setArguments(['-v','error','-y','-skip_frame','nokey','-i',source,'-an','-vf',f'fps={8/max(.1,self.window.project.duration)},scale=160:90,tile=8x1','-frames:v','1',destination])
                    def loaded(code,status):
                        if code==0:self.thumbnails=QPixmap(destination);self.update()
                    self.decoder.finished.connect(loaded);self.decoder.start()
                    QTimer.singleShot(60000,self.stop_decoder)
                except Exception as exc:self.window.log('Timeline thumbnails unavailable: '+str(exc))
        for b in self.blocks: b.deleteLater()
        self.blocks = []
        for i, cue in enumerate(self.window.project.cues):
            b = QPushButton(str(i+1), self)
            b.setAccessibleName(f'Description {i+1}, {clock(cue.start)} to {clock(cue.end)}, {cue.disposition}')
            b.setToolTip(cue.text)
            b.clicked.connect(lambda checked=False, index=i: self.window.choose(index))
            b.setProperty('primary', cue.disposition == 'pause')
            if cue.disposition=='unresolved':b.setStyleSheet('border:1px dashed palette(text);')
            elif cue.speed>1:b.setStyleSheet('background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #5980a6,stop:0.5 #b5c8da,stop:1 #5980a6);')
            elif cue.disposition=='in-gap':b.setStyleSheet('background:rgba(89,128,166,76);border:1px solid #5980a6;')
            self.blocks.append(b); b.show()
        self.position_blocks(); self.update()
    def stop_decoder(self):
        if self.decoder and self.decoder.state()!=QProcess.NotRunning:self.decoder.kill();self.decoder.waitForFinished(1000)
    def position_blocks(self):
        duration = max(.1,self.window.project.duration); width = max(1,self.width()-106)
        for b,c in zip(self.blocks,self.window.project.cues):
            b.setGeometry(round(96+c.start/duration*width),162,max(24,round((c.end-c.start)/duration*width)),38)
    def resizeEvent(self,event):
        self.position_blocks(); super().resizeEvent(event)
    def paintEvent(self,event):
        p=QPainter(self); color=self.palette().windowText().color(); muted=QColor(color);muted.setAlpha(50)
        p.setPen(color); p.drawText(12,20,'TIMELINE')
        p.drawText(120,20,'In gap   /   Sped up   /   Pauses picture   /   Needs review')
        for label,y in [('Picture',85),('Dialogue',137),('Descriptions',185)]:p.drawText(8,y,label)
        p.setPen(muted)
        for y in (32,58,112,156,206):p.drawLine(0,y,self.width(),y)
        p.drawLine(96,32,96,206)
        if not self.thumbnails.isNull():p.drawPixmap(96,59,self.width()-106,52,self.thumbnails)
        duration=max(.1,self.window.project.duration); width=max(1,self.width()-106)
        # Adapt tick density to the available width; hours-long media stays responsive.
        step=max(10,round(duration/max(1,width/80)/10)*10)
        for t in range(0,int(duration)+1,step):
            x=round(96+t/duration*width);p.drawLine(x,32,x,206);p.drawText(x+3,49,clock(t))
        analysis=self.window.project.analysis
        intervals=analysis.get('protected',[]) if isinstance(analysis,dict) else []
        for interval in intervals:
            a,b=interval if isinstance(interval,(list,tuple)) else (interval['start'],interval['end'])
            p.fillRect(QRectF(96+a/duration*width,116,(b-a)/duration*width,34),QColor('#98989b'))
        x=round(96+self.window.player.position()/1000/duration*width)
        p.setPen(QPen(color,1));p.drawLine(x,32,x,206);p.drawRect(x-3,26,6,6)


class CueEdit(QUndoCommand):
    def __init__(self, window, before, after, title):
        super().__init__(title);self.window=window;self.before=before;self.after=after
    def apply(self, data):
        self.window.project.cues=copy.deepcopy(data);self.window.dirty=True
        self.window.refresh();self.window.last_spoken=None
        if not getattr(self.window,'_typing',False) and self.window.project.cues:self.window.choose(min(max(0,self.window.table.currentRow()),len(data)-1))
    def undo(self):self.apply(self.before)
    def redo(self):self.apply(self.after)


class DesktopInterface:
    """Presentation mixin. Window retains ownership of jobs and existing safeguards."""
    def build_interface(self):
        for font in asset_path('fonts').glob('*.ttf'):QFontDatabase.addApplicationFont(str(font))
        QApplication.instance().setFont(QFont('Barlow',11))
        self.resize(1440,900);self.setMinimumSize(960,650)
        self.undo_stack=QUndoStack(self);self._syncing=False;self._selected_cue=None
        self.setAcceptDrops(True)
        self.pages=QStackedWidget();root=QWidget();outer=QVBoxLayout(root);outer.setContentsMargins(20,8,20,8)
        old=self.takeCentralWidget()
        # Reparent the live widgets before disposing of the superseded layout.
        for w in (self.video,self.model_picker,self.start,self.end,self.text,self.preset,self.prompt,
                  self.volume,self.speak_check,self.current,self.log_view,self.cancel_button,self.table,self.slider,self.file_label):w.setParent(root)
        self.table.hide();self.slider.hide();self.model_picker.hide();self.cancel_button.hide();self.file_label.hide();self.preset.hide();self.prompt.hide()
        bar=QHBoxLayout();outer.addLayout(bar)
        brand=QLabel('DESCRIBER WORKBENCH');brand.setObjectName('brand');bar.addWidget(brand)
        self.project_title=QLabel('New project');bar.addWidget(self.project_title);bar.addStretch()
        button(bar,'Open',self.show_start);button(bar,'Import cues',self.import_cues)
        self.model_chip=button(bar,'AI model',self.draft_dialog)
        self.draft_button=button(bar,'Draft with AI',self.draft_dialog)
        self.export_button=button(bar,'Export',self.export,True)
        button(bar,'Theme',self.toggle_theme);button(bar,'Settings',self.edit_settings)
        outer.addWidget(self.pages,1)
        self.start_page=self.make_start();self.pages.addWidget(self.start_page)
        editor=QSplitter();self.pages.addWidget(editor)
        left=QWidget();lv=QVBoxLayout(left);lv.setContentsMargins(0,8,16,0);editor.addWidget(left)
        frame=BlueprintFrame();fv=QVBoxLayout(frame);fv.setContentsMargins(14,14,14,14);fv.addWidget(self.video,1);self.video.show()
        self.pause_badge=QLabel('PICTURE PAUSED FOR DESCRIPTION');self.pause_badge.setObjectName('caption');fv.addWidget(self.pause_badge);self.pause_badge.hide()
        self.current.setObjectName('caption');fv.addWidget(self.current);lv.addWidget(frame,1)
        transport=QHBoxLayout();lv.addLayout(transport)
        button(transport,'−10 s',lambda:self.seek(self.player.position()-10000))
        button(transport,'Play / Pause',self.toggle,True);button(transport,'+10 s',lambda:self.seek(self.player.position()+10000))
        self.clock=QLabel('00:00.0 / 00:00.0');transport.addWidget(self.clock);transport.addStretch();transport.addWidget(self.speak_check)
        transport.addWidget(QLabel('Video'));transport.addWidget(self.volume)
        self.speech_volume=QSlider(Qt.Horizontal);self.speech_volume.setRange(0,100);self.speech_volume.setValue(self.settings.data['speech_volume']);self.speech_volume.setMaximumWidth(90);self.speech_volume.setAccessibleName('Speech volume')
        self.speech_volume.valueChanged.connect(self.change_speech_volume);transport.addWidget(QLabel('Speech'));transport.addWidget(self.speech_volume)
        self.timeline=Timeline(self);lv.addWidget(self.timeline)
        self.tabs=QTabWidget();editor.addWidget(self.tabs);editor.setSizes([950,440]);self.tabs.setMinimumWidth(440)
        descriptions=QWidget();dv=QVBoxLayout(descriptions);self.tabs.addTab(descriptions,'Descriptions · 0')
        self.job_card=BlueprintFrame();jv=QVBoxLayout(self.job_card);self.job_label=QLabel('Working');jv.addWidget(self.job_label)
        self.job_progress=QProgressBar();self.job_progress.setRange(0,0);jv.addWidget(self.job_progress)
        self.job_note=QLabel('Waiting for engine events.');self.job_note.setWordWrap(True);jv.addWidget(self.job_note)
        button(jv,'Cancel',lambda:self.cancel.set());dv.addWidget(self.job_card);self.job_card.hide()
        filters=QHBoxLayout();dv.addLayout(filters);self.cue_filter=QComboBox();self.cue_filter.addItems(['All','Needs review','Pauses']);self.cue_filter.currentIndexChanged.connect(self.render_cues);filters.addWidget(self.cue_filter)
        button(filters,'Add at playhead',self.add_at_playhead)
        self.cue_list=QListWidget();self.cue_list.setWordWrap(True);self.cue_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.cue_list.setAccessibleName('Descriptions');dv.addWidget(self.cue_list,1);self.cue_list.currentRowChanged.connect(self.list_selected);self.cue_list.itemClicked.connect(lambda item:self.inline.setVisible(not self.inline.isVisible()) if self.cue_list.row(item)==getattr(self,'_last_clicked',-1) else setattr(self,'_last_clicked',self.cue_list.row(item)))
        self.inline=QWidget();iv=QVBoxLayout(self.inline);iv.setContentsMargins(0,0,0,0);inline_scroll=QScrollArea();inline_scroll.setWidgetResizable(True);inline_scroll.setWidget(self.inline);inline_scroll.setMinimumHeight(280);dv.addWidget(inline_scroll)
        times=QHBoxLayout();iv.addLayout(times)
        for name,field in [('Start',self.start),('End',self.end)]:
            field.setMaximumWidth(75);times.addWidget(QLabel(name));button(times,'−',lambda checked=False,f=field:self.nudge(f,-.1));times.addWidget(field);button(times,'+',lambda checked=False,f=field:self.nudge(f,.1))
        points=QHBoxLayout();iv.addLayout(points)
        button(points,'Start at playhead',lambda:self.start.setText(str(self.player.position()/1000)))
        button(points,'End at playhead',lambda:self.end.setText(str(self.player.position()/1000)))
        iv.addWidget(self.text);self.fit_label=QLabel();iv.addWidget(self.fit_label);self.fit_bar=QProgressBar();self.fit_bar.setRange(0,200);iv.addWidget(self.fit_bar)
        self.review_note=QLabel();self.review_note.setWordWrap(True);iv.addWidget(self.review_note)
        actions=QHBoxLayout();iv.addLayout(actions);button(actions,'Mark as checked',self.mark_checked);button(actions,'Delete',self.delete_cue)
        contextual=QHBoxLayout();iv.addLayout(contextual);button(contextual,'Preview in context',self.preview_context);button(contextual,'Ask about scene',lambda:self.tabs.setCurrentIndex(1))
        iv.addWidget(QLabel('Changes apply as you type. Ctrl+Z undoes.'));self.inline.hide()
        self.empty=QWidget();ev=QVBoxLayout(self.empty);ev.addWidget(QLabel('NO DESCRIPTIONS YET'))
        button(ev,'Draft with AI',self.draft_dialog,True);button(ev,'Import SRT / VTT',self.import_cues);button(ev,'Add at playhead',self.add_at_playhead);dv.addWidget(self.empty)
        self.make_scene();self.make_glossary()
        self.state_label=QLabel();outer.addWidget(self.state_label)
        self.toast=QLabel();self.toast.setWordWrap(True);outer.addWidget(self.toast);self.toast.hide()
        dock=QDockWidget('Log',self);dock.setWidget(self.log_view);self.addDockWidget(Qt.BottomDockWidgetArea,dock);dock.hide()
        self.menuBar().addMenu('View').addAction(dock.toggleViewAction())
        undo=self.undo_stack.createUndoAction(self,'Undo');undo.setShortcut('Ctrl+Z');self.addAction(undo)
        redo=self.undo_stack.createRedoAction(self,'Redo');redo.setShortcut('Ctrl+Shift+Z');self.addAction(redo)
        self.setCentralWidget(root);old.deleteLater()
        self.player.positionChanged.connect(self.presentation_position)
        self.player.playbackStateChanged.connect(lambda _:self.pause_badge.setVisible(self.pause_active))
        self.ui_timer=QTimer(self);self.ui_timer.timeout.connect(self.update_status);self.ui_timer.start(400)
        self.apply_theme();self.refresh()
    def make_start(self):
        page=QWidget();layout=QHBoxLayout(page);left=QVBoxLayout();layout.addLayout(left,2)
        left.addStretch();left.addWidget(QLabel('NEW PROJECT'));heading=QLabel('START WITH A VIDEO.');heading.setObjectName('hero');left.addWidget(heading)
        lead=QLabel('Describe what matters on screen. Draft locally or with your own cloud key, then edit and export.');lead.setWordWrap(True);left.addWidget(lead)
        for title,fn in [('Open video   Ctrl+O',self.open_video),('From URL   Ctrl+U',self.open_url),('Open project   Ctrl+Shift+O',self.load_project)]:
            frame=BlueprintFrame();fl=QVBoxLayout(frame);button(fl,title,fn);left.addWidget(frame)
        drop=QLabel('Drop a video or .adproject here');drop.setObjectName('drop');drop.setMinimumHeight(90);left.addWidget(drop);left.addStretch()
        from . import __version__
        foot=QHBoxLayout();left.addLayout(foot);foot.addWidget(QLabel('v'+__version__));button(foot,'Manual and shortcuts',self.help)
        right=QVBoxLayout();layout.addLayout(right,1);right.addWidget(QLabel('RECENT PROJECTS'))
        self.recents=QListWidget();right.addWidget(self.recents);self.recents.itemActivated.connect(lambda item:self.open_recent(item.data(Qt.UserRole)))
        right.addWidget(QLabel('SETUP CHECKLIST'))
        self.setup_checks={}
        for title,section in [('Speech detector','Updates'),('Ollama','Keys & privacy'),('Windows voices','Speech & playback'),('Gemini key','Keys & privacy')]:
            line=QHBoxLayout();right.addLayout(line);check=QCheckBox(title);check.setAttribute(Qt.WA_TransparentForMouseEvents);check.setFocusPolicy(Qt.NoFocus);line.addWidget(check);self.setup_checks[title]=check;button(line,'Set up',lambda checked=False,s=section:self.edit_settings(s))
        right.addStretch();return page
    def show_start(self):
        if not self.busy():self.pages.setCurrentIndex(0)
    def toggle_theme(self):
        self.settings.data['ui_theme']='dark' if self.settings.data.get('ui_theme','light')=='light' else 'light';self.settings.save();self.apply_theme()
    def apply_theme(self):
        dark=self.settings.data.get('ui_theme')=='dark';bg='#1d1f20' if dark else '#f2f2f3';fg='#f2f2f3' if dark else '#1d1f20';surface='#2b2b2d' if dark else '#e9e9ea';border='#555558' if dark else '#ccccce'
        self.setStyleSheet(f'''QWidget {{background:{bg};color:{fg};font-family:Barlow;font-size:14px;}}
QLabel {{border:0;}} QFrame, QDialog {{border-radius:0;}} QPushButton,QLineEdit,QComboBox,QPlainTextEdit,QListWidget {{border:1px solid {border};padding:7px;selection-background-color:#5980a6;}}
QPushButton:hover {{background:{surface};border-color:#5980a6;}} QPushButton:focus,QLineEdit:focus,QPlainTextEdit:focus {{border:2px solid #5980a6;}}
QPushButton[primary="true"] {{background:#5980a6;color:#10171e;border-color:#5980a6;}} QPushButton:disabled {{color:#98989b;}}
QTabBar::tab {{padding:12px;border-bottom:1px solid {border};}} QTabBar::tab:selected {{border-bottom:2px solid #5980a6;}}
QListWidget::item {{padding:12px;border-bottom:1px solid {border};}} QListWidget::item:selected {{background:#5980a6;color:#10171e;}}
QProgressBar {{max-height:6px;border:0;background:{surface};}} QProgressBar::chunk {{background:#5980a6;}}
QLabel#brand {{font-family:'Barlow Condensed';font-size:17px;}} QLabel#hero {{font-family:'Barlow Condensed';font-size:56px;}}
QLabel#caption {{background:#1d2d3d;color:#f2f2f3;padding:10px;}} QLabel#drop {{border:1px dashed {border};padding:20px;}}
''')
    def update_status(self):
        if not hasattr(self,'state_label'):return
        provider=self.settings.data['analysis_provider'];model=self.settings.data['ollama_model' if provider=='Ollama' else 'model']
        self.model_chip.setText(provider+' · '+(model or 'Choose model'))
        self.project_title.setText((Path(self.project_path or self.project.video).stem if self.project.video else 'New project')+'  · '+('Unsaved changes (Ctrl+S)' if self.dirty else 'Saved'))
        running=self.thread is not None;self.inline.setEnabled(not running);self.glossary_list.parentWidget().setEnabled(not running);self.draft_button.setEnabled(not running and bool(self.project.video));self.export_button.setEnabled(not running and bool(self.project.cues));self.job_card.setVisible(running)
        counts={k:sum(c.disposition==k for c in self.project.cues) for k in ('in-gap','pause','unresolved')}
        from .engine.assets import default_root
        detector=Path(self.settings.data.get('sound_model') or default_root()/'assets'/'yamnet.onnx').is_file()
        for key,value in [('Speech detector',detector),('Ollama',bool(self.settings.data.get('ollama_model'))),('Windows voices',bool(self.speech.availableVoices())),('Gemini key',bool(self.settings.data.get('gemini_key')))]:self.setup_checks[key].setChecked(value)
        self.setup_checks['Ollama'].setToolTip('Exact model configured; use Test connection to verify the server.')
        self.state_label.setText(f"Speech detector: {'installed' if detector else 'not installed'}  |  {'Working' if running else 'Engine idle'}     In gap {counts['in-gap']} · Pauses {counts['pause']} · Review {counts['unresolved']}     Voice: {self.settings.data.get('playback_voice') or 'System default'}     API: {'running' if self.api_thread and self.api_thread.is_alive() else 'off'}")
    def presentation_position(self,value):
        self.clock.setText(clock(value/1000)+' / '+clock(self.project.duration));self.timeline.update();self.pause_badge.setVisible(self.pause_active)
    def render_cues(self):
        if not hasattr(self,'cue_list'):return
        self.cue_list.blockSignals(True);self.cue_list.clear();self.visible_indices=[]
        self.cue_filter.setItemText(1,f"Needs review · {sum(c.disposition=='unresolved' for c in self.project.cues)}");self.cue_filter.setItemText(2,f"Pauses · {sum(c.disposition=='pause' for c in self.project.cues)}")
        for i,c in enumerate(self.project.cues):
            if self.cue_filter.currentIndex()==1 and c.disposition!='unresolved':continue
            if self.cue_filter.currentIndex()==2 and c.disposition!='pause':continue
            tag=f'{c.speed:.2f}×' if c.speed>1 else c.disposition
            self.cue_list.addItem(f'{i+1}   {clock(c.start)} — {clock(c.end)}\n{c.text}\n{tag}');self.visible_indices.append(i)
        self.cue_list.blockSignals(False);self.tabs.setTabText(0,f'Descriptions · {len(self.project.cues)}');self.empty.setVisible(not self.project.cues)
        self.timeline.sync();self.update_status()
    def list_selected(self,row):
        if 0<=row<len(self.visible_indices):self.choose(self.visible_indices[row])
    def choose(self,index):
        if not 0<=index<len(self.project.cues):return
        self._selected_cue=self.project.cues[index];self.table.setCurrentCell(index,0);self.select_cue();self.inline.show()
        if index in self.visible_indices:
            self.cue_list.blockSignals(True);self.cue_list.setCurrentRow(self.visible_indices.index(index));self.cue_list.blockSignals(False)
        self.update_fit()
    def update_fit(self):
        try:
            slot=seconds(self.end.text())-seconds(self.start.text());speech=len(self.text.toPlainText().split())/2.6
            cue=self._selected_cue
            if cue and cue.text==self.text.toPlainText() and cue.speech_seconds:speech=cue.speech_seconds
            ratio=speech/max(.1,slot);verdict='Fits at normal speed' if ratio<=1 else f'Speeds up to {ratio:.2f}×' if ratio<=1.15 else 'Too long: picture will pause'
            self.fit_label.setText(f'≈{speech:.1f} s of speech in a {slot:.1f} s slot\n{verdict}');self.fit_bar.setValue(min(200,round(ratio*100)));self.review_note.setText(cue.uncertainty if cue else '')
        except ValueError:pass
    def commit_cues(self,cues,title):
        cues.sort(key=lambda c:c.start);self.undo_stack.push(CueEdit(self,copy.deepcopy(self.project.cues),copy.deepcopy(cues),title))
    def add_at_playhead(self):
        if self.busy() or not self.project.video:return
        start=self.player.position()/1000;end=min(self.project.duration,start+3)
        if end<=start:return
        cue=Cue(start,end,'New description',disposition='unresolved',uncertainty='New description: verify visual facts.').validate(self.project.duration)
        self.commit_cues([*self.project.cues,cue],'Add description');self.choose(next(i for i,c in enumerate(self.project.cues) if c==cue))
    def nudge(self,field,delta):
        try:field.setText(str(round(max(0,seconds(field.text())+delta),1)))
        except ValueError:pass
    def mark_checked(self):
        i=self.table.currentRow()
        if self.busy() or i<0:return
        cues=copy.deepcopy(self.project.cues);cues[i].uncertainty='';cues[i].disposition='unplanned';self.commit_cues(cues,'Mark checked');self.choose(i)
    def preview_context(self):
        try:self.seek(round(max(0,seconds(self.start.text())-2)*1000));self.player.play()
        except ValueError:pass
    def change_speech_volume(self,value):
        self.settings.data['speech_volume']=value;self.speech.setVolume(value/100);self.settings.save()
    def make_scene(self):
        scene=QWidget();sv=QVBoxLayout(scene);self.tabs.addTab(scene,'Scene');modes=QTabWidget();sv.addWidget(modes)
        ask=QWidget();av=QVBoxLayout(ask);modes.addTab(ask,'Ask');self.scene_context=QComboBox();self.scene_context.addItems(['±2.5 s','±5 s','±10 s']);av.addWidget(self.scene_context)
        self.conversation=QPlainTextEdit();self.conversation.setReadOnly(True);self.conversation.setAccessibleName('Scene conversation');av.addWidget(self.conversation)
        self.question=QLineEdit();self.question.setAccessibleName('Question about scene');av.addWidget(self.question);button(av,'Ask',self.ask,True)
        self.add_answer_button=button(av,'Add as description',self.insert_answer);self.add_answer_button.setEnabled(False)
        self.scene_note=QLabel('Uses the selected model; cloud/remote requests require confirmation.');self.scene_note.setWordWrap(True);av.addWidget(self.scene_note)
        explore=QWidget();xv=QVBoxLayout(explore);modes.addTab(explore,'Explore layout');button(xv,'Observe current scene',self.explore)
        self.explore_host=QVBoxLayout();xv.addLayout(self.explore_host,1)
    def ask(self):
        question=self.question.text().strip()
        if not question:return
        position=self.player.position()/1000
        import json
        instruction=f'Return JSON {{"answer":"your answer"}}. Answer in {self.settings.data["language"]}. Question: {question}. Prior conversation: {json.dumps(self.history[-6:])}. Character glossary: {self.project.glossary}'
        def done(text):
            answer=response_json(text)['answer']
            if not isinstance(answer,str) or not answer.strip():raise ValueError('No scene answer was returned.')
            self.history.append({'question':question,'answer':answer});self.answer=(answer,position)
            self.conversation.setPlainText('\n\n'.join('Q: '+x['question']+'\nA: '+x['answer'] for x in self.history));self.add_answer_button.setEnabled(True)
        self.scene_request(instruction,done,[5,10,20][self.scene_context.currentIndex()])
    def insert_answer(self):
        if hasattr(self,'answer'):self.add_scene_answer(*self.answer,self.add_answer_button)
    def make_glossary(self):
        page=QWidget();v=QVBoxLayout(page);self.tabs.addTab(page,'Glossary');self.glossary_list=QVBoxLayout();v.addLayout(self.glossary_list);v.addStretch();button(v,'Add character',lambda:self.glossary_card('',''))
    def glossary_card(self,name,description):
        card=BlueprintFrame();v=QVBoxLayout(card);n=QLineEdit(name);n.setPlaceholderText('Character name');n.setAccessibleName('Character name');d=QPlainTextEdit(description);d.setPlaceholderText('Visible identifying details');d.setMaximumHeight(90);d.setAccessibleName('Character description');v.addWidget(n);v.addWidget(d);self.glossary_list.addWidget(card)
        def save():
            if self._syncing or self.busy():return
            self.project.glossary='\n'.join(f'{a.text()}: {b.toPlainText()}' for a,b in self.glossary_fields);self._glossary_snapshot=self.project.glossary;self.dirty=True
        self.glossary_fields.append((n,d));n.textEdited.connect(save);d.textChanged.connect(save)
    def sync_glossary(self):
        if getattr(self,'_glossary_snapshot',None)==self.project.glossary:return
        self._glossary_snapshot=self.project.glossary
        self._syncing=True
        while self.glossary_list.count():self.glossary_list.takeAt(0).widget().deleteLater()
        self.glossary_fields=[]
        for line in self.project.glossary.splitlines():
            name,sep,description=line.partition(':');self.glossary_card(name,description if sep else '')
        self._syncing=False
    def remember_project(self):
        if not self.project_path:return
        recent=self.settings.data.get('recent_projects',[]);path=str(Path(self.project_path).resolve());self.settings.data['recent_projects']=[path]+[p for p in recent if p!=path][:9];self.settings.save()
    def open_recent(self,path):
        if not path or self.busy() or not self.guard_changes():return
        # Reuse the existing project loader, without replacing the global dialog function.
        self._recent_path=path;self.load_project()
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls() and all(u.isLocalFile() for u in event.mimeData().urls()):event.acceptProposedAction()
    def dropEvent(self,event):
        if self.busy() or not self.guard_changes():return
        path=event.mimeData().urls()[0].toLocalFile()
        try:
            if Path(path).suffix.lower()=='.adproject':self._recent_path=path;self.load_project()
            else:self.set_video(path)
        except Exception as exc:self.error(str(exc))
    def keyPressEvent(self,event):
        if event.key()==Qt.Key_Space and not isinstance(QApplication.focusWidget(),(QLineEdit,QPlainTextEdit)):
            self.toggle();event.accept();return
        super().keyPressEvent(event)
    def notify(self,text):
        self.toast.setText(text);self.toast.show();QTimer.singleShot(9000,self.toast.hide)
    def draft_dialog(self):
        if self.busy() or not self.project.video:return
        d=QDialog(self);d.setWindowTitle('DRAFT WITH AI');d.resize(720,600);v=QVBoxLayout(d)
        v.addWidget(QLabel('1 · PROVIDER'))
        providers=QHBoxLayout();v.addLayout(providers);provider_group=QButtonGroup(d)
        for provider,label in [('Ollama','Ollama · LOCAL / CLOUD\nSampled frames, no audio.'),('Gemini','Google Gemini · CLOUD\nUploads video using your key. Can hear audio.')]:
            card=BlueprintFrame();cv=QVBoxLayout(card);choice=QRadioButton(label);choice.setChecked(self.model_picker.provider.currentText()==provider);provider_group.addButton(choice);cv.addWidget(choice);providers.addWidget(card)
            choice.toggled.connect(lambda checked,p=provider:self.model_picker.provider.setCurrentText(p) if checked else None)
        v.addWidget(QLabel('2 · EXACT MODEL'))
        model_list=QListWidget();model_list.setAccessibleName('Discovered exact models');v.addWidget(model_list)
        def sync_models(*args):
            model_list.blockSignals(True);model_list.clear()
            for i in range(self.model_picker.model.count()):model_list.addItem(self.model_picker.model.itemText(i))
            if not model_list.count():model_list.addItem(self.model_picker.model.currentText())
            model_list.setCurrentRow(max(0,self.model_picker.model.currentIndex()));model_list.blockSignals(False)
        sync_models();model_list.currentRowChanged.connect(lambda i:self.model_picker.model.setCurrentIndex(i))
        exact=QLineEdit(self.model_picker.model.currentData() or self.model_picker.model.currentText());exact.setAccessibleName('Exact model tag');v.addWidget(exact)
        def set_exact():self.model_picker.store_model(exact.text().strip()) if exact.text().strip() else None
        exact.editingFinished.connect(set_exact)
        model_list.currentRowChanged.connect(lambda i:exact.setText(self.model_picker.model.itemData(i) or self.model_picker.model.currentText()))
        links=QHBoxLayout();v.addLayout(links);button(links,'Refresh models',self.model_picker.refresh);button(links,'Test connection',self.model_picker.test)
        status=QLabel(self.model_picker.help.text());status.setWordWrap(True);v.addWidget(status)
        timer=QTimer(d);timer.timeout.connect(lambda:status.setText(self.model_picker.help.text()));timer.start(300)
        self.model_picker.model.model().rowsInserted.connect(sync_models)
        self.model_picker.provider.currentTextChanged.connect(sync_models)
        v.addWidget(QLabel('3 · RANGE'))
        scope=QComboBox();scope.addItems([f'Whole video · {clock(self.project.duration)}',f'Next 20 s from {clock(self.player.position()/1000)}',f'Next 60 s from {clock(self.player.position()/1000)}']);scope.setCurrentIndex(self.model_picker.scope.currentIndex());v.addWidget(scope)
        v.addWidget(QLabel('Request count depends on range, frame interval and detected visual events.'))
        v.addWidget(QLabel('EDITORIAL INSTRUCTIONS'));v.addWidget(self.preset);v.addWidget(self.prompt);self.preset.show();self.prompt.show()
        verbosity=QComboBox();verbosity.addItems(['Short','Standard','Detailed']);verbosity.setCurrentText(self.settings.data['verbosity']);v.addWidget(verbosity)
        glossary=QCheckBox('Recognize characters and update the glossary');glossary.setChecked(self.settings.data['auto_glossary']);v.addWidget(glossary)
        note=QLabel();note.setWordWrap(True);v.addWidget(note)
        def update_note():note.setText(('Sampled frames, no audio, go to the selected Ollama server. Remote/cloud confirmation remains required.' if self.model_picker.provider.currentText()=='Ollama' else 'Uploads video to Google with your key; may include audio and incur charges.')+f' Range analysis replaces the {len(self.project.cues)} current descriptions.')
        update_note();self.model_picker.provider.currentTextChanged.connect(update_note)
        actions=QDialogButtonBox(QDialogButtonBox.Cancel);actions.addButton('Start draft',QDialogButtonBox.AcceptRole);actions.accepted.connect(d.accept);actions.rejected.connect(d.reject);v.addWidget(actions)
        accepted=d.exec();timer.stop();self.model_picker.provider.currentTextChanged.disconnect(update_note);self.model_picker.provider.currentTextChanged.disconnect(sync_models);self.model_picker.model.model().rowsInserted.disconnect(sync_models)
        for widget in (self.model_picker,self.preset,self.prompt):widget.setParent(self.centralWidget());widget.hide()
        if accepted:
            set_exact();self.model_picker.scope.setCurrentIndex(scope.currentIndex())
            self.settings.data.update(verbosity=verbosity.currentText(),auto_glossary=glossary.isChecked());self.settings.save()
            self.job_label.setText('Drafting descriptions');self.analyze()
    def export(self):
        if self.busy() or not self.project.cues:return
        d=QDialog(self);d.setWindowTitle('EXPORT');d.resize(820,460);v=QVBoxLayout(d);row=QHBoxLayout();v.addLayout(row)
        formats=QListWidget();formats.addItems(['Described video (MP4)','Narrated audio (MP3)','Narrated audio (WAV)','Subtitles (SRT)','Subtitles (VTT)','Script (TXT)','Project data (JSON)']);row.addWidget(formats)
        right=QVBoxLayout();row.addLayout(right);counts={k:sum(c.disposition==k for c in self.project.cues) for k in ('in-gap','pause','unresolved')};right.addWidget(QLabel('COVERAGE\n'+'\n'.join(f'{k}: {n}' for k,n in counts.items())))
        warning=QLabel('Unresolved visual facts block media exports.');warning.setWordWrap(True);right.addWidget(warning)
        review=button(right,'Review now',lambda:(d.reject(),self.tabs.setCurrentIndex(0),self.cue_filter.setCurrentIndex(1),self.choose(next(i for i,c in enumerate(self.project.cues) if c.disposition=='unresolved'))))
        voice=QComboBox();voice.addItems(['Windows','Windows 32-bit','Windows OneCore','OpenAI']);voice.setCurrentText(self.settings.data['voice_engine']);right.addWidget(voice)
        button(right,'Select installed export voice',self.select_windows_voice)
        path=QLineEdit();path.setAccessibleName('Export save path');right.addWidget(path)
        extensions=['mp4','mp3','wav','srt','vtt','txt','json']
        def browse():
            ext=extensions[formats.currentRow()];p,_=QFileDialog.getSaveFileName(d,'Save to','',f'{ext.upper()} (*.{ext})')
            if p:path.setText(p if Path(p).suffix else p+'.'+ext)
        button(right,'Save to…',browse);right.addStretch()
        v.addWidget(QLabel('Narration speed stays at or below 1.15×. Media exports include a coverage sidecar.'))
        actions=QDialogButtonBox(QDialogButtonBox.Cancel);go=actions.addButton('Export',QDialogButtonBox.AcceptRole);v.addWidget(actions);actions.accepted.connect(d.accept);actions.rejected.connect(d.reject)
        def state():
            media=formats.currentRow()<3;blocked=media and bool(counts['unresolved']);warning.setVisible(blocked);review.setVisible(blocked);voice.setVisible(media);go.setEnabled(bool(path.text()) and not blocked)
        formats.currentRowChanged.connect(lambda _:state());path.textChanged.connect(state);formats.setCurrentRow(0);state()
        if d.exec():
            ext=extensions[formats.currentRow()]
            if Path(path.text()).suffix.lower()!='.'+ext:self.error('Save path extension must match the selected format.');return
            self.settings.data['voice_engine']=voice.currentText();self.settings.save();self.job_label.setText('Exporting descriptions');self.export_to(path.text())


def organize_settings(window,dialog,outer,scroll,content,form,buttons,section=None):
    """Move existing validated fields into accessible categories without changing keys."""
    from PySide6.QtWidgets import QStackedWidget
    groups=['Analysis','Speech & playback','Export voice','Keys & privacy','Interface','Developer API','Updates']
    rows={name:[] for name in groups}
    # Take rows without deleting their widgets.
    while form.rowCount():
        result=form.takeRow(0)
        label=result.labelItem.widget() if result.labelItem else None
        field=result.fieldItem.widget() if result.fieldItem else None
        if field is buttons:continue
        text=label.text() if label else field.text() if isinstance(field,QCheckBox) else ''
        lower=text.lower()
        target='Analysis'
        if any(k in lower for k in ('api key','server address')):target='Keys & privacy'
        elif any(k in lower for k in ('update','feed')):target='Updates'
        elif any(k in lower for k in ('export','openai','speech model')):target='Export voice'
        elif any(k in lower for k in ('playback','volume','ducking','interrupt','windows voice')):target='Speech & playback'
        elif any(k in lower for k in ('interface','youtube','logging','notification')):target='Interface'
        rows[target].append((label,field))
    outer.removeWidget(scroll);scroll.hide();dialog.resize(900,620)
    body=QHBoxLayout();outer.addLayout(body,1);nav=QListWidget();nav.addItems(groups);nav.setMaximumWidth(220);nav.setAccessibleName('Settings sections');body.addWidget(nav)
    stack=QStackedWidget();body.addWidget(stack,1)
    for group in groups:
        pane=QWidget();f=QFormLayout(pane)
        for label,field in rows[group]:
            if label:f.addRow(label,field)
            elif field:f.addRow(field)
        if group=='Keys & privacy':f.addRow(QLabel('API keys are protected with Windows DPAPI. Cloud use requires confirmation.'))
        if group=='Export voice':
            controls=QHBoxLayout();f.addRow(controls);button(controls,'Test voice',window.test_voice);button(controls,'Manage voice presets',window.manage_voices);button(controls,'Select Windows voice',window.select_windows_voice)
        if group=='Updates':
            controls=QHBoxLayout();f.addRow(controls);button(controls,'Check now',window.check_updates);button(controls,'Install speech detector',window.install_detector)
        if group=='Developer API':
            f.addRow(QLabel('Authenticated localhost API · http://127.0.0.1:8796\nMCP · http://127.0.0.1:8796/mcp/\nToken · engine workspace / api-token.txt'))
            controls=QHBoxLayout();f.addRow(controls);button(controls,'Start',window.start_api);button(controls,'Stop',window.stop_api)
        area=QScrollArea();area.setWidgetResizable(True);area.setWidget(pane);stack.addWidget(area)
    nav.currentRowChanged.connect(stack.setCurrentIndex);nav.setCurrentRow(groups.index(section) if section in groups else 0)
    outer.addWidget(buttons);buttons.button(QDialogButtonBox.Ok).setText('Save')


class LayoutGrid(QWidget):
    def __init__(self,explorer):
        super().__init__();self.explorer=explorer;self.setMinimumHeight(220);self.setFocusPolicy(Qt.StrongFocus);self.setAccessibleName('Scene layout grid: arrows move, Enter nearest object, D speaks layout')
    def paintEvent(self,event):
        p=QPainter(self);color=self.palette().windowText().color();line=QColor(color);line.setAlpha(40);p.setPen(line)
        for i in range(11):
            x=round(i*(self.width()-1)/10);y=round(i*(self.height()-1)/10);p.drawLine(x,0,x,self.height());p.drawLine(0,y,self.width(),y)
        p.setPen(QColor('#5980a6'))
        for o in self.explorer.data.get('objects',[]):
            x=float(o.get('x',5))/10*(self.width()-1);y=float(o.get('y',5))/10*(self.height()-1)
            p.fillRect(QRectF(x-4,y-4,8,8),QColor('#5980a6'));p.drawText(QRectF(x+8,y-16,150,36),str(o.get('name','Object')))
        p.setPen(color);p.drawRect(QRectF(self.explorer.x/10*(self.width()-1)-13,self.explorer.y/10*(self.height()-1)-13,26,26))
    def keyPressEvent(self,event):self.explorer.keyPressEvent(event);self.update()
    def mousePressEvent(self,event):
        objects=self.explorer.data.get('objects',[])
        if not objects:return
        x=event.position().x()/self.width()*10;y=event.position().y()/self.height()*10
        o=min(objects,key=lambda o:(float(o.get('x',5))-x)**2+(float(o.get('y',5))-y)**2)
        self.explorer.x=float(o.get('x',5));self.explorer.y=float(o.get('y',5));self.explorer.describe(str(o.get('name','Object'))+': '+str(o.get('description','')));self.update();self.setFocus()
