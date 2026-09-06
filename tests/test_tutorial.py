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
