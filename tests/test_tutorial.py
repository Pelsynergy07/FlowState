import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
from flowstate.config import ConfigStore
from flowstate.ui.tutorial import TutorialDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class DummySignals(QObject):
    recording_started = Signal()
    recording_finished = Signal(str)


class DummyController:
    def __init__(self):
        self.config_store = ConfigStore()
        self.signals = DummySignals()


def test_tutorial_dialog_initialization(qapp):
    controller = DummyController()
    dlg = TutorialDialog(controller)
    assert dlg.stack.count() == 2
    assert dlg.stack.currentIndex() == 0
    assert dlg.step_badge.text == "✦ STEP 01 / 02"
    dlg.close()


def test_tutorial_dialog_step_navigation(qapp):
    controller = DummyController()
    dlg = TutorialDialog(controller)

    # Step 1
    assert dlg.stack.currentIndex() == 0
    assert dlg.prev_btn.isHidden()

    # Move to Step 2
    dlg._go_next()
    assert dlg.stack.currentIndex() == 1
    assert dlg.step_badge.text == "✦ STEP 02 / 02"
    assert not dlg.prev_btn.isHidden()
    assert dlg.next_btn.text() == "Open FlowState →"

    # Move back to Step 1
    dlg._go_prev()
    assert dlg.stack.currentIndex() == 0
    assert dlg.step_badge.text == "✦ STEP 01 / 02"

    dlg.close()


def test_tutorial_speech_transcription_fill(qapp):
    controller = DummyController()
    dlg = TutorialDialog(controller)

    # Simulate transcription arriving while in step 1
    sample_text = "This is a test transcription from the local model."
    dlg._on_speech_transcribed(sample_text)
    assert dlg.step1_text.toPlainText() == sample_text
    assert not dlg.step1_success_badge.isHidden()

    dlg.close()


def test_tutorial_step2_broken_button_and_paste(qapp):
    controller = DummyController()
    dlg = TutorialDialog(controller)
    dlg._go_next()
    assert dlg.stack.currentIndex() == 1

    # Simulate sample paste / hotkey paste
    dlg._fill_step2_sample()
    assert dlg.step2_text.toPlainText() == "Fix this thing"
    assert QApplication.clipboard().text() == "Fix this thing"
    assert not dlg.step2_badge.isHidden()
    assert dlg.next_btn.isEnabled()

    # Test hotkey paste handler
    dlg.step2_text.clear()
    dlg._handle_step2_hotkey_paste()
    assert dlg.step2_text.toPlainText() == "Fix this thing"
    assert QApplication.clipboard().text() == "Fix this thing"

    dlg.close()


def test_tutorial_step2_hotkey_gating(qapp):
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QPoint, Qt

    controller = DummyController()
    dlg = TutorialDialog(controller)
    dlg._go_next()
    assert dlg.stack.currentIndex() == 1

    canvas = dlg.demo_canvas
    assert not canvas.listening_active

    # Clicking canvas while listening is inactive must trigger unauthorized drag warning
    press_event = QMouseEvent(QMouseEvent.MouseButtonPress, QPoint(50, 50), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    canvas.mousePressEvent(press_event)
    assert canvas._warning_tick > 0
    assert "PRESS HOTKEY FIRST" in canvas._warning_message

    # Toggle hotkey listening on
    dlg._toggle_step2_listening()
    assert canvas.listening_active
    assert dlg._is_step2_listening

    # Drag is now authorized
    press_event_auth = QMouseEvent(QMouseEvent.MouseButtonPress, QPoint(50, 50), Qt.LeftButton, Qt.LeftButton, Qt.ControlModifier)
    canvas.mousePressEvent(press_event_auth)
    assert canvas._user_interacting

    # Toggle hotkey off -> finishes and pastes
    dlg._toggle_step2_listening()
    assert not canvas.listening_active
    assert not dlg._is_step2_listening
    assert dlg.step2_text.toPlainText() == "Fix this thing"
    assert QApplication.clipboard().text() == "Fix this thing"

    dlg.close()
