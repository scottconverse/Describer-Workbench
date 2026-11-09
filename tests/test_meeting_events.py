"""F3: meeting events first. Typed kinds, a vote pass, and no guessed gender."""
from unittest.mock import patch

from test_meeting_changes import DEFAULT, MEETING, boundaries, reply

from describer.catalogue import PROMPTS
from describer.engine.service import DescriptionService
from describer.project import Project

KINDS = ('vote', 'speaker_change', 'slide', 'on_screen_text', 'scene_change', 'other')

VOTE_VTT = """WEBVTT

00:00:20.000 --> 00:00:22.000
All those in favor?

00:00:22.500 --> 00:00:23.500
Aye.

00:00:24.000 --> 00:00:25.000
Motion carries.
"""

QUIET_VTT = """WEBVTT

00:00:20.000 --> 00:00:22.000
Next item is the water budget.
"""


def run(tmp_path, settings, answer):
    """Draft a 45 s video. `answer(instruction, settings)` gives each model reply."""
    source = tmp_path / 'meeting.mp4'; source.write_bytes(b'video')
    calls = []

    def provider(clip, instruction, settings, cancel, log, as_json=True, gate=None):
        calls.append({'instruction': instruction, 'interval': settings.get('ollama_frame_interval'), 'gate': gate})
        return answer(instruction, settings)
    with boundaries(), patch('describer.services.video_request', side_effect=provider):
        service = DescriptionService(tmp_path / 'engine', settings)
        try:
            job = service.submit(project=Project(str(source), 45))
            result = service.wait(job['id'])
        finally:
            service.close()
    return result, calls


def captions(tmp_path, text):
    path = tmp_path / 'captions.vtt'; path.write_text(text, encoding='utf-8')
    return str(path)


def is_vote_question(instruction):
    return 'raising a hand' in instruction


def test_the_catalogue_has_a_public_meeting_genre():
    rules = PROMPTS.get('Public meeting', '')
    assert all(f'"{kind}"' in rules or kind in rules for kind in KINDS)


def test_meeting_mode_asks_for_typed_events_with_templates(tmp_path):
    _, calls = run(tmp_path, MEETING, lambda i, s: reply('A slide appears.'))
    prompt = calls[0]['instruction']
    for kind in KINDS:
        assert kind in prompt, kind
    assert 'members raise their hands' in prompt
    assert 'Slide: <exact title>' in prompt


def test_meeting_mode_never_guesses_gender_from_a_wide_shot(tmp_path):
    rule = 'never a gender, unless the person is in close-up'
    _, calls = run(tmp_path, MEETING, lambda i, s: reply('A slide appears.'))
    assert all(rule in c['instruction'] for c in calls if 'Is this description true' not in c['instruction'])
    (tmp_path / 'default').mkdir()
    _, calls = run(tmp_path / 'default', DEFAULT, lambda i, s: reply('A man sits.'))
    assert not any(rule in c['instruction'] for c in calls)


def vote_answer(instruction, settings):
    if is_vote_question(instruction):
        return {'timestamp_reference': 'clip',
                'descriptions': [{'start': 3, 'end': 5, 'text': '3 members raise their hands', 'kind': 'vote'}]}
    return reply('A board sits at a long table.')


def test_vote_words_in_the_transcript_start_a_vote_pass(tmp_path):
    settings = dict(MEETING, captions=captions(tmp_path, VOTE_VTT))
    result, calls = run(tmp_path, settings, vote_answer)
    votes = [c for c in calls if is_vote_question(c['instruction'])]
    assert len(votes) == 1, 'one vote pass for one vote'
    assert votes[0]['interval'] == 1 and votes[0]['gate'] is None, 'frames every 1 s, none skipped'
    assert 'All those in favor?' in votes[0]['instruction']
    cue = next(c for c in result.cues if c.kind == 'vote')
    assert cue.text == '3 members raise their hands'
    assert abs(cue.event_start - 22) <= 3, 'within 3 s of the vote'


def test_no_vote_words_means_no_vote_pass(tmp_path):
    settings = dict(MEETING, captions=captions(tmp_path, QUIET_VTT))
    _, calls = run(tmp_path, settings, vote_answer)
    assert not any(is_vote_question(c['instruction']) for c in calls)


def test_the_vote_pass_is_meeting_mode_only(tmp_path):
    settings = dict(DEFAULT, captions=captions(tmp_path, VOTE_VTT))
    _, calls = run(tmp_path, settings, vote_answer)
    assert not any(is_vote_question(c['instruction']) for c in calls)


def test_a_failed_vote_pass_does_not_fail_the_job(tmp_path):
    def answer(instruction, settings):
        if is_vote_question(instruction):
            return {'unexpected': True}
        return reply('A board sits at a long table.')
    settings = dict(MEETING, captions=captions(tmp_path, VOTE_VTT), chunk_retries=0)
    result, _ = run(tmp_path, settings, answer)
    assert result.cues and not any(c.kind == 'vote' for c in result.cues)
