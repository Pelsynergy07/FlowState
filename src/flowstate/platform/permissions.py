"""OS privacy permissions as plain data, so onboarding and Settings can show
one checklist on every platform without knowing which OS they run on."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import IS_MACOS, IS_WINDOWS


@dataclass(frozen=True)
class Permission:
    id: str
    title: str
    why: str
    required: bool
    check: Callable[[], bool]
    request: Callable[[], object]
    settings_url: str

    def granted(self) -> bool:
        try:
            return bool(self.check())
        except Exception:
            return False


def all_permissions() -> list[Permission]:
    if IS_MACOS:
        from .macos.permissions import all_permissions as mac_permissions

        return mac_permissions()
    if IS_WINDOWS:
        from .windows.system import MICROPHONE_SETTINGS_URL, microphone_access_blocked

        return [Permission(
            id="microphone",
            title="Microphone",
            why="Windows must let desktop apps use the microphone.",
            required=True,
            check=lambda: not microphone_access_blocked(),
            request=lambda: None,
            settings_url=MICROPHONE_SETTINGS_URL,
        )]
    return []


def missing_required() -> list[Permission]:
    return [p for p in all_permissions() if p.required and not p.granted()]
