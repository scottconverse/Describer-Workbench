"""F2 part 1: the transcript reaches the prompt, and narration may use a nearby pause."""
from test_meeting_changes import DEFAULT, MEETING, draft, reply

from describer import meeting
from describer.engine.planning import place

ROLLING_VTT = """WEBVTT

00:00:01.000 --> 00:00:03.000
All in favor say aye.

00:00:03.000 --> 00:00:03.010
All in favor say aye.

00:00:03.010 --> 00:00:05.000
All in favor say aye.
&gt;&gt; Motion carries.

00:00:20.000 --> 00:00:22.000
Next item is the water budget.
"""


def test_a_line_can_use_a_pause_just_after_its_event():
    """A 3 s line never fits a 2 s event. A pause 1 s later must be usable."""
    safe = [(0, 10.5), (13, 17)]
    assert place(10, 12, 3, safe, []).disposition == 'pause'
    widened = place(10, 12, 3, safe, [], reach=5)
    assert (widened.disposition, widened.start) == ('in-gap', 13)


def test_a_pause_inside_the_event_is_still_used_first():
    safe = [(10, 14), (14.5, 20)]
    assert place(10, 14, 3, safe, [], reach=5).start == 10


def test_a_pause_just_before_the_event_is_used_when_none_comes_after():
    widened = place(10, 12, 3, [(5, 9.5)], [], reach=5)
    assert widened.disposition == 'in-gap' and 5 <= widened.start and widened.end <= 9.5


def test_only_meeting_mode_widens_the_search():
    reach = getattr(meeting, "narration_reach", lambda settings: 0)
    assert reach(MEETING) == 5 and reach(DEFAULT) == 0


def test_the_transcript_of_each_chunk_reaches_the_prompt(tmp_path):
    captions = tmp_path / 'captions.vtt'; captions.write_text(ROLLING_VTT, encoding='utf-8')
    replies = [reply('A slide appears.'), reply('A woman speaks.'), reply('A man sits.')]
    _, prompts = draft(tmp_path, dict(MEETING, captions=str(captions)), replies)
    assert 'All in favor say aye.' in prompts[0] and 'Motion carries.' in prompts[0]
    assert prompts[0].count('All in favor say aye.') == 1  # rolling captions repeat lines
    assert '&gt;' not in prompts[0]  # HTML codes are decoded
    assert 'water budget' not in prompts[0] and 'water budget' in prompts[1]
    assert 'describe only what a listener cannot learn from the audio' in prompts[0]
    (tmp_path / 'default').mkdir()
    _, prompts = draft(tmp_path / 'default', dict(DEFAULT, captions=str(captions)), replies)
    assert not any('All in favor' in p for p in prompts)
