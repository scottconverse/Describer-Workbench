"""Expose actual loader/startup errors before pytest captures Qt diagnostics."""
from pathlib import Path
import subprocess

import PySide6

plugin=Path(PySide6.__file__).parent/'Qt/plugins/platforms/libqxcb.so'
result=subprocess.run(['ldd',str(plugin)],capture_output=True,text=True,check=True)
print(result.stdout,flush=True)
assert 'not found' not in result.stdout,'Install the missing Qt X11 runtime dependencies above.'
from PySide6.QtWidgets import QApplication  # noqa: E402
app=QApplication([])
print('Native X11 QApplication startup passed',flush=True)
