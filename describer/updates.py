"""Opt-in update checks and verified staging; never run an original-app updater."""
import hashlib
import json
import re
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from . import __version__


def version(value):
    if not re.fullmatch(r'\d+\.\d+\.\d+',value):raise ValueError('Expected a numeric major.minor.patch version.')
    return tuple(map(int,value.split('.')))


def read_feed(location):
    if not Path(location).is_absolute() and urlparse(location).scheme:
        if urlparse(location).scheme!='https':raise ValueError('Remote update feeds require HTTPS.')
        with urllib.request.urlopen(location,timeout=20) as response:data=json.loads(response.read(1024*1024))
    else:data=json.loads(Path(location).read_text(encoding='utf-8-sig'))
    if data.get('application')!='DescriberWorkbench':raise ValueError('Update belongs to a different application.')
    version(data['version'])
    if not re.fullmatch('[0-9a-fA-F]{64}',data.get('sha256','')):raise ValueError('Update feed needs a SHA-256 digest.')
    data['newer']=version(data['version'])>version(__version__)
    return data


def stage_update(feed,destination,cancel,log):
    target=Path(destination)/('DescriberWorkbench-'+feed['version'])
    if target.exists():raise ValueError('This staged version already exists. Choose a new staging folder.')
    with tempfile.TemporaryDirectory(prefix='describer-update-') as tmp:
        tmp=Path(tmp);archive=tmp/'update.zip';url=feed['url']
        if not Path(url).is_absolute() and urlparse(url).scheme:
            if urlparse(url).scheme!='https':raise ValueError('Remote packages require HTTPS.')
            with urllib.request.urlopen(url,timeout=30) as source,archive.open('wb') as out:
                while block:=source.read(1024*1024):
                    if cancel.is_set():raise InterruptedError('Cancelled.')
                    out.write(block)
        else:shutil.copyfile(url,archive)
        with archive.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if digest.lower()!=feed['sha256'].lower():raise ValueError('Update hash mismatch; nothing installed.')
        extracted=tmp/'payload';extracted.mkdir()
        with zipfile.ZipFile(archive) as z:
            if sum(i.file_size for i in z.infolist())>4*1024**3:raise ValueError('Update exceeds the 4 GiB unpacked limit.')
            for entry in z.infolist():
                if cancel.is_set():raise InterruptedError('Cancelled.')
                name=entry.filename.replace('\\','/')
                resolved=(extracted/name).resolve()
                if not resolved.is_relative_to(extracted.resolve()) or ':' in name or (entry.external_attr>>16)&0o170000==0o120000:raise ValueError('Unsafe update archive path.')
            z.extractall(extracted)
        root=extracted/'DescriberWorkbench'
        if not (root/'DescriberWorkbench.exe').is_file() or not (root/'_internal').is_dir():raise ValueError('Not a portable Describer Workbench package.')
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(root,target)
        (target/'update-receipt.json').write_text(json.dumps({k:feed[k] for k in ['application','version','sha256']},indent=2))
        log('Verified update staged at '+str(target))
    return str(target)

# This helper is newly written. It runs only after an explicit Install action.
APPLY_SCRIPT = r'''
$ErrorActionPreference='Stop'
$d=Get-Content -Raw -Encoding UTF8 -LiteralPath $args[0] | ConvertFrom-Json
try {
 $p=Get-Process -Id $d.pid -ErrorAction SilentlyContinue
 if ($p) {
  if ($p.Path -ne $d.executable) {throw 'Process identity changed; update stopped'}
  $p.WaitForExit()
 }
 if (!(Test-Path -LiteralPath ($d.incoming+'\DescriberWorkbench.exe'))) {throw 'Prepared update is missing'}
 if (Test-Path -LiteralPath $d.backup) {throw 'Backup destination already exists'}
 Move-Item -LiteralPath $d.install -Destination $d.backup
 try {Move-Item -LiteralPath $d.incoming -Destination $d.install}
 catch {Move-Item -LiteralPath $d.backup -Destination $d.install;throw}
 @{success=$true;backup=$d.backup;installed=$d.install} | ConvertTo-Json | Set-Content -LiteralPath $d.receipt -Encoding UTF8
 if ($d.launch) {Start-Process -FilePath $d.executable -WorkingDirectory $d.install}
} catch {
 @{success=$false;error=$_.Exception.Message;backup=$d.backup} | ConvertTo-Json | Set-Content -LiteralPath $d.receipt -Encoding UTF8
}
'''


def prepare_apply(staged,install,executable,pid,workspace,launch=True):
    """Prepare a sibling swap and retained rollback. No install mutation here."""
    import time
    staged=Path(staged).resolve();install=Path(install).resolve();executable=Path(executable).resolve()
    if executable!=install/'DescriberWorkbench.exe' or not executable.is_file():raise ValueError('Update installation identity does not match the running executable.')
    if staged==install or staged.is_relative_to(install) or install.is_relative_to(staged):raise ValueError('Staging and installed folders must be separate.')
    label=str(time.time_ns());incoming=install.with_name(install.name+'.incoming-'+label);backup=install.with_name(install.name+'.previous-'+label)
    if incoming.exists() or backup.exists():raise ValueError('Update destinations already exist.')
    shutil.copytree(staged,incoming)
    workspace=Path(workspace);workspace.mkdir(parents=True,exist_ok=True)
    script=workspace/('apply-'+label+'.ps1');payload=workspace/('apply-'+label+'.json');receipt=workspace/('receipt-'+label+'.json')
    script.write_text(APPLY_SCRIPT,encoding='utf-8-sig')
    payload.write_text(json.dumps(dict(pid=pid,launch=launch,executable=str(executable),install=str(install),incoming=str(incoming),backup=str(backup),receipt=str(receipt))),encoding='utf8')
    return script,payload,receipt
