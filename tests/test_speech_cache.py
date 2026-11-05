import json
import threading
from types import SimpleNamespace
from unittest.mock import Mock,patch

import portalocker
import pytest

from describer.engine import speech_cache


def fixture(tmp_path):
    source=tmp_path/'source';source.write_bytes(b'original media')
    model=tmp_path/'model';model.write_bytes(b'original detector')
    decoder=tmp_path/'ffmpeg';decoder.write_bytes(b'decoder')
    analysis=Mock(return_value=([[1,2]],[{'time':0,'speech':.2,'vocal':0,'music':0}]))
    return source,model,decoder,analysis


def test_identity_corruption_and_cancellation(tmp_path):
    source,model,decoder,analysis=fixture(tmp_path);root=tmp_path/'cache';logs=[]
    def call(cancel=None):return speech_cache.measured(source,10,model,cancel,logs.append,analysis,root)
    with patch('describer.services.tool',return_value=str(decoder)):
        expected=call();assert call()==expected and analysis.call_count==1
        path=next(root.glob('*.json'));data=json.loads(path.read_text());data['value']['spans']=[];path.write_text(json.dumps(data))
        assert call()==expected and analysis.call_count==2
        source.write_bytes(b'changed media');call();assert analysis.call_count==3
        model.write_bytes(b'changed detector');call();assert analysis.call_count==4
        decoder.write_bytes(b'changed decoder');call();assert analysis.call_count==5
        cancelled=threading.Event();cancelled.set()
        with pytest.raises(InterruptedError):call(cancelled)
        assert analysis.call_count==5
        latest=max(root.glob('*.json'),key=lambda p:p.stat().st_mtime_ns)
        with portalocker.Lock(str(latest.with_suffix('.lock')),timeout=0):
            timer=threading.Timer(.2,cancelled.set);cancelled.clear();timer.start()
            try:
                with pytest.raises(InterruptedError):call(cancelled)
            finally:timer.join()
    assert any('Reusing validated' in x for x in logs) and any('rejected' in x for x in logs)


def test_failures_do_not_publish_or_disable_analysis(tmp_path):
    source,model,decoder,analysis=fixture(tmp_path)
    with patch('describer.services.tool',return_value=str(decoder)):
        unavailable=tmp_path/'unavailable';unavailable.write_text('file, not directory')
        assert speech_cache.measured(source,10,model,None,lambda _:None,analysis,unavailable)==analysis.return_value
        root=tmp_path/'cache'
        analysis.side_effect=InterruptedError('cancelled during detector')
        with pytest.raises(InterruptedError):speech_cache.measured(source,10,model,None,lambda _:None,analysis,root)
        assert not list(root.glob('*.json'))
        def changed(*args):source.write_bytes(b'changed while analyzing');return [[1,2]],[]
        with pytest.raises(ValueError,match='changed during'):speech_cache.measured(source,10,model,None,lambda _:None,changed,root)
        assert not list(root.glob('*.json'))


def test_caption_overlay_is_fresh_and_frozen_identity_works(tmp_path):
    from describer.project import Project
    from describer.engine.core import protected_audio
    source,model,decoder,analysis=fixture(tmp_path)
    captions=tmp_path/'captions.srt';captions.write_text('1\n00:00:04,000 --> 00:00:05,000\nSpeech\n')
    with patch('describer.services.tool',return_value=str(decoder)),patch('describer.services.run',return_value=b'{"streams":[{"codec_type":"audio"}]}'),patch('describer.engine.core.speech_model',return_value=model),patch('describer.engine.sound.speech_spans',analysis),patch('describer.engine.speech_cache.default_root',return_value=tmp_path),patch('describer.engine.speech_cache.sys',SimpleNamespace(frozen=True,executable=str(decoder))):
        first=protected_audio(Project(str(source),10),{},None,lambda _:None)
        second=protected_audio(Project(str(source),10),{'captions':str(captions)},None,lambda _:None)
        assert analysis.call_count==1 and first['classification']==second['classification']
        assert first['protected']==[(1,2)] and second['protected']==[(1,2),(3.7,5.3)]
