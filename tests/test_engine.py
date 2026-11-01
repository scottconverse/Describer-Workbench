"""Four defect regressions, project preservation and durable service invariants."""
import json
import threading
import time
import wave
from dataclasses import asdict
from unittest.mock import patch

import pytest

from describer.engine.core import Checkpoints, prepare
from describer.engine.planning import gaps, place
from describer.engine.service import DescriptionService
from describer.project import Cue, Project, normalize_generated


def test_real_recurrence_preserved_but_same_event_duplicate_removed():
    rows=[{'start':1,'end':3,'text':'A door opens.'},{'start':20,'end':22,'text':'A door opens.'}]
    assert len(normalize_generated(rows+[rows[0]],30))==2


def test_overlap_is_not_a_license_to_move_visual_event():
    rows=[{'start':1,'end':8,'text':'First event.'},{'start':2,'end':4,'text':'Second event.'}]
    cues=normalize_generated(rows,30)
    assert (cues[1].start,cues[1].end)==(2,4)
    occupied=[(1,3)]
    placement=place(2,4,2,[(0,30)],occupied)
    assert placement.disposition=='pause'  # Cannot move past the event to force a fit.


def test_independent_dialogue_protection_and_exact_fit():
    safe=gaps([(0,3),(5,9)],10)
    p=place(1,5,2,safe,[])
    assert (p.start,p.end,p.disposition)==(3,5,'in-gap')
    assert place(1,3,1,safe,[]).disposition=='pause'


def test_acceleration_is_bounded_and_real_repeated_speech_survives():
    assert place(0,2,2.2,[(0,2)],[]).speed<=1.15
    p=place(0,2,10,[(0,2)],[])
    assert p.disposition=='pause' and p.speed==1
    with pytest.raises(ValueError):place(0,2,3,[(0,2)],[],2)


def test_old_project_roundtrip_preserves_source_and_new_metadata(tmp_path):
    path=tmp_path/'old.adproject'
    original={'version':1,'video':'unchanged.mp4','duration':30,'cues':[{'start':1,'end':3,'text':'Original text.'}],'glossary':'Original glossary'}
    path.write_text(json.dumps(original))
    project=Project.load(path)
    assert path.read_text()==json.dumps(original)
    assert project.cues[0].event_start==1
    project.cues[0].uncertainty='Unreadable sign'
    project.coverage=[{'event_id':'one','disposition':'unresolved'}]
    new=tmp_path/'new.adproject';project.save(new)
    assert asdict(Project.load(new))==asdict(project)
    assert path.read_text()==json.dumps(original)


def test_checkpoint_does_not_repeat_passed_stage_and_refuses_changed_source(tmp_path):
    calls=[];cp=Checkpoints(tmp_path,{'source':'one'})
    assert cp.stage('stage',lambda:calls.append(1) or {'done':True})=={'done':True}
    cp=Checkpoints(tmp_path,{'source':'one'})
    assert cp.stage('stage',lambda:calls.append(2))=={'done':True}
    assert calls==[1]
    with pytest.raises(ValueError):Checkpoints(tmp_path,{'source':'changed'})


def test_synthesized_duration_drives_core_placement_and_uncertainty(tmp_path):
    def synth(text,path,settings,cancel):
        with wave.open(str(path),'wb') as out:
            out.setparams((1,2,16000,0,'NONE','not compressed'));out.writeframes(b'\0\0'*32000)
    # Real WAVs and ffprobe; only vision/speech classifier input is a fixture.
    project=Project('unused',10,[Cue(0,3,'Fits.'),Cue(4,5,'Too long.'),Cue(7,9,'Unclear.',uncertainty='Unreadable')])
    cp=Checkpoints(tmp_path,{'fixture':'measured WAV'})
    safety={'protected':[(0,1),(5,10)],'safe_gaps':[(1,5)],'classification':[]}
    with patch('describer.engine.core.protected_audio',return_value=safety),patch('describer.services.synthesize',side_effect=synth):
        prepare(project,{},tmp_path,threading.Event(),lambda _:None,cp)
    assert [c.disposition for c in project.cues]==['in-gap','pause','unresolved']
    assert project.cues[0].speech_seconds==pytest.approx(2)
    assert project.cues[0].start==1
    assert len(project.coverage)==3


def test_service_serial_cancel_resume_and_reopen(tmp_path):
    source=tmp_path/'source.mp4';source.write_bytes(b'fixture source')
    entered=threading.Event();release=threading.Event();calls=[]
    def work(project,settings,prompt,root,cancel,log,start,duration):
        calls.append(prompt);entered.set()
        if prompt=='first' and len(calls)==1:
            while not release.wait(.01):
                if cancel.is_set():raise InterruptedError('fixture cancelled')
        project.cues=[Cue(0,1,'Preserved.')];return project
    service=DescriptionService(tmp_path/'engine',{'analysis_provider':'Gemini','allow_cloud':True})
    try:
        with patch('describer.engine.core.describe',side_effect=work):
            a=service.submit(project=Project(str(source),2),prompt='first')
            assert entered.wait(3)
            b=service.submit(project=Project(str(source),2),prompt='second')
            service.cancel(b['id'])
            assert service.get_job(b['id'])['state']=='cancelled'
            assert calls==['first']
            service.cancel(a['id'])
            deadline=time.monotonic()+3
            while not service._futures[a['id']].done() and time.monotonic()<deadline:time.sleep(.01)
            assert service.get_job(a['id'])['state']=='cancelled'
            service.resume(a['id'], settings={'allow_cloud':True});result=service.wait(a['id'])
            assert result.cues[0].text=='Preserved.'
            assert calls==['first','first']
            with pytest.raises(ValueError):service.resume(a['id'])
        with pytest.raises(RuntimeError):DescriptionService(tmp_path/'engine')
    finally:release.set();service.close()
    service=DescriptionService(tmp_path/'engine')
    try:
        assert service.result(a['id']).cues[0].text=='Preserved.'
        assert source.read_bytes()==b'fixture source'
        job=service.get_job(a['id'])
        service.edit(a['id'],job['revision'],glossary='New glossary')
        with pytest.raises(ValueError):service.edit(a['id'],job['revision'],glossary='Stale')
    finally:service.close()


def test_headless_import_does_not_import_qt():
    import subprocess,sys
    p=subprocess.run([sys.executable,'-c','import sys;import describer.engine;assert not any(m.startswith("PySide6") for m in sys.modules)'],capture_output=True,text=True,timeout=15)
    assert p.returncode==0,p.stderr


def test_batch_media_failure_does_not_abandon_later_items(tmp_path):
    invalid=tmp_path/'invalid.mp4';invalid.write_text('not a video')
    service=DescriptionService(tmp_path/'engine')
    try:
        rows=service.submit_batch([{'source':str(invalid)},{'source':str(tmp_path/'missing.mp4')}])
        assert len(rows)==2 and all('error' in row for row in rows)
    finally:service.close()
