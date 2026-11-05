from describer.platforms import native_engine
"""Regressions from the deeper original-spec audit; no live provider calls."""
import json
import threading
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from describer.engine.core import Checkpoints, prepare
from describer.engine.service import DescriptionService
from describer.project import Cue, Project, normalize_chunk
from describer.services import DEFAULTS, completed_google_text, video_request


@pytest.mark.parametrize('short_seconds,expected',[(1.5,'in-gap'),(3,'pause')])
def test_safe_shortening_is_measured_retains_facts_and_reuses_checkpoint(tmp_path,short_seconds,expected):
    original='The scene shows a red ball rolling left again.'
    source=Project('fixture',10,[Cue(1,3,original,event_id='first',evidence='red ball'),Cue(5,7,original,event_id='recurrence',evidence='red ball again')])
    source.cues=[cue.validate(10) for cue in source.cues]
    safety={'protected':[],'safe_gaps':[(0,10)],'classification':[]};spoken=[]
    def synth(text,path,settings,cancel):spoken.append(text);path.write_bytes(b'fixture')
    def measured(args,cancel):return json.dumps({'format':{'duration':short_seconds if '-short.wav' in args[-1] else 4}}).encode()
    with patch('describer.engine.core.protected_audio',return_value=safety),patch('describer.services.synthesize',side_effect=synth),patch('describer.services.run',side_effect=measured):
        checkpoint=Checkpoints(tmp_path,{'fixture':'shorten'})
        prepare(source,{},tmp_path,threading.Event(),lambda _:None,checkpoint)
        assert len(spoken)==4
        assert len(source.cues)==2 and all(c.text==original and c.disposition==expected for c in source.cues)
        assert [c.event_id for c in source.cues]==['first','recurrence']
        if expected=='in-gap':
            assert all(c.narration_text=='A red ball rolling left again.' and c.speed<=1.15 for c in source.cues)
        else:assert all(not c.narration_text and '-short' not in c.audio for c in source.cues)
        prepare(source,{},tmp_path,threading.Event(),lambda _:None,checkpoint)
        assert len(spoken)==4
    path=tmp_path/'project.adproject';source.save(path);reopened=Project.load(path)
    assert reopened.cues[0].narration_text==source.cues[0].narration_text
    assert not reopened.cues[0].edited(1,3,'A different event.',10).narration_text


def test_shortening_does_not_drop_negation_or_unrecognized_facts():
    from describer.engine.shortening import concise
    for text in ('The scene does not show a car.','A man opens a door, then closes it again.','We see no exit.','We see whether the door opens.'):
        assert concise(text)==text


def test_desktop_explore_reaches_shared_layout_route_with_glossary_and_persists_usage(tmp_path):
    from describer.app import Window
    from PySide6.QtWidgets import QApplication
    application=QApplication.instance() or QApplication([])
    source=tmp_path/'fixture.mp4';source.write_bytes(b'fixture')
    window=Window(tmp_path/'settings.json');window.settings.data['sounds']=False
    window.project=Project(str(source),30,glossary='Ada: a blue jacket')
    window.explore_focus.setText('the doorway');window.explore_duration.setCurrentIndex(3)
    window.operation_preflight=lambda settings,done:done()
    window.job=lambda task,done:done(task(threading.Event(),lambda _:None))
    def answer(video,prompt,settings,cancel,log):
        assert 'the doorway' in prompt and 'Ada: a blue jacket' in prompt
        assert '"objects"' in prompt
        log.usage({'provider':'fixture','requested_model':'fixture','reported_model':None,'input_tokens':11,'output_tokens':7,'total_tokens':18})
        return '{"layout":"A doorway on the left.","objects":[{"name":"door","description":"A door","x":1,"y":5}]}'
    try:
        with closing(DescriptionService(tmp_path/'engine')) as service,patch('describer.engine.get_service',return_value=service),patch('describer.services.segment') as segment,patch('describer.services.video_request',side_effect=answer):
            window.explore()
            assert segment.call_args.args[2:4]==(0,20)
            assert window.explore_host.count()==1
            assert window.project.analysis['usage'][0]['operation']=='explore'
            assert 'input 11' in window.usage_display.text()
            path=tmp_path/'scene.adproject';window.project.save(path)
            assert Project.load(path).analysis['usage'][0]['total_tokens']==18
    finally:window.dirty=False;window.close();application.processEvents()


