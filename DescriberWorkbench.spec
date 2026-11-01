# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
reader_data,reader_binaries,reader_imports=collect_all('accessible_output2')
a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[('bin/ffmpeg.exe', 'bin'), ('bin/ffprobe.exe', 'bin')]+reader_binaries,
    datas=[('assets','assets')]+reader_data,
    hiddenimports=reader_imports,
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
    a.scripts,
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
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DescriberWorkbench',
)
