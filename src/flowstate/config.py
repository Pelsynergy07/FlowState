"""FlowState's settings: schema, JSON persistence, and change notification.

Deliberately has no dependency on Qt so it can be unit tested and reused by
the CLI smoke scripts in earlier phases before the GUI exists. The GUI layer
(Phase 6) subscribes to change callbacks and re-emits them as Qt signals.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Callable

from . import paths

CONFIG_VERSION = 1


@dataclass
class GeneralConfig:
    microphone_device: str | None = None  # None = system default input device
    launch_at_login: bool = False
    sound_cues: bool = True


@dataclass
class ShortcutConfig:
    toggle: str = "ctrl+shift+space"
    push_to_talk: str = "alt_r"


@dataclass
class CaptureConfig:
    mode: str = "circle"  # "circle" | "drag" | "off"
    sensitivity: float = 0.5  # 0.0 (loose) .. 1.0 (strict), maps to gesture thresholds


@dataclass
class CleanupConfig:
    vocabulary_enabled: bool = True
    grammar_enabled: bool = True


@dataclass
class ModelConfig:
    asr_model_id: str = "large-v3-turbo"
    compute_device: str = "auto"  # "auto" | "cuda" | "cpu"


@dataclass
class FlowStateConfig:
    version: int = CONFIG_VERSION
    general: GeneralConfig = field(default_factory=GeneralConfig)
    shortcuts: ShortcutConfig = field(default_factory=ShortcutConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    cleanup: CleanupConfig = field(default_factory=CleanupConfig)
    model: ModelConfig = field(default_factory=ModelConfig)


_NESTED_TYPES: dict[str, type] = {
    "general": GeneralConfig,
    "shortcuts": ShortcutConfig,
    "capture": CaptureConfig,
    "cleanup": CleanupConfig,
    "model": ModelConfig,
}


def _parse_nested(section_type: type, raw: dict) -> object:
    """Build a nested dataclass from a dict, filling in defaults for any
    field that is missing (covers both a corrupted section and forward
    migration when a new field is added in a later version)."""
    defaults = section_type()
    if not isinstance(raw, dict):
        return defaults
    kwargs = {}
    for f in fields(section_type):
        kwargs[f.name] = raw.get(f.name, getattr(defaults, f.name))
    return section_type(**kwargs)


def config_from_dict(raw: dict) -> FlowStateConfig:
    cfg = FlowStateConfig()
    if not isinstance(raw, dict):
        return cfg
    for name, nested_type in _NESTED_TYPES.items():
        setattr(cfg, name, _parse_nested(nested_type, raw.get(name, {})))
    return cfg


def config_to_dict(cfg: FlowStateConfig) -> dict:
    return asdict(cfg)


class ConfigStore:
    """Loads, persists, and broadcasts changes to the FlowState config."""

    def __init__(self, path: Path | None = None):
        self._path = path or paths.config_path()
        self._listeners: list[Callable[[FlowStateConfig], None]] = []
        self.config: FlowStateConfig = self._load()

    def _load(self) -> FlowStateConfig:
        if not self._path.exists():
            cfg = FlowStateConfig()
            self._write(cfg)
            return cfg
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return FlowStateConfig()
        return config_from_dict(raw)

    def _write(self, cfg: FlowStateConfig) -> None:
        self._path.write_text(json.dumps(config_to_dict(cfg), indent=2), encoding="utf-8")

    def save(self) -> None:
        """Persist the current config to disk and notify subscribers."""
        self._write(self.config)
        for listener in list(self._listeners):
            listener(self.config)

    def subscribe(self, callback: Callable[[FlowStateConfig], None]) -> None:
        self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[FlowStateConfig], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)