def test_scene_cards_keep_answer_actions_attached_to_their_position(tmp_path):
    from describer.app import Window
    from PySide6.QtWidgets import QApplication,QPushButton
    application=QApplication.instance() or QApplication([])
    window=Window(tmp_path/'settings.json');window.settings.data['sounds']=False
    window.project=Project('fixture.mp4',30);window.history=[{'question':'First?','answer':'First answer.','position':3},{'question':'Second?','answer':'Second answer.','position':12}]
    window.render_scene_history();added=[];spoken=[]
    window.add_scene_answer=lambda text,position,button:added.append((text,position))
    window.playback_speech.say=lambda text,interrupt:spoken.append(text)
    try:
        first=window.scene_cards.itemAt(0).widget();second=window.scene_cards.itemAt(1).widget()
        next(b for b in first.findChildren(QPushButton) if b.text()=='Add as description').click()
        next(b for b in second.findChildren(QPushButton) if b.text()=='Speak answer').click()
        assert added==[('First answer.',3)] and spoken==['Second answer.']
        window.reset_scene();assert window.scene_cards.count()==1 and not window.history
    finally:window.dirty=False;window.close();application.processEvents()


@pytest.mark.parametrize('provider', ['unknown', '', None, 'gemini'])
def test_unknown_provider_rejected_before_dispatch_or_queue(provider, tmp_path):
    settings = dict(DEFAULTS, analysis_provider=provider, allow_cloud=False)
    source = tmp_path/'source.mp4';source.write_bytes(b'fixture')
    with patch('describer.services.google_request') as google, patch('describer.models.video_request') as ollama:
        with pytest.raises(ValueError, match='Unsupported analysis provider'):
            video_request(source, '', settings, threading.Event(), print)
        with closing(DescriptionService(tmp_path/'engine')) as service:
            with pytest.raises(ValueError, match='Unsupported analysis provider'):
                service.submit(project=Project(str(source), 30), settings=settings)
            assert service.list_jobs() == []
        google.assert_not_called();ollama.assert_not_called()


@pytest.mark.parametrize('finish', ['MAX_TOKENS', 'SAFETY', 'OTHER', None])
def test_google_rejects_parseable_but_incomplete_response(finish):
    response = SimpleNamespace(text='{"descriptions":[]}', candidates=[SimpleNamespace(finish_reason=finish)])
    with pytest.raises(ValueError, match='cut off|did not complete'):
        completed_google_text(response)


def test_google_stop_block_empty_and_missing_candidates():
    response = SimpleNamespace(text='{"answer":"A room"}', candidates=[SimpleNamespace(finish_reason='STOP')])
    assert completed_google_text(response) == response.text
    response.prompt_feedback = SimpleNamespace(block_reason='SAFETY')
    with pytest.raises(ValueError, match='blocked'):completed_google_text(response)
    response.prompt_feedback = None;response.candidates = []
    with pytest.raises(ValueError, match='no candidates'):completed_google_text(response)
    response.candidates = [SimpleNamespace(finish_reason='STOP')];response.text = ''
    with pytest.raises(ValueError, match='no text'):completed_google_text(response)


def test_truncated_response_is_recoverable_after_reopen_but_never_a_result(tmp_path):
    source=tmp_path/'fixture.mp4';source.write_bytes(b'fixture')
    response=SimpleNamespace(text='{"answer":"partial private-fixture-key"}',candidates=[SimpleNamespace(finish_reason='MAX_TOKENS')])
    settings=dict(DEFAULTS,gemini_key='private-fixture-key',allow_cloud=True)
    with closing(DescriptionService(tmp_path/'engine')) as service,patch('describer.services.segment'),patch('describer.services.video_request',side_effect=lambda *args:completed_google_text(response)):
        job=service.submit(project=Project(str(source),10),settings=settings,operation='ask',prompt='What is here?')
        with pytest.raises(RuntimeError,match='cut off'):service.wait(job['id'])
        status=service.get_job(job['id'])
        assert status['state']=='error' and not status.get('artifact')
        partial=service.partial_response(job['id'])
        assert partial['complete'] is False and '[redacted]' in partial['text']
        assert 'private-fixture-key' not in json.dumps(partial)
        assert not (service._path(job['id'])/'result.adproject').exists()
        with pytest.raises(ValueError,match='not done'):service.result(job['id'])
    with closing(DescriptionService(tmp_path/'engine')) as reopened:
        assert reopened.partial_response(job['id'])==partial


