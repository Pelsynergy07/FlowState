import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
from flowstate.config import ConfigStore
from flowstate.ui import onboarding
from flowstate.ui.onboarding import OnboardingDialog, _PreloadWorker


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
    dlg = OnboardingDialog(DummyController())
    assert dlg.windowTitle() == "FlowState Setup"
    assert not dlg.skipped
    assert not dlg.models_ready
    dlg.resize(700, 580)
    dlg.repaint()
    dlg.close()


def test_onboarding_skip(qapp):
    dlg = OnboardingDialog(DummyController())
    dlg._skip_onboarding()
    assert dlg.skipped
    dlg.close()


def test_onboarding_mic_selector(qapp):
    dlg = OnboardingDialog(DummyController())
    assert dlg.mic_combo.count() >= 1
    dlg.mic_combo.setCurrentIndex(0)
    dlg._on_mic_changed()
    dlg.close()


def test_download_size_is_stated_before_downloading(qapp, monkeypatch):
    monkeypatch.setattr(onboarding, "_missing_download_mb", lambda controller, is_gpu: 3100)
    dlg = OnboardingDialog(DummyController())
    assert "about 3.0 GB" in dlg.status_label.text()
    assert "Hugging Face" in dlg.status_label.text()
    dlg.close()


def test_progress_is_one_continuous_bar(qapp):
    worker = _PreloadWorker(DummyController(), "GPU", True, 8)
    seen = []
    worker.progress.connect(seen.append)
    worker._range = (0, 45)
    for pct in (0, 50, 100):
        worker._on_download_progress(pct)
    worker._range = (50, 92)
    for pct in (0, 50, 100):
        worker._on_download_progress(pct)
    assert seen == sorted(seen)
    assert seen[0] == 0 and seen[-1] == 92


def test_failure_offers_retry_and_plain_language(qapp):
    dlg = OnboardingDialog(DummyController())
    dlg._on_failed("ConnectionError: Max retries exceeded")
    assert "internet connection" in dlg.status_label.text()
    assert dlg.progress.isHidden()
    assert dlg.start_btn.text() == "Try Again"
    assert dlg.skip_btn.text() == "Continue Without It"
    assert not dlg.models_ready
    dlg.close()


def test_finished_setup_has_nothing_to_skip(qapp):
    dlg = OnboardingDialog(DummyController())
    dlg._on_finished()
    assert dlg.models_ready
    assert dlg.skip_btn.isHidden()
    dlg.close()
