"""No global keyboard hook on this platform yet."""

from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger("flowstate.hotkeys")


class KeyboardHook:
    def __init__(self, on_event: Callable[[set[str], bool], bool]):
        self.failed = True

    def start(self) -> None:
        logger.warning("Global shortcuts are not available on this platform; use the tray menu.")

    def stop(self) -> None:
        pass


def modifier_held(token: str) -> bool:
    return False
