"""The first cue sets the scene, so a small move there is kept.
But a first cue that only says nothing changed tells the listener nothing. It is dropped."""
from describer import meeting


def cue(text, start, kind='other'):
    return {'start': start, 'end': start + 2, 'text': text, 'kind': kind}


def test_a_first_cue_that_says_nothing_changed_is_dropped():
    dropped = []
    out = meeting.drop_trivial([cue('No visible changes.', 0), cue('Slide: "Budget".', 10, 'slide')], dropped=dropped)
    assert [c['text'] for c in out] == ['Slide: "Budget".']
    assert [(d['start'], d['end']) for d in dropped] == [(0, 2)]


def test_a_first_cue_with_a_small_move_is_still_kept():
    out = meeting.drop_trivial([cue('A man looks forward.', 0), cue('A woman leans forward.', 10)])
    assert [c['text'] for c in out] == ['A man looks forward.']
