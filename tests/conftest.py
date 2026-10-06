import pytest


class FakeBackend:
    """Stands in for the GPU/CPU formatter runtimes: streams a scripted reply."""

    runtime = "test"

    def __init__(self, reply=None):
        self.reply = reply or (lambda source: source)
        self.calls = []

    def count_tokens(self, text):
        return len(text.split())

    def stream(self, messages, max_tokens):
        source = messages[-1]["content"]
        self.calls.append(source)
        reply = self.reply(source)
        if isinstance(reply, Exception):
            raise reply
        yield from (reply if isinstance(reply, list) else [reply])


@pytest.fixture(autouse=True)
def no_real_formatter_models(monkeypatch):
    """Tests never load or download a real formatter model, even on a
    machine that has one cached."""
    from flowstate.text import llm

    monkeypatch.setattr(llm, "is_cached", lambda model: False)
    monkeypatch.setattr(llm, "ensure_downloaded", lambda model: False)
    monkeypatch.setattr(llm, "cuda_device_available", lambda: False)
