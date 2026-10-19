"""Global hotkeys via a raw Windows low-level keyboard hook (WH_KEYBOARD_LL).

Not pynput: pynput's Listener only offers all-or-nothing suppression --
suppress=False lets every key through (including the physical keys that
make up your own hotkey, so holding Space for push-to-talk also types
real spaces into whatever's focused), and suppress=True blocks *all*
keyboard input globally, breaking normal typing entirely. Not Win32
RegisterHotKey either: that API can't bind a bare modifier and can't
distinguish press-vs-release for push-to-talk.

A raw WH_KEYBOARD_LL hook lets us block only the specific key events that
are part of an actively-matching binding, and pass every other keystroke
through completely untouched.
"""

from __future__ import annotations

import ctypes
import logging
import queue
import threading
from ctypes import wintypes
from typing import Callable

logger = logging.getLogger("flowstate.hotkeys")

DEFAULT_TOGGLE = "ctrl+shift+space"
DEFAULT_PUSH_TO_TALK = "shift+space"

# -- Win32 constants ----------------------------------------------------
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
LLKHF_EXTENDED = 0x01
LLKHF_INJECTED = 0x10  # Set by Windows when the event was injected

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_SPACE = 0x20

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

_LRESULT = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
_HOOKPROC = ctypes.WINFUNCTYPE(_LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


def vk_to_tokens(vk_code: int, flags: int) -> set[str]:
    """Every token spelling that refers to this physical key press: a
    side-specific name (e.g. "alt_r") and, for modifiers, the generic
    family name too (e.g. "alt"), so a binding of "ctrl" matches either
    physical Ctrl key while a binding of "alt_r" matches only right Alt."""
    if vk_code == VK_CONTROL:
        # Generic VK_CONTROL: some keyboards/drivers deliver this with
        # LLKHF_EXTENDED marking the right key instead of the side-specific
        # VK_LCONTROL/VK_RCONTROL codes below -- handle both spellings.
        side = "ctrl_r" if flags & LLKHF_EXTENDED else "ctrl_l"
        return {side, "ctrl"}
    if vk_code == VK_LCONTROL:
        return {"ctrl_l", "ctrl"}
    if vk_code == VK_RCONTROL:
        return {"ctrl_r", "ctrl"}
    if vk_code == VK_MENU:
        side = "alt_r" if flags & LLKHF_EXTENDED else "alt_l"
        return {side, "alt"}
    if vk_code == VK_LMENU:
        return {"alt_l", "alt"}
    if vk_code == VK_RMENU:
        return {"alt_r", "alt"}
    if vk_code == VK_LSHIFT:
        return {"shift_l", "shift"}
    if vk_code == VK_RSHIFT:
        return {"shift_r", "shift"}
    if vk_code == VK_SHIFT:
        # Generic VK_SHIFT: return all shift tokens so keyup clears shift_l and shift_r
        return {"shift_l", "shift_r", "shift"}
    if vk_code == VK_LWIN:
        return {"cmd_l", "cmd"}
    if vk_code == VK_RWIN:
        return {"cmd_r", "cmd"}
    if vk_code == VK_SPACE:
        return {"space"}
    if 0x30 <= vk_code <= 0x39:  # '0'-'9'
        return {chr(vk_code)}
    if 0x41 <= vk_code <= 0x5A:  # 'A'-'Z'
        return {chr(vk_code).lower()}
    return set()


class HotkeyBinding:
    def __init__(self, spec: str):
        self.spec = spec
        self.tokens: frozenset[str] = frozenset(
            t.strip().lower() for t in spec.split("+") if t.strip()
        )

    def matches(self, pressed_tokens: set[str]) -> bool:
        return bool(self.tokens) and self.tokens.issubset(pressed_tokens)

    def __repr__(self) -> str:
        return f"HotkeyBinding({self.spec!r})"


def bindings_conflict(spec_a: str, spec_b: str) -> bool:
    """True if one binding's keys are a subset of the other's (or they're
    identical), e.g. push-to-talk "shift+space" against toggle
    "ctrl+shift+space". A quick tap of the larger chord always satisfies
    the smaller one a moment before the rest of the chord registers, so
    the smaller binding's action (usually push-to-talk) fires first and,
    on release moments later, immediately stops again -- a toggle tap
    that was meant to start a hands-free recording instead looks like it
    "flashes and does nothing"."""
    tokens_a = HotkeyBinding(spec_a).tokens
    tokens_b = HotkeyBinding(spec_b).tokens
    if not tokens_a or not tokens_b:
        return False
    return tokens_a <= tokens_b or tokens_b <= tokens_a


class HotkeyManager:
    """Matches a toggle chord and a push-to-talk key against live keyboard
    state, and decides whether each key event should be swallowed.

    _on_keydown/_on_keyup are pure functions of (tokens, prior state) that
    return whether to suppress the event -- tests drive them directly with
    VK codes, with no OS hook involved.
    """

    def __init__(
        self,
        on_toggle: Callable[[], None],
        on_ptt_start: Callable[[], None],
        on_ptt_stop: Callable[[], None],
        toggle_spec: str = DEFAULT_TOGGLE,
        push_to_talk_spec: str = DEFAULT_PUSH_TO_TALK,
    ):
        self._on_toggle = on_toggle
        self._on_ptt_start = on_ptt_start
        self._on_ptt_stop = on_ptt_stop
        self._toggle_binding = HotkeyBinding(toggle_spec)
        self._ptt_binding = HotkeyBinding(push_to_talk_spec)
        self._pressed: set[str] = set()
        self._suppressed_tokens: set[str] = set()

        # State tracking
        self._active_mode: str | None = None  # None, "ptt", or "toggle"
        self._toggle_armed: bool = True

        # Sequential FIFO event queue to prevent callback thread race conditions
        self._event_queue: queue.Queue[Callable[[], None] | None] = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self._running: bool = False

        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._hook_handle = None
        self._hook_proc = None  # must keep a reference alive for the hook's lifetime

    def set_bindings(self, toggle_spec: str, push_to_talk_spec: str) -> None:
        self._toggle_binding = HotkeyBinding(toggle_spec)
        self._ptt_binding = HotkeyBinding(push_to_talk_spec)
        self._pressed.clear()
        self._suppressed_tokens.clear()
        self._active_mode = None
        self._toggle_armed = True

    def reset_active_mode(self) -> None:
        self._active_mode = None
        self._toggle_armed = True

    # -- Sequential Worker Thread -----------------------------------------

    def _event_worker(self) -> None:
        while self._running:
            try:
                task = self._event_queue.get(timeout=0.2)
                if task is None:
                    break
                try:
                    task()
                except Exception:
                    logger.error("Hotkey callback raised in worker thread", exc_info=True)
                finally:
                    self._event_queue.task_done()
            except queue.Empty:
                continue

    def _dispatch(self, fn: Callable[[], None]) -> None:
        """Enqueue callback for sequential execution on dedicated worker thread."""
        if self._running:
            self._event_queue.put(fn)
        else:
            # Fallback if worker not running (e.g. unit tests)
            try:
                fn()
            except Exception:
                logger.error("Hotkey callback raised", exc_info=True)

    def _safe_call(self, fn: Callable[[], None]) -> None:
        """Kept for backward compatibility with tests; delegates to _dispatch."""
        self._dispatch(fn)

    # -- Pure matching/suppression logic, OS-independent -----------------

    def _on_keydown(self, tokens: set[str]) -> bool:
        """Updates state for a key-down event and returns whether it
        should be suppressed (blocked from reaching every other app)."""
        if not tokens:
            return False

        pressed_before = set(self._pressed)
        already_held = bool(tokens & self._pressed)
        self._pressed |= tokens
        suppress = False

        toggle_tokens = self._toggle_binding.tokens
        ptt_tokens = self._ptt_binding.tokens

        if tokens & ptt_tokens and (ptt_tokens - tokens) <= pressed_before:
            suppress = True
        if tokens & toggle_tokens and (toggle_tokens - tokens) <= pressed_before:
            suppress = True

        toggle_completes_now = (
            bool(tokens & toggle_tokens)
            and (toggle_tokens - tokens) <= pressed_before
            and not already_held
            and toggle_tokens <= self._pressed
            and self._toggle_armed
        )
        ptt_completes_now = (
            bool(tokens & ptt_tokens)
            and (ptt_tokens - tokens) <= pressed_before
            and ptt_tokens <= self._pressed
        )

        if toggle_completes_now:
            self._toggle_armed = False  # Disarm toggle until ALL chord keys are released
            if self._active_mode is None:
                self._active_mode = "toggle"
                logger.info("Toggle ON (mode: None -> toggle)")
                self._dispatch(self._on_toggle)  # starts
            elif self._active_mode == "toggle":
                self._active_mode = None
                logger.info("Toggle OFF (mode: toggle -> None)")
                self._dispatch(self._on_toggle)  # stops
            elif self._active_mode == "ptt":
                self._active_mode = "toggle"
                logger.info("PTT -> toggle takeover (mode: ptt -> toggle)")
                self._dispatch(self._on_toggle)  # notify controller to upgrade PTT session to toggle
        elif ptt_completes_now and self._active_mode is None:
            self._active_mode = "ptt"
            logger.info("PTT START (mode: None -> ptt)")
            self._dispatch(self._on_ptt_start)

        if suppress:
            self._suppressed_tokens |= tokens
        return suppress

    def _on_keyup(self, tokens: set[str]) -> bool:
        if not tokens:
            return False

        suppress = bool(tokens & self._suppressed_tokens)
        self._suppressed_tokens -= tokens

        # Remove tokens and family aliases from pressed
        self._pressed -= tokens
        if "shift" in tokens:
            self._pressed -= {"shift_l", "shift_r"}
        if "ctrl" in tokens:
            self._pressed -= {"ctrl_l", "ctrl_r"}
        if "alt" in tokens:
            self._pressed -= {"alt_l", "alt_r"}

        # Re-arm toggle ONLY when ALL keys of the toggle chord have been fully released.
        toggle_tokens = self._toggle_binding.tokens
        if not self._toggle_armed and (not toggle_tokens or self._pressed.isdisjoint(toggle_tokens)):
            self._toggle_armed = True

        ptt_tokens = self._ptt_binding.tokens
        if (
            self._active_mode == "ptt"
            and (tokens & ptt_tokens)
            and not (ptt_tokens <= self._pressed)
        ):
            self._active_mode = None
            logger.info("PTT STOP (mode: ptt -> None)")
            self._dispatch(self._on_ptt_stop)

        return suppress

    # -- OS hook wiring ----------------------------------------------

    def start(self) -> None:
        self._running = True
        self._worker_thread = threading.Thread(target=self._event_worker, daemon=True)
        self._worker_thread.start()

        self._thread = threading.Thread(target=self._run_hook_thread, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._event_queue.put(None)

        if self._thread_id is not None:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None
        self._thread_id = None

    def _run_hook_thread(self) -> None:
        hook_handle_box: list = [None]

        def _proc(n_code, w_param, l_param):
            if n_code == 0:  # HC_ACTION
                kb = ctypes.cast(l_param, ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents

                # Ignore injected keystrokes (e.g. from paste_transcript's
                # simulated Ctrl+V). They pollute our _pressed state and
                # can cause spurious toggle fires.
                if kb.flags & LLKHF_INJECTED:
                    return user32.CallNextHookEx(hook_handle_box[0], n_code, w_param, l_param)

                tokens = vk_to_tokens(kb.vkCode, kb.flags)
                suppress = False
                try:
                    if w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                        suppress = self._on_keydown(tokens)
                    elif w_param in (WM_KEYUP, WM_SYSKEYUP):
                        suppress = self._on_keyup(tokens)
                except Exception:
                    logger.error("Keyboard hook callback raised", exc_info=True)
                if suppress:
                    return 1
            return user32.CallNextHookEx(hook_handle_box[0], n_code, w_param, l_param)

        self._hook_proc = _HOOKPROC(_proc)
        hook_handle_box[0] = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._hook_proc, None, 0)
        self._hook_handle = hook_handle_box[0]
        if not self._hook_handle:
            logger.error("Failed to install keyboard hook: %s", ctypes.WinError())
            self._hook_proc = None
            return

        self._thread_id = kernel32.GetCurrentThreadId()
        logger.info("Keyboard hook installed")

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        user32.UnhookWindowsHookEx(self._hook_handle)
        self._hook_handle = None
        self._hook_proc = None
        logger.info("Keyboard hook removed")
