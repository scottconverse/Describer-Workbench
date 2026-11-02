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
