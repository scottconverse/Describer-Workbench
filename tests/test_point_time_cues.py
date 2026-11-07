"""A cue the model gives as one point in time (start == end) is kept.

After the F1 gate fix, more single frames reach the model. gemma4:12b then
writes start == end for each frame (M4 and L1 re-runs: 7 rejected tries).
The whole chunk was rejected and recorded as a gap.
"""
import pytest

from describer.project import normalize_chunk


def test_a_point_time_cue_gets_a_short_length_and_the_chunk_is_kept():
    data = {'timestamp_reference': 'clip', 'descriptions': [
        {'start': 2.0, 'end': 2.0, 'text': "Slide changes to '2026 Augmentation Program Membership'"},
        {'start': 14.0, 'end': 14.0, 'text': 'The presenter points at the screen.'}]}
    cues = normalize_chunk(data, 732, 16)
    assert [(c.start, c.end) for c in cues] == [(2.0, 4.0), (14.0, 16.0)]


def test_an_end_before_the_start_is_still_rejected():
    data = {'timestamp_reference': 'clip', 'descriptions': [{'start': 4, 'end': 3, 'text': 'A member stands.'}]}
    with pytest.raises(ValueError, match='Malformed'):
        normalize_chunk(data, 0, 16)
