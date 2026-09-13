"""Critical-path tests: health, sessions, chat, retrieval, routing, artifacts.

LLM calls use LLM_PROVIDER=mock (see conftest) — no network, no cloud keys.
"""
import os

os.environ.setdefault("LLM_PROVIDER", "mock")

from backend.app.services import artifacts as artmod  # noqa: E402
from backend.app.services import router as routermod  # noqa: E402
from backend.app.services.providers import MockProvider, ProviderError, get_provider  # noqa: E402
from backend.app.services.retrieval import retrieve  # noqa: E402


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "mock"
    assert "database" in body and "ollama" in body


def test_root_health_alias(client):
    assert client.get("/health").status_code == 200


def test_session_lifecycle(client):
    c = client.post("/api/v1/sessions", json={"title": "T"}).json()
    assert c["id"]
    got = client.get(f"/api/v1/sessions/{c['id']}").json()
    assert got["id"] == c["id"]
    assert client.get("/api/v1/sessions").status_code == 200
    assert client.delete(f"/api/v1/sessions/{c['id']}").status_code == 204
    assert client.get(f"/api/v1/sessions/{c['id']}").status_code == 404


def test_chat_validation(client):
    assert client.post("/api/v1/chat", json={"message": ""}).status_code == 422
    assert client.post("/api/v1/chat", json={"session_id": "nope", "message": "hi"}).status_code == 404


def test_chat_grounded_with_sources(client):
    r = client.post("/api/v1/chat", json={"message": "What are lessons on product-market fit?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["route"] == "chat"
    assert body["sources"], "grounded answer must carry sources"
    assert body["sources"][0]["title"] == "PMF Episode"
    msgs = client.get(f"/api/v1/sessions/{body['session_id']}/messages").json()
    assert len(msgs) == 2  # user + assistant persisted


def test_chat_followup_keeps_session(client):
    first = client.post("/api/v1/chat", json={"message": "Tell me about growth loops"}).json()
    sid = first["session_id"]
    second = client.post("/api/v1/chat", json={"session_id": sid, "message": "What metric matters most for that?"})
    assert second.status_code == 200
    assert second.json()["session_id"] == sid
    msgs = client.get(f"/api/v1/sessions/{sid}/messages").json()
    assert len(msgs) == 4


def test_empty_retrieval_is_honest(client, tmp_path, monkeypatch):
    empty = tmp_path / "empty.json"
    empty.write_text("[]")
    monkeypatch.setenv("INDEX_PATH", str(empty))
    from backend.app.services import chat as chatmod
    out = chatmod.answer_question("quantum chromodynamics", [], index_path=str(empty))
    assert out["sources"] == []
    assert "don't cover" in out["answer"] or "couldn't find" in out["answer"]


def test_router_boundaries():
    assert routermod.route_message("Write a Ship 30 for 30 essay on onboarding") == "essay"
    assert routermod.route_message("Create a Markdown strategy document from this chat") == "artifact"
    assert routermod.route_message("Render this as an HTML landing page") == "artifact"
    assert routermod.route_message("How should I measure retention?") == "chat"


def test_provider_selection():
    assert isinstance(get_provider("mock"), MockProvider)
    try:
        get_provider("nope")
        raise AssertionError("expected ProviderError")
    except ProviderError:
        pass


def test_ollama_unavailable_is_actionable(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    from backend.app.services.providers import OllamaProvider
    try:
        OllamaProvider().generate("sys", "hi")
        raise AssertionError("expected ProviderError")
    except ProviderError as e:
        assert "ollama serve" in str(e).lower()


def test_chat_503_when_ollama_down(client, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")
    from backend.app import config
    config.get_settings.cache_clear()
    try:
        r = client.post("/api/v1/chat", json={"message": "What is product-market fit?"})
        assert r.status_code == 503
        assert "ollama" in r.json()["error"].lower()
    finally:
        config.get_settings.cache_clear()


def test_retrieval_scores_and_attribution():
    hits = retrieve("growth loops compound", os.environ["INDEX_PATH"], top_k=2)
    assert hits and hits[0]["source_id"] == "loops"
    assert all({"title", "source_id", "text", "score"} <= set(h) for h in hits)


def test_artifact_sanitization_strips_scripts():
    dirty = '<h1>T</h1><script>alert(1)</script><a href="javascript:alert(2)">x</a><p onclick="evil()">y</p>'
    clean = artmod.sanitize_html(dirty)
    assert "<script" not in clean and "onclick" not in clean and "javascript:" not in clean
    assert "T" in clean


def test_artifact_sanitization_keeps_benign_css():
    dirty = '<style>body{color:red}</style><h1>Hi</h1>'
    clean = artmod.sanitize_html(dirty)
    assert "<style>body{color:red}</style>" in clean
    assert "<h1>Hi</h1>" in clean


def test_artifact_sanitization_strips_iframes_forms_objects():
    dirty = '<iframe src="https://evil.example"></iframe><form action="x"></form><object data="x"></object><img src=x onerror="alert(1)">'
    clean = artmod.sanitize_html(dirty)
    assert "<iframe" not in clean and "<form" not in clean and "<object" not in clean
    assert "onerror" not in clean


def test_artifact_route_creates_viewable_artifact(client):
    r = client.post("/api/v1/chat", json={"message": "Create a Markdown product strategy document from this conversation"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["route"] == "artifact" and body["artifact_id"]
    got = client.get(f"/api/v1/artifacts/{body['artifact_id']}").json()
    assert got["content"] and got["kind"] == "markdown"


def test_essay_route_grounded(client):
    r = client.post("/api/v1/chat", json={"message": "Turn the PMF lessons into a Ship 30 for 30-style essay"})
    assert r.status_code == 200, r.text
    assert r.json()["route"] == "essay"
