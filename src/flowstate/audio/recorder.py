"""Microphone recording into a mono WAV file via a ring-buffer queue.

Requests 16 kHz directly from the device (Windows' shared-mode audio
engine transparently resamples in the vast majority of cases). If a
device refuses that rate, we fall back to its native rate -- correctness
is preserved either way, because the ASR engine decodes WAV files through
PyAV, which resamples to whatever it needs regardless of the file's rate.
"""

from __future__ import annotations

import logging
import math
import queue
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

logger = logging.getLogger("flowstate.audio")

TARGET_SAMPLERATE = 16000
CHANNELS = 1
DTYPE = "int16"


class Recorder:
    def __init__(self, device_index: int | None = None):
        self._device_index = device_index
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stream: sd.InputStream | None = None
        self._samplerate = TARGET_SAMPLERATE

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            logger.debug("Audio input status: %s", status)
        self._queue.put(indata.copy())

    def start(self) -> None:
        self._queue = queue.Queue()
        try:
            self._stream = sd.InputStream(
                device=self._device_index,
                samplerate=TARGET_SAMPLERATE,
                channels=CHANNELS,
                dtype=DTYPE,
                callback=self._callback,
            )
            self._samplerate = TARGET_SAMPLERATE
            self._stream.start()
        except Exception:
            logger.warning("16kHz capture unsupported by this device; using its default rate", exc_info=True)
            device_index = self._device_index if self._device_index is not None else sd.default.device[0]
            device_info = sd.query_devices(device_index)
            fallback_rate = int(device_info["default_samplerate"])
            self._stream = sd.InputStream(
                device=self._device_index,
                samplerate=fallback_rate,
                channels=CHANNELS,
                dtype=DTYPE,
                callback=self._callback,
            )
            self._samplerate = fallback_rate
            self._stream.start()

    def stop_and_save(self, wav_path: Path) -> Path:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        chunks = []
        while not self._queue.empty():
            chunks.append(self._queue.get_nowait())

        audio = np.concatenate(chunks, axis=0) if chunks else np.zeros((0, CHANNELS), dtype=np.int16)

        wav_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # int16
            wf.setframerate(self._samplerate)
            wf.writeframes(audio.tobytes())

        return wav_path

    def level(self) -> float:
        """Approximate current input level (0..1), for the HUD meter.
        Best-effort peek at the tail of the queue without draining it.

        Uses perceptual (dB) scaling, not linear: normal speaking volume
        sits nowhere near full-scale amplitude, so a linear 0..32768 map
        made the meter look almost static during real speech (bars barely
        cleared their minimum-height floor) while looking lively during
        the fake processing animation. -45dBFS..-3dBFS covers quiet to
        fairly loud speech and maps it across the full 0..1 range.
        """
        try:
            latest = list(self._queue.queue)[-1]
        except IndexError:
            return 0.0
        if latest.size == 0:
            return 0.0
        peak = float(np.abs(latest).max())
        if peak <= 1.0:
            return 0.0
        db = 20 * math.log10(peak / 32768.0)
        floor_db, ceiling_db = -45.0, -3.0
        return max(0.0, min(1.0, (db - floor_db) / (ceiling_db - floor_db)))
