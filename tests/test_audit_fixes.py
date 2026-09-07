from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from flowstate.app import RecordingController
from flowstate.asr import engine as engine_mod
from flowstate.asr.engine import TranscriptionEngine, _clean_corrupt_model_dir, _is_valid_model_dir
from flowstate.config import ConfigStore
from flowstate.cuda_support import ensure_cuda_dll_search_paths
from flowstate.inject.paste import _restore_clipboard
from flowstate.text.formatter import SmartFormatter
from flowstate.ui.autostart import _build_command
from flowstate.ui.tray import TrayController


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_tray_controller_click_opens_settings(qapp):
    opened = []
    toggled = []
    quitted = []

    tray = TrayController(
        on_toggle_recording=lambda: toggled.append(1),
        on_open_settings=lambda: opened.append(1),
        on_quit=lambda: quitted.append(1),
    )

    # Trigger click should invoke on_open_settings without raising AttributeError
    tray._on_activated(QSystemTrayIcon.ActivationReason.Trigger)
    assert len(opened) == 1

    # DoubleClick should also invoke on_open_settings
    tray._on_activated(QSystemTrayIcon.ActivationReason.DoubleClick)
    assert len(opened) == 2


def test_tray_refresh_recent_sessions_handles_corrupt_files(qapp, tmp_path, monkeypatch):
    session_dir = tmp_path / "session_1"
    session_dir.mkdir()
    transcript_file = session_dir / "transcript.txt"
    # Write invalid bytes that cannot be decoded as utf-8
    transcript_file.write_bytes(b"\xff\xfe\x00\x00invalid")

    monkeypatch.setattr("flowstate.ui.tray.list_sessions", lambda: [session_dir])

    tray = TrayController(
        on_toggle_recording=lambda: None,
        on_open_settings=lambda: None,
        on_quit=lambda: None,
    )
    # Must not raise UnicodeDecodeError or any exception
    tray.refresh_recent_sessions()
    actions = tray.recent_menu.actions()
    assert len(actions) == 1


def test_autostart_build_command():
    cmd = _build_command()
    assert "--autostart" in cmd


def test_paste_restore_clipboard_none_is_noop():
    with patch("win32clipboard.OpenClipboard") as mock_open:
        _restore_clipboard(None)
        mock_open.assert_not_called()


def test_formatter_correct_skips_when_model_not_cached():
    formatter = SmartFormatter()
    assert not formatter.is_ready

    # Force is_model_cached to return False
    with patch.object(SmartFormatter, "is_model_cached", return_value=False):
        with patch.object(formatter, "preload") as mock_preload:
            result = formatter.correct("this is raw transcript")
            assert result == "this is raw transcript"
            mock_preload.assert_not_called()


def test_formatter_is_ready_reflects_llm_state():
    formatter = SmartFormatter()
    assert not formatter.is_ready
    formatter._llm = MagicMock()
    assert formatter.is_ready


def test_cuda_support_ensure_paths_runs_without_error():
    # Calling this multiple times or on any machine should be completely safe
    ensure_cuda_dll_search_paths()


def test_engine_is_valid_model_dir(tmp_path):
    assert not _is_valid_model_dir(tmp_path)

    # Empty model.bin is invalid
    (tmp_path / "model.bin").write_bytes(b"")
    assert not _is_valid_model_dir(tmp_path)

    # Non-empty model.bin is valid
    (tmp_path / "model.bin").write_bytes(b"dummy model weights")
    assert _is_valid_model_dir(tmp_path)


def test_engine_clean_corrupt_model_dir(tmp_path):
    corrupt_dir = tmp_path / "corrupt_model"
    corrupt_dir.mkdir()
    (corrupt_dir / "model.bin").write_bytes(b"")  # 0 bytes

    _clean_corrupt_model_dir(corrupt_dir)
    assert not corrupt_dir.exists()


def test_engine_load_cooldown_allows_retry(monkeypatch):
    engine = TranscriptionEngine(model_id="base.en", device_preference="cpu")
    engine._failure_cooldown_seconds = 0.1  # Short cooldown for test

    calls = []

    def fake_load_locked():
        calls.append(1)
        raise RuntimeError("Network offline")

    monkeypatch.setattr(engine, "_load_locked", fake_load_locked)

    with pytest.raises(RuntimeError):
        engine._load()
    assert len(calls) == 1

    # Immediate second call within cooldown must not re-call _load_locked
    with pytest.raises(RuntimeError):
        engine._load()
    assert len(calls) == 1

    # After cooldown expires, next call must retry
    import time
    time.sleep(0.15)
    with pytest.raises(RuntimeError):
        engine._load()
    assert len(calls) == 2


def test_app_apply_config_change_updates_microphone(tmp_path):
    store = ConfigStore(path=tmp_path / "config.json")
    controller = RecordingController(config_store=store)

    fake_device = MagicMock()
    fake_device.name = "USB Mic Pro"
    fake_device.index = 7

    with patch("flowstate.app.list_input_devices", return_value=[fake_device]):
        store.config.general.microphone_device = "USB Mic Pro"
        controller.apply_config_change()
        assert controller._recorder._device_index == 7


def test_app_processing_flag_blocks_new_recording():
    controller = RecordingController()
    controller._processing = True

    controller.start_recording()
    assert not controller.is_recording
