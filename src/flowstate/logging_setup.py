"""Rotating file logging for FlowState.

The log file is the primary debugging tool for a tray app with no visible
console, and it's how we confirm, e.g., whether the ASR engine picked CUDA
or fell back to CPU on a given machine.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from . import paths

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("flowstate")
    if logger.handlers:
        return logger  # already configured (e.g. re-entrant call in tests)

    logger.setLevel(level)

    log_file = paths.logs_dir() / "flowstate.log"
    file_handler = RotatingFileHandler(
        log_file, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    logger.addHandler(console_handler)

    return logger
