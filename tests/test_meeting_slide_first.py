"""Option 1d: when the screen changes, the slide cue wins over a cue about a person."""
from describer import meeting
from tests.test_meeting_changes import MEETING, DEFAULT, draft


def cue(start, end, text, kind):
    return dict(start=start, end=end, event_start=start, event_end=end, text=text, kind=kind)


def test_a_person_cue_that_overlaps_a_slide_cue_is_dropped():
    cues = [cue(0, 3, 'People sit around a table.', 'other'),
            cue(10, 13, 'The presenter looks at the screen.', 'other'),
            cue(11, 14, 'Slide: "Budget 2027". $4.2 million.', 'slide'),
            cue(20, 23, 'Text: "Public comment".', 'on_screen_text'),
            cue(21, 24, 'A woman in a red jacket speaks.', 'scene_change'),
            cue(22, 24, '3 members raise their hands', 'vote'),
            cue(40, 43, 'A man walks to the podium.', 'other')]
    dropped = []
    out = meeting.slide_first(cues, dropped=dropped)
    assert [c['start'] for c in out] == [0, 11, 20, 22, 40]
    assert [(d['start'], d['end']) for d in dropped] == [(10, 13), (21, 24)]
    assert all('slide' in d['reason'].lower() for d in dropped)


def test_meeting_mode_keeps_the_slide_cue_not_the_person_cue(tmp_path):
    both = {'timestamp_reference': 'clip', 'descriptions': [
        {'start': 1, 'end': 4, 'text': 'A man stands at the front.', 'kind': 'other'},
        {'start': 1, 'end': 4, 'text': 'Slide: "Agenda". Item 3.', 'kind': 'slide'}]}
    single = lambda t: {'timestamp_reference': 'clip', 'descriptions': [{'start': 1, 'end': 4, 'text': t, 'kind': 'other'}]}
    result, _ = draft(tmp_path, MEETING, [single('People walk in.'), both, single('A woman walks out.')])
    assert [c.text for c in result.cues] == ['People walk in.', 'Slide: "Agenda". Item 3.', 'A woman walks out.']


def test_default_mode_keeps_both(tmp_path):
    both = {'timestamp_reference': 'clip', 'descriptions': [
        {'start': 1, 'end': 4, 'text': 'A man stands at the front.', 'kind': 'other'},
        {'start': 1, 'end': 4, 'text': 'Slide: "Agenda". Item 3.', 'kind': 'slide'}]}
    single = lambda t: {'timestamp_reference': 'clip', 'descriptions': [{'start': 1, 'end': 4, 'text': t}]}
    result, _ = draft(tmp_path, DEFAULT, [single('People walk in.'), both, single('A woman walks out.')])
    assert len(result.cues) == 4
