"""Unit tests for the KeyRecorderWidget."""

from __future__ import annotations

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


def test_key_recorder_captures_simple_key(qapp):
    w = KeyRecorderWidget()
    w.start_recording()
    assert w._is_recording is True

    event = QKeyEvent(QEvent.KeyPress, Qt.Key.Key_F9, Qt.KeyboardModifier.NoModifier)
    w.keyPressEvent(event)

    assert w.text() == "f9"
    assert w._is_recording is False


def test_key_recorder_captures_chord(qapp):
    w = KeyRecorderWidget()
    w.start_recording()

    event = QKeyEvent(
        QEvent.KeyPress,
        Qt.Key.Key_Space,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    w.keyPressEvent(event)

    assert "ctrl" in w.text()
    assert "shift" in w.text()
    assert "space" in w.text()
    assert w._is_recording is False


def test_key_recorder_captures_bare_modifier_tap(qapp):
    w = KeyRecorderWidget()
    w.start_recording()

    # Press right Alt (nativeVirtualKey = 0xA5)
    ev_down = QKeyEvent(
        QEvent.KeyPress,
        Qt.Key.Key_Alt,
        Qt.KeyboardModifier.AltModifier,
        0,
        0xA5,
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
