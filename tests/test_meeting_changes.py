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

from describer.meeting import THUMB_H, THUMB_W

BLANK = bytes(THUMB_W * THUMB_H)


def slide_changed():
    """A thumbnail that differs from BLANK only in one grid cell (a new slide)."""
    thumb = bytearray(BLANK)
    for y in range(THUMB_H // 4):
        for x in range(THUMB_W // 8):
            thumb[y * THUMB_W + x] = 200
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
        if 'raising a hand' in instruction:  # F3 vote pass: no hands up here
            return {'timestamp_reference': 'clip', 'descriptions': []}
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


def test_meeting_mode_asks_for_the_exact_slide_title(tmp_path):
    """F4: bigger frames alone did not make the model read slide titles (M4: 0 of 4)."""
    _, prompts = draft(tmp_path, MEETING, [reply('A slide appears.'), reply('A woman speaks.'), reply('A man sits.')])
    assert 'exact title' in prompts[0] and 'word for word' in prompts[0]
    (tmp_path / 'default').mkdir()
    _, prompts = draft(tmp_path / 'default', DEFAULT, [reply('A slide appears.'), reply('A woman speaks.'), reply('A man sits.')])
    assert not any('exact title' in p for p in prompts)


def test_repeats_of_earlier_cues_that_are_not_next_are_dropped():
    """L3: the model sent 4 cues for one event, then the same 4 again."""
    from describer import meeting
    said = ['People sit around tables.', 'Woman standing addresses group.', 'People use laptops and eat.', 'Room has white walls.']
    cues = [dict(start=0 + i, end=1 + i, text=t) for i, t in enumerate(said)]
    cues += [dict(start=48 + i, end=49 + i, text=t) for i, t in enumerate(said[1:])]
    cues += [dict(start=164, end=176, text=said[0]), dict(start=170, end=172, text='A man in a tan jacket stands up.')]
    cues += [dict(start=400, end=402, text=said[0])]  # minutes later: say it again
    out = meeting.merge_repeats(cues)
    assert [(c['start'], c['text']) for c in out] == [(i, t) for i, t in enumerate(said)] + [
        (170, 'A man in a tan jacket stands up.'), (400, said[0])]


def slide_frame(path, lines, noise=0):
    """A 1280x720 slide: dark template, title bar, thin bright text strokes."""
    import random
    width, height = 1280, 720
    rng = random.Random(len(lines) * 7 + noise)
    pixels = bytearray([40]) * (width * height * 3)
    for y in range(40, 100):  # the template's title bar, the same on every slide
        pixels[y * width * 3:(y + 1) * width * 3] = b'\x80' * (width * 3)
    for top in lines:  # one line of text: short strokes, 3 px high
        for y in range(top, top + 3):
            for x in range(200, 1000, 20):
                start = (y * width + x) * 3
                pixels[start:start + 36] = b'\xf0' * 36
    if noise:  # small compression-like noise on the same slide
        for i in range(0, len(pixels), 97):
            pixels[i] = max(0, min(255, pixels[i] + rng.randint(-noise, noise)))
    path.write_bytes(f'P6 {width} {height} 255\n'.encode() + bytes(pixels))
    return path


def test_a_new_slide_that_changes_only_text_is_sent(tmp_path):
    """L4b: same template, new text. The old 64x36 gate called this "no change"."""
    from describer import meeting
    old = slide_frame(tmp_path / 'old.ppm', [200, 260, 320, 380, 440, 500])
    same = slide_frame(tmp_path / 'same.ppm', [200, 260, 320, 380, 440, 500], noise=12)
    new = slide_frame(tmp_path / 'new.ppm', [230, 290, 350, 410, 470, 530])
    kept = meeting.ChangeGate()([(old, 0.0), (same, 2.0), (new, 4.0)])
    assert [p.name for p, _ in kept] == ['old.ppm', 'new.ppm']


def test_a_dropped_repeat_leaves_a_flag_not_a_silent_hole(tmp_path):
    """Step 3 regrade (L3, M1): the model described a chunk again with an
    earlier cue's words. The repeat was dropped and its chunk had no cue and
    no flag. The dropped span must be recorded as "no change"."""
    result, _ = draft(tmp_path, MEETING, [
        reply('People sit around tables.'),
        reply('A man in a tan jacket stands up.'),
        reply('People sit around tables.', start=2, end=9),
    ])
    assert [c.text for c in result.cues] == ['People sit around tables.', 'A man in a tan jacket stands up.']
    flagged = [(r['event_start'], r['event_end']) for r in result.coverage if r.get('disposition') == 'no_change']
    assert flagged == [(32, 39)], 'the dropped repeat is flagged where it was'
    reason = next(r['reason'] for r in result.coverage if r.get('disposition') == 'no_change')
    assert 'repeat' in reason.lower()


def test_merge_repeats_reports_what_it_drops():
    from describer import meeting
    cues = [dict(start=0, end=2, event_start=0, event_end=2, text='People sit around tables.'),
            dict(start=20, end=22, event_start=20, event_end=22, text='A man in a tan jacket stands up.'),
            dict(start=40, end=42, event_start=40, event_end=47, text='People sit around tables.')]
    dropped = []
    out = meeting.merge_repeats(cues, dropped=dropped)
    assert [c['start'] for c in out] == [0, 20]
    assert [(d['start'], d['end']) for d in dropped] == [(40, 47)]


def test_meeting_prompt_example_asks_for_a_short_version_and_a_meeting_kind(tmp_path):
    """Step 3 regrade: only 19 of 703 cues had short_text, and 119 had the
    non-meeting kind "action". The model copies the JSON example, and the
    example had no short_text and kind "action"."""
    import json, re
    _, prompts = draft(tmp_path, MEETING, [reply('People sit around tables.')] * 3)
    example = json.loads(re.search(r'Return JSON (\{"descriptions".*?\}\]\})', prompts[0]).group(1))['descriptions'][0]
    assert example.get('short_text'), 'the example shows a short version'
    assert example['kind'] in ('vote', 'speaker_change', 'slide', 'on_screen_text', 'scene_change', 'other')


def test_default_prompt_example_is_unchanged(tmp_path):
    _, prompts = draft(tmp_path, DEFAULT, [reply('A dog runs.')] * 3)
    assert '"kind":"action"' in prompts[0] and 'short_text' not in prompts[0]
