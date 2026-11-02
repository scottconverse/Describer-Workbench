"""Regressions for the bounded first-use/recovery handoff."""
from dataclasses import asdict
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QMessageBox
from describer.engine.service import DescriptionService
from describer.project import Cue, Project
from test_desktop_redesign import make_window


def test_service_edit_keeps_review_provenance(tmp_path):
    source=tmp_path/'source.mp4';source.write_bytes(b'unchanged source')
    cue=Cue(1,3,'Uncertain.',event_id='a',evidence='shape',uncertainty='identity',disposition='unresolved')
    service=DescriptionService(tmp_path/'engine')
    try:
        job=service.submit(project=Project(str(source),10,[cue]),operation='export',export_format='txt')
        service.wait(job['id'])
        revision=service.get_job(job['id'])['revision']
        service.edit(job['id'],revision,cues=[{'start':1,'end':3,'text':'Uncertain!'}])
        result=service.result(job['id']).cues[0]
        assert (result.event_id,result.evidence,result.uncertainty,result.disposition)==('a','shape','identity','unresolved')
        assert result.audio==''
        with pytest.raises(ValueError):service.edit(job['id'],revision,cues=[])
    finally:service.close()


@pytest.mark.parametrize('bad', ['{', '[]', '{"state":"done"}'])
def test_damaged_jobs_preserved_while_valid_work_continues(tmp_path,bad):
    root=tmp_path/'engine';damaged=root/('a'*32);damaged.mkdir(parents=True)
    record=damaged/'job.json';record.write_text(bad)
    source=tmp_path/'source.mp4';source.write_bytes(b'original')
    service=DescriptionService(root)
    try:
        assert len(service.damaged_jobs)==1
        assert service.list_jobs()==[]
        with pytest.raises(ValueError,match='Damaged'):service.get_job('a'*32)
        job=service.submit(project=Project(str(source),10,[Cue(1,2,'Text')]),operation='export',export_format='txt')
        service.wait(job['id']);assert len(service.list_jobs())==1
        with pytest.raises(RuntimeError):DescriptionService(root)
    finally:service.close()
    service=DescriptionService(root)
    try:
        assert service.result(job['id']).cues[0].text=='Text'
        assert record.read_text()==bad and source.read_bytes()==b'original'
    finally:service.close()


def test_scene_reset_for_video_and_project_and_stale_callback(tmp_path):
    app,w=make_window(tmp_path);source=tmp_path/'source.mp4';source.write_bytes(b'fixture')
    def stale():
        w.answer=('Old answer',1);w.history=[{'question':'old','answer':'old'}]
        w.conversation.setPlainText('old');w.add_answer_button.setEnabled(True)
    try:
        with patch('describer.services.probe',return_value=10):
            stale();w.set_video(source)
            assert not hasattr(w,'answer') and not w.add_answer_button.isEnabled() and not w.conversation.toPlainText()
            project=tmp_path/'new.adproject';Project(str(source),10).save(project)
            stale();w._recent_path=str(project);w.load_project()
            assert not hasattr(w,'answer') and not w.history and not w.add_answer_button.isEnabled()
            callbacks=[];w.cloud_confirm=lambda:True;w.job=lambda task,done:callbacks.append(done)
            w.scene_request('ask',lambda result:w.history.append(result))
            w.set_video(source);callbacks[0]('stale')
            assert not w.history
    finally:w.dirty=False;w.close();app.processEvents()


def test_export_decline_preserves_bytes_and_source_identity(tmp_path):
    app,w=make_window(tmp_path);target=tmp_path/'existing.txt';target.write_bytes(b'original')
    try:
        for answer in (QMessageBox.No,QMessageBox.Cancel):
            with patch.object(QMessageBox,'question',return_value=answer):
                assert not w.validate_export_destination(target,'txt')
                w.export_to(str(target))
            assert target.read_bytes()==b'original'
        w.project.video=str(target)
        with pytest.raises(ValueError,match='original media'):w.validate_export_destination(target,'txt')
        with pytest.raises(ValueError,match='extension'):w.validate_export_destination(tmp_path/'wrong.wav','txt')
        assert not list(tmp_path.glob('.describer-write-*'))
    finally:w.dirty=False;w.close();app.processEvents()


