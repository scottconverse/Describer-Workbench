"""F2 (rest): real pauses from word timings, a short variant, a pause budget, marked exports."""
import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from test_meeting_changes import DEFAULT, MEETING

from describer.engine.service import DescriptionService
from describer.project import Cue, Project

WORDS_VTT = """WEBVTT

00:00:10.000 --> 00:00:20.000
We<00:00:10.300><c> will</c><00:00:10.600><c> vote</c><00:00:15.000><c> now</c><00:00:15.300><c> please.</c>
"""

PLAIN_VTT = """WEBVTT

00:00:10.000 --> 00:00:20.000
We will vote now please.
"""


def protected(tmp_path, settings, text):
    from describer.engine.core import protected_audio
    captions = tmp_path / 'captions.vtt'; captions.write_text(text, encoding='utf-8')
    project = Project(str(tmp_path / 'm.mp4'), 30)
    with patch('describer.services.run', return_value=b'{"streams":[]}'):
        return protected_audio(project, dict(settings, captions=str(captions)), None, lambda _: None)


def covers(gaps, a, b):
    return any(x <= a and b <= y for x, y in gaps)


def test_word_timings_find_the_pause_inside_a_caption_line(tmp_path):
    """A 4 s silence between "vote" and "now" sits inside one 10 s caption line."""
    gaps = protected(tmp_path, MEETING, WORDS_VTT)['safe_gaps']
    assert covers(gaps, 11.5, 14.8), gaps
    assert not covers(gaps, 10.0, 11.0), 'spoken words stay protected'


def test_without_word_timings_the_whole_line_stays_protected(tmp_path):
    assert not covers(protected(tmp_path, MEETING, PLAIN_VTT)['safe_gaps'], 11.5, 14.8)
    assert not covers(protected(tmp_path, DEFAULT, WORDS_VTT)['safe_gaps'], 11.5, 14.8), 'default mode unchanged'


# Speech length in these tests: 0.5 s per word.
def speech_boundaries(safe_gaps, duration=60):
    def synthesize(text, path, settings, cancel):
        Path(path).write_text(text, encoding='utf-8')

    def run(args, cancel=None, **kw):
        path = Path(str(args[-1]))
        if path.suffix == '.wav' and path.is_file():
            return json.dumps({'format': {'duration': 0.5 * len(path.read_text('utf-8').split())}}).encode()
        return b'{"format":{"duration":0.5}}'
    stack = ExitStack()
    stack.enter_context(patch('describer.services.segment'))
    stack.enter_context(patch('describer.services.narration_preflight'))
    stack.enter_context(patch('describer.services.probe', return_value=duration))
    stack.enter_context(patch('describer.engine.core.identity', return_value={'fixture': 'f2'}))
    stack.enter_context(patch('describer.engine.core.protected_audio',
                              return_value={'protected': [], 'classification': [], 'safe_gaps': safe_gaps}))
    stack.enter_context(patch('describer.services.synthesize', side_effect=synthesize))
    stack.enter_context(patch('describer.services.run', side_effect=run))
    return stack


def draft(tmp_path, settings, rows, safe_gaps, duration=60):
    """One chunk of `duration` seconds; the model returns `rows` (clip times)."""
    source = tmp_path / 'meeting.mp4'; source.write_bytes(b'video')

    def provider(clip, instruction, settings, cancel, log, as_json=True, gate=None):
        return {'timestamp_reference': 'clip', 'descriptions': rows}
    settings = dict(settings, chunk=duration, ollama_frame_interval=duration)
    with speech_boundaries(safe_gaps, duration), patch('describer.services.video_request', side_effect=provider):
        service = DescriptionService(tmp_path / 'engine', settings)
        try:
            job = service.submit(project=Project(str(source), duration))
            result = service.wait(job['id'])
        finally:
            service.close()
    return result


def test_meeting_mode_asks_for_a_short_variant(tmp_path):
    from describer import meeting
    assert '"short_text"' in meeting.event_instruction('')


def test_the_short_variant_is_spoken_when_only_it_fits_a_gap(tmp_path):
    rows = [{'start': 10, 'end': 12, 'text': 'Three board members raise their hands to approve the motion',
             'short_text': 'Three hands raised', 'kind': 'vote'}]
    result = draft(tmp_path, MEETING, rows, [[13, 15]])
    cue = result.cues[0]
    assert cue.disposition == 'in-gap', cue.disposition
    assert cue.narration_text == 'Three hands raised'
    assert cue.text.startswith('Three board members'), 'the full text is kept for review'


SAID = {'other': 'A cup sits on the desk', 'scene_change': 'The camera shows the whole room',
        'slide': 'Slide: Budget. Twelve million dollars total', 'speaker_change': 'The chair speaks at the podium',
        'vote': 'Three members raise their hands now'}


def six_words(kind):
    return SAID[kind]


