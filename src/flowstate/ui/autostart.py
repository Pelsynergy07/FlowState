"""Launch at login: the per-user Run registry key on Windows, a per-user
LaunchAgent on macOS. No admin rights needed either way."""

from __future__ import annotations

from .. import platform


def _build_command() -> str:
    """The command the OS runs at login; --autostart keeps Settings closed."""
    return platform.adapter("system").autostart_command()


def set_launch_at_login(enabled: bool) -> None:
    platform.adapter("system").set_launch_at_login(enabled)
