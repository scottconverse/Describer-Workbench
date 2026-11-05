# SPDX-License-Identifier: Apache-2.0
"""Explicit, hash-verified asset provisioning; analysis never downloads models."""
import hashlib
import os
import urllib.request
from pathlib import Path

from .sound import MODEL_SHA256, MODEL_URL

_VERIFIED = {}


def default_root() -> Path:
    from ..platforms import data_directory
    return Path(os.environ.get('DESCRIBER_HOME', data_directory()))


def speech_model(settings: dict) -> Path:
    path = Path(settings.get('sound_model') or default_root() / 'assets' / 'yamnet.onnx').resolve()
    if not path.is_file():
        raise ValueError('Speech detector is missing. Use Install speech detector in the desktop, or describer assets provision.')
    with path.open('rb') as f:
        if hashlib.file_digest(f, 'sha256').hexdigest() != MODEL_SHA256:
            raise ValueError('Speech detector checksum mismatch; provision it again.')
    return path


def detector_state(settings):
    path = Path(settings.get('sound_model') or default_root() / 'assets' / 'yamnet.onnx').resolve()
    try:
        stat = path.stat()
        signature = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    except OSError:return 'missing'
    previous = _VERIFIED.get(str(path))
    return previous[1] if previous and previous[0] == signature else 'configured (not verified)'


def validate_detector(settings):
    path = Path(settings.get('sound_model') or default_root() / 'assets' / 'yamnet.onnx').resolve()
    try:
        speech_model(settings)
        validate_session(path)
    except Exception:
        if path.is_file():
            stat=path.stat();_VERIFIED[str(path)]=((stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns),'error')
        raise
    stat=path.stat();_VERIFIED[str(path)]=((stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns),'verified')
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
        stat=target.stat();_VERIFIED[str(target.resolve())]=((stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns),'verified')
        return target
    finally:
        temporary.unlink(missing_ok=True)
