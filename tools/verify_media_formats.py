"""Native decoding/seek/planned-narration acceptance using the real Qt loop.

No nested processEvents/QTest loop: retained native acceptance documented that
such pumping can stall Qt's media backend. Uses synthetic media and settings.
"""
import argparse
import faulthandler
import json
import time
from pathlib import Path

from PySide6.QtCore import QTimer,QUrl
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication

from describer.app import Window
from describer.project import Cue
from describer.services import run,tool,synthesize,DEFAULTS


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    root=args.output.resolve();root.mkdir(parents=True,exist_ok=True)
    audio=root/'narration.wav';synthesize('Blue square.',audio,dict(DEFAULTS,speech_volume=100))
    seconds=float(json.loads(run([tool('ffprobe'),'-v','error','-show_format','-of','json',str(audio)]))['format']['duration'])
    formats=[('mp4','libx264','aac'),('mkv','libx264','aac'),('mov','libx264','aac'),('avi','mpeg4','pcm_s16le'),('webm','libvpx-vp9','libopus')]
    for ext,video,audio_codec in formats:
        run([tool('ffmpeg'),'-v','error','-y','-f','lavfi','-i','color=c=blue:s=160x120:d=5:r=15',
             '-f','lavfi','-i','sine=frequency=220:duration=5','-c:v',video,'-pix_fmt','yuv420p','-c:a',audio_codec,'-shortest',str(root/('fixture.'+ext))])
    app=QApplication([]);window=Window(root/'settings.json');window.settings.data.update(sounds=False,player_volume=15,speech_volume=20);window.apply_playback_preferences()
    results=[];state={'index':-1};errors=[];window.error=errors.append
    window.video.videoSink().videoFrameChanged.connect(lambda frame:state.update(frames=state.get('frames',0)+int(frame.isValid())))
    def observed(key,value):
        if value==QMediaPlayer.PlaybackState.PlayingState:state.setdefault(key,[]).append(window.player.position())
    window.narration.playbackStateChanged.connect(lambda value:observed('narration',value))
    window.pause_player.playbackStateChanged.connect(lambda value:observed('pauses',value))
    window.player.errorOccurred.connect(lambda code,text:errors.append(text))
    window.show();timer=QTimer();timer.setInterval(30)
    def save():
        receipt={'platform':app.platformName(),'synthetic_media_only':True,'formats':results,'errors':errors,
                 'passed':len(results)==len(formats) and not errors,'human_listening':'Not claimed; decoded frames and actual audio playback states observed.'}
        (root/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');return receipt
    def finish():
        timer.stop();print(json.dumps(save()),flush=True);window.dirty=False;window.close();app.quit()
    def next_format():
        index=state['index']+1
        if index==len(formats):finish();return
        state.clear();state.update(index=index,step='ready',started=time.monotonic(),frames=0,narration=[],pauses=[])
        ext=formats[index][0];window.set_video(root/('fixture.'+ext))
        window.project.cues=[Cue(.1,2.4,'Blue square.',event_id='gap',disposition='in-gap',audio=str(audio),speech_seconds=seconds,audio_volume=100).validate(5),
                             Cue(2.6,4.9,'Blue square.',event_id='pause',disposition='pause',audio=str(audio),speech_seconds=seconds,audio_volume=100).validate(5)]
        window.refresh()
    def tick():
        try:
            assert time.monotonic()-state['started']<13,'Native format/narration timeout: '+str(state)
            assert not errors,errors
            if state['step']=='ready' and window.player.isSeekable():window.player.play();state['step']='narrate'
            elif state['step']=='narrate' and state['narration'] and state['pauses'] and not window.pause_active and window.player.position()>2700:
                window.player.pause();window.seek(1800);state.update(step='seek',frames_at_seek=state['frames'])
            elif state['step']=='seek' and abs(window.player.position()-1800)<200:window.player.play();state['step']='seek-playing'
            elif state['step']=='seek-playing' and window.player.position()>2100 and state['frames']>state['frames_at_seek']:
                results.append({'format':formats[state['index']][0],'frames':state['frames'],'in_gap_positions_ms':state['narration'],
                                'pause_positions_ms':state['pauses'],'seek_ms':1800,'post_seek_ms':window.player.position(),'passed':True})
                print(json.dumps(results[-1]),flush=True);save();window.seek(0);window.player.stop();window.player.setSource(QUrl());QTimer.singleShot(0,next_format);state['step']='switch'
        except Exception as exc:errors.append(str(exc));finish()
    timer.timeout.connect(tick);next_format();timer.start();faulthandler.dump_traceback_later(90,exit=True)
    try:app.exec()
    finally:faulthandler.cancel_dump_traceback_later()
    if not save()['passed']:raise RuntimeError(errors)


if __name__=='__main__':main()
