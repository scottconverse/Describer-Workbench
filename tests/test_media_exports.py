"""Actual FFmpeg exports: pause narration is materialized, not silently omitted."""
import json
import threading
from pathlib import Path

import pytest

from describer.engine.exporting import export
from describer.project import Cue, Project
from describer.services import run, tool


def test_complete_export_extends_audio_and_video_without_touching_original(tmp_path):
    source=tmp_path/'source.mp4'
    run([tool('ffmpeg'),'-v','error','-y','-f','lavfi','-i','color=c=blue:s=160x120:r=30:d=4',
         '-f','lavfi','-i','sine=frequency=220:duration=4','-c:v','libx264','-c:a','aac','-shortest',str(source)])
    original=source.read_bytes()
    narration=tmp_path/'narration.wav'
    run([tool('ffmpeg'),'-v','error','-y','-f','lavfi','-i','sine=frequency=880:duration=1','-ar','44100','-ac','2',str(narration)])
    project=Project(str(source),4,[
        Cue(0,1,'First.',event_id='one',event_start=0,event_end=1,disposition='in-gap',audio=str(narration),speech_seconds=1,audio_volume=100),
        Cue(2,3,'Second.',event_id='two',event_start=2,event_end=3,disposition='pause',audio=str(narration),speech_seconds=1,audio_volume=100)])
    for cue in project.cues:cue.validate(4)
    for suffix in ('wav','mp4'):
        target=tmp_path/('complete.'+suffix)
        receipt=export(project,target,{'duck_db':-15},threading.Event(),lambda _:None)
        info=json.loads(run([tool('ffprobe'),'-v','error','-show_format','-of','json',str(target)]))
        assert float(info['format']['duration'])==pytest.approx(5,abs=.15)
        assert receipt['complete'] and receipt['pause_descriptions']==1
        assert Path(str(target)+'.coverage.json').is_file()
        # Require decode, not merely an existing container.
        run([tool('ffmpeg'),'-v','error','-i',str(target),'-f','null','-'])
    assert source.read_bytes()==original
    incomplete=tmp_path/'in-gap.wav'
    receipt=export(project,incomplete,{'duck_db':-15},threading.Event(),lambda _:None,'in-gap-only')
    assert not receipt['complete'] and receipt['pause_descriptions']==0
    project.cues[1].disposition='unresolved'
    with pytest.raises(ValueError):export(project,tmp_path/'refused.mp4',{},threading.Event(),lambda _:None)
    assert not (tmp_path/'refused.mp4').exists()
