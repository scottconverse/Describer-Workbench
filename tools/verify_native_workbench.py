"""Opt-in real Windows event-loop acceptance with read-only project input."""
import argparse
import faulthandler
import json
import time
from pathlib import Path
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication
from describer.app import Window
from describer.engine.core import sha
from describer.project import Project


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    # A native backend stall must produce a traceback and terminal failure, not linger.
    faulthandler.dump_traceback_later(35,exit=True)
    original=sha(args.project);project=Project.load(args.project)
    app=QApplication([]);window=Window(out/'settings.json');window.settings.data['sounds']=False
    errors=[];window.error=errors.append
    window.show();window.set_video(project.video);window.project=project;window.refresh()
    cue=next(c for c in project.cues if c.disposition=='pause')
    state={'step':'ready','started':time.monotonic(),'visible':window.isVisible(),'window_handle':int(window.winId())}
    timer=QTimer();timer.setInterval(30)
    def tick():
        try:
            assert time.monotonic()-state['started']<25,'Playback acceptance timed out'
            if state['step']=='ready' and window.player.isSeekable():
                assert window.table.columnCount()==4 and window.table.rowCount()==len(project.cues)
                window.seek(round(cue.event_start*1000));window.player.play();state['step']='waiting-pause'
            elif state['step']=='waiting-pause' and window.pause_active:
                assert window.player.playbackState()==QMediaPlayer.PlaybackState.PausedState
                state.update(step='waiting-resume',paused_at=window.player.position(),pause_seen=True)
            elif state['step']=='waiting-resume':
                if window.pause_active:
                    assert abs(window.player.position()-state['paused_at'])<100,'Original moved during narration'
                elif window.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState:
                    window.player.pause();window.seek(0);state['step']='switch'
            elif state['step']=='switch':
                window.start_pause(cue);assert window.pause_active
                window.set_video(project.video)
                assert not window.pause_active and not window.played_pauses
                assert window.pause_player.playbackState()==QMediaPlayer.PlaybackState.StoppedState
                assert sha(args.project)==original and not errors,errors
                state.update(step='done',passed=True,cue_count=len(project.cues),source_paused_for_narration=True,
                             resumed_after_narration=True,source_switch_stops_old_narration=True,original_project_unchanged=True)
                finish()
        except Exception as exc:
            state.update(step='error',passed=False,error=str(exc));finish()
    def finish():
        timer.stop();(out/'receipt.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
        print(json.dumps(state),flush=True);window.dirty=False;window.close();app.quit()
    timer.timeout.connect(tick);timer.start()
    try:app.exec()
    finally:
        window.player.setSource(QUrl());faulthandler.cancel_dump_traceback_later()
    if not state.get('passed'):raise RuntimeError(state)

if __name__=='__main__':main()
