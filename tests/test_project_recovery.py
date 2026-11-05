import copy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QPushButton
from describer.project import Project, Cue
from describer.project_recovery import DraftStore
from test_desktop_redesign import make_window


def test_bounded_atomic_snapshots_and_identity(tmp_path):
    source=tmp_path/'video.mp4';source.write_bytes(b'untouched source')
    project=Project(str(source),90,[Cue(1,4,'First').validate(90)],'Name: detail',[{'cue_id':'evidence'}],{'requires_replan':True})
    original=tmp_path/'original.adproject';project.save(original);saved=original.read_bytes()
    store=DraftStore(tmp_path/'drafts')
    for i in range(5):
        project.cues[0].text=str(i);store.snapshot(project,original)
    assert len(store.entries())==3
    latest,meta=store.entries()[0];recovered,_=DraftStore(store.root).load(latest)
    assert recovered.cues==project.cues and recovered.cues[0].cue_id==project.cues[0].cue_id
    assert original.read_bytes()==saved and source.read_bytes()==b'untouched source'
    assert store.snapshot(project,original) is None
    previous=latest.read_bytes();project.cues[0].text='new'
    with patch('describer.project_recovery.atomic_json',side_effect=OSError('disk full')):
        with pytest.raises(OSError):store.snapshot(project,original)
    assert latest.read_bytes()==previous
    for i in range(25):store.snapshot(Project(str(source),90,[Cue(1,4,str(i))]),str(tmp_path/f'{i}.adproject'))
    assert len(store.entries())<=20
    store.max_bytes=10000
    store.snapshot(Project(str(source),90,[Cue(1,4,'bounded')]),'new')
    assert sum(p.stat().st_size for p,_ in store.entries())<=10000
    with pytest.raises(ValueError):store.load(original)
    assert meta['media_stat']==[source.stat().st_size,source.stat().st_mtime_ns]


def test_save_as_failure_cancel_and_glossary_undo():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            old=Path(tmp)/'old.adproject';new=Path(tmp)/'new.adproject'
            assert w.save_project(destination=old);original=old.read_bytes()
            w.text.setPlainText('A changed description.')
            with patch('describer.app.QFileDialog.getSaveFileName',return_value=('','')):assert not w.save_project_as()
            assert w.project_path==old and old.read_bytes()==original
            with patch('describer.app.QFileDialog.getSaveFileName',return_value=(str(new),'')):
                with patch.object(Project,'save',side_effect=OSError('disk full')),patch.object(w,'error'):
                    assert not w.save_project_as()
                assert w.project_path==old and w.dirty
                assert w.save_project_as()
            assert old.read_bytes()==original and Project.load(new).cues[0].text=='A changed description.'
            w.project.glossary='First: Red coat\nSecond: Blue hat';w.sync_glossary()
            cues=copy.deepcopy(w.project.cues);coverage=copy.deepcopy(w.project.coverage)
            card=w.glossary_list.itemAt(0).widget()
            next(b for b in card.findChildren(QPushButton) if b.text()=='Delete character').click()
            assert w.project.glossary=='Second: Blue hat'
            w.undo_stack.undo();assert w.project.glossary=='First: Red coat\nSecond: Blue hat'
            w.undo_stack.redo();assert 'First' not in w.project.glossary
            assert w.project.cues==cues and w.project.coverage==coverage
        finally:w.dirty=False;w.close();app.processEvents()


def test_recover_unsaved_pending_editor_and_changed_media():
    with tempfile.TemporaryDirectory() as tmp:
        app,w=make_window(tmp)
        try:
            source=Path(tmp)/'video';source.write_bytes(b'media')
            w.project.video=str(source);w.project.cues[0].review_status='approved'
            w.start.setText('invalid');w.text.setPlainText('Pending text preserved.');w.dirty=True
            w.snapshot_draft();rows=w.draft_store.entries();assert len(rows)==1
            meta=rows[0][1];assert meta['editor']['start']=='invalid' and meta['editor']['text']=='Pending text preserved.'
            w.dirty=False
            def select(*args):return args[3][0],True
            with patch('describer.app.QInputDialog.getItem',side_effect=select),patch('describer.services.probe',return_value=90):w.recover_unsaved()
            assert w.project_path is None and w.dirty and w.start.text()=='invalid'
            assert w.text.toPlainText()=='Pending text preserved.' and w.project.cues[0].review_status=='approved'
            w.dirty=False;before=copy.deepcopy(w.project);source.write_bytes(b'changed media')
            with patch('describer.app.QInputDialog.getItem',side_effect=select),patch.object(w,'error') as error:w.recover_unsaved()
            assert error.called and w.project==before
            assert json.loads(rows[0][0].read_text())['version']==2
        finally:w.dirty=False;w.close();app.processEvents()
