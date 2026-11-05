"""End-to-end regressions for the eight 2026-11-04 audit findings; no live AI."""
import json
import threading
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QInputDialog, QLabel, QLineEdit, QListWidget, QPushButton, QRadioButton

from describer.app import Window
from describer.engine.core import Checkpoints
from describer.engine.service import DescriptionService
from describer.project import Project, import_subtitles, normalize_chunk
from describer.services import DEFAULTS, Settings


def response(*rows):
    return {'timestamp_reference':'clip','descriptions':list(rows)}


def row(text='A door opens.', **values):
    return dict(start=1,end=3,text=text,**values)


@pytest.mark.parametrize('metadata',[{'uncertainty':None},{'kind':None},{'evidence':[]},{'event_id':7},{'disposition':'invented'}])
def test_chunk_metadata_never_drops_a_returned_row(metadata):
    with pytest.raises(ValueError,match='Malformed chunk observation 2'):
        normalize_chunk(response(row(),row('A warning sign.',**metadata)),0,10)
    # Genuine recurrence survives; only identical same-event observations collapse.
    cues=normalize_chunk(response(row(),row(),{'start':5,'end':7,'text':'A door opens.'}),0,10)
    assert len(cues)==2


def media_boundaries():
    stack=ExitStack()
    stack.enter_context(patch('describer.services.segment'))
    stack.enter_context(patch('describer.services.narration_preflight'))
    stack.enter_context(patch('describer.engine.core.identity',return_value={'fixture':'unchanged'}))
    stack.enter_context(patch('describer.engine.core.protected_audio',return_value={'protected':[],'classification':[],'safe_gaps':[[0,30]]}))
    stack.enter_context(patch('describer.services.synthesize',side_effect=lambda text,path,settings,cancel:Path(path).write_bytes(b'owned narration')))
    stack.enter_context(patch('describer.services.run',return_value=b'{"format":{"duration":0.5}}'))
    return stack


@pytest.mark.parametrize('invalid',[row('A sign.',uncertainty=None),{'start':1,'end':99,'text':'Out of bounds.'}])
def test_failed_chunk_retries_after_reopen_without_repeating_good_chunk(tmp_path,invalid):
    source=tmp_path/'source.mp4';source.write_bytes(b'unchanged source')
    settings=dict(DEFAULTS,allow_cloud=True,auto_glossary=False,chunk=15)
    workspace=tmp_path/'engine'
    with media_boundaries(),patch('describer.services.video_request',side_effect=[response(row()),response(row(),invalid)]) as provider:
        service=DescriptionService(workspace,settings)
        try:
            job=service.submit(project=Project(str(source),30))
            with pytest.raises(RuntimeError,match='chunk'):service.wait(job['id'])
            assert provider.call_count==2 and service.get_job(job['id'])['state']=='error'
            with pytest.raises(ValueError,match='not done'):service.result(job['id'])
            stages=service._path(job['id'])/'stages'
            assert (stages/'observe-0.000000.json').exists()
            assert not (stages/'observe-15.000000.json').exists()
            rejected=list(stages.glob('rejected-*.json'))
            assert len(rejected)==1
            assert json.loads(rejected[0].read_text())['stage']=='observe-15.000000'
            evidence=rejected[0].read_bytes()
        finally:service.close()
    with media_boundaries(),patch('describer.services.video_request',return_value=response(row(),row('A sign.'))) as provider:
        service=DescriptionService(workspace,settings)
        try:
            service.resume(job['id']);result=service.wait(job['id'])
            assert provider.call_count==1
            assert service.get_job(job['id'])['state']=='done'
            assert len(result.cues)==len(result.coverage)==3
            assert result.cues[-1].event_start==16
            assert rejected[0].read_bytes()==evidence
            assert source.read_bytes()==b'unchanged source'
        finally:service.close()


def test_invalid_legacy_checkpoint_is_preserved_but_not_reused(tmp_path):
    cp=Checkpoints(tmp_path,{'fixture':'legacy'})
    bad=response(row(uncertainty=None));good=response(row())
    cp.stage('observe',lambda:bad)
    assert cp.stage('observe',lambda:good,lambda value:normalize_chunk(value,0,10))==good
    assert list(tmp_path.glob('invalid-*.json'))
    assert list(tmp_path.glob('rejected-*.json'))


@pytest.mark.parametrize('mutation',[
    {'connections':{'broken':None},'connection_id':'broken','analysis_provider':'OpenAI-compatible'},
    {'connections':{'broken':{'name':'bad','url':'local','credential':[]}}},
    {'connection_id':'absent'}, {'provider_models':{'Claude CLI':None}},
    {'cli_paths':{'Codex CLI':[]}}, {'voice_engine':'Missing engine'},
])
def test_nested_settings_recover_without_rewriting_original(tmp_path,mutation):
    path=tmp_path/'settings.json'
    # A healthy sibling is retained in the backup under the existing all-defaults policy.
    content={'connections':{'healthy':{'name':'Healthy','url':'http://127.0.0.1:1234/v1','credential':'healthy_key'}},**mutation}
    path.write_text(json.dumps(content));original=path.read_bytes()
    settings=Settings(path)
    assert settings.needs_recovery and settings.load_warning
    assert path.read_bytes()==original and settings.data['connections']=={}
    window=Window(path)
    try:assert window.settings.load_warning
    finally:window.close()
    settings.save()
    backups=list(tmp_path.glob('settings.json.recovery-*'))
    assert len(backups)==1 and backups[0].read_bytes()==original
    assert not Settings(path).load_warning


