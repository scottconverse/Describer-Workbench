# macOS/Linux add-ons only. The existing Windows spec is deliberately separate.
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all,copy_metadata
assert sys.platform in ('darwin','linux')
reader_data,reader_binaries,reader_imports=collect_all('accessible_output2')
transport_data,transport_binaries,transport_imports=collect_all('mcp',filter_submodules=lambda name:not name.startswith('mcp.cli'))
key_data,key_binaries,key_imports=collect_all('keyring')
media_data=[(str(Path('unix-media/licenses')),'unix-media/licenses'),(str(Path('unix-media/build-receipt.json')),'unix-media')] if sys.platform=='darwin' else []
media=[(str(path),'bin') for path in Path('unix-media/bin').glob('*') if path.is_file()]
a=Analysis(['run.py','run_cli.py'],pathex=[],binaries=reader_binaries+transport_binaries+key_binaries+media,
    datas=[('assets','assets'),('docs','docs'),('README.md','.'),('LICENSE','.'),('NOTICE','.'),('THIRD-PARTY-NOTICES.md','.'),('third-party-licenses','third-party-licenses')]+media_data+reader_data+transport_data+key_data+copy_metadata('describer-workbench'),
    hiddenimports=reader_imports+transport_imports+key_imports+['uvicorn.logging','uvicorn.loops.auto','uvicorn.protocols.http.auto','uvicorn.protocols.websockets.auto','uvicorn.lifespan.on'],
    excludes=['PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtPdf'],noarchive=False,optimize=0)
pyz=PYZ(a.pure)
gui=EXE(pyz,[s for s in a.scripts if s[0]!='run_cli'],[],exclude_binaries=True,name='DescriberWorkbench',console=False,strip=False,upx=False)
cli=EXE(pyz,[s for s in a.scripts if s[0]!='run'],[],exclude_binaries=True,name='DescriberCLI',console=True,strip=False,upx=False)
coll=COLLECT(gui,cli,a.binaries,a.datas,strip=False,upx=False,name='DescriberWorkbench')
if sys.platform=='darwin':
    app=BUNDLE(coll,name='Describer Workbench.app',bundle_identifier='org.describer.workbench',info_plist={'CFBundleExecutable':'DescriberWorkbench','CFBundleShortVersionString':'0.6.1','CFBundleVersion':'1','NSHighResolutionCapable':True,'LSMinimumSystemVersion':'15.0'})
