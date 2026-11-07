# SPDX-License-Identifier: Apache-2.0
"""Audio-safe, event-bounded placement. Never move an event to repair its timing."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable


def intervals(rows: Iterable[Iterable[float]], duration: float) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for row in rows:
        a, b = map(float, row)
        if not all(math.isfinite(n) for n in (a, b)) or b < a:
            raise ValueError("Invalid protected interval")
        a, b = max(0.0, a), min(duration, b)
        if b > a:
            result.append((a, b))
    merged: list[tuple[float, float]] = []
    for a, b in sorted(result):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    return merged


def gaps(protected: Iterable[Iterable[float]], duration: float) -> list[tuple[float, float]]:
    result, cursor = [], 0.0
    for a, b in intervals(protected, duration):
        if a > cursor:
            result.append((cursor, a))
        cursor = b
    if cursor < duration:
        result.append((cursor, duration))
    return result


def slot(start: float, end: float, seconds: float, safe: list[tuple[float, float]],
         occupied: list[tuple[float, float]]) -> float | None:
    for a, b in safe:
        point, stop = max(a, start), min(b, end)
        for u, v in sorted(occupied):
            if point < v and point + seconds > u:
                point = max(point, v)
        if seconds > 0 and point + seconds <= stop + 1e-6:
            return point
    return None


@dataclass(frozen=True)
class Placement:
    disposition: str
    start: float
    end: float
    speed: float = 1.0
    reason: str = ""


def place(start: float, end: float, seconds: float, safe: list[tuple[float, float]],
          occupied: list[tuple[float, float]], max_speed: float = 1.15, reach: float = 0.0) -> Placement:
    """Find protected-audio-safe space for a line about the event [start, end].

    `reach` lets the line use a pause up to that many seconds away: inside the
    event first, then just after it, then just before it. 0 keeps the line
    inside the event.
    """
    if not all(math.isfinite(v) for v in (start, end, seconds, max_speed, reach)):
        raise ValueError("Non-finite placement value")
    if start < 0 or end <= start or seconds <= 0 or not 1 <= max_speed <= 1.15 or reach < 0:
        raise ValueError("Invalid event window, speech duration or speed ceiling")
    windows = [(start, end)]
    if reach:
        windows += [(start, end + reach), (max(0.0, start - reach), end + reach)]
    for a, b in windows:
        for speed in dict.fromkeys((1.0, min(1.08, max_speed), max_speed)):
            at = slot(a, b, seconds / speed, safe, occupied)
            if at is not None:
                return Placement("in-gap", at, at + seconds / speed, speed)
    return Placement("pause", start, start, reason="No protected-audio-safe space within event interval")