def configured(window):
    window.settings.data.update(connections={'local':{'name':'Local','url':'http://127.0.0.1:1234/v1','credential':'local_key','enabled':True,'model':'old-model'}},connection_id='local')


@pytest.mark.parametrize('provider',['Codex CLI','Claude CLI','Gemini CLI','Subscription gateway','OpenAI-compatible','Anthropic API','Ollama'])
def test_visible_draft_test_uses_exact_model_consent_and_correct_route(tmp_path,provider):
    window=Window(tmp_path/'settings.json');window.settings.data['sounds']=False
    configured(window);window.settings.save();before=window.settings.path.read_bytes()
    window.project=Project('fixture',10);seen=[];errors=[]
    def job(work,done):
        done(work(threading.Event(),lambda _:None));window.job_finished()
    window.job=job
    def interact():
        dialog=QApplication.activeModalWidget()
        try:
            next(x for x in dialog.findChildren(QRadioButton) if x.text()==provider).setChecked(True)
            test=next(x for x in dialog.findChildren(QPushButton) if x.text()=='Test connection')
            assert test.isEnabled()
            refresh=next(x for x in dialog.findChildren(QPushButton) if x.text()=='Refresh models')
            assert refresh.isEnabled()==(provider!='Anthropic API')
            editor=next(x for x in dialog.findChildren(QLineEdit) if x.accessibleName()=='Exact analysis model ID')
            editor.setText('exact-fixture-model');test.click();QApplication.processEvents()
            disclosure=next(x.text() for x in dialog.findChildren(QLabel) if 'Range analysis replaces' in x.text())
            assert provider in disclosure and 'no audio' in disclosure
            assert 'Uploads video to Google' not in disclosure
            if provider=='OpenAI-compatible':assert 'gateway forwards' not in disclosure
        except Exception as exc:errors.append(exc)
        finally:dialog.reject()
    try:
        with patch('describer.subscriptions.model_info',return_value={}),patch('describer.model_picker.model_info',return_value={}),patch('describer.subscriptions.test_connection',side_effect=lambda settings,c,l:seen.append(settings) or 'passed'),patch('describer.models.test_connection',side_effect=lambda settings,c,l:seen.append(settings) or 'text passed'),patch.object(window,'cloud_confirm',return_value=True) as consent,patch.object(window,'confirm_ollama',return_value=True) as ollama_consent:
            QTimer.singleShot(0,interact);window.draft_dialog()
        assert not errors,errors
        assert len(seen)==1 and seen[0]['analysis_provider']==provider
        from describer.providers import model_id
        assert model_id(seen[0])=='exact-fixture-model'
        assert (ollama_consent if provider=='Ollama' else consent).call_count==1
        assert window.settings.path.read_bytes()==before
    finally:window.dirty=False;window.close();QApplication.processEvents()


def test_visible_test_declined_consent_sends_no_image(tmp_path):
    window=Window(tmp_path/'settings.json');window.settings.data['sounds']=False;configured(window)
    window.project=Project('fixture',10)
    def job(work,done):done(work(threading.Event(),lambda _:None));window.job_finished()
    window.job=job
    def interact():
        dialog=QApplication.activeModalWidget()
        next(x for x in dialog.findChildren(QRadioButton) if x.text()=='Claude CLI').setChecked(True)
        next(x for x in dialog.findChildren(QLineEdit) if x.accessibleName()=='Exact analysis model ID').setText('fixture')
        next(x for x in dialog.findChildren(QPushButton) if x.text()=='Test connection').click()
        QApplication.processEvents();dialog.reject()
    try:
        with patch('describer.subscriptions.model_info',return_value={}),patch('describer.subscriptions.test_connection') as inference,patch.object(window,'cloud_confirm',return_value=False):
            QTimer.singleShot(0,interact);window.draft_dialog()
        inference.assert_not_called()
    finally:window.dirty=False;window.close()


