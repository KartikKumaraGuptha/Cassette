"""Forgiving small hand-drawn S trajectory recognizer."""
from __future__ import annotations
import math


def _resample(points, n=48):
    if len(points) < 2:
        return list(points)
    distances = [0.0]
    for a, b in zip(points, points[1:]):
        distances.append(distances[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = distances[-1]
    if total <= 0:
        return list(points)
    out = []
    j = 1
    for i in range(n):
        target = total * i / (n - 1)
        while j < len(distances) and distances[j] < target:
            j += 1
        j = min(j, len(distances) - 1)
        span = distances[j] - distances[j - 1]
        t = 0.0 if span <= 0 else (target - distances[j - 1]) / span
        a, b = points[j - 1], points[j]
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def _normalize(points):
    p = _resample(points)
    if not p:
        return []
    min_x = min(x for x, _ in p); max_x = max(x for x, _ in p)
    min_y = min(y for _, y in p); max_y = max(y for _, y in p)
    w = max(max_x - min_x, 1e-6)
    h = max(max_y - min_y, 1e-6)
    return [((x - min_x) / w, (y - min_y) / h) for x, y in p]


def _template(reverse=False, mirror=False):
    # A genuine S trajectory: right -> left -> right as Y increases.
    # cos(2*pi*t) gives exactly those three horizontal phases.
    out = []
    for i in range(48):
        t = i / 47.0
        x = 0.5 + 0.47 * math.cos(2.0 * math.pi * t)
        if mirror:
            x = 1.0 - x
        out.append((x, t))
    if reverse:
        out.reverse()
    return _normalize(out)


_TEMPLATES = [_template(reverse=r, mirror=m) for r in (False, True) for m in (False, True)]


def _template_score(p):
    best = 1.0
    for template in _TEMPLATES:
        error = sum(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(p, template)) / len(p)
        best = min(best, error)
    return max(0.0, min(1.0, 1.0 - best / 0.72))


def _phase_score(p):
    """Check the defining S property: x swings one way, then the other, then back."""
    if len(p) < 12:
        return 0.0
    # Average X in five horizontal slices. This is insensitive to small jitter.
    samples = []
    for i in range(5):
        lo = i / 5.0
        hi = (i + 1) / 5.0
        xs = [x for x, y in p if lo <= y <= hi]
        if not xs:
            return 0.0
        samples.append(sum(xs) / len(xs))
    # Either direction is valid. An S has high-low-high or low-high-low.
    a = (samples[0] + samples[1]) * 0.5
    b = samples[2]
    c = (samples[3] + samples[4]) * 0.5
    swing = min(abs(a - b), abs(c - b))
    same_ends = 1.0 - min(1.0, abs(a - c) * 2.0)
    return max(0.0, min(1.0, swing * 2.8)) * (0.55 + 0.45 * same_ends)


def s_score(points):
    if len(points) < 6:
        return 0.0
    p = _normalize(points)
    if len(p) < 6:
        return 0.0

    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    if width < 5.0 or height < 7.0:
        return 0.0

    aspect = width / max(height, 1e-6)
    if aspect < 0.12 or aspect > 2.8:
        return 0.0

    path = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(p, p[1:]))
    if path < 1.20:
        return 0.0

    # Template + structural score. Deliberately forgiving for mouse-drawn strokes.
    return 0.62 * _template_score(p) + 0.38 * _phase_score(p)
