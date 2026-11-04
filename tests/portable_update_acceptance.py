"""Disposable real portable update. Prepare, close its owned window, then verify."""
import hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
from describer.updates import prepare_apply,verify_staged
from describer.services import CREATE_NO_WINDOW

def digest(path):
 with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
 mode=sys.argv[1];root=Path(sys.argv[2]).resolve();state=root/'state.json'
 if mode=='prepare':
  if root.exists():raise ValueError('Choose a fresh disposable test directory.')
  old=Path(sys.argv[3]).resolve();new=Path(sys.argv[4]).resolve();install=root/'installed'
  verify_staged(new)
  root.mkdir(parents=True)
  shutil.copytree(old,install);exe=install/'DescriberWorkbench.exe';env=dict(os.environ,LOCALAPPDATA=str(root/'data'))
  process=subprocess.Popen([str(exe)],env=env);time.sleep(2)
  if process.poll() is not None:raise RuntimeError('Disposable old build exited before update.')
  script,payload,receipt=prepare_apply(new,install,exe,process.pid,root/'job',launch=True)
  helper=subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script),str(payload)],env=env,creationflags=CREATE_NO_WINDOW)
  result=dict(owned_gui_pid=process.pid,helper_pid=helper.pid,helper_script=str(script),receipt=str(receipt),old_sha256=digest(exe),new_sha256=digest(new/'DescriberWorkbench.exe'),install=str(install),expected='Close the disposable Workbench window; helper waits, swaps directories and restarts the new build.',cancel='Verify PID and executable/script identity before stopping these owned processes.')
  state.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
 elif mode=='verify':
  data=json.loads(state.read_text());receipt=Path(data['receipt']);deadline=time.monotonic()+20
  while not receipt.exists() and time.monotonic()<deadline:time.sleep(.2)
  applied=json.loads(receipt.read_text(encoding='utf-8-sig'));assert applied['success'],applied
  assert digest(Path(data['install'])/'DescriberWorkbench.exe')==data['new_sha256']
  assert digest(Path(applied['backup'])/'DescriberWorkbench.exe')==data['old_sha256']
  result=dict(passed=True,real_portable_swap=True,rollback_hash_verified=True,installed_sha256=data['new_sha256'],old_sha256=data['old_sha256'],helper_receipt=applied,relaunch='Helper requested real executable launch. Running path and UI are independently verified through Computer Use.',production_installation='Untouched during this test')
  (root/'portable-update.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
 else:raise ValueError('Expected prepare or verify.')

if __name__=='__main__':main()
