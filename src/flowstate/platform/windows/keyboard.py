"""Global keyboard hook via a raw Windows low-level hook (WH_KEYBOARD_LL).

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
import threading
from ctypes import wintypes
from typing import Callable

logger = logging.getLogger("flowstate.hotkeys")

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


class KeyboardHook:
    """Delivers (tokens, is_down) for every physical key event and blocks the
    event when on_event returns True. Runs its own message-loop thread."""

    def __init__(self, on_event: Callable[[set[str], bool], bool]):
        self._on_event = on_event
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._hook_handle = None
        self._hook_proc = None  # must keep a reference alive for the hook's lifetime
        self.failed = False

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread_id is not None:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None
        self._thread_id = None

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        lresult = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
        hookproc_type = ctypes.WINFUNCTYPE(lresult, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode", wintypes.DWORD),
                ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_void_p),
            ]

        hook_handle_box: list = [None]

        def _proc(n_code, w_param, l_param):
            if n_code == 0:  # HC_ACTION
                kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                # Ignore injected keystrokes (e.g. from paste_transcript's
                # simulated Ctrl+V). They pollute the pressed state and
                # can cause spurious toggle fires.
                if kb.flags & LLKHF_INJECTED:
                    return user32.CallNextHookEx(hook_handle_box[0], n_code, w_param, l_param)
                tokens = vk_to_tokens(kb.vkCode, kb.flags)
                suppress = False
                try:
                    if w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                        suppress = self._on_event(tokens, True)
                    elif w_param in (WM_KEYUP, WM_SYSKEYUP):
                        suppress = self._on_event(tokens, False)
                except Exception:
                    logger.error("Keyboard hook callback raised", exc_info=True)
                if suppress:
                    return 1
            return user32.CallNextHookEx(hook_handle_box[0], n_code, w_param, l_param)

        self._hook_proc = hookproc_type(_proc)
        hook_handle_box[0] = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._hook_proc, None, 0)
        self._hook_handle = hook_handle_box[0]
        if not self._hook_handle:
            logger.error("Failed to install keyboard hook: %s", ctypes.WinError())
            self._hook_proc = None
            self.failed = True
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


def modifier_held(token: str) -> bool:
    """Whether a modifier family ("ctrl", "alt", "shift") is held right now."""
    vk = {"ctrl": VK_CONTROL, "alt": VK_MENU, "shift": VK_SHIFT}[token]
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
