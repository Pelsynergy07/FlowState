"""Filesystem locations for FlowState's user data.

Everything the running app reads or writes lives under %LOCALAPPDATA%\\FlowState.
No path here may ever be hardcoded to a specific machine or username — this
module is the single place that resolves "where does FlowState live on this
computer," which is what makes the installed app portable across machines.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "FlowState"


def app_data_dir() -> Path:
    """Root folder for all FlowState user data on this machine."""
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        # Fallback for the rare environment where LOCALAPPDATA isn't set.
        base = str(Path.home() / "AppData" / "Local")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def models_dir() -> Path:
    path = app_data_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sessions_dir() -> Path:
    path = app_data_dir() / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return app_data_dir() / "config.json"


def vocabulary_user_path() -> Path:
    return app_data_dir() / "vocabulary_user.json"


def first_run_flag_path() -> Path:
    return app_data_dir() / "first_run_complete"