def test_scene_answer_end_is_explained_without_invalid_cue(tmp_path):
    app,w=make_window(tmp_path);errors=[];w.error=errors.append
    try:
        before=[asdict(c) for c in w.project.cues]
        w.add_scene_answer('Answer',w.project.duration,w.add_answer_button)
        assert errors and [asdict(c) for c in w.project.cues]==before
        w.add_scene_answer('Answer',1,w.add_answer_button)
        assert any(c.text=='Answer' and c.disposition=='unresolved' for c in w.project.cues)
    finally:w.dirty=False;w.close();app.processEvents()


def test_draft_cancel_keeps_disk_and_exact_model_test_snapshot(tmp_path):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication,QListWidget,QPushButton,QRadioButton
    app,w=make_window(tmp_path);w.settings.save();before=w.settings.path.read_bytes();calls=[]
    w.job=lambda task,done:calls.append(task)
    def interact():
        dialog=QApplication.activeModalWidget()
        next(b for b in dialog.findChildren(QRadioButton) if b.accessibleName()=='Ollama').setChecked(True)
        models=next(x for x in dialog.findChildren(QListWidget) if x.accessibleName()=='Discovered exact models')
        models.item(0).setText('exact-model:custom-tag')
        next(b for b in dialog.findChildren(QPushButton) if b.text()=='Test connection').click()
        assert w.model_picker.data['ollama_model']=='exact-model:custom-tag'
        assert w.settings.path.read_bytes()==before
        dialog.reject()
    try:
        QTimer.singleShot(0,interact);w.draft_dialog()
        assert w.settings.path.read_bytes()==before
        assert w.model_picker.data==w.settings.data
        observed=[]
        with patch('describer.model_picker.model_info',side_effect=lambda data:observed.append(data) or {}):calls[0](None,None)
        assert observed[0]['ollama_model']=='exact-model:custom-tag'
        w.model_picker.provider.setCurrentText('Gemini');calls.clear()
        w.model_picker.refresh();w.model_picker.test();assert calls==[]
    finally:w.dirty=False;w.close();app.processEvents()


@pytest.mark.parametrize('rows', [[],RuntimeError('unavailable')])
def test_failed_voice_discovery_cannot_enable_media(tmp_path,rows):
    import time
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDialog
    from describer.desktop import ExportVoices
    app,w=make_window(tmp_path);d=QDialog(w)
    def discover(*args,**kwargs):
        if isinstance(rows,Exception):raise rows
        return rows
    with patch('describer.windows_speech.windows_speech',side_effect=discover):
        picker=ExportVoices(w,d)
        try:
            deadline=time.monotonic()+3
            while picker.loading and time.monotonic()<deadline:app.processEvents();QTest.qWait(10)
            assert not picker.loading and not picker.usable()
            assert picker.voice.currentData() is None
            picker.engine.setCurrentText('OpenAI');assert picker.usable()
        finally:picker.shutdown();d.close();w.dirty=False;w.close();app.processEvents()


def test_script_export_does_not_require_speech_consent(tmp_path):
    source=tmp_path/'source.mp4';source.write_bytes(b'original')
    service=DescriptionService(tmp_path/'engine',{'voice_engine':'OpenAI','allow_cloud':False})
    try:
        with patch('describer.services.synthesize',side_effect=AssertionError('No speech allowed')):
            job=service.submit(project=Project(str(source),10,[Cue(1,2,'Caption')]),operation='export',export_format='srt')
            service.wait(job['id'])
            assert service.get_job(job['id'])['state']=='done'
        with pytest.raises(ValueError,match='OpenAI speech'):
            service.submit(project=Project(str(source),10),operation='voice-preview')
    finally:service.close()


def test_detector_cancel_or_bad_hash_preserves_selected_asset(tmp_path):
    import io
    import threading
    from describer.engine.assets import provision
    target=tmp_path/'custom.onnx';target.write_bytes(b'previous asset')
    cancel=threading.Event();cancel.set()
    with pytest.raises(InterruptedError):provision(target,cancel)
    cancel.clear()
    with patch('urllib.request.urlopen',return_value=io.BytesIO(b'invalid download')):
        with pytest.raises(ValueError,match='checksum'):provision(target,cancel)
    assert target.read_bytes()==b'previous asset'
    assert not list(tmp_path.glob('*.download'))
