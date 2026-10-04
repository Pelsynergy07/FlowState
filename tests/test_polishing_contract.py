import re
from unittest.mock import patch, MagicMock
from datetime import datetime
from pathlib import Path

from flowstate.text.pipeline import CleanupPipeline
from flowstate.text.formatter import SmartFormatter, _complete_rewrite
from flowstate.text.disfluency import clean_disfluencies
from flowstate.text.dates import format_dates
from flowstate.streaming import _join_sections
from flowstate.streaming import StreamingDictation
import wave
from flowstate.text.structure import structure_text

AUDIT = (
    "All right, so here's what I want to check right now:\n\n"
    "There are several real issues from the audit of the five pages on desktop and mobile app. "
    "and I have tested it across custom JSON plan and saved the full audit report. Here are a list of.\n"
    "the biggest findings first the weekly dates are wrong October 4th shows September 21 to 27 in your time zone "
    "next one is that sync can falsely say synced and and and basically overlapping requests can overwrite newer Edits "
    "numeric habits record 60 automatically regardless of whether you're tracking minutes, pages, or repetitions.\n\n"
    "Next, one is that monthly targets are incorrect, and October expects about 35 completions despite having 31 days.\n\n"
    "Next, one is that deleting a North Star.\n"
    "leaves broken links and one month creation from lack of one month option "
    "next one is that editing a past day i mean i mean sort of sort of like opens today "
    "while saved weekly monthly reflections aren't accessible from progress mobile tracking Controls "
    "are too small and lack keyboard accessibility support."
)


def fast_pipeline():
    return CleanupPipeline(SmartFormatter(), vocabulary_enabled=False)


def assert_audit_layout(result):
    assert len(re.findall(r"(?m)^- ", result)) == 5
    assert not re.search(r"next[,\s]+one|i mean|sort of|and and|basically", result, re.IGNORECASE)
    assert "October 4 shows September 21–27" in result
    for content in ("60", "35 completions", "31 days", "custom JSON plan", "North Star", "keyboard accessibility support",
                    "one month creation from lack of one month option"):
        assert content in result
    assert _complete_rewrite(AUDIT, result)
    assert "North Star.\n" not in result


def test_actual_audit_becomes_bullets_without_model_or_paraphrasing():
    assert_audit_layout(fast_pipeline().run(AUDIT, allow_load=False))


def test_repetitions_dates_and_emphasis_have_different_meanings():
    assert clean_disfluencies("um I I checked and and and tested basically all pages") == "I checked and tested all pages"
    assert clean_disfluencies("It is very very slow. No no, not 60 60 pages.") == "It is very very slow. No no, not 60 60 pages."
    assert clean_disfluencies('Keep "and and and" and `um um` literally.') == 'Keep "and and and" and `um um` literally.'
    assert clean_disfluencies("pages I mean minutes") == "pages I mean minutes"
    assert clean_disfluencies("it had had an error that that fix addressed") == "it had had an error that that fix addressed"


def test_dates_keep_values_years_and_ambiguous_numeric_dates():
    assert format_dates("October 4th shows September 21 to 27") == "October 4 shows September 21–27"
    assert format_dates("October twenty first 2026") == "October 21, 2026"
    assert format_dates("October thirty first") == "October 31"
    assert format_dates("03/04, 60 pages and September 32") == "03/04, 60 pages and September 32"
    assert format_dates("September 27 to 21") == "September 27 to 21"


def test_no_synonyms_pronoun_changes_or_reordering_are_allowed():
    assert not _complete_rewrite("we checked the app", "We verified the app.")
    assert not _complete_rewrite("we checked the app", "They checked the app.")
    assert not _complete_rewrite("sync can fail", "Sync cannot fail.")
    assert not _complete_rewrite("it was ready", "It is ready.")
    source = " ".join(f"word{i}" for i in range(100))
    assert not _complete_rewrite(source, source.replace("word20 word21", "word21 word20"))
    assert not _complete_rewrite("60. All tests passed", "All tests passed")


def test_next_one_is_not_a_marker_in_ordinary_single_use():
    source = "This model works, the next one is that new version."
    assert structure_text(source) == source


def test_explicit_numbering_with_next_one_stays_numbered():
    assert structure_text("Tasks: number one review the budget next one is email John next one is deploy") == (
        "Tasks:\n\n1. review the budget\n2. email John\n3. deploy"
    )


def test_disfluencies_and_next_markers_across_live_boundaries():
    pipeline = fast_pipeline()
    words = AUDIT.split()
    for size in (17, 29, 47):
        sections = [pipeline.run(" ".join(words[i:i + size]), allow_load=False)
                    for i in range(0, len(words), size)]
        joined = _join_sections(sections)
        result = structure_text(format_dates(clean_disfluencies(joined)))
        assert_audit_layout(result)


def test_formatted_audit_reaches_actual_paste_and_saved_transcript(tmp_path):
    from flowstate.app import RecordingController
    from flowstate.session.model import Session
    controller = RecordingController.__new__(RecordingController)
    controller.signals = MagicMock()
    controller._hotkeys = MagicMock()
    controller._asr = MagicMock()
    controller._asr.transcribe_segments.return_value = [(0, 90, AUDIT)]
    controller._pipeline = fast_pipeline()
    session = Session("audit", datetime.now(), tmp_path)
    with patch.object(controller._pipeline._formatter, "correct", side_effect=lambda text, **kwargs: text), \
         patch("flowstate.app.paste_transcript") as paste:
        controller._process_recording(Path("audio.wav"), session, None, [], [])
    result = paste.call_args.args[0]
    assert_audit_layout(result)
    assert session.transcript_path.read_text(encoding="utf-8") == result
    assert (tmp_path / "raw_transcript.txt").read_text(encoding="utf-8") == AUDIT


def test_disabled_polishing_keeps_fillers_dates_and_markers():
    pipeline = fast_pipeline()
    pipeline.grammar_enabled = False
    assert pipeline.run(AUDIT, allow_load=False) == AUDIT


def test_disabled_polishing_is_respected_by_actual_paste_path(tmp_path):
    from flowstate.app import RecordingController
    from flowstate.session.model import Session
    controller = RecordingController.__new__(RecordingController)
    controller.signals = MagicMock()
    controller._hotkeys = MagicMock()
    controller._asr = MagicMock()
    controller._asr.transcribe_segments.return_value = [(0, 90, AUDIT)]
    controller._pipeline = fast_pipeline()
    controller._pipeline.grammar_enabled = False
    session = Session("unformatted", datetime.now(), tmp_path)
    with patch("flowstate.app.paste_transcript") as paste:
        controller._process_recording(Path("audio.wav"), session, None, [], [])
    assert paste.call_args.args[0] == AUDIT


def test_global_validation_restores_words_lost_in_a_live_section(tmp_path):
    source = 'Keep "and and and" literally and all 60 pages.'
    stream = StreamingDictation(None, MagicMock(), fast_pipeline(), tmp_path)
    stream._thread = MagicMock()
    stream._segments = [(0, 3, source)]
    stream._cleaned = ['Keep "and" literally and all pages.']
    stream._cursor = 3
    path = tmp_path / 'audio.wav'
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(10)
        wav.writeframes(b'\x00' * 60)
    _, result = stream.finish(path)
    assert result == source