def test_the_pause_budget_keeps_the_most_important_pauses(tmp_path):
    """No gaps at all. Each line is 3 s. Budget 8 s per minute: vote + speaker change fit."""
    kinds = ['other', 'scene_change', 'slide', 'speaker_change', 'vote']
    rows = [{'start': 5 + 8 * i, 'end': 7 + 8 * i, 'text': six_words(kind), 'kind': kind} for i, kind in enumerate(kinds)]
    result = draft(tmp_path, dict(MEETING, max_pause_seconds_per_minute=8), rows, [])
    state = {c.kind: c.disposition for c in result.cues}
    assert state == {'vote': 'pause', 'speaker_change': 'pause', 'slide': 'dropped_no_gap',
                     'scene_change': 'dropped_no_gap', 'other': 'dropped_no_gap'}, state
    dropped = [r for r in result.coverage if r.get('disposition') == 'dropped_no_gap']
    assert len(dropped) == 3


def test_a_vote_may_always_pause(tmp_path):
    rows = [{'start': 5, 'end': 7, 'text': six_words('vote'), 'kind': 'vote'},
            {'start': 20, 'end': 22, 'text': six_words('slide'), 'kind': 'slide'}]
    result = draft(tmp_path, dict(MEETING, max_pause_seconds_per_minute=0), rows, [])
    assert {c.kind: c.disposition for c in result.cues} == {'vote': 'pause', 'slide': 'dropped_no_gap'}


def test_the_budget_is_meeting_mode_only(tmp_path):
    rows = [{'start': 5 + 8 * i, 'end': 7 + 8 * i, 'text': six_words(kind)} for i, kind in enumerate(SAID)]
    result = draft(tmp_path, dict(DEFAULT, max_pause_seconds_per_minute=0), rows, [])
    assert all(c.disposition == 'pause' for c in result.cues)


def test_pause_cues_are_marked_and_dropped_cues_left_out_of_text_exports(tmp_path):
    from describer.engine.exporting import export
    project = Project(str(tmp_path / 'm.mp4'), 60)
    project.cues = [Cue(1, 3, 'Fits a gap.', disposition='in-gap'),
                    Cue(10, 12, 'Needs a pause.', disposition='pause'),
                    Cue(20, 22, 'No room.', disposition='dropped_no_gap')]
    vtt = (tmp_path / 'out.vtt'); srt = (tmp_path / 'out.srt')
    export(project, vtt, {}, None, lambda _: None)
    export(project, srt, {}, None, lambda _: None)
    v, s = vtt.read_text('utf-8'), srt.read_text('utf-8')
    assert 'pause-2\n00:00:10.000' in v and 'in-gap-1\n00:00:01.000' in v
    assert '[Pause] Needs a pause.' in s and '[Pause] Fits a gap.' not in s
    assert 'No room.' not in v and 'No room.' not in s


def test_word_timings_overrule_a_detector_that_hears_speech_everywhere(tmp_path):
    """Measured S2: the speech detector marked 653 of 661 frames as speech, so no gap was left.

    With word times in meeting mode, the words say where speech is. A non-speech
    vocal sound (laughter, a shout) found by the detector stays protected.
    """
    from describer.engine.core import protected_audio
    captions = tmp_path / 'captions.vtt'; captions.write_text(WORDS_VTT, encoding='utf-8')
    project = Project(str(tmp_path / 'm.mp4'), 30)
    trace = [{'time': round(t * .48, 4), 'speech': .9, 'vocal': .9 if 13.4 <= t * .48 <= 13.5 else 0.0, 'music': 0.0}
             for t in range(63)]
    everywhere = ([[0.0, 30.0]], trace)

    def measure(settings):
        with patch('describer.services.run', return_value=b'{"streams":[{"codec_type":"audio"}]}'), \
             patch('describer.engine.core.speech_model'), \
             patch('describer.engine.speech_cache.measured', return_value=everywhere):
            return protected_audio(project, dict(settings, captions=str(captions)), None, lambda _: None)['safe_gaps']
    gaps = measure(MEETING)
    assert covers(gaps, 11.5, 12.9), gaps
    assert not covers(gaps, 13.3, 13.6), 'a vocal sound the detector found stays protected'
    assert not covers(gaps, 10.0, 11.0), 'spoken words stay protected'
    assert not covers(measure(DEFAULT), 11.5, 12.9), 'default mode keeps the detector'


def test_a_person_cue_never_stops_the_video(tmp_path):
    """Option 1e: 69 of 129 pause cues were kind other (49 small moves). Only events may pause."""
    rows = [{'start': 5, 'end': 7, 'text': 'A man in a blue shirt walks to the front', 'kind': 'other'},
            {'start': 20, 'end': 22, 'text': six_words('slide'), 'kind': 'slide'},
            {'start': 35, 'end': 37, 'text': 'A woman walks to the door', 'kind': 'other'}]
    result = draft(tmp_path, dict(MEETING, max_pause_seconds_per_minute=100), rows, [[36, 45]])
    state = [(c.kind, c.disposition) for c in result.cues]
    assert state == [('other', 'dropped_no_gap'), ('slide', 'pause'), ('other', 'in-gap')], state
    row = next(r for r in result.coverage if r.get('disposition') == 'dropped_no_gap')
    assert 'only meeting events' in row['reason'].lower()


def test_person_cues_still_pause_outside_meeting_mode(tmp_path):
    rows = [{'start': 5, 'end': 7, 'text': 'A man in a blue shirt walks to the front', 'kind': 'other'}]
    result = draft(tmp_path, DEFAULT, rows, [])
    assert result.cues[0].disposition == 'pause'
