"""Project-aware undo commands and keyboard routing for the desktop editor."""
import copy
import time
from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtGui import QUndoCommand


class CueEdit(QUndoCommand):
    def __init__(self, window, before, after, title):
        super().__init__(title);self.window=window;self.before=before;self.after=after
        from .drafting import coverage_for
        self.before_coverage=copy.deepcopy(window.project.coverage)
        self.after_coverage=coverage_for(after,self.before_coverage,before)
        self.before_analysis=copy.deepcopy(window.project.analysis)
        self.after_analysis=dict(copy.deepcopy(self.before_analysis),requires_replan=True)
    def apply(self, data, coverage, analysis):
        self.window.project.cues=copy.deepcopy(data);self.window.dirty=True
        self.window.project.coverage=copy.deepcopy(coverage);self.window.project.analysis=copy.deepcopy(analysis)
        self.window.refresh();self.window.last_spoken=None
        if not getattr(self.window,'_typing',False) and self.window.project.cues:self.window.choose(min(max(0,self.window.selected_index()),len(data)-1))
    def undo(self):self.apply(self.before,self.before_coverage,self.before_analysis)
    def redo(self):self.apply(self.after,self.after_coverage,self.after_analysis)


class ProjectUndoKeys(QObject):
    """Keep the text widget's private history from bypassing project metadata."""
    def eventFilter(self,widget,event):
        if event.type() in (QEvent.FocusOut,QEvent.MouseButtonPress) or (event.type()==QEvent.KeyPress and event.key() in (Qt.Key_Left,Qt.Key_Right,Qt.Key_Up,Qt.Key_Down,Qt.Key_Home,Qt.Key_End,Qt.Key_PageUp,Qt.Key_PageDown)):
            self.parent()._typing_session=getattr(self.parent(),'_typing_session',0)+1
        if event.type() in (QEvent.ShortcutOverride,QEvent.KeyPress) and event.key()==Qt.Key_Z and event.modifiers() in (Qt.ControlModifier,Qt.ControlModifier|Qt.ShiftModifier):
            event.accept()
            if event.type()==QEvent.KeyPress:
                stack=self.parent().undo_stack
                if event.modifiers() & Qt.ShiftModifier:stack.redo()
                else:stack.undo()
            return True
        return super().eventFilter(widget,event)


class TextEdit(QUndoCommand):
    """One cue and coverage row per typing group; structural edits stay separate."""
    def __init__(self,window,index,before,after):
        super().__init__('Edit description')
        from .drafting import coverage_for
        self.window=window;self.index=index
        self.before=copy.deepcopy(before);self.after=copy.deepcopy(after)
        self.session=getattr(window,'_typing_session',0);self.when=time.monotonic()
        self.coverage_index=next((i for i,row in enumerate(window.project.coverage) if row.get('cue_id')==before.cue_id),None)
        if self.coverage_index is None and before.event_id:
            matches=[i for i,row in enumerate(window.project.coverage) if row.get('event_id')==before.event_id]
            if len(matches)==1:self.coverage_index=matches[0]
        self.before_row=copy.deepcopy(window.project.coverage[self.coverage_index]) if self.coverage_index is not None else None
        self.after_row=coverage_for([after],[self.before_row] if self.before_row is not None else [])[0]
        self.replan=window.project.analysis.get('requires_replan')
        self.had_replan='requires_replan' in window.project.analysis
    def id(self):return 1802
    def mergeWith(self,other):
        if not isinstance(other,TextEdit) or self.window is not other.window or self.after.cue_id!=other.before.cue_id or self.session!=other.session or other.when-self.when>1.2 or self.after!=other.before:return False
        self.after=other.after;self.after_row=other.after_row;self.when=other.when
        return True
    def apply(self,cue,row,undo=False):
        w=self.window;old=w.project.cues[self.index]
        if old.cue_id!=cue.cue_id:raise ValueError('Description identity changed during undo.')
        w.project.cues[self.index]=copy.deepcopy(cue)
        if row is None:
            if self.coverage_index is not None:w.project.coverage.pop(self.coverage_index);self.coverage_index=None
        elif self.coverage_index is None:
            self.coverage_index=len(w.project.coverage);w.project.coverage.append(copy.deepcopy(row))
        else:w.project.coverage[self.coverage_index]=copy.deepcopy(row)
        if undo:
            if self.had_replan:w.project.analysis['requires_replan']=self.replan
            else:w.project.analysis.pop('requires_replan',None)
        else:w.project.analysis['requires_replan']=True
        w.dirty=True;w.last_spoken=None;w.played_pauses.clear()
        w.update_cue(self.index,old)
        if not getattr(w,'_typing',False):w.choose(self.index)
    def undo(self):self.apply(self.before,self.before_row,True)
    def redo(self):self.apply(self.after,self.after_row)


class GlossaryEdit(QUndoCommand):
    def __init__(self,window,after):
        super().__init__('Delete glossary character');self.window=window;self.before=window.project.glossary;self.after=after
    def apply(self,value):
        self.window.project.glossary=value;self.window.dirty=True
        self.window._glossary_snapshot=None;self.window.sync_glossary();self.window.update_status()
    def undo(self):self.apply(self.before)
    def redo(self):self.apply(self.after)


