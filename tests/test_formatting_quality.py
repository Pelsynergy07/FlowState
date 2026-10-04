from unittest.mock import MagicMock, patch
from datetime import datetime
from pathlib import Path
import re

from flowstate.text.pipeline import CleanupPipeline
from flowstate.text.formatter import SmartFormatter
from flowstate.streaming import _join_sections
from flowstate.text.structure import structure_text
from flowstate.text.dates import format_dates


DICTATED_CHECKS = (
    "The desktop preview now shows the correct week. September 28th, October 4th. "
    "The numeric habits accept the value entered rather than recording 60. "
    "All 16 regression tests pass, including the tests for stale cloud responses and edits made "
    "while a sync request is in flight. I am checking the remaining. desktop editing flows before "
    "publishing the changes. There are couple of things that we need to check here. "
    "First one, verify desktop manual setup is available. "
    "Second, open a complete plan in the desktop importer. "
    "Third, verify whether the importer desktop plan and habit controls are accurate. "
    "4. Verify actual numeric habit entry and fifth confirm the saved numeric tracking and corrected weekly progress"
)


def fallback_pipeline():
    formatter = SmartFormatter()
    return CleanupPipeline(formatter=formatter, vocabulary_enabled=False)


def test_unavailable_model_still_formats_email_and_bullets():
    pipeline = fallback_pipeline()
    result = pipeline.run("dear John I attached the report thanks Pranav", allow_load=False)
    assert result == "Dear John,\n\nI attached the report\n\nThanks\nPranav"
    result = pipeline.run("Tasks: bullet point review 300 pages next bullet email John", allow_load=False)
    assert result == "Tasks:\n\n- review 300 pages\n- email John"


def test_layout_cues_are_normalized_before_model_content_validation():
    formatter = SmartFormatter()
    formatter._llm = MagicMock()
    formatter._llm.tokenize.side_effect = lambda data, **kwargs: data.split()
    formatter._llm.create_chat_completion.return_value = iter([
        {"choices": [{"delta": {"content": "Tasks:\n\n- Review all 300 pages\n- Email John"}, "finish_reason": "stop"}]}
    ])
    result = CleanupPipeline(formatter, vocabulary_enabled=False).run(
        "Tasks: bullet point review all 300 pages next bullet email John"
    )
    assert result == "Tasks:\n\n- Review all 300 pages\n- Email John"


def test_live_join_preserves_separate_list_items():
    assert _join_sections(["Tasks:\n\n- review budget\n- email John", "- deploy at 4 pm"]) == (
        "Tasks:\n\n- review budget\n- email John\n- deploy at 4 pm"
    )


def test_live_join_keeps_a_split_list_item_on_one_line():
    assert _join_sections(["Tasks:\n1. Verify actual numeric habit", "entry\n2. confirm saved tracking"]) == (
        "Tasks:\n1. Verify actual numeric habit entry\n2. confirm saved tracking"
    )


def test_single_tail_bullet_gets_layout_even_when_polishing_is_cancelled():
    result = fallback_pipeline().run("next bullet deploy at 4 pm", allow_load=False)
    assert result == "- deploy at 4 pm"


def test_model_cannot_change_dictated_bullets_to_numbered_steps():
    formatter = SmartFormatter()
    formatter._llm = MagicMock()
    formatter._llm.tokenize.side_effect = lambda data, **kwargs: data.split()
    formatter._llm.create_chat_completion.return_value = iter([
        {"choices": [{"delta": {"content": "1. Review the budget\n2. Email John"}, "finish_reason": "stop"}]}
    ])
    result = CleanupPipeline(formatter, vocabulary_enabled=False).run(
        "bullet point review the budget next bullet email John"
    )
    assert result == "- Review the budget\n- Email John"


def test_actual_dictated_checks_mix_ordinals_and_numeric_markers():
    result = fallback_pipeline().run(DICTATED_CHECKS, allow_load=False)
    intro = format_dates(DICTATED_CHECKS.split("First one,", 1)[0].strip())
    assert result == intro + (
        "\n\n1. verify desktop manual setup is available."
        "\n2. open a complete plan in the desktop importer."
        "\n3. verify whether the importer desktop plan and habit controls are accurate."
        "\n4. Verify actual numeric habit entry"
        "\n5. confirm the saved numeric tracking and corrected weekly progress"
    )
    assert "September 28, October 4" in result
    assert "recording 60" in result
    assert "All 16 regression tests" in result
    assert structure_text(result) == result


def test_dictated_checks_still_format_across_live_chunk_boundaries():
    words = DICTATED_CHECKS.split()
    pipeline = fallback_pipeline()
    for size in (17, 29, 47):
        sections = [pipeline.run(" ".join(words[i:i + size]), allow_load=False)
                    for i in range(0, len(words), size)]
        result = structure_text(_join_sections(sections))
        for number, phrase in enumerate(("verify desktop manual setup", "open a complete plan", "verify whether the importer",
                                         "Verify actual numeric habit entry", "confirm the saved numeric tracking"), 1):
            assert f"{number}. {phrase}" in result
        assert result.endswith("corrected weekly progress")


def test_ordinary_dates_and_ordinals_do_not_become_list_items():
    source = "We met on May first, June second, and July third. My first meeting starts at 4.30 pm."
    assert structure_text(source) == source


def test_numbered_checks_reach_saved_transcript_and_paste(tmp_path):
    from flowstate.app import RecordingController
    from flowstate.session.model import Session

    controller = RecordingController.__new__(RecordingController)
    controller.signals = MagicMock()
    controller._hotkeys = MagicMock()
    controller._asr = MagicMock()
    controller._asr.transcribe_segments.return_value = [(0, 90, DICTATED_CHECKS)]
    controller._pipeline = fallback_pipeline()
    session = Session("numbered-checks", datetime.now(), tmp_path)
    with patch.object(controller._pipeline._formatter, "correct", side_effect=lambda text, **kwargs: text), \
         patch("flowstate.app.paste_transcript") as paste:
        controller._process_recording(Path("audio.wav"), session, None, [], [])
    pasted = paste.call_args.args[0]
    assert re.findall(r"(?m)^(\d+)\. ", pasted) == ["1", "2", "3", "4", "5"]
    assert session.transcript_path.read_text(encoding="utf-8") == pasted
    assert (tmp_path / "raw_transcript.txt").read_text(encoding="utf-8") == DICTATED_CHECKS
    controller.signals.recording_finished.emit.assert_called_once_with(pasted)
