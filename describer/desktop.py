"""Industry desktop presentation; all media/model work remains in Window services."""
import copy
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QTimer, QProcess, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QFontDatabase, QUndoStack, QUndoCommand, QPixmap, QIcon
from PySide6.QtWidgets import (QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QTabWidget, QScrollArea, QSplitter, QDialog, QDialogButtonBox,
    QPlainTextEdit, QLineEdit, QComboBox, QCheckBox, QListWidget, QRadioButton, QButtonGroup, QProgressBar, QDockWidget,
    QFormLayout, QFileDialog, QApplication, QSlider, QSizePolicy, QScrollBar, QListWidgetItem, QStyledItemDelegate, QStyle)
from .project import Cue, seconds, response_json
from .services import asset_path


def clock(value):
    minutes, sec = divmod(max(0, value), 60)
    return f'{int(minutes):02}:{sec:04.1f}'


def button(layout, text, action, primary=False, role='secondary', icon_only=False):
    widget = QPushButton('' if icon_only else text)
    widget.setAccessibleName(text);widget.setToolTip(text)
    icon={'Open':'folder-open','Open video':'folder-open','From URL':'download','Open project':'folder-open','Draft with AI':'sparkles','Export':'download','Settings':'settings','Theme':'moon','Delete':'trash-2','Play / Pause':'play','Add at playhead':'plus'}.get(text)
    if icon:widget.setProperty('iconName',icon);widget.setIcon(QIcon(str(asset_path('icons')/(icon+'.svg'))))
    widget.setProperty('role','primary' if primary else role)
    widget.setSizePolicy(QSizePolicy.Maximum,QSizePolicy.Fixed)
    if icon_only:widget.setFixedSize(34,34)
    widget.clicked.connect(action)
    layout.addWidget(widget)
    return widget


def section(text):
    label=QLabel(text);label.setProperty('section',True)
    font=QFont('Barlow',10);font.setWeight(QFont.DemiBold);font.setLetterSpacing(QFont.PercentageSpacing,108);label.setFont(font)
    return label


def dialog_header(layout,title,subtitle):
    header=QWidget();v=QVBoxLayout(header);v.setContentsMargins(6,6,6,16)
    label=QLabel(title);label.setObjectName('dialogTitle');v.addWidget(label)
    note=QLabel(subtitle);note.setWordWrap(True);note.setProperty('muted',True);v.addWidget(note);layout.insertWidget(0,header)
    return header


def mark_corners(widget):
    p=QPainter(widget);color=widget.palette().windowText().color();color.setAlphaF(.55);p.setPen(QPen(color,1))
    for x in (6,widget.width()-7):
        for y in (6,widget.height()-7):
            p.drawLine(x-5,y,x+5,y);p.drawLine(x,y-5,x,y+5)


class BlueprintDialog(QDialog):
    def paintEvent(self,event):
        super().paintEvent(event);mark_corners(self)


class FlatSelectionDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        option.state &= ~QStyle.State_HasFocus
        super().paint(painter,option,index)


class CueDelegate(QStyledItemDelegate):
    def sizeHint(self,option,index):return QSize(250,108)
    def paint(self,painter,option,index):
        painter.save();r=option.rect.adjusted(12,8,-12,-8)
        selected=bool(option.state & QStyle.State_Selected)
        if selected:
            painter.fillRect(option.rect,QColor(89,128,166,24));painter.fillRect(option.rect.x(),option.rect.y(),3,option.rect.height(),QColor('#5980a6'))
        painter.setPen(option.palette.text().color());font=QFont('Barlow',10);painter.setFont(font)
        cue=index.data(Qt.UserRole)
        if cue:
            painter.drawText(r,Qt.AlignLeft|Qt.AlignTop,f"{index.data(Qt.UserRole+1)}   {clock(cue.start)} – {clock(cue.end)}")
            painter.drawText(r.adjusted(0,23,0,-24),Qt.TextWordWrap, cue.text)
            tag=cue_status(cue);width=painter.fontMetrics().horizontalAdvance(tag)+16;tag_rect=QRectF(r.x(),r.bottom()-19,width,20)
            pen=QPen(QColor('#5980a6') if cue.speed>1 or cue.disposition=='pause' else option.palette.text().color(),1)
            if cue.disposition=='unresolved':pen.setStyle(Qt.DashLine)
            if cue.disposition=='pause':painter.fillRect(tag_rect,QColor('#5980a6'))
            painter.setPen(pen);painter.drawRect(tag_rect);painter.setPen(option.palette.text().color());painter.drawText(tag_rect,Qt.AlignCenter,tag)
        painter.restore()


def cue_status(cue):
    if cue.disposition=='unresolved':return 'Needs review'
    if cue.disposition=='pause':return f'Pause {cue.speech_seconds:.1f}s' if cue.speech_seconds else 'Pauses picture'
    if cue.speed>1:return f'Sped up · {cue.speed:.2f}×'
    return 'In gap' if cue.disposition=='in-gap' else 'Not yet placed'