def test_safety_response_does_not_expose_recovery_text():
    from describer.services import IncompleteResponse
    response=SimpleNamespace(text='blocked content',candidates=[SimpleNamespace(finish_reason='SAFETY')])
    with pytest.raises(ValueError) as failure:completed_google_text(response)
    assert not isinstance(failure.value,IncompleteResponse)


def test_scene_explore_keeps_request_focus_glossary_and_range(tmp_path):
    source=tmp_path/'source.mp4';source.write_bytes(b'fixture')
    result='{"layout":"Room","objects":[]}'
    with closing(DescriptionService(tmp_path/'engine')) as service, patch('describer.services.segment') as segment, patch('describer.services.video_request', return_value=result) as request:
        job=service.submit(project=Project(str(source),30,glossary='Ada: red coat'),operation='explore',prompt='Focus on sign',start=5,duration=7,settings={'allow_cloud':True})
        service.wait(job['id'])
        instruction=request.call_args.args[1]
        assert 'Ada: red coat' in instruction and 'Focus on sign' in instruction
        assert segment.call_args.args[2:4] == (5,7)


def test_chunk_reference_reconciliation_and_reject_partial():
    def row(a,b):return {'start':a,'end':b,'text':'A door opens.'}
    assert normalize_chunk({'descriptions':[row(21,23)]},20,15)[0].start == 1
    assert normalize_chunk({'descriptions':[row(1,3)]},20,15)[0].start == 1
    with pytest.raises(ValueError, match='Mixed'):normalize_chunk({'descriptions':[row(1,3),row(21,23)]},20,15)
    with pytest.raises(ValueError, match='Ambiguous'):normalize_chunk({'descriptions':[row(5,7)]},2,20)
    assert normalize_chunk({'timestamp_reference':'clip','descriptions':[row(5,7)]},2,20)[0].start == 5
    with pytest.raises(ValueError, match='Malformed'):normalize_chunk({'descriptions':[row(1,3),row('bad',4)]},0,15)


@pytest.mark.parametrize('safe,expected', [([(0,30)],'in-gap'), ([(0,9)],'pause')])
def test_authored_timing_survives_repair_and_roundtrip_without_changing_evidence(tmp_path,safe,expected):
    cue=Cue(1,3,'A door.',event_id='door',evidence='Visible door').validate(30).edited(10,12,'A door.',30)
    project=Project('fixture',30,[cue]);path=tmp_path/'edited.adproject';project.save(path)
    project=Project.load(path)
    safety={'protected':[],'safe_gaps':safe,'classification':[]}
    def synth(text,path,settings,cancel):path.write_bytes(b'fixture speech')
    with patch('describer.engine.core.protected_audio',return_value=safety),patch('describer.services.synthesize',side_effect=synth),patch('describer.services.run',return_value=json.dumps({'format':{'duration':1}}).encode()):
        prepare(project,{},tmp_path,threading.Event(),lambda _:None,Checkpoints(tmp_path,{'fixture':1}))
    cue=project.cues[0]
    assert cue.start == 10 and cue.disposition == expected
    assert (cue.event_start,cue.event_end,cue.evidence)==(1,3,'Visible door')
    assert cue.narration_window() == (10,12)
    assert project.coverage[0]['timing_start'] == 10


