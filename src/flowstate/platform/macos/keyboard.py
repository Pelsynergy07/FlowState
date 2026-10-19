"""Global keyboard hook via a Quartz event tap (CGEventTap).

The macOS counterpart of the Windows WH_KEYBOARD_LL hook: an *active*
session tap sees every key press system-wide and can swallow just the
events that belong to a FlowState shortcut, letting everything else
through untouched.

macOS only creates the tap once the user has allowed FlowState under
Privacy & Security > Accessibility (and Input Monitoring). Until then
CGEventTapCreate returns NULL; `failed` is set and the app keeps
working without global shortcuts, while onboarding and Settings show
how to grant access and call start() again.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

logger = logging.getLogger("flowstate.hotkeys")

# Marks key events FlowState posts itself (the Cmd+V in clipboard.py), so
# the tap can ignore them like Windows' LLKHF_INJECTED flag.
INJECTED_EVENT_MARKER = 0x464C5354  # "FLST"

# Carbon virtual key codes (HIToolbox/Events.h, kVK_*). Positions on an
# ANSI keyboard; macOS maps other layouts onto the same physical codes.
_MODIFIER_KEYS = {
    0x38: ("shift_l", "shift", 0x00000002),   # kVK_Shift, NX_DEVICELSHIFTKEYMASK
    0x3C: ("shift_r", "shift", 0x00000004),   # kVK_RightShift
    0x3B: ("ctrl_l", "ctrl", 0x00000001),     # kVK_Control
    0x3E: ("ctrl_r", "ctrl", 0x00002000),     # kVK_RightControl
    0x3A: ("alt_l", "alt", 0x00000020),       # kVK_Option
    0x3D: ("alt_r", "alt", 0x00000040),       # kVK_RightOption
    0x37: ("cmd_l", "cmd", 0x00000008),       # kVK_Command
    0x36: ("cmd_r", "cmd", 0x00000010),       # kVK_RightCommand
}

_LETTER_KEYS = {
    0x00: "a", 0x0B: "b", 0x08: "c", 0x02: "d", 0x0E: "e", 0x03: "f", 0x05: "g", 0x04: "h",
    0x22: "i", 0x26: "j", 0x28: "k", 0x25: "l", 0x2E: "m", 0x2D: "n", 0x1F: "o", 0x23: "p",
    0x0C: "q", 0x0F: "r", 0x01: "s", 0x11: "t", 0x20: "u", 0x09: "v", 0x0D: "w", 0x07: "x",
    0x10: "y", 0x06: "z",
    0x1D: "0", 0x12: "1", 0x13: "2", 0x14: "3", 0x15: "4", 0x17: "5", 0x16: "6", 0x1A: "7",
    0x1C: "8", 0x19: "9",
    0x31: "space",
}

KEYCODE_V = 0x09


def keycode_to_tokens(keycode: int) -> set[str]:
    """Same token vocabulary as the Windows hook: a side-specific name plus the
    family name for modifiers ("alt_r" and "alt"), else the key's own name."""
    modifier = _MODIFIER_KEYS.get(keycode)
    if modifier is not None:
        return {modifier[0], modifier[1]}
    name = _LETTER_KEYS.get(keycode)
    return {name} if name else set()


def modifier_is_down(keycode: int, flags: int) -> bool | None:
    """For a flagsChanged event: whether that specific modifier key is now down.
    The device-dependent bits in the low word say which side changed."""
    modifier = _MODIFIER_KEYS.get(keycode)
    if modifier is None:
        return None
    return bool(flags & modifier[2])


class KeyboardHook:
    """Delivers (tokens, is_down) for every physical key event and swallows
    the event when on_event returns True. Runs its own CFRunLoop thread."""

    def __init__(self, on_event: Callable[[set[str], bool], bool]):
        self._on_event = on_event
        self._thread: threading.Thread | None = None
        self._run_loop = None
        self._tap = None
        self._ready = threading.Event()
        self.failed = False

    def start(self) -> None:
        self.failed = False
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="FlowStateEventTap", daemon=True)
        self._thread.start()
        # Report a missing permission synchronously, so callers can show it.
        self._ready.wait(timeout=2)

    def stop(self) -> None:
        import Quartz

        if self._tap is not None:
            Quartz.CGEventTapEnable(self._tap, False)
        if self._run_loop is not None:
            Quartz.CFRunLoopStop(self._run_loop)
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None
        self._run_loop = None
        self._tap = None

    def _callback(self, proxy, event_type, event, refcon):
        import Quartz

        if event_type in (Quartz.kCGEventTapDisabledByTimeout, Quartz.kCGEventTapDisabledByUserInput):
            # macOS turns a slow tap off; turn it straight back on.
            if self._tap is not None:
                Quartz.CGEventTapEnable(self._tap, True)
            return event
        try:
            if Quartz.CGEventGetIntegerValueField(event, Quartz.kCGEventSourceUserData) == INJECTED_EVENT_MARKER:
                return event
            keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
            if event_type == Quartz.kCGEventFlagsChanged:
                down = modifier_is_down(keycode, Quartz.CGEventGetFlags(event))
                if down is None:
                    return event  # Caps Lock, Fn and other non-shortcut modifiers
            elif event_type == Quartz.kCGEventKeyDown:
                down = True
            elif event_type == Quartz.kCGEventKeyUp:
                down = False
            else:
                return event
            tokens = keycode_to_tokens(keycode)
            if tokens and self._on_event(tokens, down):
                return None  # swallowed: part of an active FlowState shortcut
        except Exception:
            logger.error("Event tap callback raised", exc_info=True)
        return event

    def _run(self) -> None:
        import Quartz

        mask = (Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
                | Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp)
                | Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged))
        try:
            self._tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionDefault,
                mask,
                self._callback,
                None,
            )
        except Exception:
            logger.error("Could not create the keyboard event tap", exc_info=True)
            self._tap = None
        if self._tap is None:
            logger.warning("Keyboard shortcuts need Accessibility and Input Monitoring access "
                           "(System Settings > Privacy & Security).")
            self.failed = True
            self._ready.set()
            return
        source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        self._run_loop = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(self._run_loop, source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(self._tap, True)
        logger.info("Keyboard event tap installed")
        self._ready.set()
        Quartz.CFRunLoopRun()
        logger.info("Keyboard event tap removed")


def modifier_held(token: str) -> bool:
    """Whether a modifier family ("ctrl", "alt", "shift", "cmd") is held now."""
    import Quartz

    masks = {
        "ctrl": Quartz.kCGEventFlagMaskControl,
        "alt": Quartz.kCGEventFlagMaskAlternate,
        "shift": Quartz.kCGEventFlagMaskShift,
        "cmd": Quartz.kCGEventFlagMaskCommand,
    }
    flags = Quartz.CGEventSourceFlagsState(Quartz.kCGEventSourceStateCombinedSessionState)
    return bool(flags & masks[token])
