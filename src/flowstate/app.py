"""Wires every subsystem together into the actual recording flow.

Runs independently of any Qt event loop: hotkeys fire on pynput's own
listener thread, so the whole pipeline can run (and be smoke-tested) from
a plain script with no GUI at all -- signals emitted with nothing
connected are harmless no-ops. The GUI layer (Phase 6) connects to
`RecordingController.signals` to update the tray/HUD; because hotkey
callbacks run on pynput's thread, not the Qt thread, those signals (not
direct widget calls) are what make cross-thread UI updates safe -- Qt
auto-queues a signal emitted from a different thread than its receiver.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .asr.engine import TranscriptionEngine
from .audio import cues
from .audio.devices import list_input_devices
from .audio.recorder import Recorder
from .capture.annotate import draw_circle_highlight, draw_rect_highlight
from .capture.drag_hook import DragCaptureHook
from .capture.gesture import Sensitivity
from .capture.mouse_hook import GestureMouseHook
from .capture.screenshot import capture_monitor_at
from .config import ConfigStore
from .hotkeys.manager import HotkeyManager
from .inject.focus import get_foreground_window, get_window_title, restore_foreground_window
from .inject.paste import paste_transcript
from .session.model import Session
from .session.store import create_session, enforce_retention, save_session
from .text.pipeline import CleanupPipeline

logger = logging.getLogger("flowstate.app")


class ControllerSignals(QObject):
    recording_started = Signal()
    processing_started = Signal()  # recording stopped, transcription/cleanup running
    recording_finished = Signal(str)  # cleaned transcript
    error = Signal(str)
    drag_selection_started = Signal(int, int)
    drag_selection_moved = Signal(int, int)
    drag_selection_ended = Signal()


class RecordingController:
    def __init__(self, config_store: ConfigStore | None = None):
        self.config_store = config_store or ConfigStore()
        self.signals = ControllerSignals()
        cfg = self.config_store.config

        self._asr = TranscriptionEngine(
            model_id=cfg.model.asr_model_id, device_preference=cfg.model.compute_device
        )
        self._pipeline = CleanupPipeline(
            vocabulary_enabled=cfg.cleanup.vocabulary_enabled,
            grammar_enabled=cfg.cleanup.grammar_enabled,
        )
        self._recorder = Recorder(device_index=self._resolve_device_index(cfg.general.microphone_device))
        self._capture_hook: GestureMouseHook | DragCaptureHook | None = None

        self._hotkeys = HotkeyManager(
            on_toggle=self.toggle_recording,
            on_ptt_start=self.start_recording,
            on_ptt_stop=self.stop_recording,
            toggle_spec=cfg.shortcuts.toggle,
            push_to_talk_spec=cfg.shortcuts.push_to_talk,
        )

        self._recording = False
        self._recording_mode: str | None = None  # None, "toggle", or "ptt"
        self._current_session: Session | None = None
        self._current_hwnd: int | None = None
        self._captured_images: list[Path] = []
        self._capture_offsets: list[float] = []  # seconds into the recording, one per captured image
        self._recording_start_monotonic: float | None = None

    @staticmethod
    def _resolve_device_index(name: str | None) -> int | None:
        if not name:
            return None
        for d in list_input_devices():
            if d.name == name:
                return d.index
        return None

    def start(self) -> None:
        self._hotkeys.start()
        enforce_retention()
        self.warmup_async()
        logger.info("FlowState controller started")

    def warmup_async(self) -> None:
        """Preloads the ASR and formatting models on a background thread."""
        threading.Thread(target=self._warmup, daemon=True).start()

    def _warmup(self) -> None:
        try:
            self._asr._load()
        except Exception:
            logger.warning("ASR warmup failed", exc_info=True)
        try:
            self._pipeline.preload()
        except Exception:
            logger.warning("Formatting model warmup failed", exc_info=True)

    def stop(self) -> None:
        self._hotkeys.stop()

    def apply_config_change(self) -> None:
        """Re-reads shortcut/cleanup settings from config_store.config."""
        cfg = self.config_store.config
        self._hotkeys.set_bindings(cfg.shortcuts.toggle, cfg.shortcuts.push_to_talk)
        self._pipeline.vocabulary_enabled = cfg.cleanup.vocabulary_enabled
        self._pipeline.grammar_enabled = cfg.cleanup.grammar_enabled

    def get_input_level(self) -> float:
        """Current mic input level (0..1), for a HUD level meter."""
        return self._recorder.level()

    def toggle_recording(self) -> None:
        if self._recording_mode == "toggle":
            self.stop_recording()
        elif self._recording_mode == "ptt":
            logger.info("Upgrading active PTT recording session to toggle mode")
            self._recording_mode = "toggle"
        else:
            self.start_recording(mode="toggle")

    def start_recording(self, mode: str = "ptt") -> None:
        if self._recording:
            return
        self._recording = True
        self._recording_mode = mode
        self._current_hwnd = get_foreground_window()
        source_app = get_window_title(self._current_hwnd)
        self._current_session = create_session(source_app=source_app)
        self._captured_images = []
        self._capture_offsets = []

        cfg = self.config_store.config
        if cfg.general.sound_cues:
            cues.play_start_cue()

        if cfg.capture.mode == "circle":
            sensitivity = Sensitivity(value=cfg.capture.sensitivity)
            self._capture_hook = GestureMouseHook(on_circle=self._on_circle_detected, sensitivity=sensitivity)
            self._capture_hook.start()
        elif cfg.capture.mode == "drag":
            self._capture_hook = DragCaptureHook(
                on_region=self._on_drag_region_detected,
                on_drag_start=lambda x, y: self.signals.drag_selection_started.emit(x, y),
                on_drag_move=lambda x, y: self.signals.drag_selection_moved.emit(x, y),
                on_drag_end=lambda: self.signals.drag_selection_ended.emit(),
            )
            self._capture_hook.start()

        self._recorder.start()
        self._recording_start_monotonic = time.monotonic()
        logger.info("Recording started (mode: %s, source app: %s)", mode, source_app)
        self.signals.recording_started.emit()

    def _elapsed_recording_seconds(self) -> float:
        if self._recording_start_monotonic is None:
            return 0.0
        return time.monotonic() - self._recording_start_monotonic

    def _on_circle_detected(self, cx: float, cy: float) -> None:
        if self._current_session is None:
            return
        try:
            image, monitor = capture_monitor_at(cx, cy)
            annotated = draw_circle_highlight(image, cx, cy, monitor["left"], monitor["top"])
            image_path = self._current_session.folder / f"capture_{len(self._captured_images) + 1}.png"
            annotated.save(image_path)
            self._captured_images.append(image_path)
            self._capture_offsets.append(self._elapsed_recording_seconds())
            logger.info("Circle gesture captured a screenshot: %s", image_path)
        except Exception:
            logger.warning("Failed to capture/annotate screenshot from gesture", exc_info=True)

    def _on_drag_region_detected(self, left: int, top: int, right: int, bottom: int) -> None:
        if self._current_session is None:
            return
        try:
            cx, cy = (left + right) / 2, (top + bottom) / 2
            image, monitor = capture_monitor_at(cx, cy)
            annotated = draw_rect_highlight(image, left, top, right, bottom, monitor["left"], monitor["top"])
            image_path = self._current_session.folder / f"capture_{len(self._captured_images) + 1}.png"
            annotated.save(image_path)
            self._captured_images.append(image_path)
            self._capture_offsets.append(self._elapsed_recording_seconds())
            logger.info("Ctrl+drag captured a screenshot: %s", image_path)
        except Exception:
            logger.warning("Failed to capture/annotate screenshot from drag", exc_info=True)

    def _build_capture_references(self, segments: list[tuple[float, float, str]]) -> str:
        """A short, plain-text block naming each screenshot taken during
        this recording, when it was taken, and what was being said nearby
        -- appended after cleanup so an agent reading the pasted transcript
        (e.g. "look at this") can tell which capture_N.png a reference
        like that points to, instead of just seeing a bare image on the
        clipboard with no textual link back to it."""
        if not self._captured_images:
            return ""
        lines = ["", "[Screenshots captured during this recording:]"]
        for i, (image_path, offset) in enumerate(zip(self._captured_images, self._capture_offsets), start=1):
            mins, secs = divmod(int(offset), 60)
            nearby = self._nearest_segment_text(segments, offset)
            entry = f'{i}. {image_path.name} at {mins}:{secs:02d}'
            if nearby:
                entry += f' -- said around then: "{nearby}"'
            lines.append(entry)
        return "\n".join(lines)

    @staticmethod
    def _nearest_segment_text(segments: list[tuple[float, float, str]], offset: float) -> str:
        if not segments:
            return ""

        def distance(segment: tuple[float, float, str]) -> float:
            start, end, _text = segment
            if start <= offset <= end:
                return 0.0
            return min(abs(start - offset), abs(end - offset))

        return min(segments, key=distance)[2]

    def stop_recording(self) -> None:
        if not self._recording or self._current_session is None:
            return
        self._recording = False
        self._recording_mode = None

        if self._capture_hook is not None:
            self._capture_hook.stop()
            self._capture_hook = None

        cfg = self.config_store.config
        if cfg.general.sound_cues:
            cues.play_stop_cue()

        wav_path = self._current_session.folder / "audio.wav"
        self._recorder.stop_and_save(wav_path)
        self.signals.processing_started.emit()

        try:
            segments = self._asr.transcribe_segments(wav_path)
            raw_text = " ".join(text for _start, _end, text in segments)
            cleaned_text = self._pipeline.run(raw_text)
            logger.info("Transcribed: %r", cleaned_text)

            final_text = cleaned_text + self._build_capture_references(segments)

            session = self._current_session
            session.transcript = final_text
            session.image_paths = list(self._captured_images)
            save_session(session)

            if self._current_hwnd is not None:
                restored = restore_foreground_window(self._current_hwnd)
                if not restored:
                    # Clipboard still has the transcript even though the
                    # paste below will likely land nowhere useful -- better
                    # than silently doing nothing and the user never
                    # knowing why. See inject/focus.py for why this can
                    # legitimately fail despite the retries in there.
                    logger.warning(
                        "Focus could not be restored to the original window; "
                        "pasting anyway, but it may not land in the right place"
                    )
            paste_transcript(final_text, self._captured_images)
        except Exception as exc:
            logger.error("Transcription/cleanup/paste failed", exc_info=True)
            self.signals.error.emit(str(exc))
            self._current_session = None
            self._current_hwnd = None
            self._hotkeys.reset_active_mode()
            return

        self._current_session = None
        self._current_hwnd = None
        self._hotkeys.reset_active_mode()
        self.signals.recording_finished.emit(final_text)