def test_discovery_retains_healthy_models_when_one_entry_fails():
    from describer.models import discover
    def request(settings,path,payload=None):
        if path=='/api/tags':return {'models':[{'name':'broken'},{'name':'healthy','capabilities':['vision']}]}
        if path=='/api/ps':return {'models':[]}
        raise RuntimeError('unreachable fixture model')
    with patch('describer.models.json_request',side_effect=request):
        rows=discover(DEFAULTS,threading.Event(),lambda _:None)
    assert next(row for row in rows if row['name']=='healthy')['vision'] is True
    assert next(row for row in rows if row['name']=='broken')['vision'] is None


def test_start_edit_preserves_duration_and_authored_intent(tmp_path):
    from describer.app import Window
    window=Window(tmp_path/'settings.json');window.settings.data['sounds']=False
    try:
        window.project=Project('fixture',30,[Cue(1,3,'A door.').validate(30)])
        window.refresh();window.choose(0);window.start.setText('10')
        cue=window.project.cues[0]
        assert (cue.start,cue.end)==(10,12)
        assert (cue.event_start,cue.event_end)==(1,3)
        window.undo_stack.undo()
        assert (window.project.cues[0].start,window.project.cues[0].end)==(1,3)
        window.undo_stack.redo()
        assert window.project.cues[0].narration_window()==(10,12)
    finally:window.dirty=False;window.close()


def test_live_wav_volume_and_video_volume_preserve_ducking(tmp_path):
    from PySide6.QtMultimedia import QMediaPlayer
    from describer.app import Window
    window=Window(tmp_path/'settings.json');window.settings.data['sounds']=False
    try:
        window.change_speech_volume(20)
        assert window.narration_audio.volume()==pytest.approx(.2)
        assert window.pause_audio.volume()==pytest.approx(.2)
        window.narration.playbackStateChanged.emit(QMediaPlayer.PlaybackState.PlayingState)
        window.set_volume(50)
        assert window.audio.volume()==pytest.approx(.5*10**(-15/20))
        window.narration.playbackStateChanged.emit(QMediaPlayer.PlaybackState.StoppedState)
        assert window.audio.volume()==pytest.approx(.5)
    finally:window.dirty=False;window.close()


def test_legacy_audio_prompts_repair_without_guessing_saved_volume(tmp_path):
    from describer.app import Window
    from PySide6.QtWidgets import QMessageBox
    audio=tmp_path/'legacy.wav';audio.write_bytes(b'fixture')
    window=Window(tmp_path/'settings.json');window.settings.data['sounds']=False
    try:
        cue=Cue(1,2,'A door.',disposition='pause',audio=str(audio)).validate(5)
        window.project=Project('fixture',5,[cue]);window.settings.data['speech_volume']=20
        assert window.missing_narration()==[]
        assert window.narration_needing_repair()==[cue]
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No) as prompt,patch.object(window,'repair_narration') as repair:
            window.start_pause(cue)
        assert 'recorded synthesis volume' in prompt.call_args.args[2]
        repair.assert_not_called()
        assert not window.pause_active and cue.audio_volume is None
        cue.audio_volume=100
        assert window.narration_needing_repair()==[]
        window._active_narration=cue;window.set_speech_volume(20)
        assert window.pause_audio.volume()==pytest.approx(.2)
    finally:window.dirty=False;window.close()


def test_settings_voice_preview_uses_draft_and_cancel_preserves_file(tmp_path):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication,QComboBox,QPushButton
    from describer.app import Window
    window=Window(tmp_path/'settings.json');window.settings.data['sounds']=False;window.settings.save()
    original=window.settings.path.read_bytes();seen=[];errors=[]
    window.test_voice=lambda settings:seen.append(settings)
    def interact():
        dialog=QApplication.activeModalWidget()
        try:
            engine=next(x for x in dialog.findChildren(QComboBox) if x.findText(native_engine())>=0)
            engine.setCurrentText('OpenAI')
            next(x for x in dialog.findChildren(QPushButton) if x.text()=='Test voice').click()
        except Exception as exc:errors.append(exc)
        finally:dialog.reject()
    try:
        QTimer.singleShot(0,interact);window.edit_settings('Export voice')
        assert not errors and seen[0]['voice_engine']=='OpenAI'
        assert window.settings.path.read_bytes()==original
        assert window.settings.data['voice_engine']==native_engine()
    finally:window.dirty=False;window.close()


