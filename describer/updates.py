"""Opt-in update checks and verified staging; never run an original-app updater."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from . import __version__

OFFICIAL_RELEASE='https://api.github.com/repos/scottconverse/Describer-Workbench/releases/latest'
SIGNER='CN=Scott Converse, O=Scott Converse, L=Longmont, S=co, C=US'


def official_feed():
    request=urllib.request.Request(OFFICIAL_RELEASE,headers={'Accept':'application/vnd.github+json','User-Agent':'DescriberWorkbench/'+__version__})
    with urllib.request.urlopen(request,timeout=20) as response:
        raw=response.read(1024*1024+1)
    if len(raw)>1024*1024:raise ValueError('Release metadata exceeds the size limit.')
    release=json.loads(raw)
    if release.get('draft') or release.get('prerelease'):raise ValueError('Expected a published stable release.')
    tag=release['tag_name'];number=tag.removeprefix('v');version(number)
    expected=f'DescriberWorkbench-{number}-windows-x64.zip'
    assets=[row for row in release.get('assets',[]) if row.get('name')==expected and row.get('state')=='uploaded']
    if len(assets)!=1:raise ValueError('The official release does not contain one Windows portable package.')
    asset=assets[0];digest=asset.get('digest','')
    if not re.fullmatch('sha256:[0-9a-fA-F]{64}',digest):raise ValueError('The official Windows package has no SHA-256 digest.')
    url=asset['browser_download_url']
    if url!=f'https://github.com/scottconverse/Describer-Workbench/releases/download/{tag}/{expected}':raise ValueError('Unexpected official package URL.')
    return {'application':'DescriberWorkbench','version':number,'sha256':digest[7:],'url':url,'source':OFFICIAL_RELEASE}


def version(value):
    if not re.fullmatch(r'\d+\.\d+\.\d+',value):raise ValueError('Expected a numeric major.minor.patch version.')
    return tuple(map(int,value.split('.')))


def read_feed(location=''):
    if not location:data=official_feed()
    elif not Path(location).is_absolute() and urlparse(location).scheme:
        if urlparse(location).scheme!='https':raise ValueError('Remote update feeds require HTTPS.')
        with urllib.request.urlopen(location,timeout=20) as response:data=json.loads(response.read(1024*1024))
    else:data=json.loads(Path(location).read_text(encoding='utf-8-sig'))
    if data.get('application')!='DescriberWorkbench':raise ValueError('Update belongs to a different application.')
    version(data['version'])
    if not re.fullmatch('[0-9a-fA-F]{64}',data.get('sha256','')):raise ValueError('Update feed needs a SHA-256 digest.')
    data['newer']=version(data['version'])>version(__version__)
    return data


SIGNATURE_SCRIPT=r'''
# Use this host's Windows modules, not inherited modules from another PowerShell
# edition or a development harness. This changes only the verifier/helper child.
$env:PSModulePath=$PSHOME+'\Modules'
function Assert-Publisher($root) {
 foreach ($name in @('DescriberWorkbench.exe','DescriberCLI.exe')) {
  $sig=Get-AuthenticodeSignature -LiteralPath (Join-Path $root $name)
  if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -ne 'CN=Scott Converse, O=Scott Converse, L=Longmont, S=co, C=US' -or !$sig.TimeStamperCertificate) {
   throw 'Update signature must be Valid, timestamped and issued to Scott Converse'
  }
 }
}
'''


def verify_signatures(root):
    if os.name!='nt':raise ValueError('Windows Authenticode verification is required to stage this Windows update.')
    shell=shutil.which('powershell.exe') or shutil.which('pwsh.exe')
    if not shell:raise ValueError('PowerShell is required to verify the update publisher.')
    # The path is passed through the child environment, never interpolated as code.
    env=dict(os.environ,DESCRIBER_VERIFY_ROOT=str(Path(root).resolve()))
    result=subprocess.run([shell,'-NoProfile','-NonInteractive','-Command',
        "$ErrorActionPreference='Stop';"+SIGNATURE_SCRIPT+'Assert-Publisher $env:DESCRIBER_VERIFY_ROOT'],
        env=env,capture_output=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise ValueError('Update signature verification failed. Both executables must be Valid, timestamped and signed by Scott Converse; nothing installed.')


def payload_hashes(root):
    return {str(path.relative_to(root)).replace('\\','/'):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(root).rglob('*')) if path.is_file() and path!=Path(root)/'update-receipt.json'}


def verify_staged(root):
    receipt=json.loads((Path(root)/'update-receipt.json').read_text(encoding='utf8'))
    if not receipt.get('files') or receipt['files']!=payload_hashes(root):raise ValueError('Staged update changed after verification; stage it again.')
    verify_signatures(root)


def stage_update(feed,destination,cancel,log):
    version(feed['version'])
    if cancel.is_set():raise InterruptedError('Cancelled.')
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
        if not all((root/name).is_file() for name in ('DescriberWorkbench.exe','DescriberCLI.exe')) or not (root/'_internal').is_dir():raise ValueError('Not a portable Describer Workbench package.')
        verify_signatures(root)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(root,target)
        receipt={k:feed[k] for k in ['application','version','sha256']}
        receipt['files']=payload_hashes(target)
        (target/'update-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
        log('Verified update staged at '+str(target))
    return str(target)

# This helper is newly written. It runs only after an explicit Install action.
APPLY_SCRIPT = SIGNATURE_SCRIPT+r'''
$ErrorActionPreference='Stop'
$d=Get-Content -Raw -Encoding UTF8 -LiteralPath $args[0] | ConvertFrom-Json
try {
 $p=Get-Process -Id $d.pid -ErrorAction SilentlyContinue
 if ($p) {
  if ($p.Path -ne $d.executable) {throw 'Process identity changed; update stopped'}
  $p.WaitForExit()
 }
 if (!(Test-Path -LiteralPath ($d.incoming+'\DescriberWorkbench.exe'))) {throw 'Prepared update is missing'}
 Assert-Publisher $d.incoming
 $verified=Get-Content -Raw -Encoding UTF8 -LiteralPath ($d.incoming+'\update-receipt.json') | ConvertFrom-Json
 $files=@(Get-ChildItem -LiteralPath $d.incoming -File -Recurse | Where-Object {$_.FullName -ne ($d.incoming+'\update-receipt.json')})
 if ($files.Count -ne @($verified.files.PSObject.Properties).Count) {throw 'Prepared update file count changed'}
 foreach ($file in $files) {
  $relative=$file.FullName.Substring($d.incoming.Length+1).Replace('\','/')
  if ((Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ne $verified.files.$relative) {throw 'Prepared update changed after verification'}
 }
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
    verify_staged(staged)
    label=str(time.time_ns());incoming=install.with_name(install.name+'.incoming-'+label);backup=install.with_name(install.name+'.previous-'+label)
    if incoming.exists() or backup.exists():raise ValueError('Update destinations already exist.')
    shutil.copytree(staged,incoming)
    workspace=Path(workspace);workspace.mkdir(parents=True,exist_ok=True)
    script=workspace/('apply-'+label+'.ps1');payload=workspace/('apply-'+label+'.json');receipt=workspace/('receipt-'+label+'.json')
    script.write_text(APPLY_SCRIPT,encoding='utf-8-sig')
    payload.write_text(json.dumps(dict(pid=pid,launch=launch,executable=str(executable),install=str(install),incoming=str(incoming),backup=str(backup),receipt=str(receipt))),encoding='utf8')
    return script,payload,receipt
