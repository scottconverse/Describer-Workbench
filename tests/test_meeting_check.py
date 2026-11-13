"""Option 1c: a check pass. The model looks at the frame again and says if each cue is true."""
from unittest.mock import patch

from describer.engine.service import DescriptionService
from describer.project import Project
from tests.test_meeting_changes import DEFAULT, MEETING, boundaries, reply

FALSE = 'A man in a red hat waves.'


def run(tmp_path, settings, replies, verdict):
    source = tmp_path / 'meeting.mp4'; source.write_bytes(b'video')
    chunks, checks = [], []

    def provider(clip, instruction, settings, cancel, log, as_json=True, gate=None):
        if 'raising a hand' in instruction:
            return {'timestamp_reference': 'clip', 'descriptions': []}
        if 'Is this description true' in instruction:
            checks.append(instruction)
            return verdict(instruction)
        chunks.append(instruction)
        return replies[len(chunks) - 1]
    with boundaries(), patch('describer.services.video_request', side_effect=provider) as _, \
            patch('describer.services.segment') as seg:
        service = DescriptionService(tmp_path / 'engine', settings)
        try:
            result = service.wait(service.submit(project=Project(str(source), 45))['id'])
        finally:
            service.close()
    return result, checks, seg


def says(instruction):
    return {'true': FALSE not in instruction}


def test_a_cue_the_check_pass_calls_false_is_dropped_and_flagged(tmp_path):
    result, checks, seg = run(tmp_path, MEETING, [reply('A woman walks to the podium.'), reply(FALSE),
                                                  reply('Slide: "Budget". $4 million.')], says)
    assert [c.text for c in result.cues] == ['A woman walks to the podium.', 'Slide: "Budget". $4 million.']
    assert len(checks) == 3
    flagged = [r for r in result.coverage if r.get('disposition') == 'no_change']
    assert [(r['event_start'], r['event_end']) for r in flagged] == [(16, 19)]
    assert 'not true' in flagged[0]['reason'].lower()
    # The check looks at one second around the middle of the event (16..19 -> 17.5).
    starts = [call.args[2] for call in seg.call_args_list]
    assert 17.0 in starts


def test_a_failed_or_unclear_check_keeps_the_cue(tmp_path):
    def broken(instruction):
        if FALSE in instruction:
            raise ValueError('bad reply')
        return {'answer': 'maybe'}
    result, _, _ = run(tmp_path, MEETING, [reply('A woman walks to the podium.'), reply(FALSE),
                                           reply('A man stands up.')], broken)
    assert len(result.cues) == 3


def test_the_check_pass_is_meeting_mode_only(tmp_path):
    result, checks, _ = run(tmp_path, DEFAULT, [reply('A woman walks.'), reply(FALSE), reply('A man stands.')], says)
    assert checks == [] and len(result.cues) == 3


def test_the_check_pass_never_leaves_the_job_with_no_cues(tmp_path):
    result, checks, _ = run(tmp_path, MEETING, [reply('A woman walks in.'), reply('A man stands up.'), reply('Two people leave the room.')],
                            lambda instruction: {'true': False})
    assert len(checks) == 3 and len(result.cues) == 3
    assert not [r for r in result.coverage if r.get('disposition') == 'no_change' and 'not true' in r['reason'].lower()]
