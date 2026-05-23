"""Tests for the FastAPI/SSE bridge (src/server.py) — all runnable WITHOUT a key.

Covers what's verifiable offline: health, the explicit no-key 503 (never fake
data), and that a (stubbed) agent run is forwarded over the run_id contract that
web/src/live.js consumes:  POST /api/migrate -> {run_id}; GET /api/stream/{run_id}
-> canonical SSE events. The live Gemini path itself is validated by
scripts/smoke_test.py once the key is provisioned.
"""
import json
import pathlib
import sys
from types import SimpleNamespace

from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import server  # noqa: E402

agent_mod = server.agent_mod


def test_health_reports_agent_and_key_flag(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = TestClient(server.app)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["agent"] == agent_mod.AGENT_ID
    assert body["base_agent"] == agent_mod.BASE_AGENT
    assert body["gemini_api_key_present"] is False


def test_migrate_without_key_returns_503(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = TestClient(server.app)
    r = client.post("/api/migrate", json={"cobol": "x", "filename": "x.cob"})
    assert r.status_code == 503
    assert "GEMINI_API_KEY" in r.json()["error"]


def test_stream_unknown_run_id_404(monkeypatch):
    client = TestClient(server.app)
    with client.stream("GET", "/api/stream/does-not-exist") as resp:
        assert resp.status_code == 404


def test_post_then_stream_emits_canonical_events(monkeypatch):
    """POST -> run_id, then GET /api/stream/{run_id} forwards canonical events."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(agent_mod.genai, "Client", lambda *a, **k: object())
    monkeypatch.setattr(agent_mod, "ensure_agent", lambda client: None)

    def fake_migrate(client, path):
        agent_mod.emit_iteration(1, agent_mod.MAX_ITERATIONS)
        agent_mod.emit_to_ui("Recovered business rules; wrote payroll.py ...")
        return SimpleNamespace()

    monkeypatch.setattr(agent_mod, "migrate", fake_migrate)
    monkeypatch.setattr(
        agent_mod, "extract_output_text",
        lambda r: "FORGED .agents/skills/numeric-display-rounding/SKILL.md. all tests pass",
    )
    monkeypatch.setattr(agent_mod, "extract_environment_id", lambda r: "env-abc123")

    client = TestClient(server.app)
    start = client.post("/api/migrate", json={"cobol": "IDENTIFICATION DIVISION.",
                                              "filename": "payroll.cob"})
    assert start.status_code == 200
    run_id = start.json()["run_id"]
    assert run_id

    seen = []
    with client.stream("GET", f"/api/stream/{run_id}") as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            s = line.decode() if isinstance(line, (bytes, bytearray)) else line
            if s and s.startswith("data:"):
                ev = json.loads(s[len("data:"):].strip())
                seen.append(ev.get("type"))
                if ev.get("type") in ("done", "error"):
                    break

    assert "phase" in seen     # enforced iteration counter + lifecycle
    assert "step" in seen      # live "agent working" trace
    assert "forge" in seen     # forged-skill detected from agent output
    assert "pytest" in seen    # RED/GREEN verdict
    assert "done" in seen      # terminal verdict
