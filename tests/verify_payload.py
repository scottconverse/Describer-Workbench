"""Link the frozen application code to its source; no executable is launched."""
import hashlib,json,sys,types
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader

def digest(path):
 with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def fingerprint(value):
 if isinstance(value,types.CodeType):
  return tuple((name,fingerprint(getattr(value,name))) for name in ['co_code','co_consts','co_names','co_varnames','co_freevars','co_cellvars','co_argcount','co_posonlyargcount','co_kwonlyargcount','co_flags','co_stacksize','co_exceptiontable'])
 if isinstance(value,tuple):return tuple(fingerprint(v) for v in value)
 return value

def main():
 exe=Path(sys.argv[1]);output=Path(sys.argv[2]);reader=CArchiveReader(str(exe));pyz=reader.open_embedded_archive('PYZ.pyz');modules={}
 for path in sorted(Path('describer').rglob('*.py')):
  parts=list(path.with_suffix('').parts)
  if parts[-1]=='__init__':parts.pop()
  module='.'.join(parts)
  modules[module]=fingerprint(pyz.extract(module))==fingerprint(compile(path.read_bytes(),str(path),'exec',optimize=0))
 assert all(modules.values()),modules
 for module in ['accessible_output2.outputs.nvda','accessible_output2.outputs.jaws','libloader.com','win32com.client']:
  assert module in pyz.toc,module
 assert (exe.parent/'_internal/accessible_output2/lib/nvdaControllerClient64.dll').is_file()
 identity={str(p).replace('\\','/'):digest(p) for folder in ['describer','assets'] for p in sorted(Path(folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
 for name in ['DescriberWorkbench.spec','requirements.txt','run.py','run_cli.py','build.ps1','pyproject.toml']:identity[name]=digest(name)
 result={'passed':True,'exe_sha256':digest(exe),'modules':modules,'reader_modules_present':True,'nvda_dll_present':True,'source_identity':identity,'comparison':'Bytecode, recursive constants, names, signatures, flags, stack sizes and exception tables. Filename/line metadata excluded.'}
 output.write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='source_identity'},indent=2))

if __name__=='__main__':main()
