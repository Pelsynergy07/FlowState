from flowstate.app import RecordingController
from flowstate.session.model import Session
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_nearest_segment_text_picks_enclosing_segment():
    segments = [
        (0.0, 2.0, "hello there"),
        (2.0, 5.0, "look at this bug"),
        (5.0, 8.0, "and here is the fix"),
    ]
    assert RecordingController._nearest_segment_text(segments, 3.5) == "look at this bug"


def test_nearest_segment_text_picks_closest_when_between_segments():
    segments = [
        (0.0, 1.0, "first"),
        (4.0, 5.0, "second"),
    ]
    # 1.4 is closer to the end of the first segment (0.4 away) than the
    # start of the second (2.6 away).
    assert RecordingController._nearest_segment_text(segments, 1.4) == "first"


def test_nearest_segment_text_handles_no_segments():
    assert RecordingController._nearest_segment_text([], 3.0) == ""


def test_long_transcript_and_screenshot_reach_saved_session_and_paste(tmp_path):
    controller = RecordingController.__new__(RecordingController)
    controller.signals = MagicMock()
    controller._hotkeys = MagicMock()
    controller._processing = True
    controller._asr = MagicMock()
    controller._pipeline = MagicMock()
    segments = [(float(i), float(i + 1), f"spoken sentence {i}") for i in range(180)]
    raw = " ".join(text for _, _, text in segments)
    controller._asr.transcribe_segments.return_value = segments
    controller._pipeline.run.return_value = raw
    session = Session("test", datetime.now(), tmp_path)
    image = tmp_path / "capture_1.png"
    image.touch()
    with patch("flowstate.app.restore_foreground_window", return_value=True), \
         patch("flowstate.app.paste_transcript") as paste:
        controller._process_recording(Path("audio.wav"), session, 42, [image], [179.5])
    pasted, images = paste.call_args.args
    assert raw[1:] in pasted and pasted.startswith("Spoken sentence 0")
    assert "179\n\n[Screenshots captured" in pasted
    assert 'capture_1.png at 2:59' in pasted
    assert 'spoken sentence 179' in pasted
    assert images == [image]
    assert (tmp_path / "raw_transcript.txt").read_text(encoding="utf-8") == raw
    assert session.transcript_path.read_text(encoding="utf-8") == pasted
    assert not controller._processing
    controller._hotkeys.reset_active_mode.assert_called_once()


def failure_controller(tmp_path):
    controller = RecordingController.__new__(RecordingController)
    controller.signals = MagicMock()
    controller._hotkeys = MagicMock()
    controller._recorder = MagicMock()
    controller._capture_hook = None
    controller._recording = False
    controller._processing = False
    controller.config_store = MagicMock()
    controller.config_store.config.capture.mode = "off"
    controller.config_store.config.general.sound_cues = False
    controller._current_session = Session("test", datetime.now(), tmp_path)
    return controller


def test_microphone_start_error_does_not_leave_recording_stuck(tmp_path):
    controller = failure_controller(tmp_path)
    controller._recorder.start.side_effect = RuntimeError("microphone disconnected")
    with patch("flowstate.app.get_foreground_window", return_value=42), \
         patch("flowstate.app.get_window_title", return_value="Editor"), \
         patch("flowstate.app.create_session", return_value=controller._current_session):
        controller.start_recording()
    assert not controller.is_recording
    assert not controller.is_processing
    controller._recorder.abort_and_close.assert_called_once()
    controller.signals.error.emit.assert_called_once_with("microphone disconnected")


def test_audio_save_error_does_not_leave_processing_stuck(tmp_path):
    controller = failure_controller(tmp_path)
    controller._recording = True
    controller._current_hwnd = 42
    controller._captured_images = []
    controller._capture_offsets = []
    controller._recorder.stop_and_save.side_effect = OSError("disk full")
    controller.stop_recording()
    assert not controller.is_recording
    assert not controller.is_processing
    controller._hotkeys.reset_active_mode.assert_called_once()
    controller.signals.error.emit.assert_called_once_with("disk full")
