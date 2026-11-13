import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import rag
from app.storage import memory_store


def _chunk(text):
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text))])


class FakeCompletions:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def create(self, model, temperature, max_tokens, messages, stream=False):
        self.calls.append({"messages": messages, "stream": stream})
        if self.fail:
            raise RuntimeError("model unavailable")
        if stream:
            return iter([_chunk("Agents keep a memory store "), _chunk(None), _chunk("[S1].")])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Draft answer [S1]."))])


@pytest.fixture
def fake_groq(monkeypatch):
    completions = FakeCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    monkeypatch.setattr(rag, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(rag, "_groq_client", lambda: client)
    memory_store.clear_memory()
    yield completions
    memory_store.clear_memory()


def _seed(session_id):
    # BM25 needs a few different passages: with one passage every word scores zero.
    texts = [
        ("Agentic memory for LLM agents", "Agentic memory lets LLM agents store, update and retrieve facts across sessions."),
        ("Coral reef ecosystems", "Coral reefs support ocean biodiversity in warm shallow water."),
        ("Soil microplastics", "Microplastics change soil structure and nitrogen cycling."),
    ]
    memory_store.save_search("agentic memory", [
        {"paper_id": f"p{i + 1}", "title": title, "url": f"https://arxiv.org/abs/000{i + 1}", "abstract": text, "full_text": text}
        for i, (title, text) in enumerate(texts)
    ], session_id=session_id)


def test_stream_events_in_order(fake_groq):
    _seed("s1")
    events = list(rag.stream_answer_events(rag.prepare_answer("what is agentic memory", session_id="s1")))

    assert [e["type"] for e in events] == ["meta", "status", "status", "delta", "delta", "done"]
    assert [e["stage"] for e in events if e["type"] == "status"] == ["drafting", "checking"]
    done = events[-1]
    assert done["answer"] == "Agents keep a memory store [S1]."
    assert done["verified"] is True
    assert done["writing_standard"] == "ASD-STE100"
    assert done["citations"][0]["paper_id"] == "p1"
    # Only the fact-check pass streams.
    assert [call["stream"] for call in fake_groq.calls] == [False, True]


def test_both_passes_use_ste_rules(fake_groq):
    _seed("s1")
    list(rag.stream_answer_events(rag.prepare_answer("what is agentic memory", session_id="s1")))
    systems = [call["messages"][0]["content"] for call in fake_groq.calls]
    assert len(systems) == 2
    assert all("ASD-STE100" in s and "25 words" in s and "active voice" in s for s in systems)


def test_stream_route_returns_ndjson(fake_groq):
    _seed("s2")
    with TestClient(app) as client:
        res = client.post("/api/chat/stream", json={"question": "what is agentic memory"}, headers={"X-Session-Id": "s2"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/x-ndjson")
    events = [json.loads(line) for line in res.text.splitlines() if line.strip()]
    assert events[0]["type"] == "meta"
    assert events[-1]["type"] == "done"
    assert "".join(e["text"] for e in events if e["type"] == "delta") == events[-1]["answer"]


def test_stream_route_needs_a_search_first(fake_groq):
    with TestClient(app) as client:
        res = client.post("/api/chat/stream", json={"question": "what is agentic memory"}, headers={"X-Session-Id": "empty"})
    assert res.status_code == 400
    assert "Search for papers first" in res.json()["detail"]


def test_stream_reports_model_errors_as_event(fake_groq):
    _seed("s3")
    fake_groq.fail = True
    events = list(rag.stream_answer_events(rag.prepare_answer("what is agentic memory", session_id="s3")))
    assert events[-1]["type"] == "error"
    assert "model unavailable" in events[-1]["message"]
