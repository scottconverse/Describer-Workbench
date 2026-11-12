"""Official release selection and authenticated staging/apply boundaries."""
import hashlib
import json
import threading
import zipfile
from unittest.mock import patch,MagicMock

import pytest

from describer import updates


def release():
    return {'tag_name':'v9.0.0','draft':False,'prerelease':False,'assets':[{
        'name':'DescriberWorkbench-9.0.0-windows-x64.zip','state':'uploaded','digest':'sha256:'+'a'*64,
        'browser_download_url':'https://github.com/scottconverse/Describer-Workbench/releases/download/v9.0.0/DescriberWorkbench-9.0.0-windows-x64.zip'}]}


@pytest.mark.parametrize('mutation',[None,'prerelease','missing_digest','wrong_url','missing_asset'])
def test_official_feed_selects_only_published_package_and_digest(mutation):
    data=release()
    if mutation=='prerelease':data['prerelease']=True
    elif mutation=='missing_digest':data['assets'][0].pop('digest')
    elif mutation=='wrong_url':data['assets'][0]['browser_download_url']='https://elsewhere.example/file.zip'
    elif mutation=='missing_asset':data['assets']=[]
    response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps(data).encode()
    with patch('urllib.request.urlopen',return_value=response) as request:
        if mutation:
            with pytest.raises(ValueError):updates.read_feed()
        else:
            result=updates.read_feed();assert result['newer'] and result['sha256']=='a'*64
        assert request.call_args.args[0].full_url==updates.OFFICIAL_RELEASE


def package(tmp_path):
    archive=tmp_path/'package.zip'
    with zipfile.ZipFile(archive,'w') as stream:
        for name,content in [('DescriberWorkbench.exe',b'gui'),('DescriberCLI.exe',b'cli'),('_internal/runtime.dll',b'runtime')]:
            stream.writestr('DescriberWorkbench/'+name,content)
    return {'application':'DescriberWorkbench','version':'9.0.0','url':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}


def test_invalid_signature_never_stages_and_runtime_tampering_never_prepares_apply(tmp_path):
    feed=package(tmp_path);target=tmp_path/'stage'
    with patch('describer.updates.verify_signatures',side_effect=ValueError('untrusted publisher')):
        with pytest.raises(ValueError,match='untrusted'):updates.stage_update(feed,target,threading.Event(),print)
    assert not target.exists()
    with patch('describer.updates.verify_signatures'):
        staged=updates.stage_update(feed,target,threading.Event(),print)
        updates.verify_staged(staged)
        installed=tmp_path/'installed';installed.mkdir();exe=installed/'DescriberWorkbench.exe';exe.write_bytes(b'old')
        script,payload,receipt=updates.prepare_apply(staged,installed,exe,12345,tmp_path/'jobs',False)
        assert 'Assert-Publisher $d.incoming' in script.read_text(encoding='utf-8-sig')
        assert 'Get-FileHash' in script.read_text(encoding='utf-8-sig')
        assert exe.read_bytes()==b'old' and not receipt.exists()
        from pathlib import Path
        (Path(staged)/'_internal/runtime.dll').write_bytes(b'tampered')
        with pytest.raises(ValueError,match='changed'):updates.prepare_apply(staged,installed,exe,12345,tmp_path/'bad-jobs',False)
        assert not (tmp_path/'bad-jobs').exists()


def test_apply_helper_leaves_the_install_folder_before_the_swap():
    # 0.8.2 bug: a helper started inside the install folder locked it, so the folder move failed.
    script=updates.APPLY_SCRIPT
    assert "Set-Location -LiteralPath (Split-Path -Parent $args[0])" in script
    # Set-Location alone leaves the Windows process folder inside the install folder.
    assert "[System.IO.Directory]::SetCurrentDirectory((Split-Path -Parent $args[0]))" in script
    assert script.index('SetCurrentDirectory')<script.index('Move-Item')
