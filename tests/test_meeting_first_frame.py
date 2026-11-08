"""An event cannot start before the first frame the model saw (L4b, S1).

The change gate skips frames that did not change. The model then copies the
example time 0.0, so a slide cue started seconds before the slide.
"""
from pathlib import Path
from unittest.mock import patch

from describer.engine.service import DescriptionService
from describer.project import Project
from tests.test_meeting_changes import BLANK, MEETING, boundaries, slide_changed

SLIDE = slide_changed()


def run(tmp_path, thumbs, replies):
    source = tmp_path / 'meeting.mp4'; source.write_bytes(b'video')
    calls = []

    def provider(clip, instruction, settings, cancel, log, as_json=True, gate=None):
        if 'raising a hand' in instruction:
            return {'timestamp_reference': 'clip', 'descriptions': []}
        n = len(calls); calls.append(n)
        gate.measure = lambda paths, cancel: thumbs[n]
        if not gate([(Path(f'{i}.jpg'), i * 2.0) for i in range(8)], cancel):
            return {'descriptions': [], 'timestamp_reference': 'clip', 'no_change': True}
        return replies[n]
    with boundaries(), patch('describer.services.video_request', side_effect=provider):
        service = DescriptionService(tmp_path / 'engine', MEETING)
        try:
            return service.wait(service.submit(project=Project(str(source), 45))['id'])
        finally:
            service.close()


def row(text, start, end, kind='other'):
    return {'timestamp_reference': 'clip', 'descriptions': [{'start': start, 'end': end, 'text': text, 'kind': kind}]}


def test_a_slide_event_starts_at_the_first_frame_that_shows_it(tmp_path):
    # Chunk 15-30 s: only the frames at 12 s and 14 s are new (the slide).
    thumbs = [[BLANK] * 8, [BLANK] * 6 + [SLIDE] * 2, [SLIDE] * 8]
    result = run(tmp_path, thumbs, [row('Members sit at the dais.', 1, 3),
                                    row('Slide: "Current Compost Collection".', 0, 15, 'slide')])
    slide = [c for c in result.cues if c.kind == 'slide']
    assert len(slide) == 1
    assert slide[0].event_start == 27, 'the slide is first seen at 15 + 12 s'
    assert slide[0].start >= 27 and slide[0].event_end >= slide[0].event_start


def test_an_event_after_the_first_new_frame_is_not_moved(tmp_path):
    thumbs = [[BLANK] * 8, [BLANK] * 2 + [SLIDE] * 6, [SLIDE] * 8]
    result = run(tmp_path, thumbs, [row('Members sit at the dais.', 1, 3),
                                    row('Slide: "Budget".', 6, 9, 'slide')])
    slide = [c for c in result.cues if c.kind == 'slide']
    assert [c.event_start for c in slide] == [21]


def test_a_short_event_moved_to_the_first_frame_is_kept(tmp_path):
    # S1 48-64 s: the model said 0-2 s, the slide is first seen at 12 s.
    # Moving the start must not leave a zero-length event that is thrown away.
    thumbs = [[BLANK] * 8, [BLANK] * 6 + [SLIDE] * 2, [SLIDE] * 8]
    result = run(tmp_path, thumbs, [row('Members sit at the dais.', 1, 3),
                                    row('Slide: "Space Usage".', 0, 2, 'slide')])
    slide = [c for c in result.cues if c.kind == 'slide']
    assert len(slide) == 1, 'the slide cue was dropped'
    assert slide[0].event_start == 27
    assert slide[0].event_end > slide[0].event_start and slide[0].end > slide[0].start
