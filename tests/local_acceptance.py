"""Real local media/GUI/speech checks; no cloud calls or credentials needed."""
import json
import sys
import tempfile
import threading
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from describer.app import Window
from describer.services import segment, probe, Settings, synthesize, export_audio, run, tool


def main():
    source=Path(sys.argv[1]);output=Path(sys.argv[2]);output.mkdir(parents=True,exist_ok=True)
    results={};app=QApplication([])
    with tempfile.TemporaryDirectory(prefix='describer-acceptance-') as tmp:
        tmp=Path(tmp);clip=tmp/'clip.mp4';segment(source,clip,0,8,2)
        results['segment_duration']=probe(clip)
        window=Window(tmp/'settings.json');window.show();window.set_video(clip)
        for _ in range(30):
            app.processEvents();QTest.qWait(100)
            if window.player.isSeekable():break
        window.start.setText('1');window.end.setText('3');window.text.setPlainText('An astronaut steps onto the moon.');window.add_cue()
        assert len(window.project.cues)==1
        window.choose(0);app.processEvents();assert window.player.position()==1000
        window.start.setText('2');window.shift_end();assert float(window.end.text())==4
        window.text.setPlainText('The astronaut descends the ladder.');window.apply_edit();assert window.project.cues[0].start==2
        project=tmp/'project.adproject';window.project.save(project);window.project.export(output/'sample.srt')
        window.player.play()
        for _ in range(50):app.processEvents();QTest.qWait(100)
        results['playback_position_ms']=window.player.position();assert results['playback_position_ms']>2000
        window.player.pause();window.grab().save(str(output/'app.png'))
        window.player.setSource(__import__('PySide6.QtCore',fromlist=['QUrl']).QUrl());app.processEvents();QTest.qWait(300)
        settings=window.settings.data
        settings['gemini_key']='acceptance-dummy';window.settings.save();raw=(tmp/'settings.json').read_text();assert 'acceptance-dummy' not in raw
        assert Settings(tmp/'settings.json').data['gemini_key']=='acceptance-dummy';settings['gemini_key']=''
        results['encrypted_settings_roundtrip']=True
        speech=tmp/'speech.wav';synthesize('The astronaut descends the ladder.',speech,settings)
        assert speech.stat().st_size>1000;results['windows_speech_bytes']=speech.stat().st_size
        export_audio(window.project,output/'sample-described.mp3',settings,threading.Event(),print)
        mixed=json.loads(run([tool('ffprobe'),'-v','error','-show_format','-show_streams','-of','json',str(output/'sample-described.mp3')]))
        results['mixed_audio_duration']=float(mixed['format']['duration']);assert 7.9<results['mixed_audio_duration']<8.3
        window.dirty=False;window.close();window.player.setSource(__import__('PySide6.QtCore',fromlist=['QUrl']).QUrl());app.processEvents();QTest.qWait(300)
    results['passed']=True;(output/'local-acceptance.json').write_text(json.dumps(results,indent=2));print(json.dumps(results))


if __name__=='__main__':main()
