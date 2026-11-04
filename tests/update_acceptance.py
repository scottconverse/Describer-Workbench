"""Disposable signed update acceptance; preserves historical evidence.

Usage: python -m tests.update_acceptance SIGNED_ARCHIVE NEW_OUTPUT_DIRECTORY
The archive must match the current official published release digest.
"""
import hashlib
import json
import subprocess
import sys
import threading
from pathlib import Path
from describer.updates import prepare_apply, read_feed, stage_update


def main():
    archive=Path(sys.argv[1]).resolve();root=Path(sys.argv[2]).resolve()
    if root.exists():raise ValueError('Choose a fresh disposable output directory.')
    feed=read_feed()
    with archive.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if digest!=feed['sha256']:raise ValueError('Archive does not match current official release digest.')
    root.mkdir(parents=True)
    staged=Path(stage_update(dict(feed,url=str(archive)),root/'staging',threading.Event(),print))
    installed=root/'installed';installed.mkdir();exe=installed/'DescriberWorkbench.exe'
    exe.write_bytes(b'previous installation fixture')
    script,payload,receipt=prepare_apply(staged,installed,exe,2147483647,root/'job',launch=False)
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script),str(payload)],capture_output=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
    applied=json.loads(receipt.read_text(encoding='utf-8-sig'))
    assert applied['success'],applied
    assert exe.read_bytes()==(staged/'DescriberWorkbench.exe').read_bytes()
    assert (Path(applied['backup'])/'DescriberWorkbench.exe').read_bytes()==b'previous installation fixture'
    result={'passed':True,'official_version':feed['version'],'sha256':digest,'signed_package_verified':True,'real_directory_swap':True,'rollback_bytes_verified':True,'relaunch':'Not exercised; separate portable acceptance required.','production_installation':'Untouched'}
    (root/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))


if __name__=='__main__':main()
