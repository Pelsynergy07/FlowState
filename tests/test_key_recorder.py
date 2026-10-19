"""Unit tests for the KeyRecorderWidget."""

from __future__ import annotations

import sys

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication
import pytest

from flowstate.ui.key_recorder import KeyRecorderWidget


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_key_recorder_initial_value(qapp):
    w = KeyRecorderWidget("ctrl+shift+space")
    assert w.text() == "ctrl+shift+space"
    assert w.key_combination() == "ctrl+shift+space"


def test_key_recorder_clearing(qapp):
    w = KeyRecorderWidget("ctrl+m")
    w.clear_combo()
    assert w.text() == ""


def test_key_recorder_resets_to_default_instead_of_clearing(qapp):
    w = KeyRecorderWidget("alt_r", default_combo="ctrl+m")
    assert w._clear_btn.text() == "RESET"
    changes = []
    w.keyChanged.connect(changes.append)
    w._clear_btn.click()
    assert w.text() == "ctrl+m"
    assert changes == ["ctrl+m"]


def test_key_recorder_captures_simple_key(qapp):
    w = KeyRecorderWidget()
    w.start_recording()
    assert w._is_recording is True

    event = QKeyEvent(QEvent.KeyPress, Qt.Key.Key_F9, Qt.KeyboardModifier.NoModifier)
    w.keyPressEvent(event)

    assert w.text() == "f9"
    assert w._is_recording is False


# Qt reports the Control key as MetaModifier on macOS (Command is ControlModifier).
CONTROL_MODIFIER = Qt.KeyboardModifier.MetaModifier if sys.platform == "darwin" else Qt.KeyboardModifier.ControlModifier
RIGHT_ALT_NATIVE_KEY = 0x3D if sys.platform == "darwin" else 0xA5  # kVK_RightOption / VK_RMENU


def test_key_recorder_captures_chord(qapp):
    w = KeyRecorderWidget()
    w.start_recording()

    event = QKeyEvent(
        QEvent.KeyPress,
        Qt.Key.Key_Space,
        CONTROL_MODIFIER | Qt.KeyboardModifier.ShiftModifier,
    )
    w.keyPressEvent(event)

    assert "ctrl" in w.text()
    assert "shift" in w.text()
    assert "space" in w.text()
    assert w._is_recording is False


def test_key_recorder_captures_bare_modifier_tap(qapp):
    w = KeyRecorderWidget()
    w.start_recording()

    # Press right Alt / right Option
    ev_down = QKeyEvent(
        QEvent.KeyPress,
        Qt.Key.Key_Alt,
        Qt.KeyboardModifier.AltModifier,
        0,
        RIGHT_ALT_NATIVE_KEY,
        0,
    )
    w.keyPressEvent(ev_down)
    assert w._is_recording is True
    assert w._pending_modifier == "alt_r"

    # Release
    ev_up = QKeyEvent(
        QEvent.KeyRelease,
        Qt.Key.Key_Alt,
        Qt.KeyboardModifier.NoModifier,
        0,
        0xA5,
        0,
    )
    w.keyReleaseEvent(ev_up)

    assert w.text() == "alt_r"
    assert w._is_recording is False
