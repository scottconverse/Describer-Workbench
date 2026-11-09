"""F6 (DW-9): a chunk with no descriptions key is a failure, never a silent hole."""
import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

from describer import cli
from describer.engine.service import DescriptionService
from describer.project import Project, normalize_chunk
from describer.services import DEFAULTS

GLOSSARY_ONLY = {'timestamp_reference': 'clip', 'character_glossary': [{'id': 'man_1', 'name': None, 'description': 'man in a suit'}]}


def good(text='A man speaks at a podium.'):
    return {'timestamp_reference': 'clip', 'descriptions': [{'start': 1, 'end': 3, 'text': text}]}


def boundaries():
    stack = ExitStack()
    stack.enter_context(patch('describer.services.segment'))
    stack.enter_context(patch('describer.services.narration_preflight'))
    stack.enter_context(patch('describer.services.probe', return_value=30))
    stack.enter_context(patch('describer.engine.core.identity', return_value={'fixture': 'f6'}))
    stack.enter_context(patch('describer.engine.core.protected_audio', return_value={'protected': [], 'classification': [], 'safe_gaps': [[0, 30]]}))
    stack.enter_context(patch('describer.services.synthesize', side_effect=lambda text, path, settings, cancel: Path(path).write_bytes(b'narration')))
    stack.enter_context(patch('describer.services.run', return_value=b'{"format":{"duration":0.5}}'))
    return stack


SETTINGS = dict(DEFAULTS, allow_cloud=True, auto_glossary=False, chunk=15)


def test_a_missing_descriptions_key_is_malformed():
    with pytest.raises(ValueError, match='Malformed chunk output; retry the chunk'):
        normalize_chunk(GLOSSARY_ONLY, 0, 15)


def test_an_explicit_empty_list_is_still_allowed():
    assert normalize_chunk({'timestamp_reference': 'clip', 'descriptions': []}, 0, 15) == []


def test_the_chunk_is_retried_then_recorded_as_a_gap_and_resume_fills_it(tmp_path):
    source = tmp_path / 'meeting.mp4'; source.write_bytes(b'video')
    workspace = tmp_path / 'engine'
    with boundaries(), patch('describer.services.video_request', side_effect=[good(), GLOSSARY_ONLY, GLOSSARY_ONLY, GLOSSARY_ONLY]) as provider:
        service = DescriptionService(workspace, SETTINGS)
        try:
            job = service.submit(project=Project(str(source), 30))
            result = service.wait(job['id'])
            assert provider.call_count == 4, 'one good chunk, then the bad chunk is tried 3 times (2 retries)'
            assert service.get_job(job['id'])['state'] == 'done_with_gaps'
            stages = service._path(job['id']) / 'stages'
            assert len(list(stages.glob('rejected-*.json'))) == 3
            gaps = [row for row in service.coverage(job['id'])['events'] if row.get('disposition') == 'failed_chunk']
            assert [(g['event_start'], g['event_end']) for g in gaps] == [(15, 30)]
            assert 'Malformed chunk output' in gaps[0]['reason']
            assert len(result.cues) == 1
        finally:
            service.close()
    with boundaries(), patch('describer.services.video_request', return_value=good('A sign reads Agenda.')) as provider:
        service = DescriptionService(workspace, SETTINGS)
        try:
            service.resume(job['id']); result = service.wait(job['id'])
            assert provider.call_count == 1, 'resume re-tries only the failed chunk'
            assert service.get_job(job['id'])['state'] == 'done'
            assert not [r for r in result.coverage if r.get('disposition') == 'failed_chunk']
            assert len(result.cues) == 2
        finally:
            service.close()


def test_the_cli_exits_non_zero_when_a_chunk_failed(tmp_path, capsys):
    source = tmp_path / 'meeting.mp4'; source.write_bytes(b'video')
    settings = tmp_path / 'settings.json'; settings.write_text(json.dumps(SETTINGS), 'utf-8')
    with boundaries(), patch('describer.services.video_request', side_effect=[good(), GLOSSARY_ONLY, GLOSSARY_ONLY, GLOSSARY_ONLY]):
        code = cli.main(['--workspace', str(tmp_path / 'engine'), '--settings', str(settings), 'describe', str(source)])
    assert code != 0
    out = json.loads(capsys.readouterr().out)
    assert out['state'] == 'done_with_gaps' and out['failed_chunks'] == [{'start': 15, 'end': 30, 'error': out['failed_chunks'][0]['error']}]


# Seen in the Option 1 re-run (M1, 288-300 s): with "describe only events",
# gemma4:12b answers a quiet chunk with blank placeholder rows, not an empty list.
BLANK = {'start': 2.0, 'end': 2.0, 'text': '', 'short_text': '', 'kind': 'other', 'evidence': '', 'uncertainty': ''}


def test_blank_placeholder_rows_mean_nothing_happened():
    rows = [dict(BLANK, start=t, end=t) for t in (2.0, 4.0, 6.0)]
    assert normalize_chunk({'timestamp_reference': 'clip', 'descriptions': rows}, 288, 12) == []


def test_blank_rows_are_skipped_and_the_real_row_is_kept():
    rows = [{'start': 0.0, 'end': 2.0, 'text': 'A man in a grey shirt sits at a large table.', 'kind': 'other'},
            dict(BLANK, start=2.0, end=4.0), dict(BLANK, start=4.0, end=6.0)]
    cues = normalize_chunk({'timestamp_reference': 'clip', 'descriptions': rows}, 0, 16)
    assert [c.text for c in cues] == ['A man in a grey shirt sits at a large table.']


def test_a_row_with_no_text_string_is_still_malformed():
    with pytest.raises(ValueError, match='Malformed'):
        normalize_chunk({'timestamp_reference': 'clip', 'descriptions': [{'start': 1, 'end': 3, 'text': None}]}, 0, 15)
