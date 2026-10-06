import threading

from flowstate.text import formatter as module
from flowstate.text.formatter import SmartFormatter, join_sections
from tests.conftest import FakeBackend


def fake_formatter(reply=None):
    formatter = SmartFormatter()
    formatter._backend = FakeBackend(reply)
    return formatter


def test_long_dictation_preserves_every_section_and_final_sentence(monkeypatch):
    monkeypatch.setattr(module, "CHUNK_TOKENS", 60)
    formatter = fake_formatter()
    text = " ".join(f"Sentence {i} describes unique item {i}." for i in range(100))
    result = formatter.correct(text, budget_seconds=30)
    assert len(formatter._backend.calls) > 1
    assert " ".join(result.split()) == text
    assert result.endswith("unique item 99.")
    # Chunks split mid-paragraph must not gain paragraph breaks.
    assert "\n" not in result


def test_model_punctuation_and_layout_are_kept():
    formatter = fake_formatter(lambda s: "Hey John,\n\nCan we talk tomorrow?\n\nThanks,\nSarah")
    assert formatter.correct("Hey john can we talk tomorrow thanks sarah") == (
        "Hey John,\n\nCan we talk tomorrow?\n\nThanks,\nSarah")


def test_paraphrase_is_reverted_but_layout_kept():
    formatter = fake_formatter(lambda s: "Dear John,\n\nCan we talk tomorrow, please?\n\nThanks,\nPranav")
    result = formatter.correct("Dear John can we talk tomorrow thanks Pranav")
    assert result == "Dear John,\n\nCan we talk tomorrow?\n\nThanks,\nPranav"


def test_summary_or_answer_keeps_the_source():
    source = "Review all 300 pages then email John and deploy at 4 pm"
    assert fake_formatter(lambda s: "Finish the tasks.").correct(source) == source
    answer = "Sure, I can make the changes. Can you provide the details?"
    assert fake_formatter(lambda s: answer).correct("make the changes in the mobile app as well") == (
        "make the changes in the mobile app as well")


def test_failure_in_one_chunk_keeps_that_chunk_and_continues(monkeypatch):
    monkeypatch.setattr(module, "CHUNK_TOKENS", 3)
    formatter = fake_formatter(lambda s: RuntimeError("model failed"))
    text = "alpha beta gamma delta epsilon zeta eta theta"
    assert " ".join(formatter.correct(text).split()) == text


def test_expired_budget_preserves_all_remaining_text():
    formatter = fake_formatter()
    text = "speech " * 700 + "the last words"
    assert " ".join(formatter.correct(text, budget_seconds=0).split()) == " ".join(text.split())
    assert formatter._backend.calls == []


def test_deadline_keeps_finished_sentences_and_complete_source():
    class StopAfterTwoPieces:
        """A stop arriving mid-generation, after the first sentence."""
        checks = 0

        def is_set(self):
            StopAfterTwoPieces.checks += 1
            return StopAfterTwoPieces.checks > 3

    formatter = fake_formatter(lambda s: ["First sentence here. ", "Second sentence is ", "here, and more."])
    source = "First sentence here second sentence is here and more"
    result = formatter.correct(source, cancel_event=StopAfterTwoPieces())
    assert result.startswith("First sentence here. ")
    assert " ".join(result.replace(".", "").split()).casefold() == source.casefold()


def test_non_english_and_whitespace_survive_chunking(monkeypatch):
    formatter = fake_formatter()
    monkeypatch.setattr(module, "CHUNK_TOKENS", 2)
    text = "नमस्ते दुनिया। This is speech. 最后的句子。"
    assert " ".join(formatter._split_chunks(text)) == text


def test_busy_formatter_does_not_block_or_drop_text():
    formatter = fake_formatter()
    formatter._inference_lock.acquire()
    try:
        assert formatter.correct("complete original speech") == "complete original speech"
        assert formatter._backend.calls == []
    finally:
        formatter._inference_lock.release()


def test_cancelled_generation_is_closed_and_lock_released():
    event = threading.Event()
    formatter = fake_formatter(lambda s: ["Partial ", "rewrite"])
    event.set()
    source = "all original words must remain here"
    assert formatter.correct(source, cancel_event=event) == source
    assert formatter._inference_lock.acquire(blocking=False)
    formatter._inference_lock.release()


def test_section_seams_keep_case_and_have_no_added_full_stop():
    formatter = fake_formatter(lambda s: "To the point where it works.")
    assert formatter.correct("to the point where it works") == "to the point where it works"


def test_join_capitalizes_only_new_sentences():
    assert join_sections(["We met.", "then left"]) == "We met. Then left"
    assert join_sections(["We met and", "then left"]) == "We met and then left"
    assert join_sections(["iPhone works."]) == "iPhone works."
    assert join_sections(["lower start"], capitalize_first=False) == "lower start"


def test_no_model_returns_input_without_download(monkeypatch):
    formatter = SmartFormatter()
    monkeypatch.setattr(SmartFormatter, "is_model_cached", staticmethod(lambda: False))
    assert formatter.correct("this is raw transcript") == "this is raw transcript"
    assert not formatter.is_ready
