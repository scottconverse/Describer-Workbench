"""GUI-independent audio-description engine and durable application service."""

import os

for _key in ('HF_HUB_DISABLE_TELEMETRY','DO_NOT_TRACK','OTEL_SDK_DISABLED'):
    os.environ.setdefault(_key, '1' if _key != 'OTEL_SDK_DISABLED' else 'true')

from .service import DescriptionService, get_service

__all__ = ["DescriptionService", "get_service"]
