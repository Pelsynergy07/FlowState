"""Process-level macOS integration: menu-bar app mode, single instance,
relaunch, launch at login (a per-user LaunchAgent), sound cues, and
hardware names."""

from __future__ import annotations

import io
import logging
import math
import os
import plistlib
import shlex
import struct
import subprocess
import sys
import wave
from pathlib import Path

logger = logging.getLogger("flowstate.platform")

BUNDLE_ID = "com.pelsynergy.flowstate"
_LAUNCH_AGENT = Path.home() / "Library" / "LaunchAgents" / f"{BUNDLE_ID}.plist"
_lock = None  # keeps the QLockFile alive for the process lifetime
_sounds: list = []  # NSSound objects must outlive play()


def app_bundle() -> Path | None:
    """FlowState.app when running the packaged build, else None (dev)."""
    if not getattr(sys, "frozen", False):
        return None
    exe = Path(sys.executable).resolve()
    for parent in exe.parents:
        if parent.suffix == ".app":
            return parent
    return None


def prepare_process() -> None:
    """Nothing to do before Qt starts."""


def configure_qt_application(app) -> None:
    """Menu-bar app: no Dock icon and no app menu, like the Windows tray app.
    The packaged app also sets LSUIElement in Info.plist.

    FlowState draws its own light paper-and-ink design. The native macOS
    style would paint tab bars and scroll bars in Dark Mode colors under
    it, so Qt's neutral Fusion style is used and windows stay light."""
    app.setStyle("Fusion")
    try:
        from AppKit import NSAppearance, NSApplication, NSApplicationActivationPolicyAccessory

        ns_app = NSApplication.sharedApplication()
        ns_app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        ns_app.setAppearance_(NSAppearance.appearanceNamed_("NSAppearanceNameAqua"))
    except Exception:
        logger.debug("Could not switch to menu-bar app mode", exc_info=True)


def acquire_single_instance_lock():
    """A lock file in FlowState's data folder. Stale locks from a crash are
    detected by Qt (dead PID) and taken over."""
    global _lock
    from PySide6.QtCore import QLockFile

    from ... import paths

    lock = QLockFile(str(paths.app_data_dir() / "flowstate.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(200):
        return None
    _lock = lock
    return lock


def allow_other_instance_to_take_focus() -> None:
    """macOS has no foreground lock to lift."""


def _launch_arguments(autostart: bool) -> list[str]:
    bundle = app_bundle()
    extra = ["--autostart"] if autostart else []
    if bundle is not None:
        return ["/usr/bin/open", "-a", str(bundle), "--args", *extra]
    return [sys.executable, "-m", "flowstate", *extra]


def autostart_command() -> str:
    return " ".join(shlex.quote(part) for part in _launch_arguments(autostart=True))


def set_launch_at_login(enabled: bool) -> None:
    """A per-user LaunchAgent: no admin rights, visible and removable under
    System Settings > General > Login Items."""
    if not enabled:
        _LAUNCH_AGENT.unlink(missing_ok=True)
        return
    agent = {
        "Label": BUNDLE_ID,
        "ProgramArguments": _launch_arguments(autostart=True),
        "RunAtLoad": True,
        "ProcessType": "Interactive",
        "LimitLoadToSessionType": "Aqua",
    }
    if app_bundle() is None:
        # Development runs need the source folder on the import path.
        src = str(Path(__file__).resolve().parents[3])
        agent["EnvironmentVariables"] = {"PYTHONPATH": src}
        agent["WorkingDirectory"] = src
    try:
        _LAUNCH_AGENT.parent.mkdir(parents=True, exist_ok=True)
        with open(_LAUNCH_AGENT, "wb") as f:
            plistlib.dump(agent, f)
    except OSError:
        logger.warning("Could not write the login item", exc_info=True)


def launch_at_login_enabled() -> bool:
    return _LAUNCH_AGENT.exists()


def spawn_relaunch() -> None:
    """Starts a new FlowState a moment after this process exits."""
    args = " ".join(shlex.quote(part) for part in _launch_arguments(autostart=False))
    if app_bundle() is not None:
        args = args.replace("/usr/bin/open -a", "/usr/bin/open -n -a", 1)
    env = os.environ.copy()
    if app_bundle() is None:
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[3])
    subprocess.Popen(["/bin/sh", "-c", f"sleep 1; {args}"], start_new_session=True, close_fds=True, env=env)


def _tone_wav(frequency: int, duration_ms: int, volume: float = 0.25) -> bytes:
    rate = 44100
    count = int(rate * duration_ms / 1000)
    fade = max(1, int(rate * 0.006))
    frames = bytearray()
    for i in range(count):
        envelope = min(1.0, i / fade, (count - i) / fade)
        sample = volume * envelope * math.sin(2 * math.pi * frequency * i / rate)
        frames += struct.pack("<h", int(sample * 32767))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(bytes(frames))
    return buffer.getvalue()


def play_tone(frequency: int, duration_ms: int) -> None:
    """A short soft blip through NSSound (independent of the recording stream)."""
    try:
        from AppKit import NSSound
        from Foundation import NSData

        data = _tone_wav(frequency, max(duration_ms, 60))
        sound = NSSound.alloc().initWithData_(NSData.dataWithBytes_length_(data, len(data)))
        if sound is None:
            return
        del _sounds[:-4]
        _sounds.append(sound)
        sound.play()
    except Exception:
        logger.debug("Sound cue failed to play", exc_info=True)


def microphone_access_blocked() -> bool:
    from . import permissions

    return permissions.microphone_status() == "denied"


MICROPHONE_SETTINGS_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"


def cpu_name() -> str:
    """e.g. "Apple M2 Max"."""
    try:
        out = subprocess.run(["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"],
                             capture_output=True, text=True, timeout=2)
        name = " ".join(out.stdout.split())
        if name:
            return name
    except Exception:
        pass
    import platform

    return platform.processor() or "Your Mac"


def memory_gb() -> int:
    try:
        out = subprocess.run(["/usr/sbin/sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=2)
        return round(int(out.stdout.strip()) / 1024 ** 3)
    except Exception:
        return 0
