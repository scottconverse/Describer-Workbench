"""Narration plays at the video's loudness, and finished exports do not clip."""
import array
import threading
import wave
from pathlib import Path
from unittest.mock import patch

import pytest

from describer import services
from describer.engine.exporting import export
from describer.project import Cue, Project
from describer.services import measure_loudness, narration_gain, narration_target, run, tool


def test_target_follows_the_video_inside_the_speech_range():
    assert narration_target(None) == services.NARRATION_DEFAULT_LUFS
    assert narration_target(-22.6) == -22.6
    assert narration_target(-45.0) == -30.0
    assert narration_target(-8.0) == -14.0


def test_gain_brings_each_clip_to_the_target_and_speech_volume_is_a_trim():
    cue = Cue(0, 1, 'A door opens.', audio='clip.wav', audio_volume=100)
    with patch('describer.services.measure_loudness', return_value=-10.0):
        assert narration_gain(cue, {'speech_volume': 100}, -20.0) == pytest.approx(10**(-10/20))
        assert narration_gain(cue, {'speech_volume': 50}, -20.0) == pytest.approx(.5*10**(-10/20))
    with patch('describer.services.measure_loudness', return_value=None):
        assert narration_gain(cue, {'speech_volume': 80}, -20.0) == pytest.approx(.8)
    with pytest.raises(ValueError, match='synthesis volume'):
        narration_gain(Cue(0, 1, 'x', audio='clip.wav'), {}, -20.0)


def tone(path, frequency, amplitude, seconds):
    run([tool('ffmpeg'), '-v', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={frequency}:duration={seconds}',
         '-af', f'volume={amplitude}', '-ar', '44100', '-ac', '2', str(path)])


def piece(source, start, seconds, dest):
    run([tool('ffmpeg'), '-v', 'error', '-y', '-ss', str(start), '-t', str(seconds), '-i', str(source), str(dest)])
    return dest


def peak(path):
    with wave.open(str(path)) as stream:
        samples = array.array('h', stream.readframes(stream.getnframes()))
    return max(abs(x) for x in samples)/32768


def test_quiet_meeting_gets_a_matching_voice_and_no_export_clips(tmp_path):
    # A quiet video (about -26 LUFS) and a loud voice clip (about -5 LUFS), as in the meeting tests.
    source = tmp_path/'source.mp4'
    run([tool('ffmpeg'), '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=gray:s=160x120:r=30:d=8',
         '-f', 'lavfi', '-i', 'sine=frequency=220:duration=8', '-af', 'volume=0.6',
         '-c:v', 'libx264', '-c:a', 'aac', '-shortest', str(source)])
    voice = tmp_path/'voice.wav';tone(voice, 880, .95, 2)
    project = Project(str(source), 8, [
        Cue(1, 3, 'First.', event_id='one', event_start=1, event_end=3, disposition='in-gap', audio=str(voice), speech_seconds=2, audio_volume=100),
        Cue(5, 7, 'Second.', event_id='two', event_start=5, event_end=7, disposition='pause', audio=str(voice), speech_seconds=2, audio_volume=100)])
    for cue in project.cues:cue.validate(8)
    target = tmp_path/'complete.wav'
    export(project, target, {'duck_db': -15}, threading.Event(), lambda _:None)
    video = measure_loudness(piece(target, 4, 1, tmp_path/'video.wav'))
    in_gap = measure_loudness(piece(target, 1.2, 1.6, tmp_path/'in-gap.wav'))
    paused = measure_loudness(piece(target, 5.2, 1.6, tmp_path/'paused.wav'))
    assert video is not None and -29 < video < -20
    # Before 0.8.3 the voice was about 25 dB louder than this video.
    assert in_gap == pytest.approx(video, abs=2.5)
    assert paused == pytest.approx(video, abs=2.5)
    assert peak(target) < .95


def test_loud_video_under_a_voice_is_limited_below_full_scale(tmp_path):
    source = tmp_path/'loud.mp4'
    run([tool('ffmpeg'), '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=gray:s=160x120:r=30:d=4',
         '-f', 'lavfi', '-i', 'sine=frequency=220:duration=4', '-af', 'volume=0.99',
         '-c:v', 'libx264', '-c:a', 'pcm_s16le', '-shortest', str(source.with_suffix('.mkv'))])
    source = source.with_suffix('.mkv')
    voice = tmp_path/'voice.wav';tone(voice, 330, .99, 2)
    project = Project(str(source), 4, [Cue(1, 3, 'Loud.', event_id='one', event_start=1, event_end=3, disposition='in-gap',
                                           audio=str(voice), speech_seconds=2, audio_volume=100)])
    project.cues[0].validate(4)
    target = tmp_path/'loud.wav'
    export(project, target, {'duck_db': 0, 'speech_volume': 100}, threading.Event(), lambda _:None)
    assert peak(target) < .95

def test_mix_steps_use_float_files_so_nothing_clips_before_the_limiter(tmp_path):
    source = tmp_path/'source.mkv'
    run([tool('ffmpeg'), '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=gray:s=160x120:r=30:d=4',
         '-f', 'lavfi', '-i', 'sine=frequency=220:duration=4', '-c:v', 'libx264', '-c:a', 'pcm_s16le', '-shortest', str(source)])
    voice = tmp_path/'voice.wav';tone(voice, 330, .2, 2)
    project = Project(str(source), 4, [Cue(1, 3, 'Loud.', event_id='one', event_start=1, event_end=3, disposition='in-gap',
                                           audio=str(voice), speech_seconds=2, audio_volume=100)])
    project.cues[0].validate(4)
    calls = []
    def spy(args, *rest, **kw):
        calls.append([str(a) for a in args]);return run(args, *rest, **kw)
    with patch('describer.services.run', side_effect=spy):
        services._mix_planned_audio(project, tmp_path/'bed.mp3', {'duck_db': -15}, threading.Event(), lambda _:None)
    steps = [c for c in calls if c[-1].endswith('.wav') and Path(c[-1]).name.startswith(('timed', 'ducked', 'mix'))]
    assert {Path(c[-1]).name.rstrip('0123456789.wav') for c in steps} == {'timed', 'ducked', 'mix'}
    for c in steps:
        assert c[c.index('-c:a')+1] == 'pcm_f32le', c[-1]
