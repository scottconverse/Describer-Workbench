import tempfile
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox,QTableWidget

from describer.editor_selection import CueSelection
from describer.project import Cue,Project
from test_desktop_redesign import make_window


def test_selection_tracks_identity_and_falls_back_only_after_removal():
    cues=[Cue(1,2,'One'),Cue(3,4,'Two')];selection=CueSelection()
    selection.select(cues,1);ident=selection.cue_id
    cues.reverse();selection.reconcile(cues)
    assert selection.index(cues)==0 and selection.cue_id==ident
    cues.pop(0);selection.reconcile(cues);assert selection.index(cues)==0
    cues.clear();selection.reconcile(cues);assert selection.index(cues)==-1


def test_visible_editor_sort_filter_delete_and_undo_keep_identity():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            assert not w.findChildren(QTableWidget)
            w.choose(1);ident=w.project.cues[1].cue_id
            w.start.setText('5')
            assert w.selected_index()==0 and w.project.cues[0].cue_id==ident
            w.undo_stack.undo()
            assert w.selected_index()==1 and w.project.cues[1].cue_id==ident
            w.cue_filter.setCurrentIndex(1)
            assert w.selected_index()==1 and w.cue_list.currentRow()==0
            with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):w.delete_cue()
            assert len(w.project.cues)==1 and w.selected_index()==0
            w.undo_stack.undo();w.choose(1)
            assert w.project.cues[w.selected_index()].cue_id==ident
            assert w.text.toPlainText()=='Verify this.'
        finally:w.dirty=False;w.close();app.processEvents()


def test_loading_another_project_cannot_save_previous_editor_text(tmp_path):
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        source=tmp_path/'source.mp4';source.write_bytes(b'video fixture')
        target=tmp_path/'second.adproject'
        Project(str(source),90,[Cue(1,3,'Second project text.').validate(90)]).save(target)
        try:
            w.choose(1);w.dirty=False;w._recent_path=str(target)
            with patch('describer.services.probe',return_value=90):w.load_project()
            assert w.text.toPlainText()=='Second project text.'
            assert w.save_project()
            assert Project.load(target).cues[0].text=='Second project text.'
        finally:w.dirty=False;w.close();app.processEvents()
