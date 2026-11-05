"""Real Qt typing, project undo and retained-widget regressions."""
import copy
from pathlib import Path
import tempfile
from unittest.mock import patch

from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from describer.project import Project
from test_desktop_redesign import make_window


def test_typing_keeps_widgets_cursor_and_groups_undo():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            before=copy.deepcopy(w.project)
            for cue in before.cues:cue.validate(before.duration)
            w.project=copy.deepcopy(before)
            blocks=list(w.timeline.blocks);item=w.cue_list.item(0)
            cursor=w.text.textCursor();cursor.movePosition(cursor.MoveOperation.End);w.text.setTextCursor(cursor)
            with patch.object(w,'refresh',side_effect=AssertionError('full refresh during text edit')),patch.object(w.timeline,'sync',side_effect=AssertionError('timeline rebuild')):
                QTest.keyClicks(w.text,' More words.')
                assert w.project.cues[0].text==before.cues[0].text+' More words.'
                assert w.text.textCursor().position()==len(w.text.toPlainText())
                assert w.undo_stack.count()==1
                assert list(w.timeline.blocks)==blocks and w.cue_list.item(0) is item
                w.undo_stack.undo()
                assert w.project.cues==before.cues and w.project.coverage==before.coverage and w.project.analysis==before.analysis
                w.undo_stack.redo()
                w.project_path=Path(tmp)/'typed.adproject';assert w.save_project()
                assert Project.load(w.project_path).cues==w.project.cues
        finally:w.dirty=False;w.close();app.processEvents()


def test_review_coverage_filter_and_group_boundaries():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            cue=w.project.cues[1];cue.review_status='approved'
            w.project.coverage=[{'cue_id':cue.cue_id,'detector_evidence':'preserve this'}]
            w.refresh();w.cue_filter.setCurrentIndex(1);w.choose(1)
            original=copy.deepcopy(w.project)
            QTest.keyClicks(w.text,'a')
            assert w.project.cues[1].review_status=='needs-review'
            assert w.project.coverage[0]['detector_evidence']=='preserve this'
            w.undo_stack.undo();assert w.project.cues==original.cues and w.project.coverage==original.coverage
            w.undo_stack.redo()
            with patch('describer.desktop.time.monotonic',return_value=10**12):QTest.keyClicks(w.text,'b')
            assert w.undo_stack.count()==2
            w.choose(1);QTest.keyClicks(w.text,'c');assert w.undo_stack.count()==3
            w.cue_filter.setCurrentIndex(0);w.choose(0);QTest.keyClicks(w.text,'d');assert w.undo_stack.count()==4
            w.start.setText('12');assert w.undo_stack.count()==5
            w.undo_stack.undo();assert w.project.cues[0].start==10
            w.undo_stack.undo();assert w.project.cues[0].text==original.cues[0].text
        finally:w.dirty=False;w.close();app.processEvents()


def test_keyboard_undo_uses_project_history():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            w.show();w.text.setFocus();app.processEvents()
            original=w.project.cues[0].text
            QTest.keyClicks(w.text,'test')
            QTest.keyClick(w.text,Qt.Key_Z,Qt.ControlModifier);app.processEvents()
            assert w.project.cues[0].text==original
            assert w.undo_stack.index()==0
            QTest.keyClick(w.text,Qt.Key_Z,Qt.ControlModifier|Qt.ShiftModifier);app.processEvents()
            assert w.project.cues[0].text!=original and w.undo_stack.index()==1
        finally:w.dirty=False;w.close();app.processEvents()


def test_context_undo_and_cursor_navigation_split_groups():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            original=w.project.cues[0].text
            QTest.keyClicks(w.text,'first')
            QTest.keyClick(w.text,Qt.Key_Left);QTest.keyClicks(w.text,'second')
            assert w.undo_stack.count()==2
            def undo():
                menu=QApplication.activePopupWidget()
                assert menu.actions()[0].isEnabled()
                menu.actions()[0].trigger();menu.close()
            QTimer.singleShot(0,undo);w.text_context_menu(QPoint(1,1))
            assert w.undo_stack.index()==1 and w.project.cues[0].text=='first'+original
            w.undo_stack.undo();assert w.project.cues[0].text==original
            w.project.cues[0].disposition='pause';w.refresh();w.cue_filter.setCurrentIndex(2);w.choose(0)
            QTest.keyClicks(w.text,'new')
            assert not w.visible_indices and w.project.cues[0].disposition=='unplanned'
            w.undo_stack.undo();assert w.visible_indices==[0]
        finally:w.dirty=False;w.close();app.processEvents()