def test_nonsecret_original_preferences_are_mapped_without_secret_import(tmp_path):
    from describer.compatibility import read_original_settings
    data={'application_language':'es','tts_engine':'onecore','onecore_voice_id':'fixture',
          'onecore_voice_rate_percent':200,'sapi5_voice_volume':.4,'gemini_key':'do-not-copy'}
    path=tmp_path/'settings.json';path.write_text(json.dumps(data));original=path.read_bytes()
    assert read_original_settings(path)=={'ui_language':'Español','voice_engine':'Windows OneCore',
        'windows_voice':'fixture','speech_rate':10,'speech_volume':40}
    assert path.read_bytes()==original


def test_original_sapi32_uses_shared_sapi_keys_and_normal_percent_default(tmp_path):
    from describer.compatibility import read_original_settings
    path=tmp_path/'settings.json'
    path.write_text(json.dumps({'tts_engine':'sapi5_32bit','sapi5_voice_id':'original32',
        'sapi5_voice_rate_percent':100,'sapi5_voice_volume':1.0}))
    assert read_original_settings(path)=={'voice_engine':'Windows 32-bit','windows_voice':'original32',
        'speech_rate':0,'speech_volume':100}


def test_original_settings_preview_warns_missing_voice_and_cancel_preserves_settings(tmp_path):
    from describer.app import Window
    from PySide6.QtWidgets import QMessageBox
    window=Window(tmp_path/'settings.json');window.settings.data['sounds']=False;window.settings.save()
    original=window.settings.path.read_bytes()
    window.job=lambda work,done:done(work(threading.Event(),lambda _:None))
    try:
        with patch('describer.services.narration_preflight',side_effect=ValueError('Selected voice is missing.')),patch.object(QMessageBox,'question',return_value=QMessageBox.No) as prompt:
            window.preview_original_settings({'voice_engine':'Windows 32-bit','windows_voice':'missing','speech_rate':0})
        assert 'Selected voice is missing' in prompt.call_args.args[2]
        assert 'nearest supported setting' in prompt.call_args.args[2]
        assert window.settings.path.read_bytes()==original
        assert window.settings.data['voice_engine']==native_engine()
    finally:window.dirty=False;window.close()


def test_preset_manager_entry_startup_language_and_explore_controls(tmp_path):
    from PySide6.QtGui import QAction
    from describer.app import Window
    from describer.services import Settings
    path=tmp_path/'settings.json';settings=Settings(path);settings.data.update(sounds=False,ui_language='Español');settings.save()
    window=Window(path)
    try:
        assert any(action.property('source_text')=='Manage presets' for action in window.findChildren(QAction))
        assert window.export_button.text()=='Exportar'
        window.explore_duration.setCurrentIndex(2);window.explore_focus.setText('Focus on doorway')
        seen=[];window.scene_request=lambda *args:seen.append(args);window.explore()
        assert seen[0][3]=='explore'
        assert seen[0][0]=='Focus on doorway' and seen[0][2]==10
    finally:window.dirty=False;window.close()


def test_structured_scene_progress_usage_and_history_survive_reopen(tmp_path):
    from describer.engine.progress import usage
    source=tmp_path/'source.mp4';source.write_bytes(b'fixture')
    project=Project(str(source),30,analysis={'usage':[{'provider':'Gemini','operation':'describe','input_tokens':5,'output_tokens':2}]})
    def request(video,prompt,settings,cancel,log):
        usage(log,'fixture','requested','reported',12,3,15)
        return '{"answer":"A room."}'
    with closing(DescriptionService(tmp_path/'engine')) as service,patch('describer.services.segment'),patch('describer.services.video_request',side_effect=request):
        job=service.submit(project=project,operation='ask',prompt='Where?',settings={'allow_cloud':True})
        snapshots=[]
        def log(text):pass
        log.snapshot=snapshots.append
        result=service.wait(job['id'],log=log)
        current=service.get_job(job['id'])
        assert current['pipeline']['percent']==100
        assert current['pipeline']['stages'][0]['state']=='done'
        assert current['usage'][0]['requested_model']=='requested'
        assert current['usage'][0]['reported_model']=='reported'
        assert result.analysis['usage'][1]['input_tokens']==12
        assert snapshots[-1]['usage'][0]['total_tokens']==15
    with closing(DescriptionService(tmp_path/'engine')) as service:
        assert service.result(job['id']).analysis['usage']==result.analysis['usage']


