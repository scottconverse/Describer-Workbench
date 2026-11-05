"""Regressions for the bounded first-use/recovery handoff."""
from dataclasses import asdict
from pathlib import Path
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
            callbacks=[];w.operation_preflight=lambda settings,done:done();w.job=lambda task,done:callbacks.append(done)
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
        sidecar=tmp_path/'fresh.txt.coverage.json';sidecar.write_bytes(b'prior coverage')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):
            assert not w.validate_export_destination(tmp_path/'fresh.txt','txt')
        assert sidecar.read_bytes()==b'prior coverage' and not (tmp_path/'fresh.txt').exists()
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
    from PySide6.QtWidgets import QApplication,QPushButton,QRadioButton,QLineEdit
    app,w=make_window(tmp_path);w.settings.save();before=w.settings.path.read_bytes();calls=[]
    w.job=lambda task,done:calls.append(task)
    def interact():
        dialog=QApplication.activeModalWidget()
        next(b for b in dialog.findChildren(QRadioButton) if b.accessibleName()=='Ollama').setChecked(True)
        editor=next(x for x in dialog.findChildren(QLineEdit) if x.accessibleName()=='Exact analysis model ID')
        editor.setText('exact-model:custom-tag');editor.editingFinished.emit()
        next(b for b in dialog.findChildren(QPushButton) if b.text()=='Test connection').click()
        assert w.model_picker.data['ollama_model']=='exact-model:custom-tag'
        assert w.settings.path.read_bytes()==before
        dialog.reject()
    try:
        observed=[]
        with patch('describer.model_picker.model_info',side_effect=lambda data:observed.append(data) or {}):
            QTimer.singleShot(0,interact);w.draft_dialog()
            calls[0](None,None)
        assert w.settings.path.read_bytes()==before
        assert w.model_picker.data==w.settings.data
        assert observed[0]['ollama_model']=='exact-model:custom-tag'
        w.model_picker.provider.setCurrentText('Gemini');calls.clear()
        w.model_picker.refresh();w.model_picker.test();assert calls==[]
    finally:w.dirty=False;w.close();app.processEvents()


@pytest.mark.parametrize('rows', [[],RuntimeError('unavailable'),[{'id':'available','name':'Available voice'}]])
def test_failed_voice_discovery_cannot_enable_media(tmp_path,rows):
    import time
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDialog
    from describer.desktop import ExportVoices
    app,w=make_window(tmp_path);d=QDialog(w);w.settings.data['windows_voice']='removed-voice'
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
    class CancelDuringRead(io.BytesIO):
        def read(self,size=-1):
            block=super().read(size);cancel.set();return block
    with patch('urllib.request.urlopen',return_value=CancelDuringRead(b'transfer in progress')):
        with pytest.raises(InterruptedError):provision(target,cancel)
    assert target.read_bytes()==b'previous asset' and not list(tmp_path.glob('*.download'))


def test_preflight_declined_detector_does_not_call_provider_or_change_project(tmp_path):
    import copy
    import threading
    app,w=make_window(tmp_path);started=[];before=copy.deepcopy(w.project)
    w.job=lambda task,done:done(task(threading.Event(),lambda text:None))
    w.after_job=lambda callback:callback()
    try:
        with patch('describer.engine.assets.speech_model',side_effect=ValueError('missing')),patch.object(QMessageBox,'question',return_value=QMessageBox.Cancel),patch('describer.models.model_info',side_effect=AssertionError('No provider call')):
            w.operation_preflight(copy.deepcopy(w.settings.data),lambda:started.append(True),narration=True,detector=True)
        assert not started and w.project==before
    finally:w.dirty=False;w.close();app.processEvents()


