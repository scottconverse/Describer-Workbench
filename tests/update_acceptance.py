import json,tempfile
from pathlib import Path
from describer.updates import prepare_apply
from describer.services import run


def main():
 with tempfile.TemporaryDirectory(prefix='describer-update-test-') as tmp:
  tmp=Path(tmp);installed=tmp/'installed';staged=tmp/'staged'
  for folder in [installed,staged]:(folder/'_internal').mkdir(parents=True)
  (installed/'DescriberWorkbench.exe').write_bytes(b'old fixture - not executable')
  (staged/'DescriberWorkbench.exe').write_bytes(b'new fixture - not executable')
  script,payload,receipt=prepare_apply(staged,installed,installed/'DescriberWorkbench.exe',2147483647,tmp/'job',launch=False)
  run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script),str(payload)])
  result=json.loads(receipt.read_text(encoding='utf-8-sig'));assert result['success'],result
  assert (installed/'DescriberWorkbench.exe').read_bytes().startswith(b'new')
  assert (Path(result['backup'])/'DescriberWorkbench.exe').read_bytes().startswith(b'old')
  result={'passed':True,'real_directory_swap':True,'rollback_copy_verified':True,'relaunch':'Not exercised; fixture files intentionally not executable.','production_installation':'Untouched'}
  Path('evidence/acceptance-0.2/update-apply.json').write_text(json.dumps(result,indent=2));print(result)

if __name__=='__main__':main()
