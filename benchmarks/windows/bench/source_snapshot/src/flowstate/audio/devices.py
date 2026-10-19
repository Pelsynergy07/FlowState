"""Microphone enumeration.

Scoped to WASAPI only: PortAudio on Windows enumerates the same physical
microphone once per audio host API it's reachable through (MME,
DirectSound, WASAPI, WDM-KS), so an unfiltered sd.query_devices() can
list a dozen-plus entries for one or two real microphones -- confusing
in Settings, and worse, means "system default" is ambiguous across those
duplicate host APIs and can resolve to one that doesn't actually work.
WASAPI is the modern Windows audio API and has exactly one entry per
physical device, so filtering to it gives a clean list and a default
that's actually consistent with what's shown.
"""

from __future__ import annotations

from dataclasses import dataclass

import sounddevice as sd


@dataclass(frozen=True)
class InputDevice:
    index: int
    name: str
    default_samplerate: float


def _wasapi_index() -> int | None:
    try:
        for i, api in enumerate(sd.query_hostapis()):
            if "wasapi" in api["name"].lower():
                return i
    except Exception:
        pass
    return None


def list_input_devices() -> list[InputDevice]:
    devices = sd.query_devices()
    wasapi = _wasapi_index()
    result = []
    for i, d in enumerate(devices):
        if d.get("max_input_channels", 0) <= 0:
            continue
        if wasapi is not None and d.get("hostapi") != wasapi:
            continue
        result.append(InputDevice(index=i, name=d["name"], default_samplerate=d["default_samplerate"]))
    return result


def default_input_device() -> InputDevice | None:
    """The system default input device, resolved through WASAPI
    specifically -- PortAudio's own cross-host-API "default" can pick a
    different host API than list_input_devices() shows, landing on a
    device the user never actually sees or chose."""
    wasapi = _wasapi_index()
    try:
        if wasapi is not None:
            idx = sd.query_hostapis(wasapi)["default_input_device"]
        else:
            idx = sd.default.device[0]
        if idx is None or idx < 0:
            return None
        d = sd.query_devices(idx)
        return InputDevice(index=idx, name=d["name"], default_samplerate=d["default_samplerate"])
    except Exception:
        return None
