import json
import threading
import time

import pytest
import requests

from nemo.ai.ollama_client import GenerationCancelled, ModelError, OllamaClient


class FakeResponse:
    def __init__(self, chunks):
        self.chunks = chunks
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self.closed = True

    def raise_for_status(self):
        pass

    def iter_lines(self, chunk_size=1):
        for chunk in self.chunks:
            yield json.dumps(chunk).encode()


def test_streams_answer_tokens_and_ignores_thinking(monkeypatch):
    response = FakeResponse([{"thinking": "private internal text"}, {"response": "Hello "}, {"response": "world"}, {"done": True}])
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: response)
    tokens = []
    assert OllamaClient("http://localhost", "test").answer("Question", on_token=tokens.append) == "Hello world"
    assert tokens == ["Hello ", "world"]
    assert response.closed


def test_cancel_returns_promptly_while_transport_is_waiting(monkeypatch):
    waiting = threading.Event()
    release = threading.Event()
    def post(*args, **kwargs):
        waiting.set()
        release.wait(5)
        return FakeResponse([{"done": True}])
    monkeypatch.setattr(requests, "post", post)
    cancel = threading.Event()
    def stop():
        waiting.wait(2)
        cancel.set()
    threading.Thread(target=stop, daemon=True).start()
    start = time.monotonic()
    try:
        with pytest.raises(GenerationCancelled):
            OllamaClient("http://localhost", "test").answer("Question", cancel_event=cancel)
        assert time.monotonic() - start < 1
    finally:
        release.set()


def test_connection_error_has_recovery_guidance(monkeypatch):
    def post(*args, **kwargs):
        raise requests.ConnectionError("offline")
    monkeypatch.setattr(requests, "post", post)
    with pytest.raises(ModelError, match="Open Ollama"):
        OllamaClient("http://localhost", "test").answer("Question")


def test_interrupted_stream_is_an_error_not_a_completed_answer(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: FakeResponse([{"response": "Partial"}]))
    with pytest.raises(ModelError) as caught:
        OllamaClient("http://localhost", "test").answer("Question")
    assert caught.value.partial == "Partial"


def test_embedding_transport_uses_the_selected_model_and_all_inputs(monkeypatch):
    calls = []
    response = FakeResponse([])
    response.json = lambda: {"embeddings": [[1.0, 0.0], [0.0, 1.0]]}
    def post(url, **kwargs):
        calls.append((url, kwargs["json"]))
        return response
    monkeypatch.setattr(requests, "post", post)
    ai = OllamaClient("http://localhost", "chat-model", embedding_model="embedding-model")
    assert ai.embed(["first", "second"]) == [[1.0, 0.0], [0.0, 1.0]]
    assert calls[0] == ("http://localhost/api/embed", {"model": "embedding-model", "input": ["first", "second"]})


def test_embedding_model_is_never_downloaded_or_chosen_implicitly():
    with pytest.raises(ModelError, match="No embedding model"):
        OllamaClient("http://localhost", "chat-model").embed(["input"])