class BlueprintFrame(QFrame):
    def paintEvent(self,event):
        super().paintEvent(event)
        p=QPainter(self);color=QColor('#5980a6') if self.property('selected') else self.palette().windowText().color()
        if not self.property('selected'):color.setAlphaF(.18)
        p.setPen(QPen(color,1));p.drawRect(6,6,self.width()-13,self.height()-13);p.end();mark_corners(self)


class Timeline(QWidget):
    """Real cue geometry and seeking, with native focusable cue buttons."""
    def __init__(self, window):
        super().__init__(); self.window = window; self.blocks = []; self.thumbnails=QPixmap();self.source=None;self.decoder=None;self.view_start=0.;self.view_seconds=90.
        self.setFixedHeight(238); self.setAccessibleName('Timeline: Ctrl+wheel zoom, wheel scroll')
        self.scroll=QScrollBar(Qt.Horizontal,self);self.scroll.valueChanged.connect(self.scroll_to)
    def seconds_at(self, x):
        return max(0, min(self.window.project.duration, self.view_start+(x-96)/max(1,self.width()-106)*self.span()))
    def span(self):return min(max(.1,self.window.project.duration),self.view_seconds)
    def scroll_to(self,value):self.view_start=value/1000;self.position_blocks();self.update()
    def set_view(self,start):
        self.scroll.setRange(0,round(max(0,self.window.project.duration-self.span())*1000));self.scroll.setPageStep(round(self.span()*1000));self.scroll.setValue(round(max(0,start)*1000))
        self.view_start=self.scroll.value()/1000;self.position_blocks();self.update()
    def ensure_visible(self,seconds):
        if not self.view_start<=seconds<self.view_start+self.span():self.set_view(seconds-self.span()*.2)
    def wheelEvent(self,event):
        delta=event.angleDelta().y() or event.angleDelta().x()
        if event.modifiers() & Qt.ControlModifier:
            anchor=self.seconds_at(event.position().x());ratio=max(0,min(1,(event.position().x()-96)/max(1,self.width()-106)))
            self.view_seconds=max(5,min(max(5,self.window.project.duration),self.view_seconds*(.8 if delta>0 else 1.25)));self.set_view(anchor-ratio*self.span())
        else:self.set_view(self.view_start-delta/120*self.span()*.1)
        event.accept()
    def mousePressEvent(self, event):
        self.window.seek(round(self.seconds_at(event.position().x())*1000))
    def sync(self):
        source=self.window.project.video
        if self.source!=source:
            self.source=source;self.thumbnails=QPixmap();self.view_start=0;self.view_seconds=min(90,max(5,self.window.project.duration))
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
            b.setProperty('role','primary' if cue.disposition=='pause' else 'secondary')
            if cue.disposition=='unresolved':b.setStyleSheet('border:1px dashed palette(text);')
            elif cue.speed>1:b.setStyleSheet('background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #5980a6,stop:0.5 #b5c8da,stop:1 #5980a6);')
            elif cue.disposition=='in-gap':b.setStyleSheet('background:rgba(89,128,166,76);border:1px solid #5980a6;')
            self.blocks.append(b); b.show()
        self.set_view(self.view_start)
    def stop_decoder(self):
        if self.decoder and self.decoder.state()!=QProcess.NotRunning:self.decoder.kill();self.decoder.waitForFinished(1000)
    def position_blocks(self):
        duration = self.span(); width = max(1,self.width()-106)
        for b,c in zip(self.blocks,self.window.project.cues):
            left=max(96,round(96+(c.start-self.view_start)/duration*width));right=min(self.width()-10,round(96+(c.end-self.view_start)/duration*width))
            b.setVisible(c.end>self.view_start and c.start<self.view_start+duration)
            b.setGeometry(left,162,max(1,right-left),38)
    def resizeEvent(self,event):
        self.scroll.setGeometry(96,216,max(1,self.width()-106),16);self.position_blocks(); super().resizeEvent(event)
    def paintEvent(self,event):
        p=QPainter(self); color=self.palette().windowText().color(); muted=QColor(color);muted.setAlpha(50)
        p.setPen(color); p.drawText(12,20,'TIMELINE')
        p.drawText(120,20,'In gap   /   Sped up   /   Pauses picture   /   Needs review')
        for label,y in [('Picture',85),('Dialogue',137),('Descriptions',185)]:p.drawText(8,y,label)
        p.setPen(muted)
        for y in (32,58,112,156,206):p.drawLine(0,y,self.width(),y)
        p.drawLine(96,32,96,206)
        p.save();p.setClipRect(96,26,max(1,self.width()-106),180)
        if not self.thumbnails.isNull():
            total=max(.1,self.window.project.duration);count=max(1,round((self.width()-106)/110));cell=(self.width()-106)/count
            for i in range(count):
                time=self.view_start+(i+.5)/count*self.span();sample=min(7,int(time/total*8))
                source=QRectF(sample*self.thumbnails.width()/8,0,self.thumbnails.width()/8,self.thumbnails.height())
                p.drawPixmap(QRectF(96+i*cell,59,cell-1,52),self.thumbnails,source)
        duration=self.span(); width=max(1,self.width()-106)
        # Adapt tick density to the available width; hours-long media stays responsive.
        step=max(10,round(duration/max(1,width/80)/10)*10)
        for t in range(int(self.view_start//step)*step,int(self.view_start+duration)+1,step):
            x=round(96+(t-self.view_start)/duration*width);p.drawLine(x,32,x,206);p.drawText(x+3,49,clock(t))
        analysis=self.window.project.analysis
        intervals=analysis.get('protected',[]) if isinstance(analysis,dict) else []
        for interval in intervals:
            a,b=interval if isinstance(interval,(list,tuple)) else (interval['start'],interval['end'])
            p.fillRect(QRectF(96+(a-self.view_start)/duration*width,116,(b-a)/duration*width,34),QColor('#98989b'))
        x=round(96+(self.window.player.position()/1000-self.view_start)/duration*width)
        p.setPen(QPen(color,1));p.drawLine(x,32,x,206);p.drawRect(x-3,26,6,6);p.restore()


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
        self.editor_toolbar=QWidget();toolbar=QHBoxLayout(self.editor_toolbar);toolbar.setContentsMargins(0,0,0,0);bar.addWidget(self.editor_toolbar)
        button(toolbar,'Open',self.show_start,role='ghost');button(toolbar,'Import cues',self.import_cues,role='ghost')
        self.model_chip=button(toolbar,'AI model',self.draft_dialog)
        self.draft_button=button(toolbar,'Draft with AI',self.draft_dialog)
        self.export_button=button(toolbar,'Export',self.export,True)
        self.theme_button=button(bar,'Theme',self.toggle_theme,role='ghost',icon_only=True);button(bar,'Settings',self.edit_settings,role='ghost',icon_only=True)
        self.pages.currentChanged.connect(lambda index:(self.editor_toolbar.setVisible(index==1),self.project_title.setVisible(index==1)))
        outer.addWidget(self.pages,1)
        self.start_page=self.make_start();self.pages.addWidget(self.start_page)
        editor=QSplitter();self.pages.addWidget(editor)
        left=QWidget();lv=QVBoxLayout(left);lv.setContentsMargins(0,8,16,0);editor.addWidget(left)
        frame=BlueprintFrame();fv=QVBoxLayout(frame);fv.setContentsMargins(14,14,14,14);fv.addWidget(self.video,1);self.video.show()
        self.pause_badge=QLabel('PICTURE PAUSED FOR DESCRIPTION');self.pause_badge.setObjectName('caption');fv.addWidget(self.pause_badge);self.pause_badge.hide()
        self.current.setObjectName('caption');self.current.hide();fv.addWidget(self.current);lv.addWidget(frame,1)
        transport=QHBoxLayout();lv.addLayout(transport)
        button(transport,'−10 s',lambda:self.seek(self.player.position()-10000))
        self.play_button=button(transport,'Play / Pause',self.toggle,True,icon_only=True);button(transport,'+10 s',lambda:self.seek(self.player.position()+10000))
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
        self.cue_list=QListWidget();self.cue_list.setWordWrap(True);self.cue_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.cue_list.setAccessibleName('Descriptions');self.cue_list.setItemDelegate(CueDelegate(self.cue_list));dv.addWidget(self.cue_list,1);self.cue_list.currentRowChanged.connect(self.list_selected);self.cue_list.itemClicked.connect(lambda item:self.inline.setVisible(not self.inline.isVisible()) if self.cue_list.row(item)==getattr(self,'_last_clicked',-1) else setattr(self,'_last_clicked',self.cue_list.row(item)))
        self.inline=QWidget();iv=QVBoxLayout(self.inline);iv.setContentsMargins(0,0,0,0);inline_scroll=QScrollArea();self.inline_scroll=inline_scroll;inline_scroll.setWidgetResizable(True);inline_scroll.setWidget(self.inline);inline_scroll.setMinimumHeight(280);dv.addWidget(inline_scroll)
        times=QHBoxLayout();iv.addLayout(times)
        for name,field in [('Start',self.start),('End',self.end)]:
            field.setMaximumWidth(75);times.addWidget(QLabel(name));button(times,'−',lambda checked=False,f=field:self.nudge(f,-.1));times.addWidget(field);button(times,'+',lambda checked=False,f=field:self.nudge(f,.1))
        points=QHBoxLayout();iv.addLayout(points)
        button(points,'Start at playhead',lambda:self.start.setText(str(self.player.position()/1000)))
        button(points,'End at playhead',lambda:self.end.setText(str(self.player.position()/1000)))
        iv.addWidget(self.text);self.fit_label=QLabel();self.fit_label.setWordWrap(True);self.fit_label.setMinimumHeight(48);iv.addWidget(self.fit_label);iv.addSpacing(8);self.fit_bar=QProgressBar();self.fit_bar.setTextVisible(False);self.fit_bar.setFixedHeight(6);self.fit_bar.setRange(0,200);iv.addWidget(self.fit_bar);iv.addSpacing(8)
        self.review_note=QLabel();self.review_note.setWordWrap(True);iv.addWidget(self.review_note)
        actions=QHBoxLayout();iv.addLayout(actions);button(actions,'Mark as checked',self.mark_checked);button(actions,'Delete',self.delete_cue)
        contextual=QHBoxLayout();iv.addLayout(contextual);button(contextual,'Preview in context',self.preview_context);button(contextual,'Ask about scene',lambda:self.tabs.setCurrentIndex(1))
        iv.addWidget(QLabel('Changes apply as you type. Ctrl+Z undoes.'));self.inline.hide()
        self.empty=QWidget();ev=QVBoxLayout(self.empty);ev.addWidget(QLabel('NO DESCRIPTIONS YET'))
        button(ev,'Draft with AI',self.draft_dialog,True);button(ev,'Import SRT / VTT',self.import_cues);button(ev,'Add at playhead',self.add_at_playhead);dv.addWidget(self.empty)
        self.make_scene();self.make_glossary()
        self.state_label=QLabel();outer.addWidget(self.state_label)
        self.toast=BlueprintFrame();tv=QHBoxLayout(self.toast);self.toast_text=QLabel();self.toast_text.setWordWrap(True);tv.addWidget(self.toast_text);button(tv,'Close',self.toast.hide,role='ghost');outer.addWidget(self.toast);self.toast.hide()
        dock=QDockWidget('Log',self);dock.setWidget(self.log_view);self.addDockWidget(Qt.BottomDockWidgetArea,dock);dock.hide()
        self.menuBar().addMenu('View').addAction(dock.toggleViewAction())
        undo=self.undo_stack.createUndoAction(self,'Undo');undo.setShortcut('Ctrl+Z');self.addAction(undo)
        redo=self.undo_stack.createRedoAction(self,'Redo');redo.setShortcut('Ctrl+Shift+Z');self.addAction(redo)
        self.setCentralWidget(root);old.deleteLater()
        self.player.positionChanged.connect(self.presentation_position)
        self.player.playbackStateChanged.connect(lambda _:self.presentation_position(self.player.position()))
        self.ui_timer=QTimer(self);self.ui_timer.timeout.connect(self.update_status);self.ui_timer.start(400)
        self.apply_theme();self.refresh()
    def make_start(self):
        page=QWidget();layout=QHBoxLayout(page);layout.setContentsMargins(12,40,12,20);layout.setSpacing(36)
        left=QVBoxLayout();left.setAlignment(Qt.AlignTop);layout.addLayout(left,2)
        left.addWidget(section('NEW PROJECT'));heading=QLabel('START WITH A VIDEO.');heading.setObjectName('hero');left.addWidget(heading)
        lead=QLabel('Describe what matters on screen. Draft locally or with your own cloud key, then edit and export.');lead.setWordWrap(True);left.addWidget(lead);left.addSpacing(24)
        cards=QHBoxLayout();cards.setSpacing(16);left.addLayout(cards)
        for title,shortcut,icon,fn in [('Open video','Ctrl+O','folder-open',self.open_video),('From URL','Ctrl+U','download',self.open_url),('Open project','Ctrl+Shift+O','folder-open',self.load_project)]:
            frame=BlueprintFrame();frame.setFixedSize(180,180);fl=QVBoxLayout(frame);fl.setContentsMargins(18,22,18,18)
            action=button(fl,title,fn,role='ghost');action.setIcon(QIcon(str(asset_path('icons')/(icon+'.svg'))));action.setIconSize(QSize(28,28));fl.addStretch();fl.addWidget(QLabel(shortcut));cards.addWidget(frame,0,Qt.AlignTop)
        cards.addStretch();left.addSpacing(24)
        drop=QLabel('Drop a video or .adproject here');drop.setObjectName('drop');drop.setMinimumHeight(90);left.addWidget(drop);left.addStretch()
        from . import __version__
        foot=QHBoxLayout();left.addLayout(foot);foot.addWidget(QLabel('v'+__version__));button(foot,'Manual and shortcuts',self.help,role='ghost');foot.addStretch()
        right=QVBoxLayout();right.setAlignment(Qt.AlignTop);layout.addLayout(right,1);right.addWidget(section('RECENT PROJECTS'))
        self.recent_empty=QLabel('No recent projects yet.\nOpen a video and save your first project.');self.recent_empty.setWordWrap(True);right.addWidget(self.recent_empty)
        self.recents=QListWidget();right.addWidget(self.recents);self.recents.itemActivated.connect(lambda item:self.open_recent(item.data(Qt.UserRole)))
        right.addSpacing(28);right.addWidget(section('SETUP CHECKLIST'));self.setup_checks={};self.setup_actions={}
        for title,group in [('Speech detector','Updates'),('Ollama','Keys & privacy'),('Windows voices','Speech & playback'),('Gemini key','Keys & privacy')]:
            line=QHBoxLayout();right.addLayout(line);check=QCheckBox(title);check.setAttribute(Qt.WA_TransparentForMouseEvents);check.setFocusPolicy(Qt.NoFocus);line.addWidget(check);self.setup_checks[title]=check;line.addStretch();action=button(line,'Set up',lambda checked=False,s=group:self.edit_settings(s),role='link');self.setup_actions[title]=action
        right.addStretch();return page
    def show_start(self):
        if not self.busy():self.pages.setCurrentIndex(0);self.editor_toolbar.hide()
    def toggle_theme(self):
        self.settings.data['ui_theme']='dark' if self.settings.data.get('ui_theme','light')=='light' else 'light';self.settings.save();self.apply_theme()
    def apply_theme(self):
        dark=self.settings.data.get('ui_theme')=='dark';bg='#1d1f20' if dark else '#f2f2f3';fg='#f2f2f3' if dark else '#1d1f20';surface='#2b2b2d' if dark else '#e9e9ea';border='#555558' if dark else '#ccccce'
        self.setStyleSheet(f'''QWidget {{background:{bg};color:{fg};font-family:Barlow;font-size:14px;}}
QLabel {{border:0;background:transparent;}} QFrame, QDialog {{border-radius:0;}}
QPushButton {{border:1px solid {border};padding:7px 10px;background:transparent;}}
QLineEdit,QComboBox,QPlainTextEdit,QListWidget {{border:1px solid {border};padding:7px;selection-background-color:rgba(89,128,166,24);selection-color:{fg};}}
QPushButton:hover {{background:rgba(89,128,166,20);border-color:#5980a6;}}
QPushButton:focus,QLineEdit:focus,QPlainTextEdit:focus {{border:2px solid #5980a6;}}
QPushButton[role="primary"] {{background:#5980a6;color:#10171e;border:1px solid #5980a6;}}
QPushButton[role="ghost"],QPushButton[role="link"] {{border:1px solid transparent;background:transparent;}}
QPushButton[role="link"] {{color:{'#b5d9fd' if dark else '#416180'};font-size:12px;padding:3px;}}
QPushButton[role="ghost"]:hover,QPushButton[role="link"]:hover {{background:rgba(89,128,166,20);}}
QPushButton:disabled {{color:#98989b;}}
QTabBar::tab {{padding:12px;border-bottom:1px solid {border};}} QTabBar::tab:selected {{border-bottom:2px solid #5980a6;}}
QListWidget::item {{padding:10px;border:0;border-bottom:1px solid {border};border-left:3px solid transparent;}}
QListWidget::item:selected {{background:rgba(89,128,166,24);color:{fg};border-left:3px solid #5980a6;}}
QListWidget::item:hover {{background:rgba(89,128,166,15);}}
QFrame[providerCard="true"] {{border:0;}} QFrame[providerCard="true"][selected="true"] {{border:0;background:rgba(89,128,166,24);}}
QFrame[providerCard="true"] QRadioButton {{background:transparent;}}
QProgressBar {{height:6px;min-height:6px;max-height:6px;border:0;background:{surface};}} QProgressBar::chunk {{background:#5980a6;}}
QLabel#brand {{font-family:'Barlow Condensed';font-size:17px;}} QLabel#hero {{font-family:'Barlow Condensed';font-size:56px;}}
QLabel#dialogTitle {{font-family:'Barlow Condensed';font-weight:600;font-size:24px;}}
QLabel[section="true"] {{font-weight:600;font-size:12px;}}
QLabel#caption {{background:#1d2d3d;color:#f2f2f3;padding:10px;}} QLabel#drop {{border:1px dashed {border};padding:20px;}}
''')
        self.theme_button.setProperty('iconName','sun' if dark else 'moon')
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtCore import QByteArray
        for widget in self.findChildren(QPushButton):
            name=widget.property('iconName')
            if not name:continue
            data=(asset_path('icons')/(name+'.svg')).read_text().replace('currentColor',fg).replace('stroke-width="2"','stroke-width="1.5"')
            pixmap=QPixmap(24,24);pixmap.fill(Qt.transparent);painter=QPainter(pixmap);QSvgRenderer(QByteArray(data.encode())).render(painter);painter.end();widget.setIcon(QIcon(pixmap))
    def themed_icon(self,name):
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtCore import QByteArray
        fg='#f2f2f3' if self.settings.data.get('ui_theme')=='dark' else '#1d1f20'
        data=(asset_path('icons')/(name+'.svg')).read_text().replace('currentColor',fg).replace('stroke-width="2"','stroke-width="1.5"')
        pixmap=QPixmap(24,24);pixmap.fill(Qt.transparent);painter=QPainter(pixmap);QSvgRenderer(QByteArray(data.encode())).render(painter);painter.end();return QIcon(pixmap)
    def update_status(self):
        if not hasattr(self,'state_label'):return
        provider=self.settings.data['analysis_provider'];model=self.settings.data['ollama_model' if provider=='Ollama' else 'model']
        self.model_chip.setText(provider+' · '+(model or 'Choose model'))
        self.project_title.setText((Path(self.project_path or self.project.video).stem if self.project.video else 'New project')+'  · '+('Unsaved changes (Ctrl+S)' if self.dirty else 'Saved'))
        running=self.thread is not None;self.inline.setEnabled(not running);self.glossary_list.parentWidget().setEnabled(not running);self.draft_button.setEnabled(not running and bool(self.project.video));self.export_button.setEnabled(not running and bool(self.project.cues));self.job_card.setVisible(running)
        counts={k:sum(c.disposition==k for c in self.project.cues) for k in ('in-gap','pause','unresolved')}
        from .engine.assets import default_root
        detector=Path(self.settings.data.get('sound_model') or default_root()/'assets'/'yamnet.onnx').is_file()
        for key,value in [('Speech detector',detector),('Ollama',bool(self.settings.data.get('ollama_model'))),('Windows voices',bool(self.speech.availableVoices())),('Gemini key',bool(self.settings.data.get('gemini_key')))]:self.setup_checks[key].setChecked(value);self.setup_actions[key].setVisible(not value)
        self.setup_checks['Ollama'].setToolTip('Exact model configured; use Test connection to verify the server.')
        self.state_label.setText(f"Speech detector: {'installed' if detector else 'not installed'}  |  {'Working' if running else 'Engine idle'}     In gap {counts['in-gap']} · Pauses {counts['pause']} · Review {counts['unresolved']}     Voice: {self.settings.data.get('playback_voice') or 'System default'}     API: {'running' if self.api_thread and self.api_thread.is_alive() else 'off'}")
    def presentation_position(self,value):
        cue=next((c for c in self.project.cues if c.start<=value/1000<c.end),None);self.current.setText(cue.text if cue else '')
        self.clock.setText(clock(value/1000)+' / '+clock(self.project.duration));self.timeline.ensure_visible(value/1000);self.timeline.update();self.pause_badge.setVisible(self.pause_active);self.current.setVisible(bool(self.current.text().strip()))
        playing=self.player.playbackState()==self.player.PlaybackState.PlayingState
        name='pause' if playing else 'play';self.play_button.setProperty('iconName',name);self.play_button.setIcon(self.themed_icon(name));self.play_button.setAccessibleName('Pause' if playing else 'Play');self.play_button.setToolTip('Pause' if playing else 'Play')
    def render_cues(self):
        if not hasattr(self,'cue_list'):return
        self.cue_list.blockSignals(True);self.cue_list.clear();self.visible_indices=[]
        self.cue_filter.setItemText(1,f"Needs review · {sum(c.disposition=='unresolved' for c in self.project.cues)}");self.cue_filter.setItemText(2,f"Pauses · {sum(c.disposition=='pause' for c in self.project.cues)}")
        for i,c in enumerate(self.project.cues):
            if self.cue_filter.currentIndex()==1 and c.disposition!='unresolved':continue
            if self.cue_filter.currentIndex()==2 and c.disposition!='pause':continue
            item=QListWidgetItem(c.text);item.setData(Qt.UserRole,c);item.setData(Qt.UserRole+1,i+1);item.setToolTip(cue_status(c)+': '+c.text);item.setSizeHint(QSize(250,108));self.cue_list.addItem(item);self.visible_indices.append(i)
        self.cue_list.blockSignals(False);self.tabs.setTabText(0,f'Descriptions · {len(self.project.cues)}');self.empty.setVisible(not self.project.cues);self.cue_list.setVisible(bool(self.project.cues));self.inline_scroll.setVisible(bool(self.project.cues))
        self.timeline.sync();self.update_status()
    def list_selected(self,row):
        if 0<=row<len(self.visible_indices):self.choose(self.visible_indices[row])
    def choose(self,index):
        if not 0<=index<len(self.project.cues):return
        self._selected_cue=self.project.cues[index];self.table.setCurrentCell(index,0);self.select_cue();self.inline.show()
        if index in self.visible_indices:
            self.cue_list.blockSignals(True);self.cue_list.setCurrentRow(self.visible_indices.index(index));self.cue_list.blockSignals(False)
        self.timeline.ensure_visible(self.project.cues[index].start);self.update_fit()
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
        self.toast_text.setText(text);self.toast.show();QTimer.singleShot(9000,self.toast.hide)
    def draft_dialog(self):
        if self.busy() or not self.project.video:return
        d=BlueprintDialog(self);d.setWindowTitle('DRAFT WITH AI');d.resize(760,840);v=QVBoxLayout(d);v.setContentsMargins(20,20,20,20);dialog_header(v,'DRAFT WITH AI','Choose a model, analysis range and editorial guidance.')
        v.addWidget(section('1 · PROVIDER'))
        providers=QHBoxLayout();providers.setSpacing(20);v.addLayout(providers);provider_group=QButtonGroup(d)
        for provider,label in [('Ollama','Ollama · LOCAL / CLOUD\nSampled frames, no audio.'),('Gemini','Google Gemini · CLOUD\nUploads video using your key. Can hear audio.')]:
            card=BlueprintFrame();cv=QVBoxLayout(card);choice=QRadioButton(label);choice.setChecked(self.model_picker.provider.currentText()==provider);provider_group.addButton(choice);cv.addWidget(choice);providers.addWidget(card);card.setProperty('providerCard',True);card.setProperty('selected',choice.isChecked());card.setMinimumHeight(86)
            choice.toggled.connect(lambda checked,c=card:(c.setProperty('selected',checked),c.style().unpolish(c),c.style().polish(c),c.update()))
            choice.toggled.connect(lambda checked,p=provider:self.model_picker.provider.setCurrentText(p) if checked else None)
        v.addWidget(section('2 · EXACT MODEL'))
        model_list=QListWidget();model_list.setItemDelegate(FlatSelectionDelegate(model_list));model_list.setAccessibleName('Discovered exact models');v.addWidget(model_list)
        def sync_models(*args):
            model_list.blockSignals(True);model_list.clear()
            for i in range(self.model_picker.model.count()):model_list.addItem(self.model_picker.model.itemText(i))
            if not model_list.count():model_list.addItem(self.model_picker.model.currentText())
            for i in range(model_list.count()):model_list.item(i).setFlags(model_list.item(i).flags()|Qt.ItemIsEditable)
            model_list.setCurrentRow(max(0,self.model_picker.model.currentIndex()));model_list.blockSignals(False)
        sync_models();model_list.currentRowChanged.connect(lambda i:self.model_picker.model.setCurrentIndex(i))
        model_list.setEditTriggers(QListWidget.DoubleClicked|QListWidget.EditKeyPressed)
        for i in range(model_list.count()):model_list.item(i).setFlags(model_list.item(i).flags()|Qt.ItemIsEditable)
        model_list.itemChanged.connect(lambda item:self.model_picker.store_model(item.text().strip()) if item.text().strip() else None)
        links=QHBoxLayout();v.addLayout(links);button(links,'Refresh models',self.model_picker.refresh,role='ghost');button(links,'Test connection',self.model_picker.test,role='ghost');links.addStretch()
        status=QLabel(self.model_picker.help.text());status.setWordWrap(True);v.addWidget(status)
        timer=QTimer(d);timer.timeout.connect(lambda:status.setText(self.model_picker.help.text()));timer.start(300)
        self.model_picker.model.model().rowsInserted.connect(sync_models)
        self.model_picker.provider.currentTextChanged.connect(sync_models)
        v.addWidget(section('3 · RANGE'))
        scope=QComboBox();scope.addItems([f'Whole video · {clock(self.project.duration)}',f'Next 20 s from {clock(self.player.position()/1000)}',f'Next 60 s from {clock(self.player.position()/1000)}']);scope.setCurrentIndex(self.model_picker.scope.currentIndex());v.addWidget(scope)
        v.addWidget(QLabel('Request count depends on range, frame interval and detected visual events.'))
        v.addWidget(section('4 · EDITORIAL INSTRUCTIONS'));v.addWidget(QLabel('Preset'));v.addWidget(self.preset);self.preset.show();v.addWidget(QLabel('Editorial prompt'));v.addWidget(self.prompt);self.prompt.show()
        verbosity=QComboBox();verbosity.addItems(['Short','Standard','Detailed']);verbosity.setCurrentText(self.settings.data['verbosity']);v.addWidget(QLabel('Verbosity'));v.addWidget(verbosity)
        glossary=QCheckBox('Recognize characters and update the glossary');glossary.setChecked(self.settings.data['auto_glossary']);v.addWidget(glossary)
        note=QLabel();note.setWordWrap(True);v.addWidget(note)
        def update_note():note.setText(('Sampled frames, no audio, go to the selected Ollama server. Remote/cloud confirmation remains required.' if self.model_picker.provider.currentText()=='Ollama' else 'Uploads video to Google with your key; may include audio and incur charges.')+f' Range analysis replaces the {len(self.project.cues)} current descriptions.')
        update_note();self.model_picker.provider.currentTextChanged.connect(update_note)
        actions=QDialogButtonBox(QDialogButtonBox.Cancel);actions.addButton('Start draft',QDialogButtonBox.AcceptRole).setProperty('role','primary');actions.accepted.connect(d.accept);actions.rejected.connect(d.reject);v.addWidget(actions)
        accepted=d.exec();timer.stop();self.model_picker.provider.currentTextChanged.disconnect(update_note);self.model_picker.provider.currentTextChanged.disconnect(sync_models);self.model_picker.model.model().rowsInserted.disconnect(sync_models)
        for widget in (self.model_picker,self.preset,self.prompt):widget.setParent(self.centralWidget());widget.hide()
        if accepted:
            self.model_picker.scope.setCurrentIndex(scope.currentIndex())
            self.settings.data.update(verbosity=verbosity.currentText(),auto_glossary=glossary.isChecked());self.settings.save()
            self.job_label.setText('Drafting descriptions');self.analyze()
    def export(self):
        if self.busy() or not self.project.cues:return
        d=BlueprintDialog(self);d.setWindowTitle('EXPORT');d.resize(920,780);v=QVBoxLayout(d);v.setContentsMargins(20,20,20,20);dialog_header(v,'EXPORT','Choose an output format and review narration coverage.');row=QHBoxLayout();v.addLayout(row)
        formats=QListWidget();formats.setItemDelegate(FlatSelectionDelegate(formats));formats.setObjectName('formatCards');formats.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff);formats.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for title,description,extension in [('Described video','Picture with narration and soundtrack','MP4'),('Narrated audio','Compressed audio with narration','MP3'),('Narrated audio','Uncompressed audio with narration','WAV'),('Subtitles','Timed description captions','SRT'),('Web subtitles','Web-ready description captions','VTT'),('Script','Readable description script','TXT'),('Project data','Structured project and cue data','JSON')]:
            item=QListWidgetItem(f'{title} · .{extension.lower()}\n{description}');item.setSizeHint(QSize(330,72));formats.addItem(item)
        formats.setFixedHeight(520);formats.setMinimumWidth(340);row.addWidget(formats,0,Qt.AlignTop)
        right=QVBoxLayout();row.addLayout(right);counts={k:sum(c.disposition==k for c in self.project.cues) for k in ('in-gap','pause','unresolved')};right.addWidget(section('COVERAGE'));right.addWidget(QLabel(f"In gap: {sum(c.disposition=='in-gap' and c.speed<=1 for c in self.project.cues)}\nSped up: {sum(c.speed>1 for c in self.project.cues)}\nPauses picture: {counts['pause']}\nNeeds review: {counts['unresolved']}"))
        warning=QLabel('Unresolved visual facts block media exports.');warning.setWordWrap(True);right.addWidget(warning)
        review=button(right,'Review now',lambda:(d.reject(),self.tabs.setCurrentIndex(0),self.cue_filter.setCurrentIndex(1),self.choose(next(i for i,c in enumerate(self.project.cues) if c.disposition=='unresolved'))))
        voice_label=QLabel('Narration engine');right.addWidget(voice_label)
        voice=QComboBox();voice.addItems(['Windows','Windows 32-bit','Windows OneCore','OpenAI']);voice.setCurrentText(self.settings.data['voice_engine']);right.addWidget(voice)
        voice_button=button(right,'Select installed export voice',self.select_windows_voice,role='ghost')
        right.addWidget(QLabel('Save to'));path=QLineEdit();path.setPlaceholderText('Choose an output file…');path.setAccessibleName('Export save path');right.addWidget(path)
        extensions=['mp4','mp3','wav','srt','vtt','txt','json']
        def browse():
            ext=extensions[formats.currentRow()];p,_=QFileDialog.getSaveFileName(d,'Save to','',f'{ext.upper()} (*.{ext})')
            if p:path.setText(p if Path(p).suffix else p+'.'+ext)
        button(right,'Save to…',browse);right.addStretch()
        v.addWidget(QLabel('Narration speed stays at or below 1.15×. Media exports include a coverage sidecar.'))
        actions=QDialogButtonBox(QDialogButtonBox.Cancel);go=actions.addButton('Export',QDialogButtonBox.AcceptRole);go.setProperty('role','primary');v.addWidget(actions);actions.accepted.connect(d.accept);actions.rejected.connect(d.reject)
        def state():
            media=formats.currentRow()<3;blocked=media and bool(counts['unresolved']);warning.setVisible(blocked);review.setVisible(blocked);voice.setVisible(media);voice_label.setVisible(media);voice_button.setVisible(media);go.setEnabled(bool(path.text()) and not blocked)
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
    dialog_header(outer,'SETTINGS','Configure analysis, speech, privacy and developer access.');outer.setContentsMargins(20,20,20,20)
    outer.removeWidget(scroll);scroll.hide();dialog.resize(960,720)
    body=QHBoxLayout();outer.addLayout(body,1);nav=QListWidget();nav.setItemDelegate(FlatSelectionDelegate(nav));nav.addItems(groups);nav.setMaximumWidth(220);nav.setAccessibleName('Settings sections');body.addWidget(nav)
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
    outer.addWidget(buttons);buttons.button(QDialogButtonBox.Ok).setText('Save');buttons.button(QDialogButtonBox.Ok).setProperty('role','primary');buttons.button(QDialogButtonBox.Ok).style().unpolish(buttons.button(QDialogButtonBox.Ok));buttons.button(QDialogButtonBox.Ok).style().polish(buttons.button(QDialogButtonBox.Ok))


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
