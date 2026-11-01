# SPDX-License-Identifier: Apache-2.0
"""Explicit, hash-verified asset provisioning; analysis never downloads models."""
import hashlib
import os
import urllib.request
from pathlib import Path

from .sound import MODEL_SHA256, MODEL_URL


def default_root() -> Path:
    return Path(os.environ.get('DESCRIBER_HOME', Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'DescriberWorkbench'))


def speech_model(settings: dict) -> Path:
    path = Path(settings.get('sound_model') or default_root() / 'assets' / 'yamnet.onnx').resolve()
    if not path.is_file():
        raise ValueError('Speech detector is missing. Use Install speech detector in the desktop, or describer assets provision.')
    with path.open('rb') as f:
        if hashlib.file_digest(f, 'sha256').hexdigest() != MODEL_SHA256:
            raise ValueError('Speech detector checksum mismatch; provision it again.')
    return path


def provision(destination: str | Path | None = None) -> Path:
    target = Path(destination) if destination else default_root() / 'assets' / 'yamnet.onnx'
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.download')
    try:
        with urllib.request.urlopen(MODEL_URL, timeout=120) as response, temporary.open('wb') as out:
            while block := response.read(1024 * 1024):
                out.write(block)
        with temporary.open('rb') as f:
            if hashlib.file_digest(f, 'sha256').hexdigest() != MODEL_SHA256:
                raise ValueError('Downloaded speech detector checksum mismatch')
        temporary.replace(target)
        return target
    finally:
        temporary.unlink(missing_ok=True)
