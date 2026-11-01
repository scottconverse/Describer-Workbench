"""An output-signal oracle for speech timing and background ducking; no cloud."""
import array
import json
import math
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from describer.project import Cue, Project
from describer.services import DEFAULTS, export_audio, run, tool


def main():
    with tempfile.TemporaryDirectory(prefix='describer-signal-') as tmp:
        tmp=Path(tmp);source=tmp/'source.mp4';output=tmp/'mixed.mp3'
        run([tool('ffmpeg'),'-v','error','-y','-f','lavfi','-i','color=black:s=160x90:r=1',
             '-f','lavfi','-i','sine=frequency=1000:sample_rate=44100','-t','5','-c:v','libx264','-c:a','aac',str(source)])
        def voice(text,path,settings,cancel):
            run([tool('ffmpeg'),'-v','error','-y','-f','lavfi','-i',('anullsrc=r=44100:cl=mono' if text=='silent' else 'sine=frequency=500:sample_rate=44100'),'-t','2',str(path)])
        with patch('describer.services.synthesize',voice):
            export_audio(Project(str(source),5,[Cue(1,3,'Signal fixture')]),output,dict(DEFAULTS),threading.Event(),lambda _:None)
        b=run([tool('ffmpeg'),'-v','error','-i',str(output),'-f','s16le','-ac','1','-ar','44100','-'])
        samples=array.array('h');samples.frombytes(b)
        def amplitude(start,freq):
            chunk=samples[int(start*44100):int((start+.25)*44100)]
            sin=sum(x*math.sin(2*math.pi*freq*i/44100) for i,x in enumerate(chunk))
            cos=sum(x*math.cos(2*math.pi*freq*i/44100) for i,x in enumerate(chunk))
            return 2*math.hypot(sin,cos)/len(chunk)
        gain=20*math.log10(amplitude(1.5,1000)/amplitude(.5,1000))
        voice_inside=amplitude(1.5,500);voice_outside=amplitude(.5,500)
        result={'measured_background_duck_db':gain,'expected_background_duck_db':-15,
                'speech_inside_window':voice_inside,'speech_outside_window':voice_outside,
                'passed':abs(gain+15)<1.5 and voice_inside>voice_outside*20}
        with patch('describer.services.synthesize',voice):
            export_audio(Project(str(source),5,[Cue(1,3,'Signal fixture')]+[Cue(1,3,'silent') for _ in range(20)]),output,dict(DEFAULTS),threading.Event(),lambda _:None)
        b=run([tool('ffmpeg'),'-v','error','-i',str(output),'-f','s16le','-ac','1','-ar','44100','-'])
        samples=array.array('h');samples.frombytes(b)
        result['batch_21_speech_gain_db']=20*math.log10(amplitude(1.5,500)/voice_inside)
        result['passed']=result['passed'] and abs(result['batch_21_speech_gain_db'])<.5
        Path('evidence/acceptance-0.2/audio-signal-check.json').write_text(json.dumps(result,indent=2));print(result)
        assert result['passed']


if __name__=='__main__':main()
