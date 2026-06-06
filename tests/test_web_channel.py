"""Tests for the web UI."""
import pytest

fastapi = pytest.importorskip("fastapi")


def test_create_app():
    from channels.web import create_app
    app = create_app()
    assert app.title == "Nonull"


def test_index_route():
    from channels.web import create_app
    from fastapi.testclient import TestClient
    app = create_app()
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Nonull" in resp.text


def test_skills_api():
    from channels.web import create_app
    from fastapi.testclient import TestClient
    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/skills")
    assert resp.status_code == 200
    assert "skills" in resp.json()


def test_scenarios_api():
    from channels.web import create_app
    from fastapi.testclient import TestClient
    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/scenarios")
    assert resp.status_code == 200
    assert "scenarios" in resp.json()


def test_domains_api():
    from channels.web import create_app
    from fastapi.testclient import TestClient
    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/domains")
    assert resp.status_code == 200
    assert "domains" in resp.json()


def test_agent_status_no_agent():
    from channels.web import create_app
    from fastapi.testclient import TestClient
    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/agent/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "not_loaded"


def test_chat_no_agent():
    from channels.web import create_app
    from fastapi.testclient import TestClient
    app = create_app()
    client = TestClient(app)
    resp = client.post("/api/agent/chat", json={"message": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "no_agent"


def test_chat_empty_message():
    from channels.web import create_app
    from fastapi.testclient import TestClient
    app = create_app()
    client = TestClient(app)
    resp = client.post("/api/agent/chat", json={"message": ""})
    # 400 raised via HTTPException
    assert resp.status_code == 400


def test_chat_with_mock_agent():
    """Smoke test that the chat route delegates to a `run_sync` agent."""
    from channels.web import create_app
    from fastapi.testclient import TestClient

    class _MockAgent:
        def run_sync(self, message: str):
            return {"output": f"echo: {message}", "status": "ok"}

    app = create_app(agent=_MockAgent())
    client = TestClient(app)
    resp = client.post("/api/agent/chat", json={"message": "ping"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "echo: ping" in data["response"]


def test_chat_with_failing_agent():
    """Exceptions from `run_sync` are returned, not raised."""
    from channels.web import create_app
    from fastapi.testclient import TestClient

    class _BadAgent:
        def run_sync(self, message: str):
            raise RuntimeError("boom")

    app = create_app(agent=_BadAgent())
    client = TestClient(app)
    resp = client.post("/api/agent/chat", json={"message": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"
    assert "boom" in data["response"]


def test_index_html_contains_advisory_disclaimer():
    """The web UI must surface the advisory-only disclaimer, matching the
    project's CLAUDE.md red lines (no ISO 26262 / ASIL-D marketing claims)."""
    from channels.web import create_app
    from fastapi.testclient import TestClient
    app = create_app()
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text.upper()
    # Disclaimer keywords
    assert "ADVISORY" in body
    assert "NOT" in body and "CERTIFIED" in body


def test_env_resolve_port_default():
    """`_resolve_port` falls back to default when no env var is set."""
    import os
    from channels import web
    saved = os.environ.pop("NONULL_WEB_PORT", None)
    try:
        assert web._resolve_port() == 8765
    finally:
        if saved is not None:
            os.environ["NONULL_WEB_PORT"] = saved


def test_env_resolve_port_override(monkeypatch):
    """`NONULL_WEB_PORT` overrides the default port."""
    from channels import web
    monkeypatch.setenv("NONULL_WEB_PORT", "9999")
    assert web._resolve_port() == 9999


def test_env_resolve_port_invalid_falls_back(monkeypatch):
    """Invalid port values fall back to the default (no crash at import / startup)."""
    from channels import web
    for bad in ("abc", "-1", "0", "99999", ""):
        monkeypatch.setenv("NONULL_WEB_PORT", bad)
        assert web._resolve_port() == 8765


def test_env_resolve_host_override(monkeypatch):
    """`NONULL_WEB_HOST` overrides the default host."""
    from channels import web
    monkeypatch.setenv("NONULL_WEB_HOST", "0.0.0.0")
    assert web._resolve_host() == "0.0.0.0"
