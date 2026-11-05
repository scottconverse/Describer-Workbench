"""Platform boundaries: native defaults, measured voices and secure references."""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from describer import platforms


@pytest.mark.parametrize('host,engine,relative',[
    ('win32','Windows','DescriberWorkbench'),
    ('darwin','macOS','Library/Application Support/DescriberWorkbench'),
    ('linux','eSpeak NG','.local/share/DescriberWorkbench')])
def test_platform_defaults_keep_windows_identity(tmp_path,host,engine,relative):
    with patch.object(sys,'platform',host),patch.object(Path,'home',return_value=tmp_path),patch.dict(os.environ,{},clear=True):
        assert platforms.data_directory()==tmp_path/relative
        assert platforms.native_engine()==engine
        assert engine in platforms.narration_engines()
        if host=='win32':assert platforms.native_text('Windows DPAPI and Windows voice')=='Windows DPAPI and Windows voice'
        else:assert 'Windows' not in platforms.native_text('Windows DPAPI and Windows voice')


@pytest.mark.parametrize('host,engine,listing,voice',[
    ('darwin','macOS','Samantha           en_US    # Hello\n','Samantha'),
    ('linux','eSpeak NG','Pty Language Age/Gender VoiceName File Other\n 5 en-us --/M English_(America) gmw/en-US (en 3)\n','gmw/en-US')])
def test_native_voice_ids_and_safe_file_input(tmp_path,host,engine,listing,voice):
    from describer.unix_speech import unix_speech
    calls=[];text='--danger; $(echo secret)';output=tmp_path/'measured.wav'
    def run(args,cancel):
        calls.append(args)
        if '--voices' in args or '?' in args:return listing.encode()
        if '-f' in args and 'ffmpeg' not in args[0]:
            assert Path(args[args.index('-f')+1]).read_text()==text
        if '-af' in args:output.write_bytes(b'RIFF'+b'0'*64)
        return b''
    with patch.object(sys,'platform',host),patch('shutil.which',return_value='/usr/bin/espeak-ng'),patch.object(Path,'is_file',return_value=True),patch('describer.services.run',side_effect=run),patch('describer.services.tool',return_value='ffmpeg'):
        assert unix_speech(engine,listing=True)[0]['id']==voice
        unix_speech(engine,text,output,voice,volume=40)
    assert all(text not in part for args in calls for part in args)
    assert calls[-2][-2:]==['-v',voice]
    assert 'volume=0.4' in calls[-1]


def test_frozen_linux_system_tools_do_not_load_bundle_libraries():
    with patch.object(sys,'platform','linux'),patch.object(sys,'frozen',True,create=True),patch.dict(os.environ,{'LD_LIBRARY_PATH':'bundle','LD_LIBRARY_PATH_ORIG':'system'},clear=True):
        assert platforms.external_environment()=={'LD_LIBRARY_PATH':'system'}
    with patch.object(sys,'platform','linux'),patch.object(sys,'frozen',True,create=True),patch.dict(os.environ,{'LD_LIBRARY_PATH':'bundle'},clear=True):
        assert not platforms.external_environment()


@pytest.mark.skipif(sys.platform=='win32',reason='Windows retains its existing console/process ownership')
def test_native_login_preserves_desktop_bus_but_excludes_api_overrides(tmp_path):
    from describer.subscriptions import open_native_login
    fixture={'HOME':str(tmp_path),'PATH':'/usr/bin:/bin','DISPLAY':':98','DBUS_SESSION_BUS_ADDRESS':'unix:path=/fixture','OPENAI_API_KEY':'private-key','NODE_OPTIONS':'--require private.js'}
    with patch.dict(os.environ,fixture,clear=True),patch('describer.subscriptions.cli_command',return_value=['/fixture/native tool']),patch('shutil.which',return_value='/usr/bin/xterm'),patch('subprocess.Popen') as launch:
        open_native_login({'analysis_provider':'Codex CLI'},tmp_path)
    env=launch.call_args.kwargs['env']
    assert env['DISPLAY']==':98' and env['DBUS_SESSION_BUS_ADDRESS']=='unix:path=/fixture'
    assert 'OPENAI_API_KEY' not in env and 'NODE_OPTIONS' not in env
    script=(tmp_path/'subscription-login.command').read_text()
    assert 'private-key' not in script and 'private.js' not in script
    assert "'/fixture/native tool'" in script


@pytest.mark.skipif(sys.platform=='win32',reason='Windows uses the unchanged owned taskkill tree path')
def test_unix_cli_cancellation_stops_its_owned_child(tmp_path):
    import threading
    import time
    from describer.subscriptions import run_cli
    ready=tmp_path/'ready';stopped=tmp_path/'stopped'
    child="import signal,time,sys;from pathlib import Path;signal.signal(signal.SIGTERM,lambda *args:(Path(sys.argv[2]).write_text('stopped'),sys.exit(0)));Path(sys.argv[1]).write_text('ready');time.sleep(30)"
    parent="import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2],sys.argv[3]]);time.sleep(30)"
    cancel=threading.Event()
    def request_cancel():
        deadline=time.monotonic()+10
        while not ready.exists() and time.monotonic()<deadline:time.sleep(.02)
        cancel.set()
    owner=threading.Thread(target=request_cancel);owner.start()
    try:
        with pytest.raises(InterruptedError):run_cli([sys.executable],['-c',parent,child,str(ready),str(stopped)],'',tmp_path,cancel,15)
        deadline=time.monotonic()+3
        while not stopped.exists() and time.monotonic()<deadline:time.sleep(.02)
        assert ready.exists() and stopped.read_text()=='stopped'
    finally:cancel.set();owner.join(timeout=11)


@pytest.mark.skipif(sys.platform=='win32',reason='Windows retains independently verified DPAPI storage')
def test_keyring_roundtrip_reuses_reference_and_never_writes_plaintext(tmp_path):
    from describer.services import Settings
    module='keyring.backends.macOS' if sys.platform=='darwin' else 'keyring.backends.SecretService'
    store={}
    with patch(module+'.Keyring') as cls:
        backend=cls.return_value
        backend.set_password.side_effect=lambda service,key,value:store.__setitem__((service,key),value)
        backend.get_password.side_effect=lambda service,key:store.get((service,key))
        settings=Settings(tmp_path/'settings.json');settings.data['gemini_key']='fixture-private-key';settings.save()
        first=json.loads(settings.path.read_text())['gemini_key'];settings.save()
        assert backend.set_password.call_count==1
        assert Settings(settings.path).data['gemini_key']=='fixture-private-key'
        assert json.loads(settings.path.read_text())['gemini_key']==first
        assert 'fixture-private-key' not in settings.path.read_text()
        backend.set_password.side_effect=RuntimeError('locked')
        settings.data['gemini_key']='replacement-private-key'
        with pytest.raises(RuntimeError,match='not saved as plaintext'):settings.save()
        assert json.loads(settings.path.read_text())['gemini_key']==first


@pytest.mark.skipif(sys.platform=='win32',reason='Windows updater remains unchanged')
def test_unix_update_never_enters_windows_staging(tmp_path,qt_application_lifetime):
    from describer.app import Window
    from PySide6.QtWidgets import QMessageBox
    window=Window(tmp_path/'settings.json')
    try:
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No),patch('describer.updates.read_feed',side_effect=AssertionError('Windows feed must not run')):
            window.check_updates()
    finally:window.dirty=False;window.close()
