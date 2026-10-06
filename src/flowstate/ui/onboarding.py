"""First-run setup: one window, a few short steps, each with one job.

1. Welcome: what FlowState does, this PC's hardware, what will download.
2. Microphone: pick a device, watch a live level meter, fix Windows
   microphone permissions.
3. Shortcuts: see and change both hotkeys, with conflict warnings, and
   choose whether FlowState starts with Windows.
4. Try it: one real dictation that shows the formatting.
5. Screenshot: one real Ctrl+drag (or circle) capture. Optional.
6. Finish: the anonymous-stats choice, and where FlowState lives.

Models download in the background from step 1 on, so the user is never
stuck watching a progress bar. Everything shown in the "try it" steps
comes from a real recording through the controller.
"""

from __future__ import annotations

import logging
import math
import shutil
import time

from PySide6.QtCore import QObject, QRectF, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .. import paths
from .fonts import make_font
from ..config import ShortcutConfig
from .key_recorder import KeyRecorderWidget, format_hotkey_display
from .theme import (
    FONT_FAMILY,
    FONT_FAMILY_DISPLAY,
    FONT_FAMILY_MONO,
    INK,
    LIME,
    LINE,
    MUTED_TEXT,
    PAPER_ALT,
    PAPER_RAISED,
    build_stylesheet,
    paint_paper_background,
    setup_brutalist_combobox,
)
from .widgets import BrutalistCheckBox

logger = logging.getLogger("flowstate.onboarding")

WIZARD_SIZE = (720, 640)  # 1080x960 at 150% scaling: fits a 1080p laptop screen above the taskbar.
DANGER_TEXT = "#B42318"
WARN_BG = "#FFF4D6"

# Shortcuts other popular apps already use. FlowState takes its hotkeys
# over system-wide, so the other app's shortcut stops working.
KNOWN_SHORTCUT_CONFLICTS = {
    "ctrl+m": "VS Code (toggle Tab key moves focus)",
    "ctrl+shift+space": "VS Code and JetBrains (parameter hints)",
    "ctrl+space": "autocomplete in most code editors",
    "ctrl+shift+m": "Microsoft Teams (mute)",
    "ctrl+shift+a": "Slack and many browsers",
    "alt+space": "Windows (window menu)",
    "ctrl+alt+space": "some input-method switchers",
}


def _normalize_spec(spec: str) -> str:
    order = {"ctrl": 0, "shift": 1, "alt": 2, "cmd": 3}
    tokens = [token.strip("<> ").lower() for token in spec.split("+") if token.strip("<> ")]
    tokens = [token.split("_")[0] if token.split("_")[0] in order else token for token in tokens]
    return "+".join(sorted(tokens, key=lambda token: (order.get(token, 9), token)))


def shortcut_conflict(spec: str) -> str | None:
    """Name of the app whose shortcut this hotkey would take over, if known."""
    return KNOWN_SHORTCUT_CONFLICTS.get(_normalize_spec(spec))


def microphone_access_blocked() -> bool:
    """True if Windows privacy settings stop desktop apps using the microphone.

    When blocked, every recording is silent and FlowState can only report
    "no speech detected", so setup checks it explicitly.
    """
    try:
        import winreg
    except ImportError:
        return False
    base = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
    for hive, key_path in ((winreg.HKEY_LOCAL_MACHINE, base), (winreg.HKEY_CURRENT_USER, base),
                           (winreg.HKEY_CURRENT_USER, base + r"\NonPackaged")):
        try:
            with winreg.OpenKey(hive, key_path) as key:
                if str(winreg.QueryValueEx(key, "Value")[0]).lower() == "deny":
                    return True
        except OSError:
            continue
    return False


def open_microphone_privacy_settings() -> None:
    QDesktopServices.openUrl(QUrl("ms-settings:privacy-microphone"))


def _cpu_name() -> str:
    """Readable processor name, e.g. "Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz"."""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            return " ".join(str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).split())
    except Exception:
        import platform

        return platform.processor() or "Your processor"


def _detect_hardware_summary() -> tuple[str, str, bool, int]:
    """Returns (hardware_title, detail_text, is_gpu, core_count).

    Asks the NVIDIA driver directly (milliseconds) rather than importing
    the CUDA runtime (seconds): the window must appear immediately. The
    models themselves still verify CUDA when they load.
    """
    import os
    from ..text import llm

    cores = os.cpu_count() or 4
    gpu = llm.cuda_device_name()
    if gpu:
        return gpu, "NVIDIA graphics card", True, cores
    return _cpu_name(), f"Processor ({cores} threads)", False, cores


