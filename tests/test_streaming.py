import queue
import wave
from unittest.mock import MagicMock

import numpy as np

from flowstate.audio.recorder import Recorder
from flowstate.streaming import StreamingDictation


def write_audio(path, audio, rate=10):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(audio.astype(np.int16).tobytes())


class TimedEngine:
    def __init__(self, words):
        self.words = words

    def transcribe_words(self, path):
        with wave.open(str(path)) as wav:
            audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
            begin = float(audio[0]) / wav.getframerate()
            end = begin + len(audio) / wav.getframerate()
        return [(start - begin, stop - begin, text) for start, stop, text in self.words
                if begin <= (start + stop) / 2 < end]


def pipeline():
    result = MagicMock()
    result.run.side_effect = lambda raw, **kwargs: raw
    return result


def test_overlapping_windows_keep_boundary_words_exactly_once_and_final_tail(tmp_path):
    audio = np.arange(900, dtype=np.int16)
    words = [(float(i) - .3, float(i) + .3, f"word{i}") for i in range(1, 90)]
    engine = TimedEngine(words)
    stream = StreamingDictation(MagicMock(), engine, pipeline(), tmp_path)
    # Run completed live windows deterministically; the end is still processed
    # through finish(), including the word whose midpoint lies exactly at 8s.
    for cutoff in range(8, 89, 8):
        begin = max(0, stream._cursor - 1.5)
        end = cutoff + 2
        stream._process(audio[int(begin * 10):int(end * 10)], 10, begin, cutoff, budget=2)
    path = tmp_path / "audio.wav"
    write_audio(path, audio)
    stream._thread = MagicMock()
    segments, cleaned = stream.finish(path)
    assert cleaned.split() == [word for _, _, word in words]
    assert "word89" in cleaned
    assert "word8" in cleaned.split()
    assert segments[0][0] == .7
    assert not (tmp_path / "_live_window.wav").exists()


def test_failed_live_window_recovers_full_audio_not_partial_prefix(tmp_path):
    engine = MagicMock()
    engine.transcribe_segments.return_value = [(0, 90, "beginning middle final words")]
    stream = StreamingDictation(MagicMock(), engine, pipeline(), tmp_path)
    stream._thread = MagicMock()
    stream._segments = [(0, 8, "partial prefix")]
    stream._error = RuntimeError("GPU failed")
    path = tmp_path / "audio.wav"
    segments, cleaned = stream.finish(path)
    assert cleaned == "beginning middle final words"
    engine.transcribe_segments.assert_called_once_with(path)


def test_audio_snapshot_does_not_consume_or_change_full_recording(tmp_path):
    recorder = Recorder.__new__(Recorder)
    recorder._queue = queue.Queue()
    recorder._samplerate = 10
    recorder._stream = None
    original = np.arange(100, dtype=np.int16).reshape(-1, 1)
    for chunk in np.array_split(original, 5):
        recorder._queue.put(chunk)
    window, rate = recorder.snapshot_audio(1.5, 7.5)
    assert rate == 10
    np.testing.assert_array_equal(window, original[15:75])
    assert recorder._queue.qsize() == 5
    path = tmp_path / "audio.wav"
    recorder.stop_and_save(path)
    with wave.open(str(path)) as wav:
        assert wav.readframes(wav.getnframes()) == original.tobytes()


def test_short_audio_gets_whole_message_budget_without_model_loading(tmp_path):
    stream = StreamingDictation(MagicMock(), TimedEngine([(0.2, 0.5, "hello")]), pipeline(), tmp_path)
    stream._thread = MagicMock()
    path = tmp_path / "audio.wav"
    write_audio(path, np.arange(30, dtype=np.int16))
    _, result = stream.finish(path)
    assert result == "hello"
    stream._pipeline.run.assert_called_once_with("hello", budget_seconds=2.0, allow_load=False, cancel_event=None)


def test_final_word_aligned_past_file_end_is_not_cut_off(tmp_path):
    engine = MagicMock()
    engine.transcribe_words.return_value = [(2.9, 3.2, "essential-ending")]
    stream = StreamingDictation(MagicMock(), engine, pipeline(), tmp_path)
    stream._thread = MagicMock()
    path = tmp_path / "audio.wav"
    write_audio(path, np.arange(30, dtype=np.int16))
    _, result = stream.finish(path)
    assert result == "essential-ending"
