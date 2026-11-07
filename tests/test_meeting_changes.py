"""F1 (DW-1): in Public meeting mode, describe what changes, not every frame."""
import threading
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from describer.engine.service import DescriptionService
from describer.project import Project
from describer.services import DEFAULTS, validate_connection_settings

MEETING = dict(DEFAULTS, allow_cloud=True, auto_glossary=False, chunk=15, drafting_mode='Public meeting')
DEFAULT = dict(MEETING, drafting_mode='')

BLANK = bytes(64 * 36)


def slide_changed():
    """A thumbnail that differs from BLANK only in one 8x9 cell (a new slide)."""
    thumb = bytearray(BLANK)
    for y in range(9):
        for x in range(8):
            thumb[y * 64 + x] = 200
    return bytes(thumb)


def reply(text, start=1, end=4):
    return {'timestamp_reference': 'clip', 'descriptions': [{'start': start, 'end': end, 'text': text}]}


def boundaries(duration=45):
    stack = ExitStack()
    stack.enter_context(patch('describer.services.segment'))
    stack.enter_context(patch('describer.services.narration_preflight'))
    stack.enter_context(patch('describer.services.probe', return_value=duration))
    stack.enter_context(patch('describer.engine.core.identity', return_value={'fixture': 'f1'}))
    stack.enter_context(patch('describer.engine.core.protected_audio', return_value={'protected': [], 'classification': [], 'safe_gaps': [[0, duration]]}))
    stack.enter_context(patch('describer.services.synthesize', side_effect=lambda text, path, settings, cancel: Path(path).write_bytes(b'narration')))
    stack.enter_context(patch('describer.services.run', return_value=b'{"format":{"duration":0.5}}'))
    return stack


def draft(tmp_path, settings, replies):
    source = tmp_path / 'meeting.mp4'; source.write_bytes(b'video')
    prompts = []

    def provider(clip, instruction, settings, cancel, log, as_json=True, gate=None):
        prompts.append(instruction)
        return replies[len(prompts) - 1]
    with boundaries(), patch('describer.services.video_request', side_effect=provider):
        service = DescriptionService(tmp_path / 'engine', settings)
        try:
            job = service.submit(project=Project(str(source), 45))
            result = service.wait(job['id'])
        finally:
            service.close()
    return result, prompts


def test_the_mode_is_a_validated_setting():
    validate_connection_settings(dict(MEETING))
    try:
        validate_connection_settings(dict(MEETING, drafting_mode='Sports'))
    except ValueError as exc:
        assert 'drafting_mode' in str(exc)
    else:
        raise AssertionError('An unknown drafting mode was accepted.')


def test_unchanged_frames_never_reach_the_model(tmp_path):
    from describer import meeting, models
    frames = [(tmp_path / f'{i}.jpg', i * 2.0) for i in range(8)]
    for path, _ in frames:
        path.write_bytes(b'jpg')
    gate = meeting.ChangeGate(measure=lambda paths, cancel: [BLANK] * len(paths))
    gate.last = BLANK
    logs = []
    with patch('describer.services.probe', return_value=16), patch('describer.models.model_info', return_value={}), \
         patch('describer.frames.sample', return_value=frames), patch('describer.models.chat') as chat:
        data = models.video_request('clip.mp4', 'Describe.', dict(DEFAULTS, ollama_model='gemma4:12b'),
                                    threading.Event(), logs.append, gate=gate)
    chat.assert_not_called()
    assert data['descriptions'] == [] and data['no_change'] is True
    assert gate.skipped == 8 and gate.sent == 0


def test_a_new_slide_in_one_area_is_sent_but_camera_noise_is_not():
    from describer import meeting
    noise = bytes(min(255, b + 3) for b in BLANK)
    assert not meeting.changed(BLANK, noise)
    assert meeting.changed(BLANK, slide_changed())
    gate = meeting.ChangeGate(measure=lambda paths, cancel: [BLANK, noise, slide_changed(), slide_changed()])
    kept = gate([('a', 0), ('b', 2), ('c', 4), ('d', 6)])
    assert [name for name, _ in kept] == ['a', 'c']


def test_meeting_mode_merges_repeats_and_records_unchanged_spans(tmp_path):
    result, prompts = draft(tmp_path, MEETING, [
        reply('A slide titled Budget 2027 appears on the screen.'),
        reply('The slide titled Budget 2027 remains on the screen.'),
        {'timestamp_reference': 'clip', 'descriptions': [], 'no_change': True},
    ])
    assert [c.text for c in result.cues] == ['A slide titled Budget 2027 appears on the screen.']
    assert result.cues[0].event_end >= 19, 'the merged cue spans the restated event'
    assert 'Budget 2027 appears' in prompts[1], 'the model sees what it already said'
    assert 'return an empty descriptions list' in prompts[0]
    unchanged = [r for r in result.coverage if r.get('disposition') == 'no_change']
    assert [(r['event_start'], r['event_end']) for r in unchanged] == [(30, 45)]


def test_default_mode_is_unchanged(tmp_path):
    result, prompts = draft(tmp_path, DEFAULT, [
        reply('A slide titled Budget 2027 appears on the screen.'),
        reply('The slide titled Budget 2027 remains on the screen.'),
        reply('A woman speaks at the podium.'),
    ])
    assert len(result.cues) == 3
    assert not any('Previous descriptions' in p for p in prompts)
    assert not [r for r in result.coverage if r.get('disposition') == 'no_change']


def test_real_ffmpeg_measures_every_frame(tmp_path):
    """The gate gets one thumbnail per sampled frame from the real ffmpeg."""
    from describer import meeting
    width, height = 320, 180
    paths = []
    for i in range(8):
        pixels = bytearray(width * height * 3)
        if i >= 4:  # a new slide appears in the top-left area
            for y in range(60):
                pixels[y * width * 3:(y * width + 60) * 3] = b'\xff' * 180
        path = tmp_path / f'{i:03d}.ppm'
        path.write_bytes(f'P6 {width} {height} 255\n'.encode() + bytes(pixels))
        paths.append(path)
    thumbs = meeting.thumbnails(paths)
    assert len(thumbs) == 8
    kept = meeting.ChangeGate()([(p, i * 2.0) for i, p in enumerate(paths)])
    assert [p.name for p, _ in kept] == ['000.ppm', '004.ppm']
