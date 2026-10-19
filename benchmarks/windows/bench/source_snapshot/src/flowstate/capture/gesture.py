"""Circle-gesture detection: recognizes when a mouse path traces a loop.

Kept as a pure function over (x, y, t) points -- no Qt, no pynput, no I/O
-- so it can be exhaustively unit tested against synthetic paths, mirroring
the reference app's own TrailSegments-based approach.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

WINDOW_SECONDS = 1.5
COOLDOWN_SECONDS = 1.5
MIN_RADIUS_PX = 30.0
MAX_RADIUS_PX = 500.0
CLOSURE_TOLERANCE_FRACTION = 0.15  # start/end must be within 15% of mean radius


@dataclass
class Sensitivity:
    """Maps a single 0.0 (loose) .. 1.0 (strict) UI slider value onto the
    detector's actual thresholds."""

    value: float = 0.5

    @property
    def sweep_threshold(self) -> float:
        # 0.70*2pi (loose) .. 0.95*2pi (strict)
        return (0.70 + 0.25 * self.value) * 2 * math.pi


@dataclass
class _Point:
    x: float
    y: float
    t: float


@dataclass
class CircleGestureDetector:
    sensitivity: Sensitivity = field(default_factory=Sensitivity)
    _points: list[_Point] = field(default_factory=list)
    _last_fire_t: float | None = None

    def reset(self) -> None:
        self._points.clear()
        self._last_fire_t = None

    def add_point(self, x: float, y: float, t: float) -> tuple[float, float] | None:
        """Feed one mouse sample. Returns the (x, y) centroid of the
        circled region if a loop closure just fired, else None."""
        self._points.append(_Point(x, y, t))
        self._trim_window(t)

        if self._last_fire_t is not None and (t - self._last_fire_t) < COOLDOWN_SECONDS:
            return None

        result = self._evaluate()
        if result is not None:
            self._last_fire_t = t
            self._points.clear()
        return result

    def _trim_window(self, now: float) -> None:
        cutoff = now - WINDOW_SECONDS
        while self._points and self._points[0].t < cutoff:
            self._points.pop(0)

    def _evaluate(self) -> tuple[float, float] | None:
        pts = self._points
        if len(pts) < 8:
            return None

        cx = sum(p.x for p in pts) / len(pts)
        cy = sum(p.y for p in pts) / len(pts)

        radii = [math.hypot(p.x - cx, p.y - cy) for p in pts]
        mean_radius = sum(radii) / len(radii)
        if not (MIN_RADIUS_PX <= mean_radius <= MAX_RADIUS_PX):
            return None

        # Signed angle swept around the centroid, accumulated step by step.
        sweep = 0.0
        prev_angle = math.atan2(pts[0].y - cy, pts[0].x - cx)
        for p in pts[1:]:
            angle = math.atan2(p.y - cy, p.x - cx)
            delta = angle - prev_angle
            while delta > math.pi:
                delta -= 2 * math.pi
            while delta < -math.pi:
                delta += 2 * math.pi
            sweep += delta
            prev_angle = angle

        if abs(sweep) < self.sensitivity.sweep_threshold:
            return None

        start, end = pts[0], pts[-1]
        closure_dist = math.hypot(end.x - start.x, end.y - start.y)
        if closure_dist > mean_radius * CLOSURE_TOLERANCE_FRACTION:
            return None

        return (cx, cy)
