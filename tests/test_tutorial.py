import pytest
from PySide6.QtCore import QObject, QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent
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
    processing_started = Signal()
    recording_finished = Signal(str)
    no_speech_detected = Signal()
    error = Signal(str)


class DummyController:
    def __init__(self):
        self.config_store = ConfigStore()
        self.signals = DummySignals()
        self.calls = []

    def start_recording(self, mode="ptt"):
        self.calls.append(("start", mode))

    def stop_recording(self):
        self.calls.append(("stop",))

    def toggle_recording(self):
        self.calls.append(("toggle",))


def test_tutorial_dialog_initialization(qapp):
    dlg = TutorialDialog(DummyController())
    assert dlg.stack.count() == 2
    assert dlg.stack.currentIndex() == 0
    assert dlg.step_badge.text == "STEP 01 / 02"
    dlg.close()


def test_tutorial_dialog_step_navigation(qapp):
    dlg = TutorialDialog(DummyController())
    assert dlg.prev_btn.isHidden()
    dlg._go_next()
    assert dlg.stack.currentIndex() == 1
    assert dlg.step_badge.text == "STEP 02 / 02"
    assert not dlg.prev_btn.isHidden()
    assert dlg.next_btn.text() == "Open FlowState →"
    dlg._go_prev()
    assert dlg.stack.currentIndex() == 0
    assert dlg.step_badge.text == "STEP 01 / 02"
    dlg.close()


def test_buttons_drive_real_recordings(qapp):
    controller = DummyController()
    dlg = TutorialDialog(controller)
    dlg.step1_hold_btn.pressed.emit()
    dlg.step1_hold_btn.released.emit()
    dlg._go_next()
    dlg.step2_hotkey_btn.click()
    assert controller.calls == [("start", "ptt"), ("stop",), ("toggle",)]
    dlg.close()


def test_results_come_only_from_real_dictation_and_never_touch_clipboard(qapp):
    controller = DummyController()
    dlg = TutorialDialog(controller)
    QApplication.clipboard().setText("user's own clipboard")

    controller.signals.recording_started.emit()
    assert dlg.step1_success_badge.text.startswith("LISTENING")
    controller.signals.processing_started.emit()
    assert dlg.step1_success_badge.text.startswith("FORMATTING")
    controller.signals.recording_finished.emit("Hi Sam,\n\nQuick update.")
    assert dlg.step1_text.toPlainText() == "Hi Sam,\n\nQuick update."
    assert dlg.step1_success_badge.text.startswith("DONE")

    dlg._go_next()
    controller.signals.recording_started.emit()
    assert dlg.demo_canvas.listening_active
    controller.signals.recording_finished.emit("Fix this button.")
    assert not dlg.demo_canvas.listening_active
    assert dlg.step2_text.toPlainText() == "Fix this button."
    assert QApplication.clipboard().text() == "user's own clipboard"
    dlg.close()


def test_silence_and_errors_are_reported(qapp):
    controller = DummyController()
    dlg = TutorialDialog(controller)
    controller.signals.no_speech_detected.emit()
    assert "DIDN'T HEAR" in dlg.step1_success_badge.text
    controller.signals.error.emit("boom")
    assert "WRONG" in dlg.step1_success_badge.text
    assert dlg.step1_text.toPlainText() == ""
    dlg.close()


def test_closed_tutorial_stops_reacting_to_later_dictations(qapp):
    controller = DummyController()
    dlg = TutorialDialog(controller)
    dlg._go_next()
    dlg.reject()
    QApplication.clipboard().setText("kept")
    controller.signals.recording_finished.emit("a later dictation")
    assert dlg.step2_text.toPlainText() == ""
    assert QApplication.clipboard().text() == "kept"


def test_closing_mid_recording_stops_it(qapp):
    controller = DummyController()
    dlg = TutorialDialog(controller)
    controller.signals.recording_started.emit()
    dlg.reject()
    assert controller.calls == [("stop",)]


def test_step2_capture_requires_listening_and_ctrl(qapp):
    dlg = TutorialDialog(DummyController())
    dlg._go_next()
    canvas = dlg.demo_canvas
    press = QMouseEvent(QMouseEvent.MouseButtonPress, QPoint(50, 50), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    canvas.mousePressEvent(press)
    assert "PRESS HOTKEY FIRST" in canvas._warning_message

    dlg._controller.signals.recording_started.emit()
    assert canvas.listening_active
    canvas.mousePressEvent(press)
    assert "HOLD CTRL" in canvas._warning_message
    assert not canvas._user_interacting

    press_ctrl = QMouseEvent(QMouseEvent.MouseButtonPress, QPoint(50, 50), Qt.LeftButton, Qt.LeftButton, Qt.ControlModifier)
    canvas.mousePressEvent(press_ctrl)
    assert canvas._user_interacting
    dlg.close()
