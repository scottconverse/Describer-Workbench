"""A vote is a motion: hands go up and down. One still frame can miss it.
The vote check already looked at the clip for this, so the check pass does not drop a vote cue."""
import threading
from types import SimpleNamespace
from unittest.mock import patch

from describer import services
from tests.test_meeting_changes import MEETING


def test_the_check_pass_does_not_drop_a_vote_cue():
    rows = [{'start': 10, 'end': 12, 'text': '3 members raise their hands', 'kind': 'vote',
             'event_id': 'vote-8.000000:10.000000:12.000000:0'},
            {'start': 20, 'end': 22, 'text': 'A man in a red hat waves.', 'kind': 'other'}]
    asked = []

    def provider(clip, instruction, settings, cancel, log, as_json=True, gate=None):
        asked.append(instruction)
        return {'true': False}
    with patch('describer.services.video_request', side_effect=provider), patch('describer.services.segment'):
        out = services.check_pass(SimpleNamespace(video='meeting.mp4'), MEETING, rows, threading.Event(), lambda _: None)
    assert [r['text'] for r in out] == ['3 members raise their hands']
    assert len(asked) == 1 and '3 members' not in asked[0]


def test_a_vote_cue_from_the_picture_alone_is_still_checked():
    """The vote check runs only where the transcript says a vote happens.
    A "vote" the model saw on its own (L4a, 1942 s: no vote words, no hands) gets the second look."""
    rows = [{'start': 10, 'end': 12, 'text': '3 members raise their hands', 'kind': 'vote',
             'event_id': 'vote-8.000000:10.000000:12.000000:0'},
            {'start': 20, 'end': 22, 'text': 'A person raises a hand.', 'kind': 'vote',
             'event_id': '16.000000:20.000000:22.000000:5'}]
    asked = []

    def provider(clip, instruction, settings, cancel, log, as_json=True, gate=None):
        asked.append(instruction)
        return {'true': False}
    with patch('describer.services.video_request', side_effect=provider), patch('describer.services.segment'):
        out = services.check_pass(SimpleNamespace(video='meeting.mp4'), MEETING, rows, threading.Event(), lambda _: None)
    assert [r['text'] for r in out] == ['3 members raise their hands']
    assert len(asked) == 1 and 'A person raises a hand.' in asked[0]