def test_combined_glossary_usage_is_not_presented_as_separately_measured(tmp_path):
    from contextlib import closing
    from describer.engine.service import DescriptionService
    from describer.engine.progress import usage
    from describer.app import Window
    source=tmp_path/'source.mp4';source.write_bytes(b'fixture')
    project=Project(str(source),5)
    def describe(project,settings,prompt,root,cancel,log,start,duration):
        usage(log,'fixture','requested','reported',10,5,15)
        project.glossary='Rabbit: white fur'
        return project
    with closing(DescriptionService(tmp_path/'engine')) as service,patch('describer.engine.core.describe',side_effect=describe):
        job=service.submit(project=project,operation='describe',settings={'allow_cloud':True,'auto_glossary':True})
        result=service.wait(job['id'])
    row=result.analysis['usage'][0]
    assert row['components']==['description','glossary']
    assert 'separate glossary token counts are unavailable' in row['attribution']
    with closing(DescriptionService(tmp_path/'engine')) as service:
        assert service.result(job['id']).analysis['usage']==[row]
    window=Window(tmp_path/'settings.json');window.settings.data['sounds']=False
    try:
        window.render_usage([row])
        assert 'description + glossary (combined): input 10, output 5' in window.usage_display.text()
        assert 'separate glossary token counts are unavailable' in window.usage_display.toolTip()
    finally:window.dirty=False;window.close()


def test_cached_audio_recheck_does_not_undo_completed_observation_progress():
    from describer.engine.progress import pipeline,advance
    value=advance(pipeline('describe'),'observation',1,1)
    assert value['percent']==67
    value=advance(value,'protected-audio')
    assert value['percent']==67 and value['stages'][0]['state']=='done'
    assert value['stages'][1]['state']=='done'


def test_legacy_job_without_pipeline_resumes_and_reports_progress(tmp_path):
    from describer.engine.core import atomic_json
    source=tmp_path/'source.mp4';source.write_bytes(b'fixture')
    with closing(DescriptionService(tmp_path/'engine')) as service,patch('describer.services.segment'),patch('describer.services.video_request',side_effect=ValueError('fixture interruption')):
        job=service.submit(project=Project(str(source),30),operation='ask',prompt='Where?',settings={'allow_cloud':True})
        with pytest.raises(RuntimeError,match='fixture interruption'):service.wait(job['id'])
        service._futures[job['id']].result(timeout=3)
        path=service.root/job['id']/'job.json';data=service.get_job(job['id']);data.pop('pipeline');data.pop('usage');atomic_json(path,data)
    with closing(DescriptionService(tmp_path/'engine')) as service,patch('describer.services.segment'),patch('describer.services.video_request',return_value='{"answer":"A room."}'):
        service.resume(job['id'],settings={'allow_cloud':True});service.wait(job['id'])
        assert service.get_job(job['id'])['pipeline']['percent']==100


def test_desktop_renders_stage_checklist_and_honest_usage_counts(tmp_path):
    from describer.app import Window
    from describer.engine.progress import pipeline,advance
    window=Window(tmp_path/'settings.json');window.settings.data['sounds']=False
    try:
        progress=advance(pipeline('describe'),'observation',1,4)
        window.job_snapshot({'pipeline':progress,'usage':[{'operation':'describe','input_tokens':12,'output_tokens':None}]})
        assert window.job_progress.maximum()==100
        assert window.job_progress.value()==42
        assert '✓ Protect original audio' in window.job_stages.text()
        assert '→ Observe video (1/4)' in window.job_stages.text()
        assert '○ Measure and place narration' in window.job_stages.text()
        assert 'input 12, output unknown' in window.usage_display.text()
    finally:window.dirty=False;window.close()
