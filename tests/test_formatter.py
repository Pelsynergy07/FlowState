from unittest.mock import MagicMock

from flowstate.text import formatter as module
from flowstate.text.formatter import SmartFormatter, _complete_rewrite, _preserve_content


def fake_formatter():
    formatter = SmartFormatter()
    formatter._llm = MagicMock()
    formatter._llm.tokenize.side_effect = lambda text, **kwargs: list(text.split())
    return formatter


def test_long_dictation_preserves_every_section_and_final_sentence():
    formatter = fake_formatter()
    text = " ".join(f"Sentence {i} describes unique item {i}." for i in range(100))
    seen = []
    def completion(**kwargs):
        source = kwargs["messages"][-1]["content"].split("<<<\n", 1)[1].rsplit("\n>>>", 1)[0]
        seen.append(source)
        return iter([{"choices": [{"finish_reason": "stop", "delta": {"content": source.strip()}}]}])
    formatter._llm.create_chat_completion.side_effect = completion
    result = formatter.correct(text)
    assert len(seen) > 1
    assert " ".join(result.split()) == text
    assert result.endswith("unique item 99.")


def test_token_limit_keeps_complete_source():
    formatter = fake_formatter()
    source = "The beginning is here. The final sentence is essential."
    formatter._llm.create_chat_completion.return_value = iter([{
        "choices": [{"finish_reason": "length", "delta": {"content": "The beginning is here."}}]
    }])
    assert formatter.correct(source) == source


def test_model_summary_or_missing_middle_is_rejected():
    assert not _complete_rewrite("alpha beta crucial gamma delta", "Alpha beta gamma delta.")
    assert not _complete_rewrite("word " * 200 + "essential ending", "word " * 200)
    assert not _complete_rewrite("ship 123 units tomorrow", "Ship 12 units tomorrow.")
    assert _complete_rewrite("hello this is the full text", "Hello, this is the full text.")
    assert _complete_rewrite("number one milk number two eggs number three bread", "1. Milk\n2. Eggs\n3. Bread")
    assert not _complete_rewrite("buy one book and two pens", "Buy a book and pens.")
    assert not _complete_rewrite("dear John please review the report", "Dear John, please review the report. Thanks, Pranav.")


def test_failure_in_one_chunk_keeps_that_chunk_and_continues(monkeypatch):
    formatter = fake_formatter()
    monkeypatch.setattr(module, "CHUNK_TOKENS", 3)
    formatter._llm.create_chat_completion.side_effect = RuntimeError("model failed")
    text = "alpha beta gamma delta epsilon zeta eta theta"
    assert " ".join(formatter.correct(text).split()) == text


def test_expired_budget_preserves_all_remaining_text(monkeypatch):
    formatter = fake_formatter()
    monkeypatch.setattr(module, "POLISH_BUDGET_SECONDS", 0)
    text = "speech " * 700 + "the last words"
    assert " ".join(formatter.correct(text).split()) == " ".join(text.split())
    formatter._llm.create_chat_completion.assert_not_called()


def test_generation_deadline_discards_partial_output():
    formatter = fake_formatter()
    def completion(**kwargs):
        assert kwargs["stream"] is True
        return iter([{"choices": [{"finish_reason": "stop", "delta": {"content": "Only half"}}]}])
    formatter._llm.create_chat_completion.side_effect = completion
    assert formatter._correct_chunk("Only half and the rest", 0) == "Only half and the rest"


def test_non_english_and_whitespace_survive_chunking(monkeypatch):
    formatter = fake_formatter()
    monkeypatch.setattr(module, "CHUNK_TOKENS", 2)
    text = "  नमस्ते दुनिया।\n\nThis is speech.  最后的句子。  "
    assert "".join(formatter._split_chunks(text)) == text


def test_busy_formatter_does_not_block_or_drop_text():
    formatter = fake_formatter()
    formatter._inference_lock.acquire()
    try:
        assert formatter.correct("complete original speech") == "complete original speech"
        formatter._llm.create_chat_completion.assert_not_called()
    finally:
        formatter._inference_lock.release()


def test_stopping_recording_cancels_live_polishing_without_partial_output():
    import threading
    event = threading.Event()
    formatter = fake_formatter()
    closed = []
    def response(**kwargs):
        try:
            yield {"choices": [{"delta": {"content": "Partial "}, "finish_reason": None}]}
            event.set()
            yield {"choices": [{"delta": {"content": "rewrite"}, "finish_reason": "stop"}]}
        finally:
            closed.append(True)
    formatter._llm.create_chat_completion.side_effect = response
    source = "all original words must remain here"
    assert formatter.correct(source, cancel_event=event) == source
    assert closed == [True]
    assert formatter._inference_lock.acquire(blocking=False)
    formatter._inference_lock.release()


def test_small_invented_politeness_does_not_discard_email_layout():
    source = "dear John can we talk tomorrow thanks Pranav"
    formatted = "Dear John,\n\nCan we talk tomorrow, please?\n\nThanks, Pranav"
    result = _preserve_content(source, formatted)
    assert "\n\n" in result
    assert "please" not in result
    assert _complete_rewrite(source, result)


def test_missing_content_is_restored_without_discarding_list_layout():
    source = "Buy 12 fresh eggs and two books then call John"
    formatted = "- Buy 12 eggs and two books\n- Then call John"
    result = _preserve_content(source, formatted)
    assert "fresh" in result
    assert "\n- " in result
    assert _complete_rewrite(source, result)


def test_summary_is_not_repaired_into_an_unrelated_layout():
    source = "Review all 300 pages then email John and deploy at 4 pm"
    assert _preserve_content(source, "Finish the tasks.") == source