def test_preflight_reports_both_cloud_destinations_and_decline_stops(tmp_path):
    import copy
    import threading
    app,w=make_window(tmp_path);started=[];messages=[]
    w.settings.data.update(analysis_provider='Gemini',gemini_key='fixture-key',voice_engine='OpenAI',openai_key='fixture-key')
    w.job=lambda task,done:done(task(threading.Event(),lambda text:None));w.after_job=lambda callback:callback()
    try:
        with patch.object(QMessageBox,'question',side_effect=lambda parent,title,message:messages.append(message) or QMessageBox.No),patch('describer.services.synthesize',side_effect=AssertionError('No synthesis')):
            w.operation_preflight(copy.deepcopy(w.settings.data),lambda:started.append(True),narration=True)
        assert not started and 'Google Gemini' in messages[0] and 'OpenAI' in messages[0]
    finally:w.dirty=False;w.close();app.processEvents()


def test_missing_narration_key_prevents_observation(tmp_path):
    import threading
    from describer.engine.core import describe
    with patch('describer.services.observe',side_effect=AssertionError('Must not observe')):
        with pytest.raises(ValueError,match='API key'):
            describe(Project('unused',10),{'voice_engine':'OpenAI','openai_key':''},'',tmp_path,threading.Event(),lambda text:None)


def test_readiness_does_not_equate_presence_with_verification(tmp_path):
    from describer.engine.assets import detector_state,validate_detector
    app,w=make_window(tmp_path);asset=tmp_path/'bad.onnx';asset.write_bytes(b'bad')
    try:
        w.settings.data.update(sound_model=str(asset),ollama_model='unverified:tag')
        assert detector_state(w.settings.data)=='configured (not verified)'
        w.update_status()
        assert not w.setup_checks['Speech detector'].isChecked()
        assert not w.setup_checks['Ollama'].isChecked()
        assert not w.setup_checks['Windows voices'].isChecked()
        with pytest.raises(ValueError,match='checksum'):validate_detector(w.settings.data)
        assert detector_state(w.settings.data)=='error'
        asset.write_bytes(b'changed')
        assert detector_state(w.settings.data)=='configured (not verified)'
    finally:w.dirty=False;w.close();app.processEvents()


@pytest.mark.skipif(__import__('sys').platform!='win32',reason='Windows signed updater only; Unix manual-download boundary has its own test')
def test_missing_update_feed_checks_official_release(tmp_path):
    app,w=make_window(tmp_path);w.settings.data['update_feed']='';messages=[];calls=[]
    try:
        w.job=lambda task,done:calls.append((task,done));w.log=messages.append
        with patch('describer.updates.read_feed',return_value={'newer':False}) as read:
            w.check_updates();calls[0][1](calls[0][0](None,None))
        read.assert_called_once_with('')
        assert 'official GitHub release' in messages[0]
    finally:w.dirty=False;w.close();app.processEvents()


def test_repair_uses_common_service_preserves_cues_without_vision(tmp_path):
    import copy
    import threading
    source=tmp_path/'source.mp4';source.write_bytes(b'source')
    original=Project(str(source),10,[Cue(1,3,'A visible door.',event_id='door',evidence='visible frame',audio='missing.wav',disposition='in-gap')])
    def plan(project,settings,root,cancel,log):
        root.mkdir(parents=True,exist_ok=True);audio=root/'repaired.wav';audio.write_bytes(b'fixture audio')
        project.cues[0].audio=str(audio);return project
    service=DescriptionService(tmp_path/'engine')
    try:
        with patch('describer.services.narration_preflight'),patch('describer.engine.core.plan_export',side_effect=plan),patch('describer.services.observe',side_effect=AssertionError('No vision')):
            result=service.repair_narration(copy.deepcopy(original),{},threading.Event(),lambda text:None)
        assert result.cues[0].text==original.cues[0].text and result.cues[0].evidence=='visible frame'
        assert result.cues[0].event_id=='door' and Path(result.cues[0].audio).is_file()
        assert source.read_bytes()==b'source' and original.cues[0].audio=='missing.wav'
    finally:service.close()


