from unittest.mock import patch

from flowstate.audio.devices import default_input_device, list_input_devices

_HOSTAPIS = [
    {"name": "MME"},
    {"name": "Windows DirectSound"},
    {"name": "Windows WASAPI", "default_input_device": 5},
    {"name": "Windows WDM-KS"},
]

# One real microphone, duplicated across all four host APIs like PortAudio
# actually does on Windows -- plus one WASAPI-only device to prove the
# filter isn't just "keep the first occurrence of each name".
_RAW_DEVICES = [
    {"name": "Microphone Array (Realtek)", "max_input_channels": 2, "hostapi": 0, "default_samplerate": 48000.0},
    {"name": "Microphone Array (Realtek)", "max_input_channels": 2, "hostapi": 1, "default_samplerate": 48000.0},
    {"name": "Microphone Array (Realtek)", "max_input_channels": 2, "hostapi": 2, "default_samplerate": 48000.0},
    {"name": "Microphone Array (Realtek)", "max_input_channels": 2, "hostapi": 3, "default_samplerate": 48000.0},
    {"name": "Headset Mic (Bluetooth)", "max_input_channels": 1, "hostapi": 2, "default_samplerate": 16000.0},
    {"name": "Some Output Device", "max_input_channels": 0, "hostapi": 2, "default_samplerate": 48000.0},
]


def test_list_input_devices_collapses_duplicates_across_host_apis():
    """Regression test for a real bug: an unfiltered device list showed
    the same physical microphone once per Windows audio host API
    (MME/DirectSound/WASAPI/WDM-KS) -- a laptop with one or two real
    mics displayed as roughly twenty entries in Settings."""
    with patch("flowstate.audio.devices.sd.query_devices", return_value=_RAW_DEVICES):
        with patch("flowstate.audio.devices.sd.query_hostapis", return_value=_HOSTAPIS):
            devices = list_input_devices()

    names = [d.name for d in devices]
    assert names == ["Microphone Array (Realtek)", "Headset Mic (Bluetooth)"]


def test_list_input_devices_excludes_output_only_entries():
    with patch("flowstate.audio.devices.sd.query_devices", return_value=_RAW_DEVICES):
        with patch("flowstate.audio.devices.sd.query_hostapis", return_value=_HOSTAPIS):
            devices = list_input_devices()

    assert all(d.name != "Some Output Device" for d in devices)


def test_default_input_device_resolves_through_wasapi():
    wasapi_default = {"name": "Microphone Array (Realtek)", "max_input_channels": 2, "default_samplerate": 48000.0}
    with patch("flowstate.audio.devices.sd.query_hostapis", side_effect=lambda i=None: _HOSTAPIS if i is None else _HOSTAPIS[i]):
        with patch("flowstate.audio.devices.sd.query_devices", return_value=wasapi_default):
            result = default_input_device()

    assert result is not None
    assert result.index == 5
    assert result.name == "Microphone Array (Realtek)"


def test_default_input_device_returns_none_when_nothing_resolves():
    """When WASAPI can't be found at all, falls back to PortAudio's own
    sd.default.device -- and if that's also unset (-1, the PortAudio
    sentinel for "none"), there's genuinely no default to report."""
    with patch("flowstate.audio.devices.sd.query_hostapis", side_effect=Exception("no audio subsystem")):
        with patch("flowstate.audio.devices.sd.default") as mock_default:
            mock_default.device = (-1, -1)
            assert default_input_device() is None