def test_available_catalog_metadata_reaches_visible_dialog_and_failure_isolated(tmp_path):
    from describer.models import discover
    tags=[{'name':'healthy','size':123456,'capabilities':['vision'],'details':{'family':'fixture-family','parameter_size':'12B','quantization_level':'Q4_K_M'}},{'name':'unhealthy'}]
    def request(settings,path,payload=None):
        if path=='/api/tags':return {'models':tags}
        if path=='/api/ps':return {'models':[{'name':'healthy'}]}
        if payload['model']=='unhealthy':raise RuntimeError('unavailable')
        return {'model_info':{'fixture.context_length':65536}}
    with patch('describer.models.json_request',side_effect=request):rows=discover(DEFAULTS,threading.Event(),lambda _:None)
    assert rows[0]['name']=='healthy' and rows[0]['vision'] is True
    assert rows[1]['vision'] is None and rows[1]['family'] is None and rows[1]['error']
    window=Window(tmp_path/'settings.json');window.settings.data['sounds']=False
    window.settings.data.update(analysis_provider='Ollama',ollama_model='healthy')
    window.model_picker.provider.setCurrentText('Ollama');window.model_picker.discovered(rows)
    window.project=Project('fixture',10);errors=[]
    def interact():
        dialog=QApplication.activeModalWidget()
        try:
            listing=next(x for x in dialog.findChildren(QListWidget) if x.accessibleName()=='Discovered exact models')
            text='\n'.join(listing.item(i).text() for i in range(listing.count()))
            for field in ('fixture-family','12B','Q4_K_M','123456','65536','unknown'):assert field in text
        except Exception as exc:errors.append(exc)
        finally:dialog.reject()
    try:QTimer.singleShot(0,interact);window.draft_dialog();assert not errors,errors
    finally:window.close()


@pytest.mark.parametrize('encoding',['utf-8','utf-16','cp1252'])
def test_vtt_optional_hours_and_existing_srt_variants(tmp_path,encoding):
    path=tmp_path/'captions.vtt'
    path.write_bytes(('WEBVTT\n\n00:01.000 --> 00:02.000\nA café.\n\n00:00:03.000 --> 00:00:04.000\nA door.\n').encode(encoding))
    assert [(c.start,c.end,c.text) for c in import_subtitles(path,10)]==[(1,2,'A café.'),(3,4,'A door.')]
    path.write_text('1\n0:00:01,000 --> 0:00:02,000\nA door.\n',encoding='utf-8')
    assert len(import_subtitles(path,10))==1
    path.write_text('WEBVTT\n\n00:09.000 --> 00:11.000\nPast end.\n')
    with pytest.raises(ValueError,match='past the video'):import_subtitles(path,10)


@pytest.mark.parametrize('new_name,accepted',[('Renamed',True),('Existing',False),('Renamed',False)])
def test_preset_rename_persists_or_preserves_on_collision_cancel(tmp_path,new_name,accepted):
    window=Window(tmp_path/'settings.json');window.settings.data['sounds']=False
    window.settings.data['presets']={'English':{'Old':'Keep every fact.','Existing':'Other.'},'Español':{'Old':'Otro.'}}
    window.reload_presets();window.preset.setCurrentText('Old');window.settings.save();before=window.settings.path.read_bytes();errors=[];window.error=errors.append
    try:
        with patch.object(QInputDialog,'getItem',side_effect=[('Rename',True),('Old',True)]),patch.object(QInputDialog,'getText',return_value=(new_name,accepted)):
            window.presets()
        if accepted and new_name=='Renamed':
            assert window.preset.currentText()=='Renamed'
            assert window.prompt.toPlainText()=='Keep every fact.'
            loaded=Settings(window.settings.path)
            assert loaded.data['presets']['English']=={'Renamed':'Keep every fact.','Existing':'Other.'}
            assert loaded.data['presets']['Español']=={'Old':'Otro.'}
        else:
            assert window.settings.path.read_bytes()==before and 'Old' in window.settings.data['presets']['English']
            assert bool(errors)==(accepted and new_name=='Existing')
    finally:window.close()


def test_maintained_and_rendered_guidance_matches_editor_behavior(tmp_path):
    from tools import build_site
    root=Path(__file__).resolve().parents[1]
    manual=(root/'docs/USER-MANUAL.md').read_text(encoding='utf-8')
    readme=(root/'README.md').read_text(encoding='utf-8')
    for text in (manual,readme):
        assert 'Changing Start shifts End to preserve cue duration' in text
        assert 'double-click' not in text and 'F2' not in text
        assert 'Exact analysis model ID' in text
    assert 'Existing measured WAV playback, OpenAI exports and a screen reader retain their own audio levels' not in manual
    assert 'measured WAV playback and exported narration, including OpenAI narration' in manual
    assert 'rename or delete a prompt preset' in manual
    for text in (build_site.downloadable_markdown(manual),build_site.render(manual,'Manual','manual.html')):
        assert 'Exact analysis model ID' in text and 'Changing Start shifts End' in text
    window=Window(tmp_path/'settings.json');window.settings.data['sounds']=False
    from describer.project import Cue
    try:
        window.project=Project('fixture',30,[Cue(1,3,'A door.').validate(30)])
        window.refresh();window.choose(0);window.start.setText('10')
        assert (window.project.cues[0].start,window.project.cues[0].end)==(10,12)
        window.end.setText('14')
        assert (window.project.cues[0].start,window.project.cues[0].end)==(10,14)
        window._active_narration=Cue(1,3,'A door.',audio_volume=100)
        window.set_speech_volume(40)
        assert window.narration_audio.volume()==pytest.approx(.4)
    finally:window.dirty=False;window.close()
