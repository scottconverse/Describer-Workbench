"""A vote is a motion: hands go up and down. One still frame can miss it.
The vote check already looked at the clip for this, so the check pass does not drop a vote cue."""
import threading
from types import SimpleNamespace
from unittest.mock import patch

from describer import services
from tests.test_meeting_changes import MEETING


def test_the_check_pass_does_not_drop_a_vote_cue():
    rows = [{'start': 10, 'end': 12, 'text': '3 members raise their hands', 'kind': 'vote'},
            {'start': 20, 'end': 22, 'text': 'A man in a red hat waves.', 'kind': 'other'}]
    asked = []

    def provider(clip, instruction, settings, cancel, log, as_json=True, gate=None):
        asked.append(instruction)
        return {'true': False}
    with patch('describer.services.video_request', side_effect=provider), patch('describer.services.segment'):
        out = services.check_pass(SimpleNamespace(video='meeting.mp4'), MEETING, rows, threading.Event(), lambda _: None)
    assert [r['text'] for r in out] == ['3 members raise their hands']
    assert len(asked) == 1 and '3 members' not in asked[0]
