"""Runs the update check off the Qt thread and hands the result back via a
signal -- same cross-thread pattern as ControllerSignals in app.py, since
touching widgets from a plain background thread isn't safe."""

from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, Signal

from ..update_check import UpdateInfo, check_for_update

logger = logging.getLogger("flowstate.update_check")


class UpdateNotifierSignals(QObject):
    checked = Signal(object)  # UpdateInfo | None


def check_for_update_async(signals: UpdateNotifierSignals) -> None:
    def _run() -> None:
        try:
            result = check_for_update()
        except Exception:
            logger.warning("Update check failed unexpectedly", exc_info=True)
            result = None
        signals.checked.emit(result)

    threading.Thread(target=_run, daemon=True).start()
