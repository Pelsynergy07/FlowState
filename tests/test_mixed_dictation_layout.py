import re
import wave
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from flowstate.text.formatter import SmartFormatter
from flowstate.text.guard import preserves_words
from flowstate.text.pipeline import apply_rules


def _complete_rewrite(original, result):
    """The result keeps every dictated word (allowing formatting edits)."""
    return preserves_words(apply_rules(original), result)
from flowstate.text.pipeline import CleanupPipeline
from flowstate.text.structure import structure_text
from flowstate.streaming import StreamingDictation


TRANSCRIPT = """I have published version 1.0.4 beta. and removed the older release. also couple things for you to keep in mind:

1. I have fixed the Qt core startup crash.
2. I have upgraded your installed application and preserved all the 24 cached model. files and settings so there is no need to re -download the model.
3. that I have passed all the 212 regression tests and verified the update detection as well and last point is that local analytics is available under the settings part now inside the stats option so yeah and I have added like a post hoc dashboard that will still need my project API but that's about it

I wanted to write this email to you so let me know if this email sounds good hey Johnson hope you're doing great please find attached the file that you are looking to download I have included and made all the corrections and then attach this file thanks regards PranavShopping list to buy tomatoes, onions, garlic, chillies, potatoes, carrots, beetroots."""


def assert_layout(result):
    assert "Hey Johnson,\n\nHope you're doing great.\n\nPlease find attached" in result
    assert "\n\nThanks\nRegards,\nPranav\n\nShopping list to buy:" in result
    assert re.findall(r"(?m)^- (.+)$", result) == [
        "Tomatoes", "Onions", "Garlic", "Chillies", "Potatoes", "Carrots", "Beetroots."]
    assert len(re.findall(r"(?m)^\d+\. ", result)) == 3
    assert _complete_rewrite(TRANSCRIPT, result)
    assert structure_text(result) == result


def test_exact_mixed_dictation_formats_without_model():
    pipeline = CleanupPipeline(SmartFormatter(), vocabulary_enabled=False)
    assert_layout(pipeline.run(TRANSCRIPT, allow_load=False))


def test_mixed_layout_across_streaming_sections(tmp_path):
    pipeline = CleanupPipeline(SmartFormatter(), vocabulary_enabled=False)
    words = TRANSCRIPT.split()
    for size in (17, 29, 47):
        parts = [pipeline.run(" ".join(words[i:i + size]), allow_load=False)
                 for i in range(0, len(words), size)]
        stream = StreamingDictation(None, MagicMock(), pipeline, tmp_path)
        stream._thread = MagicMock()
        stream._segments = [(0, 3, TRANSCRIPT)]
        stream._cleaned = parts
        stream._cursor = 3
        path = tmp_path / 'audio.wav'
        with wave.open(str(path), 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(10)
            wav.writeframes(b'\x00' * 60)
        _, result = stream.finish(path)
        assert_layout(result)


def test_named_inventory_does_not_split_ordinary_prose():
    for text in ("I bought tomatoes, onions, garlic.",
                 'Shopping list: "tomatoes, onions", garlic.',
                 "Shopping list: tomatoes, then I went to the shop and bought garlic."):
        assert structure_text(text) == text


def test_email_after_intro_keeps_all_words_and_separates_greeting():
    source = "Here is my email. hey Johnson hope you're doing great thanks regards Pranav"
    result = structure_text(source)
    assert result == "Here is my email.\n\nHey Johnson,\n\nHope you're doing great\n\nThanks\nRegards,\nPranav"
    assert _complete_rewrite(source, result)


def test_email_and_shopping_recorded_independently():
    pipeline = CleanupPipeline(SmartFormatter(), vocabulary_enabled=False)
    email = TRANSCRIPT[TRANSCRIPT.index('I wanted to write'):TRANSCRIPT.index('Shopping list')]
    result = pipeline.run(email, allow_load=False)
    assert "Hey Johnson,\n\nHope you're doing great.\n\nPlease find attached" in result
    assert result.endswith("Thanks\nRegards,\nPranav")
    assert _complete_rewrite(email, result)
    shopping = TRANSCRIPT[TRANSCRIPT.index('Shopping list'):]
    assert len(re.findall(r'(?m)^- ', pipeline.run(shopping, allow_load=False))) == 7


def test_mixed_layout_reaches_actual_paste_and_history(tmp_path):
    from flowstate.app import RecordingController
    from flowstate.session.model import Session

    controller = RecordingController.__new__(RecordingController)
    controller.signals = MagicMock()
    controller._hotkeys = MagicMock()
    controller._asr = MagicMock()
    controller._asr.transcribe_segments.return_value = [(0, 90, TRANSCRIPT)]
    controller._pipeline = CleanupPipeline(SmartFormatter(), vocabulary_enabled=False)
    session = Session('mixed-layout', datetime.now(), tmp_path)
    with patch.object(controller._pipeline._formatter, 'correct', side_effect=lambda text, **kwargs: text), \
         patch('flowstate.app.paste_transcript') as paste:
        controller._process_recording(Path('audio.wav'), session, None, [], [])
    result = paste.call_args.args[0]
    assert_layout(result)
    assert session.transcript_path.read_text(encoding='utf-8') == result


def test_subject_email_and_inventory_are_independent_sections():
    source = 'subject budget update dear John please review this thanks Pranav Shopping list: milk, eggs, bread'
    result = structure_text(source)
    assert result.startswith('Subject: budget update\n\nDear John,\n\nPlease review this')
    assert '\n\nThanks,\nPranav\n\nShopping list:\n\n- Milk\n- Eggs\n- Bread' in result
    assert structure_text(result) == result
    assert _complete_rewrite(source, result)
