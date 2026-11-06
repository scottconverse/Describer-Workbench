"""F7 (DW-13): a short last chunk must not fail the whole job."""
import threading
from unittest.mock import patch

from describer.project import Project, normalize_chunk
from describer.services import observe


def test_event_running_past_a_short_chunk_is_clamped():
    data = {'timestamp_reference': 'clip', 'descriptions': [{'start': 0, 'end': 2, 'text': 'A member stands.'}]}
    cues = normalize_chunk(data, 316, 1.3)
    assert [(c.start, c.end) for c in cues] == [(0, 1.3)]
    source = {'timestamp_reference': 'source', 'descriptions': [{'start': 316, 'end': 318, 'text': 'A member stands.'}]}
    assert [(c.start, c.end) for c in normalize_chunk(source, 316, 1.3)] == [(0, 1.3)]


def test_event_starting_outside_the_chunk_is_still_rejected():
    import pytest
    data = {'timestamp_reference': 'clip', 'descriptions': [{'start': 2, 'end': 3, 'text': 'A member stands.'}]}
    with pytest.raises(ValueError, match='out-of-range'):
        normalize_chunk(data, 316, 1.3)


def test_short_remainder_is_folded_into_the_previous_chunk():
    # The DW-13 window: start 300, duration 17, Ollama 16-second chunks.
    project = Project('fixture.mp4', 320)
    settings = {'chunk': 30, 'fps': 2, 'language': 'English', 'analysis_provider': 'Ollama', 'ollama_frame_interval': 2}
    reply = '{"timestamp_reference":"clip","descriptions":[{"start":0,"end":2,"text":"A member stands."}]}'
    with patch('describer.services.segment') as clip, patch('describer.services.video_request', return_value=reply):
        cues = observe(project, settings, '', threading.Event(), lambda _: None, 300, 17)
    assert [call.args[2:4] for call in clip.call_args_list] == [(300, 17)]
    assert len(cues) == 1
