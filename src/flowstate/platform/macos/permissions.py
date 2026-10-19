"""The four macOS privacy permissions FlowState uses, each with a check, a
way to ask, and the System Settings pane to fix it.

macOS grants these to the app the user launched. In development that is
the terminal or editor running Python, not FlowState itself.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("flowstate.permissions")

_PANE = "x-apple.systempreferences:com.apple.preference.security?"
SETTINGS_URLS = {
    "microphone": _PANE + "Privacy_Microphone",
    "accessibility": _PANE + "Privacy_Accessibility",
    "input_monitoring": _PANE + "Privacy_ListenEvent",
    "screen_recording": _PANE + "Privacy_ScreenCapture",
}


def microphone_status() -> str:
    """"granted", "denied" or "undetermined"."""
    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeAudio

        status = AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeAudio)
    except Exception:
        return "granted"  # no AVFoundation: let the recorder report problems
    # AVAuthorizationStatus: 0 not determined, 1 restricted, 2 denied, 3 authorized
    return {0: "undetermined", 1: "denied", 2: "denied", 3: "granted"}.get(int(status), "undetermined")


def request_microphone() -> None:
    """Shows the system prompt the first time; no-op once answered."""
    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeAudio

        AVCaptureDevice.requestAccessForMediaType_completionHandler_(AVMediaTypeAudio, lambda granted: None)
    except Exception:
        logger.debug("Could not request microphone access", exc_info=True)


def accessibility_granted(prompt: bool = False) -> bool:
    """Needed to post Cmd+V into other apps and to create the shortcut tap."""
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt

        return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: bool(prompt)}))
    except Exception:
        logger.debug("Accessibility check unavailable", exc_info=True)
        return False


def input_monitoring_granted() -> bool:
    try:
        import Quartz

        return bool(Quartz.CGPreflightListenEventAccess())
    except Exception:
        return True  # older macOS without this API


def request_input_monitoring() -> None:
    try:
        import Quartz

        Quartz.CGRequestListenEventAccess()
    except Exception:
        logger.debug("Could not request Input Monitoring", exc_info=True)


def screen_recording_granted() -> bool:
    try:
        import Quartz

        return bool(Quartz.CGPreflightScreenCaptureAccess())
    except Exception:
        return True


def request_screen_recording() -> None:
    try:
        import Quartz

        Quartz.CGRequestScreenCaptureAccess()
    except Exception:
        logger.debug("Could not request Screen Recording", exc_info=True)


def all_permissions():
    """Ordered for onboarding: required first, screenshots last."""
    from ..permissions import Permission

    return [
        Permission(
            id="microphone",
            title="Microphone",
            why="To hear you while you hold or tap your shortcut. Nothing is recorded otherwise.",
            required=True,
            check=lambda: microphone_status() == "granted",
            request=request_microphone,
            settings_url=SETTINGS_URLS["microphone"],
        ),
        Permission(
            id="accessibility",
            title="Accessibility",
            why="To paste your text into the app you're using, and to make your shortcuts work everywhere.",
            required=True,
            check=accessibility_granted,
            request=lambda: accessibility_granted(prompt=True),
            settings_url=SETTINGS_URLS["accessibility"],
        ),
        Permission(
            id="input_monitoring",
            title="Input Monitoring",
            why="To notice when you press your FlowState shortcut in another app. Other keys are ignored.",
            required=True,
            check=input_monitoring_granted,
            request=request_input_monitoring,
            settings_url=SETTINGS_URLS["input_monitoring"],
        ),
        Permission(
            id="screen_recording",
            title="Screen Recording",
            why="Only for screenshots you point at while dictating. Skip it if you don't need them.",
            required=False,
            check=screen_recording_granted,
            request=request_screen_recording,
            settings_url=SETTINGS_URLS["screen_recording"],
        ),
    ]