def test_desktop_resume_reopened_owner_retains_checkpoints_and_original_settings(tmp_path):
    import threading
    from describer.engine.core import Checkpoints,sha
    source=tmp_path/'source.mp4';source.write_bytes(b'source')
    project=Project(str(source),10,[Cue(1,2,'Original.')]);calls=[];fail=[True]
    def describe(project,settings,prompt,root,cancel,log,start,duration):
        checkpoint=Checkpoints(root,{'source':sha(project.video),'model':settings['model']})
        checkpoint.stage('observed',lambda:calls.append('observe') or {'complete':True})
        if fail[0]:raise RuntimeError('transient speech failure')
        project.cues=[Cue(1,2,'Recovered').validate(project.duration)];return project
    service=DescriptionService(tmp_path/'engine')
    with patch('describer.engine.core.describe',side_effect=describe):
        job=service.submit(project=project,settings={'allow_cloud':True,'model':'original-exact-model'})
        with pytest.raises(RuntimeError,match='transient'):service.wait(job['id'])
        service.close();service=DescriptionService(tmp_path/'engine');fail[0]=False
        app,w=make_window(tmp_path/'ui');w.settings.data['model']='different-current-model'
        w.operation_preflight=lambda settings,done,**kwargs:done()
        w.job=lambda task,done:done(task(threading.Event(),lambda text:None))
        try:
            with patch('describer.engine.get_service',return_value=service),patch('describer.app.QInputDialog.getItem',side_effect=lambda *args:(args[3][0],True)),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes),patch('describer.drafting.review_proposal',side_effect=lambda window,proposal:proposal.apply(window.project,set(proposal.candidates),set(proposal.existing),False)):
                w.recover_jobs()
            assert w.project.cues[0].text=='Recovered' and w.dirty and w.project_path is None
            assert calls==['observe']
            assert w.settings.data['model']=='different-current-model'
            assert service.get_job(job['id'])['settings']['model']=='original-exact-model'
        finally:w.dirty=False;w.close();app.processEvents();service.close()


def test_draft_cancel_discards_late_model_test_callback(tmp_path):
    app,w=make_window(tmp_path);callbacks=[]
    try:
        w.model_picker.begin_draft();w.model_picker.provider.setCurrentText('Ollama');w.model_picker.store_model('chosen:exact')
        w.job=lambda task,done:callbacks.append(done)
        w.model_picker.test();w.model_picker.end_draft(False)
        with patch.object(w,'confirm_ollama',side_effect=AssertionError('No late consent')):callbacks[0]({'capabilities':['vision']})
        assert not getattr(w,'pending_model_test',None)
    finally:w.dirty=False;w.close();app.processEvents()


@pytest.mark.parametrize('cues,edit', [
    ([Cue(1,3,'Uncertain',uncertainty='identity',disposition='unresolved')],[{'start':2,'end':4,'text':'Uncertain'}]),
    ([Cue(1,3,'One',uncertainty='identity',disposition='unresolved'),Cue(1,3,'Two')],[{'start':1,'end':3,'text':'One!'},{'start':1,'end':3,'text':'Two'}])])
def test_service_ambiguous_edits_never_clear_review(tmp_path,cues,edit):
    source=tmp_path/'source';source.write_bytes(b'original');service=DescriptionService(tmp_path/'engine')
    try:
        job=service.submit(project=Project(str(source),10,cues),operation='export',export_format='txt');service.wait(job['id'])
        try:service.edit(job['id'],service.get_job(job['id'])['revision'],cues=edit)
        except ValueError:pass  # Explicit ambiguity rejection preserves the old result.
        result=service.result(job['id'])
        assert any(c.uncertainty=='identity' and c.disposition=='unresolved' for c in result.cues)
    finally:service.close()


def test_cli_provision_optional_cancel_reaches_download(tmp_path):
    import io
    from describer.engine.assets import provision
    with patch('urllib.request.urlopen',return_value=io.BytesIO(b'bad')) as opened:
        with pytest.raises(ValueError,match='checksum'):provision(tmp_path/'asset.onnx')
    assert opened.called


def test_export_does_not_use_existing_partial_as_scratch(tmp_path):
    import threading
    source=tmp_path/'output.txt.partial';source.write_bytes(b'original-media')
    service=DescriptionService(tmp_path/'engine')
    try:
        service.export(Project(str(source),10,[Cue(1,2,'Caption')]),tmp_path/'output.txt',{},threading.Event(),lambda text:None)
        assert source.read_bytes()==b'original-media'
    finally:service.close()


