import math

from flowstate.capture.gesture import CircleGestureDetector, Sensitivity


def _feed_circle(detector, cx=500.0, cy=500.0, radius=100.0, n=40, t0=0.0, dt=0.02, fraction=1.0, start_angle=0.0):
    """Feeds points along a circular arc. fraction=1.0 is a full loop back
    to the start; fraction=0.5 is a half circle (arc, no closure)."""
    result = None
    total_angle = 2 * math.pi * fraction
    for i in range(n):
        angle = start_angle + total_angle * i / (n - 1)
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        t = t0 + i * dt
        result = detector.add_point(x, y, t)
    return result


def test_full_circle_fires():
    detector = CircleGestureDetector()
    result = _feed_circle(detector, fraction=1.0)
    assert result is not None
    cx, cy = result
    assert abs(cx - 500.0) < 5
    assert abs(cy - 500.0) < 5


def test_half_circle_arc_does_not_fire():
    detector = CircleGestureDetector()
    result = _feed_circle(detector, fraction=0.5)
    assert result is None


def test_straight_line_does_not_fire():
    detector = CircleGestureDetector()
    result = None
    for i in range(40):
        result = detector.add_point(x=100.0 + i * 5, y=200.0, t=i * 0.02)
    assert result is None


def test_tiny_jitter_below_min_radius_does_not_fire():
    detector = CircleGestureDetector()
    result = _feed_circle(detector, radius=5.0, fraction=1.0)
    assert result is None


def test_huge_sweep_above_max_radius_does_not_fire():
    detector = CircleGestureDetector()
    result = _feed_circle(detector, radius=800.0, fraction=1.0)
    assert result is None


def test_unclosed_loop_does_not_fire():
    # Sweeps a full 2*pi but ends far from where it started.
    detector = CircleGestureDetector()
    cx, cy, radius = 500.0, 500.0, 100.0
    result = None
    for i in range(40):
        angle = 2 * math.pi * i / 39
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        if i == 39:
            x += 200  # jump away right before closing
        result = detector.add_point(x, y, i * 0.02)
    assert result is None


def test_cooldown_prevents_double_fire():
    detector = CircleGestureDetector()
    first = _feed_circle(detector, t0=0.0, fraction=1.0)
    assert first is not None
    # Immediately circle again, well within the cooldown window.
    second = _feed_circle(detector, t0=0.9, fraction=1.0)
    assert second is None


def test_sensitivity_slider_changes_threshold():
    loose = Sensitivity(value=0.0)
    strict = Sensitivity(value=1.0)
    assert loose.sweep_threshold < strict.sweep_threshold


def test_stricter_sensitivity_rejects_a_looser_loop():
    # An 85%-of-a-full-loop sweep should pass at loose sensitivity but can
    # fail at strict sensitivity, since strict demands a fuller loop.
    detector = CircleGestureDetector(sensitivity=Sensitivity(value=1.0))
    result = _feed_circle(detector, fraction=0.85)
    assert result is None
