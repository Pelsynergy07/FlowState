"""Microphone enumeration."""

from __future__ import annotations

from dataclasses import dataclass

import sounddevice as sd


@dataclass(frozen=True)
class InputDevice:
    index: int
    name: str
    default_samplerate: float


def list_input_devices() -> list[InputDevice]:
    devices = sd.query_devices()
    result = []
    for i, d in enumerate(devices):
        if d.get("max_input_channels", 0) > 0:
            result.append(InputDevice(index=i, name=d["name"], default_samplerate=d["default_samplerate"]))
    return result


def default_input_device() -> InputDevice | None:
    try:
        idx = sd.default.device[0]
        if idx is None or idx < 0:
            return None
        d = sd.query_devices(idx)
        return InputDevice(index=idx, name=d["name"], default_samplerate=d["default_samplerate"])
    except Exception:
        return None
