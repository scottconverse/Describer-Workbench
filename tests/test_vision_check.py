"""F8 (DW-12): refuse a model that cannot read a known test image."""
import json
import threading
from unittest.mock import patch

import pytest

from describer import models
from describer.services import asset_path

SEEING = 'The image shows the text "CIVIC 42" above a red circle.'
BLIND = 'Dark abstract background with glowing patterns.'
TAGS = {'models': [{'name': 'gemma4:12b', 'digest': 'aaa'}, {'name': 'gemma4:e4b', 'digest': 'bbb'}]}


def settings(model):
    return {'ollama_url': 'http://127.0.0.1:11434', 'ollama_model': model}


def run(model, answer, cache):
    with patch.object(models, 'model_info', return_value={'capabilities': ['vision']}), \
         patch.object(models, 'json_request', return_value=TAGS), \
         patch.object(models, 'chat', return_value=answer) as chat:
        try:
            models.vision_check(settings(model), threading.Event(), lambda _: None, cache)
        finally:
            run.calls = chat.call_args_list


def test_the_built_in_image_ships_with_the_app():
    assert asset_path('vision-check.png').is_file()


def test_a_blind_model_is_refused_before_the_job(tmp_path):
    with pytest.raises(ValueError, match=r'Model gemma4:e4b failed the vision check \(could not read a test image\)\. '
                                         r'Choose a vision-capable model\.'):
        run('gemma4:e4b', BLIND, tmp_path / 'vision.json')
    message = run.calls[0].args[1][0]
    assert message['images'] and 'text' in message['content'].lower()


def test_a_seeing_model_passes_and_the_result_is_cached_by_digest(tmp_path):
    cache = tmp_path / 'vision.json'
    run('gemma4:12b', SEEING, cache)
    assert len(run.calls) == 1
    run('gemma4:12b', BLIND, cache)
    assert len(run.calls) == 0, 'a cached pass for the same digest needs no new request'
    assert json.loads(cache.read_text('utf-8'))['gemma4:12b@aaa']['passed'] is True


def test_the_job_runs_the_check_before_any_frame_is_described(tmp_path):
    from describer.engine import core
    from describer.project import Project
    order = []
    with patch('describer.services.narration_preflight'), \
         patch.object(core, 'identity', return_value={'fixture': 1}), \
         patch.object(core, 'protected_audio', return_value={'protected': [], 'classification': [], 'safe_gaps': []}), \
         patch('describer.models.vision_check', side_effect=ValueError('Model x failed the vision check')) as check, \
         patch('describer.services.observe', side_effect=lambda *a, **k: order.append('observe')):
        with pytest.raises(ValueError, match='vision check'):
            core.describe(Project('fixture.mp4', 10), dict(settings('x'), analysis_provider='Ollama'), '',
                          tmp_path / 'job' / 'stages', threading.Event(), lambda _: None)
    assert check.called and order == []