def _missing_download_mb(controller, is_gpu: bool) -> int:
    """Approximate size of the models this machine still has to download."""
    total = 0
    try:
        from ..asr.engine import _find_model_dir

        spec = controller._asr.resolve_target_model(cuda_available=is_gpu)
        if _find_model_dir(paths.models_dir() / spec.id) is None:
            total += spec.approx_size_mb
    except Exception:
        pass
    try:
        from ..text import llm

        model = controller._pipeline._formatter.target_model(cuda_available=is_gpu)
        if not llm.is_cached(model):
            total += model.approx_size_mb
    except Exception:
        pass
    return total


class _PreloadWorker(QObject):
    """Downloads (if needed) and loads both models, off the UI thread."""

    progress = Signal(int)
    telemetry = Signal(str)
    status = Signal(str)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, controller, hw_name: str, is_gpu: bool, cores: int):
        super().__init__()
        self._controller = controller
        self._hw_name = hw_name
        self._is_gpu = is_gpu
        self._cores = cores
        # Each download fills its own slice of one continuous 0-100% bar.
        self._range = (0, 100)

    def run(self) -> None:
        try:
            if getattr(self._controller, "_is_preview", False):
                for pct in (20, 45, 70, 100):
                    time.sleep(0.3)
                    self.progress.emit(pct)
                self.finished.emit()
                return
            self._range = (0, 45)
            self._download_asr()
            self.status.emit("Loading the speech model…")
            self.telemetry.emit("")
            self.progress.emit(47)
            self._controller._asr._load()

            self._range = (50, 92)
            self.progress.emit(50)
            self._download_formatter()
            self.status.emit("Loading the formatting model…")
            self.telemetry.emit("")
            self.progress.emit(95)
            self._controller._pipeline.preload()
            self.progress.emit(100)
        except Exception as exc:
            logger.error("Preload worker failed", exc_info=True)
            self.failed.emit(str(exc))
            return
        self.finished.emit()

    def _on_download_progress(self, pct, current_bytes=0, total_bytes=0, speed=0.0, eta=None):
        low, high = self._range
        self.progress.emit(low + pct * (high - low) // 100)
        if total_bytes > 0 and speed > 0:
            text = f"{current_bytes / 1048576:,.0f} of {total_bytes / 1048576:,.0f} MB · {speed / 1048576:.1f} MB/s"
            if eta:
                minutes, seconds = divmod(int(eta), 60)
                text += f" · about {minutes} min left" if minutes else f" · {seconds}s left"
            self.telemetry.emit(text)

    def _download_asr(self) -> None:
        from huggingface_hub import snapshot_download
        from ..asr.downloader import download_dir_with_progress
        from ..asr.engine import _find_model_dir

        spec = self._controller._asr.resolve_target_model()
        target_dir = paths.models_dir() / spec.id
        if _find_model_dir(target_dir) is not None:
            return  # Already downloaded: never needs the network.
        self.status.emit("Downloading the speech model…")
        download_dir_with_progress(
            target_dir,
            max(spec.approx_size_mb, 1) * 1024 * 1024,
            do_download=lambda: snapshot_download(repo_id=spec.ct2_repo, local_dir=str(target_dir)),
            on_progress=self._on_download_progress,
        )

    def _download_formatter(self) -> None:
        from ..asr.downloader import download_dir_with_progress
        from ..text import llm

        # GPU machines download only the GPU model; CPU-only machines only the CPU one.
        model = self._controller._pipeline._formatter.target_model()
        if llm.is_cached(model):
            return
        self.status.emit("Downloading the formatting model…")
        download_dir_with_progress(
            llm.model_dir(model),
            model.approx_size_mb * 1024 * 1024,
            do_download=lambda: llm.download(model),
            on_progress=self._on_download_progress,
        )


class _MicMonitor:
    """Reads a microphone just to show its level; nothing is recorded."""

    def __init__(self):
        self._stream = None
        self._peak = 0.0

    def start(self, device_name: str | None) -> bool:
        self.stop()
        try:
            import numpy as np
            import sounddevice as sd

            device = None
            if device_name:
                for index, info in enumerate(sd.query_devices()):
                    if info["name"] == device_name and info["max_input_channels"] > 0:
                        device = index
                        break

            def callback(indata, frames, time_info, status):
                self._peak = max(self._peak, float(np.abs(indata).max()))

            self._stream = sd.InputStream(device=device, channels=1, dtype="float32", callback=callback)
            self._stream.start()
            return True
        except Exception:
            logger.info("Microphone level monitor unavailable", exc_info=True)
            self._stream = None
            return False

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def take_level(self) -> float:
        """Peak since the last call, on a perceptual 0..1 scale."""
        peak, self._peak = self._peak, 0.0
        if peak <= 1e-5:
            return 0.0
        db = 20 * math.log10(peak)
        return max(0.0, min(1.0, (db + 50) / 47))


class _LevelMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(18)
        self._level = 0.0

    def set_level(self, level: float) -> None:
        # Fast attack, slow release, like a hardware meter.
        self._level = level if level > self._level else self._level * 0.8 + level * 0.2
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.setPen(QPen(QColor(INK), 1))
        painter.setBrush(QColor(PAPER_ALT))
        painter.drawRoundedRect(rect, 4, 4)
        if self._level > 0.01:
            fill = QRectF(2, 2, (self.width() - 4) * self._level, self.height() - 4)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(LIME))
            painter.drawRoundedRect(fill, 3, 3)


