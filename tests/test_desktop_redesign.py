"""Desktop redesign regressions: edit persistence, undo, range controls and export gate."""
import tempfile
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QLineEdit, QListWidget
from describer.app import Window
from describer.project import Cue


def make_window(tmp):
    app=QApplication.instance() or QApplication([])
    w=Window(Path(tmp)/'settings.json');w.settings.data['sounds']=False;w.error=lambda message: (_ for _ in ()).throw(AssertionError(message))
    w.project.video='fixture';w.project.duration=90
    w.project.cues=[Cue(10,14,'Original description.'),Cue(20,24,'Verify this.',disposition='unresolved',uncertainty='Identity uncertain')]
    w.refresh();w.choose(0)
    return app,w


def test_live_edits_undo_sort_and_save():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            w.text.setPlainText('Corrected description.')
            assert w.project.cues[0].text=='Corrected description.'
            w.undo_stack.undo();assert w.text.toPlainText()=='Original description.'
            w.undo_stack.redo();assert w.text.toPlainText()=='Corrected description.'
            w.start.setText('12');assert w.project.cues[0].start==12
            w.project_path=Path(tmp)/'save.adproject';assert w.save_project()
            from describer.project import Project
            assert Project.load(w.project_path).cues[0].start==12
            assert str(w.project_path.resolve()) in w.settings.data['recent_projects']
        finally:w.dirty=False;w.close();app.processEvents()


def test_add_review_filter_and_timeline_keyboard_targets():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            w.add_at_playhead();assert len(w.project.cues)==3
            w.cue_filter.setCurrentIndex(1);assert len(w.visible_indices)==2
            assert all(b.accessibleName().startswith('Description ') for b in w.timeline.blocks)
            w.choose(w.visible_indices[0]);w.mark_checked()
            assert len(w.visible_indices)==1
            w.undo_stack.undo();assert len(w.visible_indices)==2
        finally:w.dirty=False;w.close();app.processEvents()


def test_export_blocks_unresolved_media_but_allows_text():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp);observed=[]
        def inspect():
            d=QApplication.activeModalWidget();assert isinstance(d,QDialog)
            formats=d.findChildren(QListWidget)[0]
            path=next(x for x in d.findChildren(QLineEdit) if x.accessibleName()=='Export save path')
            go=next(x for x in d.findChildren(QPushButton) if x.text()=='Export')
            path.setText(str(Path(tmp)/'output.mp4'));observed.append(not go.isEnabled())
            formats.setCurrentRow(5);path.setText(str(Path(tmp)/'output.txt'));observed.append(go.isEnabled());d.reject()
        try:
            QTimer.singleShot(0,inspect);w.export();assert observed==[True,True]
        finally:w.dirty=False;w.close();app.processEvents()


def test_settings_categories_and_draft_cancel_keep_widgets_alive():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        def close():QApplication.activeModalWidget().reject()
        try:
            QTimer.singleShot(0,close);w.edit_settings('Developer API')
            QTimer.singleShot(0,close);w.draft_dialog()
            assert w.model_picker.scope.count()==3
            w.refresh();assert w.project.cues[0].text=='Original description.'
        finally:w.dirty=False;w.close();app.processEvents()


def test_timeline_zoom_scroll_and_selection_follow():
    from PySide6.QtCore import QPointF, QPoint, Qt
    from PySide6.QtGui import QWheelEvent
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            w.project.duration=600;w.timeline.view_seconds=90;w.timeline.resize(800,238);w.timeline.set_view(200)
            anchor=w.timeline.seconds_at(400);old_span=w.timeline.span()
            event=QWheelEvent(QPointF(400,80),QPointF(400,80),QPoint(),QPoint(0,120),Qt.NoButton,Qt.ControlModifier,Qt.NoScrollPhase,False)
            w.timeline.wheelEvent(event)
            assert w.timeline.span()<old_span
            assert abs(w.timeline.seconds_at(400)-anchor)<.002
            w.timeline.ensure_visible(550)
            assert w.timeline.view_start<=550<w.timeline.view_start+w.timeline.span()
            w.choose(0)
            assert w.timeline.view_start<=10<w.timeline.view_start+w.timeline.span()
        finally:w.dirty=False;w.close();app.processEvents()


def test_visual_hierarchy_start_state_caption_and_fit_spacing():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            w.show();app.processEvents();w.show_start();app.processEvents()
            assert not w.editor_toolbar.isVisible()
            assert w.recent_empty.isVisible()
            for name in ('Theme','Settings'):
                control=next(b for b in w.findChildren(QPushButton) if b.accessibleName()==name)
                assert not control.text() and control.property('role')=='ghost'
            w.pages.setCurrentIndex(1);w.current.setText('');w.presentation_position(0)
            assert not w.current.isVisible()
            w.presentation_position(10000)
            assert w.current.isVisible()
            cues=w.project.cues;w.project.cues=[];w.refresh();assert not w.current.isVisible();w.project.cues=cues;w.refresh()
            assert not w.fit_bar.isTextVisible()
            assert w.fit_label.geometry().bottom()<w.fit_bar.geometry().top()
            assert w.export_button.property('role')=='primary'
            assert w.cue_list.item(0).data(256).text=='Original description.'
        finally:w.dirty=False;w.close();app.processEvents()
