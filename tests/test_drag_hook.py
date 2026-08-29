from unittest.mock import patch

from pynput import mouse

from flowstate.capture.drag_hook import DragCaptureHook


class _Recorder:
    def __init__(self):
        self.regions = []

    def on_region(self, left, top, right, bottom):
        self.regions.append((left, top, right, bottom))


def test_ctrl_drag_reports_normalized_region():
    recorder = _Recorder()
    hook = DragCaptureHook(on_region=recorder.on_region)

    with patch("flowstate.capture.drag_hook._ctrl_held", return_value=True):
        hook._on_click(100, 200, mouse.Button.left, True)
    hook._on_click(300, 250, mouse.Button.left, False)

    assert recorder.regions == [(100, 200, 300, 250)]


def test_drag_without_ctrl_is_ignored():
    recorder = _Recorder()
    hook = DragCaptureHook(on_region=recorder.on_region)

    with patch("flowstate.capture.drag_hook._ctrl_held", return_value=False):
        hook._on_click(100, 200, mouse.Button.left, True)
    hook._on_click(300, 250, mouse.Button.left, False)

    assert recorder.regions == []


def test_reversed_drag_direction_still_normalizes():
    recorder = _Recorder()
    hook = DragCaptureHook(on_region=recorder.on_region)

    with patch("flowstate.capture.drag_hook._ctrl_held", return_value=True):
        hook._on_click(300, 250, mouse.Button.left, True)
    hook._on_click(100, 200, mouse.Button.left, False)

    assert recorder.regions == [(100, 200, 300, 250)]


def test_tiny_drag_below_threshold_is_ignored():
    recorder = _Recorder()
    hook = DragCaptureHook(on_region=recorder.on_region)

    with patch("flowstate.capture.drag_hook._ctrl_held", return_value=True):
        hook._on_click(100, 100, mouse.Button.left, True)
    hook._on_click(102, 101, mouse.Button.left, False)

    assert recorder.regions == []


def test_right_click_is_ignored():
    recorder = _Recorder()
    hook = DragCaptureHook(on_region=recorder.on_region)

    with patch("flowstate.capture.drag_hook._ctrl_held", return_value=True):
        hook._on_click(100, 100, mouse.Button.right, True)
    hook._on_click(300, 300, mouse.Button.right, False)

    assert recorder.regions == []


def test_release_without_matching_ctrl_press_is_ignored():
    recorder = _Recorder()
    hook = DragCaptureHook(on_region=recorder.on_region)

    # A left-click release with no prior Ctrl-held press recorded.
    hook._on_click(300, 250, mouse.Button.left, False)

    assert recorder.regions == []


def test_drag_start_and_end_callbacks_fire_for_live_visual_feedback():
    starts = []
    ends = []
    hook = DragCaptureHook(
        on_region=lambda *a: None,
        on_drag_start=lambda x, y: starts.append((x, y)),
        on_drag_end=lambda: ends.append(True),
    )

    with patch("flowstate.capture.drag_hook._ctrl_held", return_value=True):
        hook._on_click(100, 200, mouse.Button.left, True)
    assert starts == [(100, 200)]
    assert ends == []

    hook._on_click(300, 250, mouse.Button.left, False)
    assert ends == [True]


def test_drag_start_callback_does_not_fire_without_ctrl():
    starts = []
    hook = DragCaptureHook(on_region=lambda *a: None, on_drag_start=lambda x, y: starts.append((x, y)))

    with patch("flowstate.capture.drag_hook._ctrl_held", return_value=False):
        hook._on_click(100, 200, mouse.Button.left, True)

    assert starts == []


def test_drag_move_callback_only_fires_during_an_active_drag():
    moves = []
    hook = DragCaptureHook(on_region=lambda *a: None, on_drag_move=lambda x, y: moves.append((x, y)))

    hook._on_move(50, 60)  # no drag in progress
    assert moves == []

    with patch("flowstate.capture.drag_hook._ctrl_held", return_value=True):
        hook._on_click(100, 200, mouse.Button.left, True)
    hook._on_move(150, 220)
    assert moves == [(150, 220)]

    hook._on_click(150, 220, mouse.Button.left, False)
    hook._on_move(999, 999)
    assert moves == [(150, 220)]  # nothing new after the drag ended
