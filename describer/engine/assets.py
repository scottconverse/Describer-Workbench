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


def validate_session(path):
    import onnxruntime as ort
    ort.disable_telemetry_events()
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    ort.InferenceSession(str(path), options, providers=['CPUExecutionProvider'])


def provision(destination: str | Path | None = None, cancel=None) -> Path:
    import tempfile
    from .core import check_cancel
    target = Path(destination) if destination else default_root() / 'assets' / 'yamnet.onnx'
    check_cancel(cancel)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=target.name+'.', suffix='.download', dir=target.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        # Socket operations are bounded by ten seconds; cancellation is checked
        # between reads and before the atomic replacement of an existing asset.
        with urllib.request.urlopen(MODEL_URL, timeout=10) as response, temporary.open('wb') as out:
            while True:
                check_cancel(cancel)
                block = response.read(64 * 1024)
                if not block:break
                out.write(block)
        check_cancel(cancel)
        with temporary.open('rb') as f:
            if hashlib.file_digest(f, 'sha256').hexdigest() != MODEL_SHA256:
                raise ValueError('Downloaded speech detector checksum mismatch')
        validate_session(temporary)
        check_cancel(cancel)
        temporary.replace(target)
        return target
    finally:
        temporary.unlink(missing_ok=True)
