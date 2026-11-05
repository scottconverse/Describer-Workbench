"""Transport and credential boundaries for subscription/API analysis routes."""
import threading
import json
from contextlib import closing
from unittest.mock import patch

import pytest

from describer import subscriptions
from describer.engine.service import DescriptionService
from describer.project import Project
from describer.services import DEFAULTS,Settings,video_request


def test_subscription_environment_preserves_native_home_and_excludes_unrelated_secrets():
    import os
    fixture={'Path':'native-path','USERPROFILE':'native-home','CODEX_HOME':'native-codex','CLAUDE_CONFIG_DIR':'native-claude',
             'HTTPS_PROXY':'fixture-proxy','LC_MESSAGES':'en_US','DATABASE_URL':'private-db','AWS_SECRET_ACCESS_KEY':'private-aws',
             'AGY_ADC_AUTH':'true','GOOGLE_APPLICATION_CREDENTIALS':'private-adc','GOOGLE_GEMINI_BASE_URL':'api-override',
             'OPENAI_API_KEY':'private-api','ANTHROPIC_API_KEY':'private-api','NODE_OPTIONS':'--require fixture.js'}
    with patch.dict(os.environ,fixture,clear=True):env=subscriptions.subscription_environment()
    if __import__('sys').platform=='darwin':env.pop('PATH',None)  # Finder PATH additions are tested separately.
    assert {key.upper():value for key,value in env.items()}=={key.upper():fixture[key] for key in ('Path','USERPROFILE','CODEX_HOME','CLAUDE_CONFIG_DIR','HTTPS_PROXY','LC_MESSAGES')}


