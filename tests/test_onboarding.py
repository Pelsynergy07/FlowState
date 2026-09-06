import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
from flowstate.config import ConfigStore
from flowstate.ui.onboarding import OnboardingDialog


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


def test_onboarding_dialog_initialization(qapp):
    controller = DummyController()
    dlg = OnboardingDialog(controller)
    assert dlg.windowTitle() == "FlowState Setup"
    assert not dlg.skipped
    # Test paintEvent execution
    dlg.resize(700, 580)
    dlg.repaint()
    dlg.close()


def test_onboarding_skip(qapp):
    controller = DummyController()
    dlg = OnboardingDialog(controller)
    dlg._skip_onboarding()
    assert dlg.skipped
    dlg.close()


def test_onboarding_mic_selector(qapp):
    controller = DummyController()
    dlg = OnboardingDialog(controller)
    assert hasattr(dlg, "mic_combo")
    assert dlg.mic_combo.count() >= 1
    # Test changing mic
    dlg.mic_combo.setCurrentIndex(0)
    dlg._on_mic_changed()
    dlg.close()