def test_resume_rechecks_speech_permission(tmp_path):
    source=tmp_path/'source';source.write_bytes(b'original');service=DescriptionService(tmp_path/'engine')
    try:
        with patch('describer.services.synthesize',side_effect=RuntimeError('voice unavailable')):
            job=service.submit(project=Project(str(source),10),operation='voice-preview',settings={'voice_engine':'Windows','allow_cloud':False})
            with pytest.raises(RuntimeError):service.wait(job['id'])
        with patch('describer.services.synthesize',side_effect=AssertionError('No speech call')),pytest.raises(ValueError,match='OpenAI speech'):
            service.resume(job['id'],settings={'voice_engine':'OpenAI','openai_key':'fixture','allow_cloud':False})
    finally:service.close()


def test_discovery_registry_prevents_main_close_until_worker_terminal(tmp_path):
    import threading,time
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDialog
    from describer.desktop import ExportVoices
    app,w=make_window(tmp_path);d=QDialog(w);entered=threading.Event();release=threading.Event()
    def discover(*args,**kwargs):
        entered.set();assert release.wait(3);return []
    with patch('describer.windows_speech.windows_speech',side_effect=discover):
        picker=ExportVoices(w,d)
        try:
            assert entered.wait(3)
            assert not picker.shutdown()
            event=QCloseEvent();w.closeEvent(event)
            assert not event.isAccepted() and picker in w.voice_discoveries
            release.set();deadline=time.monotonic()+3
            while picker.thread is not None and time.monotonic()<deadline:app.processEvents();QTest.qWait(10)
            assert not w.voice_discoveries and picker.thread is None
        finally:release.set();picker.shutdown();d.close();w.dirty=False;w.close();app.processEvents()


def test_refresh_keeps_visible_exact_id_even_when_not_discovered(tmp_path):
    from PySide6.QtCore import QTimer,Qt
    from PySide6.QtWidgets import QApplication,QListWidget
    app,w=make_window(tmp_path);w.model_picker.provider.setCurrentText('Ollama');w.model_picker.store_model('B')
    def interact():
        dialog=QApplication.activeModalWidget();visible=next(x for x in dialog.findChildren(QListWidget) if x.accessibleName()=='Discovered exact models')
        rows=[dict(name=name,cloud=False,vision=True,loaded=False) for name in ('A','B')]
        w.model_picker.discovered(rows)
        assert visible.currentItem().data(Qt.UserRole)=='B'
        assert 'vision' in visible.currentItem().text() and 'local' in visible.currentItem().text()
        w.model_picker.store_model('manual:exact');w.model_picker.discovered(rows)
        assert visible.currentItem().text()=='manual:exact'
        w.model_picker.discovered([])
        assert visible.currentItem().text()=='manual:exact'
        dialog.reject()
    try:QTimer.singleShot(0,interact);w.draft_dialog()
    finally:w.dirty=False;w.close();app.processEvents()


def test_background_preflight_cancel_stays_responsive_and_does_not_launch(tmp_path):
    import copy,threading,time
    from PySide6.QtCore import QTimer
    from PySide6.QtTest import QTest
    app,w=make_window(tmp_path);w.settings.data.update(analysis_provider='Ollama',ollama_model='vision:exact')
    entered=threading.Event();release=threading.Event();ticks=[];launched=[];errors=[];w.error=errors.append
    def slow(settings):entered.set();assert release.wait(3);return {'capabilities':['vision']}
    timer=QTimer();timer.setInterval(10);timer.timeout.connect(lambda:ticks.append(1));timer.start()
    with patch('describer.models.model_info',side_effect=slow):
        try:
            w.operation_preflight(copy.deepcopy(w.settings.data),lambda:launched.append(True))
            assert entered.wait(3)
            deadline=time.monotonic()+1
            while len(ticks)<3 and time.monotonic()<deadline:app.processEvents();QTest.qWait(10)
            assert len(ticks)>=3
            w.cancel.set();release.set();deadline=time.monotonic()+3
            while w.thread is not None and time.monotonic()<deadline:app.processEvents();QTest.qWait(10)
            assert w.thread is None and not launched
        finally:release.set();timer.stop();w.dirty=False;w.close();app.processEvents()