class _CaptureTarget(QFrame):
    """A small mock app window with something to point at."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(112)
        self.setMinimumWidth(420)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        painter.setPen(QPen(QColor(LINE), 1))
        painter.setBrush(QColor(PAPER_RAISED))
        painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 6, 6)
        painter.setBrush(QColor("#F1ECE3"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(QRectF(1, 1, w - 2, 26), 6, 6)
        painter.setPen(QColor(MUTED_TEXT))
        painter.setFont(make_font(FONT_FAMILY_MONO, 8))
        painter.drawText(12, 18, "Checkout · My Store")
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#DDD6CA"))
        for i, width in enumerate((0.55, 0.4, 0.48)):
            painter.drawRoundedRect(QRectF(16, 40 + i * 16, (w - 32) * width, 8), 4, 4)
        # The misaligned button: the thing worth pointing at.
        painter.save()
        painter.translate(w - 170, 72)
        painter.rotate(-4)
        painter.setPen(QPen(QColor(INK), 1.5))
        painter.setBrush(QColor(LIME))
        painter.drawRoundedRect(QRectF(0, 0, 140, 34), 5, 5)
        painter.setPen(QColor(INK))
        painter.setFont(make_font(FONT_FAMILY, 10, bold=True))
        painter.drawText(QRectF(0, 0, 140, 34), Qt.AlignCenter, "Pay now")
        painter.restore()


def _heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    # A style sheet, not setFont: the app-wide QLabel rule would override it.
    label.setStyleSheet(f"font-family: '{FONT_FAMILY_DISPLAY}'; font-size: 28px;")
    return label


def _body(text: str, muted: bool = False) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextFormat(Qt.RichText)
    label.setStyleSheet(f"font-size: 14px; color: {MUTED_TEXT if muted else INK};")
    return label


def _section(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setStyleSheet(f"font-family: '{FONT_FAMILY_MONO}'; font-size: 11px; font-weight: 700; "
                        f"letter-spacing: 1px; color: {MUTED_TEXT};")
    return label


def _card(*widgets, spacing: int = 8) -> QFrame:
    card = QFrame()
    card.setProperty("role", "card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(spacing)
    for widget in widgets:
        if isinstance(widget, QWidget):
            layout.addWidget(widget)
        else:
            layout.addLayout(widget)
    return card


class _Status(QLabel):
    """One line of live feedback: neutral, good, or a problem."""

    STYLES = {
        "idle": (PAPER_ALT, MUTED_TEXT),
        "good": (LIME, INK),
        "warn": (WARN_BG, DANGER_TEXT),
    }

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.set(text, "idle")

    def set(self, text: str, tone: str = "idle") -> None:
        background, color = self.STYLES[tone]
        self.setText(text)
        self.setVisible(bool(text))
        self.setStyleSheet(f"background: {background}; color: {color}; border-radius: 4px; "
                           f"padding: 7px 10px; font-size: 13px; font-weight: 600;")


class OnboardingDialog(QDialog):
    """The single first-run window."""

    def __init__(self, controller):
        super().__init__()
        self._controller = controller
        self.setWindowTitle("FlowState Setup")
        self.setStyleSheet(build_stylesheet())
        self.resize(*WIZARD_SIZE)
        self.setMinimumSize(640, 540)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        cfg = controller.config_store.config
        self.hw_name, self.hw_detail, self.is_gpu, self.cores = _detect_hardware_summary()
        self.skipped = False
        # True once both models are downloaded and loaded; otherwise the app
        # finishes preparing them in the background after this dialog.
        self.models_ready = False
        self.consent: bool | None = None
        self.launch_at_login = True
        self._download_state = "idle"  # idle | running | done | failed
        self._download_mb = _missing_download_mb(controller, self.is_gpu)
        self._recording = False
        self._thread: QThread | None = None
        self._worker: _PreloadWorker | None = None
        self._mic_monitor = _MicMonitor()
        self._meter_timer = QTimer(self)
        self._meter_timer.setInterval(50)
        self._meter_timer.timeout.connect(self._update_meter)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 18)
        outer.setSpacing(12)

        self.download_strip = QFrame()
        self.download_strip.setProperty("role", "shortcut-panel")
        strip = QHBoxLayout(self.download_strip)
        strip.setContentsMargins(12, 8, 12, 8)
        strip.setSpacing(10)
        self.download_label = QLabel("")
        self.download_label.setStyleSheet("font-size: 12px; font-weight: 600;")
        self.download_detail = QLabel("")
        self.download_detail.setStyleSheet(f"font-size: 12px; color: {MUTED_TEXT};")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setFixedSize(150, 16)
        self.progress.setTextVisible(False)
        self.retry_btn = QPushButton("Try again")
        self.retry_btn.setProperty("role", "secondary")
        self.retry_btn.clicked.connect(self._start_download)
        self.retry_btn.hide()
        strip.addWidget(self.download_label)
        strip.addWidget(self.download_detail, 1)
        strip.addWidget(self.progress)
        strip.addWidget(self.retry_btn)
        self.download_strip.hide()
        outer.addWidget(self.download_strip)

        self.stack = QStackedWidget()
        self.pages: list[str] = []
        self._add_page("welcome", self._build_welcome())
        self._add_page("microphone", self._build_microphone(cfg))
        self._add_page("shortcuts", self._build_shortcuts(cfg))
        self._add_page("try", self._build_try(cfg))
        if cfg.capture.mode in ("drag", "circle"):
            self._add_page("capture", self._build_capture(cfg))
        self._add_page("finish", self._build_finish())
        outer.addWidget(self.stack, 1)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        self.back_btn = QPushButton("Back")
        self.back_btn.setProperty("role", "secondary")
        self.back_btn.clicked.connect(self._go_back)
        self.skip_btn = QPushButton("Skip setup")
        self.skip_btn.setProperty("role", "secondary")
        self.skip_btn.clicked.connect(self._skip_onboarding)
        self.step_label = QLabel("")
        self.step_label.setStyleSheet(f"font-family: '{FONT_FAMILY_MONO}'; font-size: 11px; color: {MUTED_TEXT};")
        self.next_btn = QPushButton("")
        self.next_btn.setProperty("role", "primary")
        self.next_btn.setMinimumWidth(190)
        self.next_btn.clicked.connect(self._go_next)
        footer.addWidget(self.back_btn)
        footer.addWidget(self.skip_btn)
        footer.addStretch(1)
        footer.addWidget(self.step_label)
        footer.addWidget(self.next_btn)
        outer.addLayout(footer)

        # Real recordings drive the "try it" steps; disconnected in done().
        self._connections = []
        for name, slot in (("recording_started", self._on_recording_started),
                           ("processing_started", self._on_processing_started),
                           ("recording_finished", self._on_recording_finished),
                           ("no_speech_detected", self._on_no_speech),
                           ("error", self._on_error)):
            signal = getattr(controller.signals, name, None)
            if signal is not None:
                signal.connect(slot)
                self._connections.append((signal, slot))

        self._show_page(0)

    # -- Page construction ------------------------------------------------
    def _add_page(self, name: str, content: QWidget) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        self.stack.addWidget(scroll)
        self.pages.append(name)

    @staticmethod
    def _page() -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(10)
        return page, layout

    def _build_welcome(self) -> QWidget:
        page, layout = self._page()
        layout.addWidget(_section("Welcome to FlowState"))
        layout.addWidget(_heading("Talk, and clean text appears wherever you type."))
        layout.addWidget(_body(
            "Hold a shortcut, speak, let go. FlowState writes down what you said with punctuation, "
            "emails and lists laid out, in your own words, and pastes it into the app you're using. "
            "It runs entirely on this PC."))

        if self.is_gpu:
            speed = "Your graphics card will run dictation, so text appears in about 2 seconds."
        else:
            speed = ("No NVIDIA graphics card was found, so FlowState runs on your processor with a smaller "
                     "speech model. It works fully offline; text takes a few seconds longer to appear.")
        hardware = _card(_section("This PC"), _body(f"<b>{self.hw_name}</b>"), _body(speed, muted=True))
        layout.addWidget(hardware)

        self.welcome_download = _body(self._intro_text(self._download_mb))
        layout.addWidget(_card(_section("One-time download"), self.welcome_download))
        layout.addStretch(1)
        return page

    @staticmethod
    def _intro_text(needed_mb: int) -> str:
        """Say what will be downloaded before anything is."""
        if not needed_mb:
            return "The speech and formatting models are already on this PC. Nothing to download."
        text = (f"FlowState downloads its speech and formatting models once (about {needed_mb / 1024:.1f} GB) "
                "from Hugging Face. After that, everything runs offline. You can keep setting up while it downloads.")
        try:
            free_mb = shutil.disk_usage(paths.models_dir()).free // (1024 * 1024)
            if free_mb < needed_mb + 500:
                text += (f" <b>Only {free_mb / 1024:.1f} GB is free on this drive, so please make room "
                         "first.</b>")
        except OSError:
            pass
        return text

    def _build_microphone(self, cfg) -> QWidget:
        page, layout = self._page()
        layout.addWidget(_section("Step 1 · Microphone"))
        layout.addWidget(_heading("Pick your microphone"))
        layout.addWidget(_body("Say something. The bar should move while you talk.", muted=True))

        self.mic_combo = QComboBox()
        self.mic_combo.setFixedHeight(36)
        self.mic_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        setup_brutalist_combobox(self.mic_combo)
        self.mic_combo.addItem("System default", None)
        try:
            from ..audio.devices import list_input_devices

            for device in list_input_devices():
                self.mic_combo.addItem(device.name, device.name)
        except Exception:
            logger.warning("Could not enumerate audio devices in onboarding", exc_info=True)
        index = self.mic_combo.findData(cfg.general.microphone_device)
        self.mic_combo.setCurrentIndex(index if index >= 0 else 0)
        self.mic_combo.currentIndexChanged.connect(self._on_mic_changed)

        self.level_meter = _LevelMeter()
        self.mic_status = _Status()
        layout.addWidget(_card(self.mic_combo, self.level_meter, self.mic_status))

        self.mic_permission_card = QFrame()
        self.mic_permission_card.setStyleSheet(f"QFrame {{ background: {WARN_BG}; border: 1px solid {DANGER_TEXT}; "
                                               "border-radius: 6px; }")
        permission = QVBoxLayout(self.mic_permission_card)
        permission.setContentsMargins(14, 12, 14, 12)
        permission_text = _body("<b>Windows is blocking microphone access for desktop apps.</b> "
                                "Turn on “Let desktop apps access your microphone”, then come back here.")
        permission_text.setStyleSheet(f"font-size: 13px; color: {DANGER_TEXT};")
        fix_btn = QPushButton("Open Windows microphone settings")
        fix_btn.clicked.connect(open_microphone_privacy_settings)
        permission.addWidget(permission_text)
        permission.addWidget(fix_btn, 0, Qt.AlignLeft)
        self.mic_permission_card.hide()
        layout.addWidget(self.mic_permission_card)
        layout.addStretch(1)
        return page

    def _build_shortcuts(self, cfg) -> QWidget:
        page, layout = self._page()
        layout.addWidget(_section("Step 2 · Shortcuts"))
        layout.addWidget(_heading("Your shortcuts"))
        layout.addWidget(_body("These work in every app. Click a shortcut to change it.", muted=True))

        self.ptt_edit = KeyRecorderWidget(cfg.shortcuts.push_to_talk, default_combo=ShortcutConfig.push_to_talk)
        self.toggle_edit = KeyRecorderWidget(cfg.shortcuts.toggle, default_combo=ShortcutConfig.toggle)
        self.ptt_edit.keyChanged.connect(self._on_shortcut_changed)
        self.toggle_edit.keyChanged.connect(self._on_shortcut_changed)
        layout.addWidget(_card(_body("<b>Hold to talk</b> · hold while you speak, let go to paste"), self.ptt_edit,
                               _body("<b>Hands-free</b> · tap to start, tap again to paste"), self.toggle_edit))
        self.shortcut_status = _Status()
        layout.addWidget(self.shortcut_status)

        self.autostart_check = BrutalistCheckBox("Start FlowState when Windows starts", checked=True)
        layout.addWidget(_card(self.autostart_check, _body(
            "FlowState sits in the system tray and only listens while you hold or tap your shortcut.",
            muted=True)))
        layout.addStretch(1)
        self._on_shortcut_changed()
        return page

    def _build_try(self, cfg) -> QWidget:
        page, layout = self._page()
        layout.addWidget(_section("Step 3 · Try it"))
        layout.addWidget(_heading("Say this out loud"))
        self.sample_prompt = ("Hi Sam, quick update. First, the report is done. Second, the demo moved to Friday. "
                              "Thanks, Alex")
        quote = QLabel(f"“{self.sample_prompt}”")
        quote.setWordWrap(True)
        quote.setStyleSheet(f"font-family: '{FONT_FAMILY_DISPLAY}'; font-size: 21px;")
        self.try_hint = _body("")
        self.hold_btn = QPushButton(f"Hold to talk  ({format_hotkey_display(cfg.shortcuts.push_to_talk)})")
        self.hold_btn.setProperty("role", "primary")
        self.hold_btn.pressed.connect(self._hold_to_talk_pressed)
        self.hold_btn.released.connect(self._hold_to_talk_released)
        layout.addWidget(_card(quote, self.try_hint, self.hold_btn))

        self.try_status = _Status()
        self.try_result = QTextEdit()
        self.try_result.setReadOnly(True)
        self.try_result.setPlaceholderText("Your formatted text appears here.")
        self.try_result.setMinimumHeight(110)
        layout.addWidget(self.try_status)
        layout.addWidget(self.try_result, 1)
        return page

    def _build_capture(self, cfg) -> QWidget:
        page, layout = self._page()
        layout.addWidget(_section("Step 4 · Screenshots (optional)"))
        layout.addWidget(_heading("Point at what you're talking about"))
        if cfg.capture.mode == "circle":
            how = "draw a loop around the <b>Pay now</b> button with your mouse"
        else:
            how = "hold <b>Ctrl</b> and drag a box around the <b>Pay now</b> button"
        toggle = format_hotkey_display(cfg.shortcuts.toggle)
        layout.addWidget(_body(
            f"Tap <b>{toggle}</b>, say <i>“this button is crooked”</i>, {how}, then tap <b>{toggle}</b> again. "
            "The screenshot is pasted with your words: handy for bug reports and AI assistants."))
        layout.addWidget(_CaptureTarget())
        self.capture_btn = QPushButton(f"Start  ({toggle})")
        self.capture_btn.clicked.connect(self._toggle_recording)
        layout.addWidget(self.capture_btn, 0, Qt.AlignLeft)
        self.capture_status = _Status()
        self.capture_result = QTextEdit()
        self.capture_result.setReadOnly(True)
        self.capture_result.setPlaceholderText("Your text and the screenshot reference appear here.")
        self.capture_result.setMinimumHeight(56)
        layout.addWidget(self.capture_status)
        layout.addWidget(self.capture_result, 1)
        return page

    def _build_finish(self) -> QWidget:
        page, layout = self._page()
        layout.addWidget(_section("Last step"))
        layout.addWidget(_heading("You're all set"))
        layout.addWidget(_card(_body(
            "<b>Where FlowState lives:</b> the FlowState icon in the system tray, at the bottom right of the "
            "taskbar (it may be under the ^ arrow). Right-click it for Settings, History and recent dictations."),
            _body("<b>While you talk</b> a small recording bar appears at the bottom of the screen.", muted=True)))

        try:
            from ..usage import analytics_config

            self._analytics_available = bool(analytics_config()[0])
        except Exception:
            self._analytics_available = False
        if self._analytics_available:
            self.share_btn = QPushButton("Share anonymous stats")
            self.decline_btn = QPushButton("Don't share")
            for button, choice in ((self.share_btn, True), (self.decline_btn, False)):
                button.setCheckable(True)
                button.clicked.connect(lambda _checked=False, c=choice: self._choose_consent(c))
            choices = QHBoxLayout()
            choices.addWidget(self.share_btn)
            choices.addWidget(self.decline_btn)
            choices.addStretch(1)
            layout.addWidget(_card(
                _section("Help improve FlowState?"),
                _body("Share anonymous counts: how many words and dictations, how long processing takes, and "
                      "whether it worked. <b>Never</b> your audio, text, screenshots, clipboard, or anything "
                      "you type. You can change this anytime in Settings → Stats."),
                choices))
        layout.addStretch(1)
        return page

    # -- Navigation ---------------------------------------------------------
    def _show_page(self, index: int) -> None:
        previous = self.pages[self.stack.currentIndex()] if self.stack.count() else None
        if previous == "microphone" and index != self.stack.currentIndex():
            self._stop_mic_monitor()
        self.stack.setCurrentIndex(index)
        name = self.pages[index]
        self.back_btn.setVisible(index > 0)
        self.skip_btn.setVisible(name == "welcome")
        visible_steps = len(self.pages) - 2
        self.step_label.setText(f"Step {index} of {visible_steps}" if 0 < index <= visible_steps else "")
        labels = {
            "welcome": "Download && continue" if self._download_state == "idle" and self._download_mb else "Continue",
            "microphone": "Next",
            "shortcuts": "Next",
            "try": "Next",
            "capture": "Next",
            "finish": "Finish",
        }
        if name == "capture":
            labels["capture"] = "Next" if self.capture_result.toPlainText() else "Skip this step"
        self.next_btn.setText(labels[name])
        if name == "microphone":
            self._start_mic_monitor()
        if name in ("try", "capture"):
            self._refresh_try_state()
        if name == "finish":
            self.next_btn.setEnabled(not self._analytics_available or self.consent is not None)
        else:
            self.next_btn.setEnabled(True)

    def _go_next(self) -> None:
        index = self.stack.currentIndex()
        name = self.pages[index]
        if name == "welcome" and self._download_state in ("idle", "failed"):
            self._start_download()
        if name == "shortcuts":
            self.launch_at_login = self.autostart_check.isChecked()
        if name == "finish":
            self._finish()
            return
        self._show_page(index + 1)

    def _go_back(self) -> None:
        self._show_page(max(0, self.stack.currentIndex() - 1))

    def _skip_onboarding(self) -> None:
        self.skipped = True
        logger.info("User skipped onboarding.")
        self.accept()

    def _finish(self) -> None:
        cfg = self._controller.config_store.config
        cfg.general.launch_at_login = self.launch_at_login
        if self._analytics_available and self.consent is not None:
            cfg.analytics.enabled = self.consent
            cfg.analytics.asked = True
        self._controller.config_store.save()
        try:
            from .autostart import set_launch_at_login

            set_launch_at_login(self.launch_at_login)
        except Exception:
            logger.warning("Could not update launch at login", exc_info=True)
        self.accept()

    def done(self, result: int) -> None:
        self._stop_mic_monitor()
        for signal, slot in self._connections:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._connections = []
        if self._recording:
            stop = getattr(self._controller, "stop_recording", None)
            if stop is not None:
                stop()
        super().done(result)

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_paper_background(painter, self.rect())

    # -- Background download ------------------------------------------------
    def _start_download(self) -> None:
        if self._download_state == "running":
            return
        # A retry must actually retry, not replay the previous failure.
        for component in (getattr(self._controller, "_asr", None),
                          getattr(getattr(self._controller, "_pipeline", None), "_formatter", None)):
            if component is not None and hasattr(component, "clear_load_failure"):
                component.clear_load_failure()
        self._download_state = "running"
        self.download_strip.show()
        self.retry_btn.hide()
        self.progress.show()
        self.progress.setValue(0)
        self.download_label.setText("Preparing models…")
        self.download_detail.setText("")
        self._thread = QThread()
        self._worker = _PreloadWorker(self._controller, self.hw_name, self.is_gpu, self.cores)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.status.connect(self.download_label.setText)
        self._worker.telemetry.connect(self.download_detail.setText)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.start()

    def _on_finished(self) -> None:
        self.models_ready = True
        self._download_state = "done"
        self.progress.setValue(100)
        self.download_label.setText("Models ready")
        self.download_detail.setText("FlowState now works offline.")
        self.retry_btn.hide()
        self._refresh_try_state()

    def _on_failed(self, message: str) -> None:
        self._download_state = "failed"
        self.download_strip.show()
        self.progress.hide()
        network = any(marker in message for marker in (
            "Connection", "Timeout", "Max retries", "getaddrinfo", "NameResolution", "internet connection"))
        self.download_label.setText("Download failed")
        self.download_detail.setText("Check your internet connection." if network else "Something went wrong.")
        self.download_detail.setToolTip(message)
        self.retry_btn.show()
        self._refresh_try_state()

    # -- Microphone -----------------------------------------------------------
    def _start_mic_monitor(self) -> None:
        if microphone_access_blocked():
            self.mic_permission_card.show()
            self.mic_status.set("")
            return
        self.mic_permission_card.hide()
        if self._mic_monitor.start(self.mic_combo.currentData()):
            self.mic_status.set("Listening to this microphone…", "idle")
            self._heard_voice = False
            self._meter_timer.start()
        else:
            self.mic_status.set("This microphone couldn't be opened. Try another one.", "warn")

    def _stop_mic_monitor(self) -> None:
        self._meter_timer.stop()
        self._mic_monitor.stop()
        if hasattr(self, "level_meter"):
            self.level_meter.set_level(0.0)

    def _update_meter(self) -> None:
        level = self._mic_monitor.take_level()
        self.level_meter.set_level(level)
        if level > 0.35 and not getattr(self, "_heard_voice", False):
            self._heard_voice = True
            self.mic_status.set("Your microphone works.", "good")

    def _on_mic_changed(self) -> None:
        new_mic = self.mic_combo.currentData()
        self._controller.config_store.config.general.microphone_device = new_mic
        self._controller.config_store.save()
        self._stop_mic_monitor()
        if hasattr(self._controller, "switch_microphone"):
            self._controller.switch_microphone(new_mic)
        elif hasattr(self._controller, "apply_config_change"):
            self._controller.apply_config_change()
        logger.info("Microphone updated in onboarding: %r", new_mic)
        if self.pages[self.stack.currentIndex()] == "microphone":
            self._start_mic_monitor()

    # -- Shortcuts --------------------------------------------------------------
    def _on_shortcut_changed(self, *_args) -> None:
        from ..hotkeys.manager import bindings_conflict

        ptt = self.ptt_edit.text().strip()
        toggle = self.toggle_edit.text().strip()
        if not ptt or not toggle:
            self.shortcut_status.set("Both shortcuts need a key combination.", "warn")
            return
        if bindings_conflict(toggle, ptt):
            self.shortcut_status.set("These two shortcuts overlap, so one would trigger the other. "
                                     "Pick keys that don't share everything.", "warn")
            return
        notes = [f"{format_hotkey_display(spec)}: {app}"
                 for spec in (ptt, toggle) if (app := shortcut_conflict(spec))]
        if notes:
            self.shortcut_status.set("Also used by other apps, which lose the shortcut while FlowState runs. "
                                     "Change it if you use them:\n" + "\n".join(notes), "warn")
        else:
            self.shortcut_status.set("")
        cfg = self._controller.config_store.config
        if (cfg.shortcuts.push_to_talk, cfg.shortcuts.toggle) != (ptt, toggle):
            cfg.shortcuts.push_to_talk, cfg.shortcuts.toggle = ptt, toggle
            self._controller.config_store.save()
            set_shortcuts = getattr(self._controller, "set_shortcuts", None)
            if set_shortcuts is not None:
                set_shortcuts(toggle, ptt)
            self._refresh_shortcut_labels()

    def _refresh_shortcut_labels(self) -> None:
        cfg = self._controller.config_store.config
        if hasattr(self, "hold_btn"):
            self.hold_btn.setText(f"Hold to talk  ({format_hotkey_display(cfg.shortcuts.push_to_talk)})")
        if hasattr(self, "capture_btn") and not self._recording:
            self.capture_btn.setText(f"Start  ({format_hotkey_display(cfg.shortcuts.toggle)})")

    # -- Real dictation -----------------------------------------------------------
    def _refresh_try_state(self) -> None:
        if not hasattr(self, "hold_btn"):
            return
        ready = self.models_ready
        ptt = format_hotkey_display(self._controller.config_store.config.shortcuts.push_to_talk)
        self.hold_btn.setEnabled(ready)
        if hasattr(self, "capture_btn"):
            self.capture_btn.setEnabled(ready)
        if ready:
            self.try_hint.setText(f"Hold <b>{ptt}</b> (or the button), say the sentence, then let go.")
        elif self._download_state == "failed":
            self.try_hint.setText("The models didn't download. Use <b>Try again</b> at the top, or finish "
                                  "setup and FlowState will keep trying in the background.")
        else:
            self.try_hint.setText("Waiting for the models to finish downloading (progress at the top)…")

    def _current_try(self) -> tuple[_Status, QTextEdit] | None:
        name = self.pages[self.stack.currentIndex()]
        if name == "try":
            return self.try_status, self.try_result
        if name == "capture":
            return self.capture_status, self.capture_result
        return None

    def _hold_to_talk_pressed(self) -> None:
        start = getattr(self._controller, "start_recording", None)
        if start is not None:
            start(mode="ptt")

    def _hold_to_talk_released(self) -> None:
        stop = getattr(self._controller, "stop_recording", None)
        if stop is not None:
            stop()

    def _toggle_recording(self) -> None:
        toggle = getattr(self._controller, "toggle_recording", None)
        if toggle is not None:
            toggle()

    def _set_recording(self, recording: bool) -> None:
        self._recording = recording
        if hasattr(self, "capture_btn"):
            toggle = format_hotkey_display(self._controller.config_store.config.shortcuts.toggle)
            self.capture_btn.setText(f"{'Finish' if recording else 'Start'}  ({toggle})")

    def _on_recording_started(self) -> None:
        self._set_recording(True)
        current = self._current_try()
        if current:
            current[0].set("Listening… speak now.", "good")

    def _on_processing_started(self) -> None:
        self._set_recording(False)
        current = self._current_try()
        if current:
            current[0].set("Formatting…", "idle")

    def _on_recording_finished(self, text: str) -> None:
        self._set_recording(False)
        current = self._current_try()
        if not current or not text or not text.strip():
            return
        status, result = current
        result.setPlainText(text.strip())
        status.set("Done. In any other app, this is pasted where your cursor is.", "good")
        if self.pages[self.stack.currentIndex()] == "capture":
            self.next_btn.setText("Next")

    def _on_no_speech(self) -> None:
        self._set_recording(False)
        current = self._current_try()
        if current:
            current[0].set("Didn't hear anything. Check your microphone (step 1) and try again.", "warn")

    def _on_error(self, _message: str) -> None:
        self._set_recording(False)
        current = self._current_try()
        if current:
            current[0].set("Something went wrong. Try again.", "warn")

    # -- Consent ---------------------------------------------------------------------
    def _choose_consent(self, share: bool) -> None:
        self.consent = share
        self.share_btn.setChecked(share)
        self.decline_btn.setChecked(not share)
        for button, chosen in ((self.share_btn, share), (self.decline_btn, not share)):
            button.setProperty("role", "primary" if chosen else "")
            button.style().unpolish(button)
            button.style().polish(button)
        if self.pages[self.stack.currentIndex()] == "finish":
            self.next_btn.setEnabled(True)
