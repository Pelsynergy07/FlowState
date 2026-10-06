import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
from flowstate.config import ConfigStore
from flowstate.ui import consent, onboarding
from flowstate.ui.onboarding import OnboardingDialog, _PreloadWorker, shortcut_conflict


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def quiet_hardware(monkeypatch):
    """No real microphone, GPU probe or analytics key in these tests."""
    monkeypatch.setattr(onboarding._MicMonitor, "start", lambda self, device: True)
    monkeypatch.setattr(onboarding, "microphone_access_blocked", lambda: False)
    monkeypatch.setattr(onboarding, "_detect_hardware_summary", lambda: ("Test GPU", "GPU", True, 8))
    monkeypatch.setattr(onboarding, "_missing_download_mb", lambda controller, is_gpu: 3100)
    monkeypatch.setattr("flowstate.usage.analytics_config", lambda: ("phc_test", "https://eu.i.posthog.com"))


class DummySignals(QObject):
    recording_started = Signal()
    processing_started = Signal()
    recording_finished = Signal(str)
    no_speech_detected = Signal()
    error = Signal(str)


class DummyController:
    _is_preview = True

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

    def set_shortcuts(self, toggle, ptt):
        self.calls.append(("shortcuts", toggle, ptt))

    def switch_microphone(self, name):
        self.calls.append(("mic", name))


def go_to(dlg, name):
    dlg._show_page(dlg.pages.index(name))


def test_one_window_with_short_steps_that_fits_a_laptop(qapp):
    dlg = OnboardingDialog(DummyController())
    assert dlg.pages == ["welcome", "microphone", "shortcuts", "try", "capture", "finish"]
    assert dlg.width() <= 720 and dlg.height() <= 640
    assert not dlg.skipped and not dlg.models_ready
    dlg.close()


def test_capture_step_is_left_out_when_capture_is_off(qapp):
    controller = DummyController()
    controller.config_store.config.capture.mode = "off"
    dlg = OnboardingDialog(controller)
    assert "capture" not in dlg.pages
    dlg.close()


def test_welcome_states_download_size_and_source(qapp):
    dlg = OnboardingDialog(DummyController())
    text = dlg.welcome_download.text()
    assert "about 3.0 GB" in text and "Hugging Face" in text
    assert dlg.next_btn.text() == "Download && continue"  # "&&" renders as one "&"
    assert dlg.skip_btn.isVisibleTo(dlg)
    dlg.close()


def test_skip_setup(qapp):
    dlg = OnboardingDialog(DummyController())
    dlg._skip_onboarding()
    assert dlg.skipped
    assert not dlg.models_ready


def test_download_runs_in_background_while_setup_continues(qapp):
    dlg = OnboardingDialog(DummyController())
    dlg._go_next()
    assert dlg._download_state == "running"
    assert dlg.pages[dlg.stack.currentIndex()] == "microphone"
    dlg._on_finished()
    assert dlg.models_ready
    assert "ready" in dlg.download_label.text().lower()
    dlg.close()


def test_failed_download_explains_and_offers_retry(qapp):
    dlg = OnboardingDialog(DummyController())
    dlg._on_failed("ConnectionError: Max retries exceeded")
    assert dlg.download_label.text() == "Download failed"
    assert "internet connection" in dlg.download_detail.text()
    assert dlg.retry_btn.isVisibleTo(dlg)
    go_to(dlg, "try")
    assert not dlg.hold_btn.isEnabled()
    assert "Try again" in dlg.try_hint.text()
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


def test_blocked_microphone_permission_is_explained(qapp, monkeypatch):
    monkeypatch.setattr(onboarding, "microphone_access_blocked", lambda: True)
    dlg = OnboardingDialog(DummyController())
    go_to(dlg, "microphone")
    assert dlg.mic_permission_card.isVisibleTo(dlg)
    dlg.close()


def test_mic_meter_confirms_voice(qapp):
    dlg = OnboardingDialog(DummyController())
    go_to(dlg, "microphone")
    dlg._mic_monitor._peak = 0.5
    dlg._update_meter()
    assert "works" in dlg.mic_status.text()
    dlg.close()


def test_changing_microphone_switches_device(qapp):
    controller = DummyController()
    dlg = OnboardingDialog(controller)
    dlg.mic_combo.setCurrentIndex(0)
    dlg._on_mic_changed()
    assert ("mic", None) in controller.calls
    dlg.close()