@pytest.mark.parametrize('provider,expected',[('Codex CLI',['login','--device-auth']),('Claude CLI',['auth','login','--claudeai']),('Gemini CLI',['--sandbox','--settings'])])
def test_native_login_hands_off_without_reading_tokens_or_api_environment(tmp_path,provider,expected):
    import os,subprocess
    with patch.dict(os.environ,{'OPENAI_API_KEY':'fixture','ANTHROPIC_API_KEY':'fixture','GEMINI_API_KEY':'fixture'}),patch.object(subscriptions,'cli_command',return_value=['native-cli']),patch.object(subscriptions.subprocess,'Popen') as launch:
        subscriptions.open_native_login(dict(DEFAULTS,analysis_provider=provider),tmp_path)
    command=launch.call_args.args[0]
    if os.name!='nt':
        script=(tmp_path/'subscription-login.command').read_text()
        import shlex
        command=shlex.split(script.split(' native-cli ',1)[1]);command.insert(0,'native-cli')
        assert 'fixture' not in script
    assert command[1:1+len(expected)]==expected
    env=launch.call_args.kwargs['env']
    assert all(key not in env for key in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','GEMINI_API_KEY'))
    if os.name=='nt':assert launch.call_args.kwargs['creationflags']==subprocess.CREATE_NEW_CONSOLE
    assert 'stdout' not in launch.call_args.kwargs and 'stderr' not in launch.call_args.kwargs
    if provider=='Gemini CLI':assert json.loads(command[-1])['useG1Credits'] is False


def test_gateway_unavailable_error_guides_auth_recovery_without_exposing_body():
    import io,urllib.error
    error=urllib.error.HTTPError('http://127.0.0.1:8317/v1/chat/completions',503,'error',{},io.BytesIO(b'{"error":"fixture-private-refresh-token"}'))
    with patch('urllib.request.OpenerDirector.open',side_effect=error),pytest.raises(RuntimeError) as result:
        subscriptions.api_request('http://127.0.0.1:8317/v1/chat/completions','fixture-key',{})
    assert 'gateway/provider sign-in' in str(result.value)
    assert 'fixture-private' not in str(result.value) and 'fixture-key' not in str(result.value)


@pytest.mark.parametrize('provider',['Subscription gateway','Codex CLI','Claude CLI','Gemini CLI','Anthropic API'])
def test_cloud_subscription_routes_require_explicit_consent(provider):
    with pytest.raises(ValueError,match='allow_cloud'):
        DescriptionService._check_permissions(dict(DEFAULTS,analysis_provider=provider),'explore')


def test_new_provider_never_falls_through_to_google():
    with patch('describer.subscriptions.video_request',return_value='fixture') as request,patch('describer.services.google_request') as google:
        settings=dict(DEFAULTS,analysis_provider='Codex CLI')
        assert video_request('clip','prompt',settings,threading.Event(),print)=='fixture'
        request.assert_called_once();google.assert_not_called()


def test_gateway_reads_existing_key_by_reference_and_rejects_credential_urls(tmp_path):
    path=tmp_path/'client-key.txt';path.write_text('private-fixture-key')
    settings=dict(DEFAULTS,analysis_provider='Subscription gateway',gateway_key_file=str(path))
    assert subscriptions.connection(settings)=={'url':'http://127.0.0.1:8317/v1','key':'private-fixture-key'}
    assert path.read_text()=='private-fixture-key'
    for url in ('http://user:pass@localhost/v1','http://remote.example/v1','file:///tmp','https://example.org/v1?key=secret'):
        with pytest.raises(ValueError):subscriptions.connection(dict(settings,gateway_url=url))


def test_custom_connections_keep_separate_credentials_and_models_across_restart(tmp_path):
    from describer.providers import set_model,model_id
    settings=Settings(tmp_path/'settings.json')
    settings.data.update(analysis_provider='OpenAI-compatible',connections={'first':{'url':'http://127.0.0.1:1234/v1','credential':'connection_first_key'},
        'second':{'url':'https://example.org/v1','credential':'connection_second_key'}},connection_id='first',connection_first_key='fixture-one',connection_second_key='fixture-two')
    set_model(settings.data,'local-model');settings.data['connection_id']='second';set_model(settings.data,'remote-model')
    settings.save();assert 'fixture-one' not in settings.path.read_text() and 'fixture-two' not in settings.path.read_text()
    settings=Settings(settings.path)
    assert model_id(settings.data)=='remote-model' and subscriptions.connection(settings.data)['key']=='fixture-two'
    settings.data['connection_id']='first'
    assert model_id(settings.data)=='local-model' and subscriptions.connection(settings.data)['key']=='fixture-one'


def test_job_status_and_project_never_persist_custom_api_key(tmp_path):
    source=tmp_path/'fixture.mp4';source.write_bytes(b'fixture')
    settings=dict(DEFAULTS,analysis_provider='OpenAI-compatible',connections={'one':{'url':'http://127.0.0.1:1234/v1','model':'fixture','credential':'connection_one_key'}},connection_id='one',connection_one_key='private-test-secret')
    with closing(DescriptionService(tmp_path/'engine')) as service,patch('describer.services.segment'),patch('describer.services.video_request',return_value='{"answer":"A room"}'):
        job=service.submit(project=Project(str(source),30),operation='ask',settings=settings);service.wait(job['id'])
        for path in (service.root/job['id']).rglob('*.json'):
            assert 'private-test-secret' not in path.read_text(encoding='utf8')
        assert 'connection_one_key' not in service.get_job(job['id'])['settings']


@pytest.mark.parametrize('provider,event',[
    ('Codex CLI','{"type":"item.completed","item":{"type":"agent_message","text":"answer"}}\n{"type":"turn.completed","usage":{"input_tokens":12,"output_tokens":3}}'),
    ('Claude CLI','{"type":"result","result":"answer","usage":{"input_tokens":12}}'),
    ('Gemini CLI','{"event":"result","result":{"status":"SUCCESS","response":"answer"}}'),
])
def test_native_cli_uses_exact_model_image_and_no_permission_bypass(provider,event,tmp_path):
    image=tmp_path/'frame.jpg';image.write_bytes(b'fixture')
    settings=dict(DEFAULTS,analysis_provider=provider,provider_models={provider:'exact-model'},analysis_effort='medium')
    with patch('describer.subscriptions.cli_command',return_value=['fixture-cli']),patch('describer.subscriptions.run_cli',return_value=event) as run:
        assert subscriptions.cli_reply(settings,[image],'Describe this image.',threading.Event(),print,tmp_path)=='answer'
    args=run.call_args.args[1]
    assert args[args.index('--model')+1]=='exact-model'
    assert not any('bypass' in arg or 'dangerously' in arg for arg in args)
    if provider=='Codex CLI':assert str(image) in args and 'shell_tool' in args and 'multi_agent' in args
    elif provider=='Claude CLI':assert 'base64' in run.call_args.args[2] and '--tools' in args
    else:
        assert image.name in run.call_args.args[2] and '--mode' in args
        restrictions=json.loads(args[args.index('--settings')+1])
        assert restrictions['allowNonWorkspaceAccess'] is False
        assert restrictions['useG1Credits'] is False
        assert set(restrictions['permissions']['deny'])=={'command(*)','write_file(*)','read_url(*)','execute_url(*)','mcp(*)'}


def test_native_cli_rejects_incomplete_or_error_envelope(tmp_path):
    settings=dict(DEFAULTS,analysis_provider='Codex CLI',provider_models={'Codex CLI':'exact'})
    with patch('describer.subscriptions.cli_command',return_value=['fixture']),patch('describer.subscriptions.run_cli',return_value='{"type":"item.completed","item":{"type":"agent_message","text":"partial"}}'):
        with pytest.raises(ValueError,match='completed'):subscriptions.cli_reply(settings,[],'prompt',threading.Event(),print,tmp_path)


@pytest.mark.parametrize('answer,accepted',[( '{"answer":"blue"}',True),('{"answer":"red"}',False),('partial',False)])
def test_image_test_requires_correct_visual_answer(answer,accepted):
    settings=dict(DEFAULTS,analysis_provider='Claude CLI',provider_models={'Claude CLI':'exact'})
    with patch('describer.services.run'),patch('describer.services.tool',return_value='ffmpeg'),patch('describer.subscriptions.video_request',return_value=answer) as request:
        if accepted:assert 'Image test passed' in subscriptions.test_connection(settings,threading.Event(),print)
        else:
            with pytest.raises(ValueError,match='unverified'):subscriptions.test_connection(settings,threading.Event(),print)
    assert 'dominant color' in request.call_args.args[1]


def test_connection_editor_cancel_save_and_credential_removal(tmp_path):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication,QDialog,QDialogButtonBox,QLineEdit,QPushButton,QCheckBox
    from describer.app import Window
    application=QApplication.instance() or QApplication([])
    window=Window(tmp_path/'settings.json');window.settings.data['sounds']=False;window.settings.save()
    original=window.settings.path.read_bytes()
    def edit(save):
        dialog=application.activeModalWidget();assert isinstance(dialog,QDialog)
        next(b for b in dialog.findChildren(QPushButton) if b.text()=='Add connection').click()
        fields={f.accessibleName():f for f in dialog.findChildren(QLineEdit)}
        fields['Name'].setText('Local fixture');fields['Base URL including /v1'].setText('http://127.0.0.1:1234/v1');fields['API key (optional)'].setText('private-fixture')
        buttons=dialog.findChild(QDialogButtonBox)
        buttons.button(QDialogButtonBox.Save if save else QDialogButtonBox.Cancel).click()
    try:
        QTimer.singleShot(0,lambda:edit(False));window.manage_connections()
        assert window.settings.path.read_bytes()==original and not window.settings.data['connections']
        QTimer.singleShot(0,lambda:edit(True));window.manage_connections()
        data=window.settings.data;ident=data['connection_id'];entry=data['connections'][ident]
        assert entry['name']=='Local fixture' and data[entry['credential']]=='private-fixture'
        assert data['analysis_provider']==DEFAULTS['analysis_provider']
        assert 'private-fixture' not in window.settings.path.read_text()
        def remove_key():
            dialog=application.activeModalWidget()
            next(x for x in dialog.findChildren(QCheckBox) if x.text()=='Remove saved credential').setChecked(True)
            dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Save).click()
        QTimer.singleShot(0,remove_key);window.manage_connections()
        assert entry['credential'] not in window.settings.data
    finally:window.close()
