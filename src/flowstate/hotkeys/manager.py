"""Global hotkeys: matches a toggle chord and a push-to-talk binding
against live keyboard state and decides which key events to swallow.

The matching logic here is pure and OS-independent. The OS keyboard hook
that feeds it lives in the platform adapter (platform/windows/keyboard.py,
a WH_KEYBOARD_LL hook; platform/macos/keyboard.py, a Quartz event tap).
Both translate physical keys into the same tokens ("ctrl_l", "ctrl",
"alt_r", "space", "m", ...), so bindings and this logic are shared.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Callable

from .. import platform
from ..platform.windows.keyboard import (  # noqa: F401  (pure helpers, re-exported for tests)
    LLKHF_EXTENDED,
    VK_CONTROL,
    VK_LCONTROL,
    VK_LMENU,
    VK_LSHIFT,
    VK_LWIN,
    VK_MENU,
    VK_RCONTROL,
    VK_RMENU,
    VK_RSHIFT,
    VK_RWIN,
    VK_SHIFT,
    VK_SPACE,
    vk_to_tokens,
)

logger = logging.getLogger("flowstate.hotkeys")

DEFAULT_TOGGLE, DEFAULT_PUSH_TO_TALK = platform.default_shortcuts()


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

        self._hook = None  # the platform adapter's KeyboardHook

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

    def _on_os_event(self, tokens: set[str], is_down: bool) -> bool:
        return self._on_keydown(tokens) if is_down else self._on_keyup(tokens)

    @property
    def hook_failed(self) -> bool:
        """True when the OS refused the keyboard hook (on macOS: Accessibility
        or Input Monitoring not granted yet)."""
        return bool(self._hook is not None and self._hook.failed)

    def start(self) -> None:
        self._running = True
        self._worker_thread = threading.Thread(target=self._event_worker, daemon=True)
        self._worker_thread.start()
        self._start_hook()

    def _start_hook(self) -> None:
        keyboard = platform.adapter("keyboard")
        self._hook = keyboard.KeyboardHook(self._on_os_event)
        self._hook.start()

    def restart_hook(self) -> bool:
        """Try the OS hook again, e.g. after the user granted access. Returns
        True when shortcuts now work."""
        if self._hook is not None:
            self._hook.stop()
        self._pressed.clear()
        self._suppressed_tokens.clear()
        self._start_hook()
        return not self.hook_failed

    def stop(self) -> None:
        self._running = False
        self._event_queue.put(None)
        if self._hook is not None:
            self._hook.stop()
            self._hook = None
