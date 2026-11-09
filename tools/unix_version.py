"""The package version for Mac and Linux packaging, read from describer/__init__.py."""
import re
from pathlib import Path

_TEXT = (Path(__file__).resolve().parents[1] / "describer" / "__init__.py").read_text(encoding="utf-8")
VERSION = re.search(r'^__version__ = "([^"]+)"', _TEXT, re.M).group(1)
