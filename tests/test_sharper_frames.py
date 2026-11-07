"""F4 (DW-2): in Public meeting mode, frames keep enough pixels to read slides."""
import threading
from unittest.mock import patch

from describer import frames, models
from describer.services import DEFAULTS, run, segment, tool

MEETING = dict(DEFAULTS, drafting_mode='Public meeting', ollama_model='gemma4:12b')


def source(tmp_path, size='1920x1080'):
    path = tmp_path / 'room.mp4'
    run([tool('ffmpeg'), '-v', 'error', '-y', '-f', 'lavfi', '-i', f'testsrc=size={size}:rate=2:duration=4',
         '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)])
    return path


def width_height(path):
    out = run([tool('ffprobe'), '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
               '-of', 'csv=p=0', str(path)]).decode().strip()
    return tuple(int(v) for v in out.split(','))


def test_sampled_frames_keep_the_long_side_up_to_1280(tmp_path):
    video = source(tmp_path)
    (tmp_path / 'a').mkdir(); (tmp_path / 'b').mkdir()
    sharp = frames.sample(video, tmp_path / 'a', 1, threading.Event(), max_side=1280)
    assert width_height(sharp[0][0]) == (1280, 720)
    default = frames.sample(video, tmp_path / 'b', 1, threading.Event())
    assert width_height(default[0][0])[0] == 640


def test_small_sources_are_never_upscaled(tmp_path):
    video = source(tmp_path, '960x540')
    (tmp_path / 'a').mkdir()
    sharp = frames.sample(video, tmp_path / 'a', 1, threading.Event(), max_side=1280)
    assert width_height(sharp[0][0]) == (960, 540)


def test_meeting_segments_keep_1280(tmp_path):
    video = source(tmp_path)
    clip = tmp_path / 'clip.mp4'
    segment(video, clip, 0, 2, 2, threading.Event(), True, max_side=1280)
    assert width_height(clip) == (1280, 720)


def test_the_ollama_request_asks_for_sharp_frames_only_in_meeting_mode(tmp_path):
    calls = []

    def fake_sample(video, root, interval, cancel, max_side=640):
        calls.append(max_side)
        return []
    with patch('describer.services.probe', return_value=16), patch('describer.models.model_info', return_value={}), \
         patch('describer.frames.sample', side_effect=fake_sample), patch('describer.models.chat', return_value='{}'):
        models.video_request('clip.mp4', 'Describe.', MEETING, threading.Event(), lambda _: None)
        models.video_request('clip.mp4', 'Describe.', dict(MEETING, drafting_mode=''), threading.Event(), lambda _: None)
    assert calls == [1280, 640]