def test_shortcut_conflicts_are_flagged_and_changes_apply_immediately(qapp):
    assert shortcut_conflict("ctrl+m")
    assert shortcut_conflict("Shift+Ctrl+Space")
    assert shortcut_conflict("alt_r") is None
    controller = DummyController()
    dlg = OnboardingDialog(controller)
    assert "VS Code" in dlg.shortcut_status.text()
    dlg.ptt_edit.setText("alt_r")
    dlg._on_shortcut_changed()
    assert controller.config_store.config.shortcuts.push_to_talk == "alt_r"
    assert ("shortcuts", controller.config_store.config.shortcuts.toggle, "alt_r") in controller.calls
    dlg.toggle_edit.setText("alt_r")
    dlg._on_shortcut_changed()
    assert "overlap" in dlg.shortcut_status.text()
    dlg.close()


def test_try_it_uses_real_recordings_and_reports_every_state(qapp):
    controller = DummyController()
    dlg = OnboardingDialog(controller)
    dlg._on_finished()
    go_to(dlg, "try")
    assert dlg.hold_btn.isEnabled()
    dlg.hold_btn.pressed.emit()
    dlg.hold_btn.released.emit()
    assert controller.calls[-2:] == [("start", "ptt"), ("stop",)]

    controller.signals.recording_started.emit()
    assert "Listening" in dlg.try_status.text()
    controller.signals.processing_started.emit()
    assert "Formatting" in dlg.try_status.text()
    controller.signals.recording_finished.emit("Hi Sam,\n\nQuick update:\n1. The report is done.")
    assert dlg.try_result.toPlainText().startswith("Hi Sam,")
    controller.signals.no_speech_detected.emit()
    assert "Didn't hear" in dlg.try_status.text()
    controller.signals.error.emit("boom")
    assert "went wrong" in dlg.try_status.text()
    dlg.close()


def test_capture_step_is_real_and_skippable(qapp):
    controller = DummyController()
    dlg = OnboardingDialog(controller)
    dlg._on_finished()
    go_to(dlg, "capture")
    assert dlg.next_btn.text() == "Skip this step"
    dlg.capture_btn.click()
    assert controller.calls[-1] == ("toggle",)
    controller.signals.recording_started.emit()
    assert dlg.capture_btn.text().startswith("Finish")
    controller.signals.recording_finished.emit("This button is crooked.\n\n[Screenshots captured during this recording:]")
    assert "Screenshots captured" in dlg.capture_result.toPlainText()
    assert dlg.next_btn.text() == "Next"
    dlg.close()


def test_finish_requires_a_consent_choice_and_saves_choices(qapp, monkeypatch):
    applied = []
    monkeypatch.setattr("flowstate.ui.autostart.set_launch_at_login", applied.append)
    controller = DummyController()
    dlg = OnboardingDialog(controller)
    go_to(dlg, "finish")
    assert dlg.next_btn.text() == "Finish"
    assert not dlg.next_btn.isEnabled()
    dlg._choose_consent(False)
    assert dlg.next_btn.isEnabled()
    dlg._go_next()
    cfg = controller.config_store.config
    assert cfg.analytics.enabled is False and cfg.analytics.asked is True
    assert cfg.general.launch_at_login is True and applied == [True]


def test_closed_setup_stops_listening_to_dictations_and_open_recordings(qapp):
    controller = DummyController()
    dlg = OnboardingDialog(controller)
    dlg._on_finished()
    go_to(dlg, "try")
    controller.signals.recording_started.emit()
    dlg.reject()
    assert controller.calls[-1] == ("stop",)
    controller.signals.recording_finished.emit("later dictation")
    assert dlg.try_result.toPlainText() == ""


def test_existing_users_are_asked_once(qapp, monkeypatch):
    monkeypatch.setattr("flowstate.usage.analytics_config", lambda: ("phc_test", "https://eu.i.posthog.com"))
    store = ConfigStore()
    answers = iter([True])

    def fake_exec(dialog):
        dialog._answer(next(answers))

    monkeypatch.setattr(consent.ConsentDialog, "exec", fake_exec)
    consent.ask_once(store)
    assert store.config.analytics.enabled is True and store.config.analytics.asked is True
    consent.ask_once(store)  # Already answered: no second dialog (answers would be exhausted).


def test_people_already_sharing_are_not_asked(qapp, monkeypatch):
    monkeypatch.setattr("flowstate.usage.analytics_config", lambda: ("phc_test", "https://eu.i.posthog.com"))
    store = ConfigStore()
    store.config.analytics.enabled = True
    monkeypatch.setattr(consent.ConsentDialog, "exec", lambda dialog: pytest.fail("should not ask"))
    consent.ask_once(store)
    assert store.config.analytics.asked is True
