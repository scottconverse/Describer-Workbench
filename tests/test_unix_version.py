"""Mac and Linux packaging must use the package version, not a fixed number."""
import re
from pathlib import Path

import describer

ROOT = Path(__file__).resolve().parents[1]
FILES = ["DescriberUnix.spec", "tools/package_unix.py", "tools/install_unix.py", "tools/verify_unix.py"]


def test_unix_packaging_has_no_fixed_version():
    for name in FILES:
        text = (ROOT / name).read_text(encoding="utf-8")
        fixed = re.findall(r"['\"]\d+\.\d+\.\d+(?:-\d+)?['\"]|DescriberWorkbench-\d+\.\d+\.\d+|Version: \d", text)
        assert not fixed, (name, fixed)


def test_unix_version_helper_reads_package_version():
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    from unix_version import VERSION
    assert VERSION == describer.__version__
