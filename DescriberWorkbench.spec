# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, copy_metadata
reader_data,reader_binaries,reader_imports=collect_all('accessible_output2')
transport_data,transport_binaries,transport_imports=collect_all('mcp', filter_submodules=lambda name:not name.startswith('mcp.cli'))
a = Analysis(
    ['run.py', 'run_cli.py'],
    pathex=[],
    binaries=[('bin/ffmpeg.exe', 'bin'), ('bin/ffprobe.exe', 'bin')]+reader_binaries+transport_binaries,
    datas=[('assets','assets'), ('docs','docs'), ('README.md','.'),
           ('LICENSE','.'), ('NOTICE','.'), ('THIRD-PARTY-NOTICES.md','.'),
           ('third-party-licenses','third-party-licenses'), ('bin/FFmpeg-LICENSE.txt','bin')]+reader_data+transport_data+copy_metadata('describer-workbench'),
    hiddenimports=reader_imports+transport_imports+['uvicorn.logging','uvicorn.loops.auto',
        'uvicorn.protocols.http.auto','uvicorn.protocols.websockets.auto','uvicorn.lifespan.on'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtPdf'],
    noarchive=False,
    optimize=0,
)
# Qt on Windows uses the OS ICU API. An unrelated Poppler ICU on PATH has
# the same DLL name but versioned, incompatible exports. Do not bundle it.
a.binaries = [entry for entry in a.binaries if entry[0].replace('\\', '/').split('/')[-1].lower()
              not in {'icuuc.dll', 'icuin.dll', 'icudt.dll'}]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    [entry for entry in a.scripts if entry[0] != 'run_cli'],
    [],
    exclude_binaries=True,
    name='DescriberWorkbench',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
cli = EXE(
    pyz,
    [entry for entry in a.scripts if entry[0] != 'run'],
    [],
    exclude_binaries=True,
    name='DescriberCLI',
    debug=False,
    strip=False,
    upx=True,
    console=True,
)
coll = COLLECT(
    exe,
    cli,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DescriberWorkbench',
)