def test_detector_install_then_continue_only_after_verification(tmp_path):
    import copy,threading
    app,w=make_window(tmp_path);w.settings.data.update(analysis_provider='Ollama',ollama_model='vision:exact',sound_model=str(tmp_path/'custom.onnx'))
    events=[];checks=[False]
    def validate(settings):
        events.append('verify')
        if not checks[0]:raise ValueError('missing')
    def provision(target,cancel):
        assert target==str(tmp_path/'custom.onnx');events.append('install');checks[0]=True;return Path(target)
    w.job=lambda task,done:done(task(threading.Event(),lambda text:None));w.after_job=lambda callback:callback()
    try:
        with patch('describer.engine.assets.validate_detector',side_effect=validate),patch('describer.engine.assets.provision',side_effect=provision),patch('describer.models.model_info',return_value={'capabilities':['vision']}),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):
            w.operation_preflight(copy.deepcopy(w.settings.data),lambda:events.append('launch'),detector=True)
        assert events==['verify','install','verify','launch']
    finally:w.dirty=False;w.close();app.processEvents()


def test_export_inline_error_keeps_configuration(tmp_path):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication,QListWidget,QLineEdit,QPushButton,QLabel
    app,w=make_window(tmp_path);observed=[]
    def interact():
        dialog=QApplication.activeModalWidget();formats=dialog.findChildren(QListWidget)[0];formats.setCurrentRow(5)
        path=next(x for x in dialog.findChildren(QLineEdit) if x.accessibleName()=='Export save path');path.setText(str(tmp_path/'wrong.wav'))
        next(b for b in dialog.findChildren(QPushButton) if b.text()=='Export').click()
        observed.append(dialog.isVisible() and path.text().endswith('wrong.wav') and any('extension' in label.text() for label in dialog.findChildren(QLabel)))
        dialog.reject()
    try:QTimer.singleShot(0,interact);w.export();assert observed==[True]
    finally:w.dirty=False;w.close();app.processEvents()


def test_api_bind_failure_can_retry_without_stopping_port_owner(tmp_path):
    import socket,time
    app,w=make_window(tmp_path);errors=[];w.error=errors.append
    service=DescriptionService(tmp_path/'api-engine')
    occupied=socket.socket();occupied.bind(('127.0.0.1',8796));occupied.listen()
    try:
        with patch('describer.engine.get_service',return_value=service),patch('sys.stdout',None),patch('sys.stderr',None):
            w.start_api();deadline=time.monotonic()+5
            while w.api_thread is not None and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
            assert errors and w.api_thread is None and not w.api_ready
            assert occupied.getsockname()[1]==8796
            occupied.close();w.start_api();deadline=time.monotonic()+5
            while not w.api_ready and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
            assert w.api_ready and w.api_thread.is_alive()
            assert w.stop_api() and not w.api_ready
    finally:occupied.close();w.stop_api();service.close();w.dirty=False;w.close();app.processEvents()


@pytest.mark.parametrize('message,expected',[('Sign in to confirm not a bot?token=secret','account access'),('JavaScript runtime unavailable','runtime'),('Connection timed out','connection')])
def test_download_failure_guidance_is_sanitized(tmp_path,message,expected):
    import threading
    from unittest.mock import MagicMock
    from describer.services import download
    downloader=MagicMock();downloader.__enter__.return_value.extract_info.side_effect=RuntimeError(message)
    with patch('yt_dlp.YoutubeDL',return_value=downloader):
        with pytest.raises(RuntimeError) as error:download('https://example.invalid/video',tmp_path,threading.Event(),lambda text:None)
    assert expected in str(error.value) and 'Open video' in str(error.value) and 'secret' not in str(error.value)
