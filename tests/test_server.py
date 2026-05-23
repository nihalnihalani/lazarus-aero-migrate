"""Tests for the FastAPI/SSE bridge (src/server.py) — all runnable WITHOUT a key.

Covers what's verifiable offline: the health endpoint, the explicit no-key 503
(never fake data), and that a (stubbed) agent run is forwarded to the browser as
the canonical SSE event sequence. The live Gemini path itself is validated by
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
    r = client.get("/api/migrate")
    assert r.status_code == 503
    assert "GEMINI_API_KEY" in r.json()["error"]


def test_migrate_streams_canonical_events(monkeypatch):
    """A stubbed agent run is forwarded as phase/step/forge/pytest/done events."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(agent_mod.genai, "Client", lambda *a, **k: object())
    monkeypatch.setattr(agent_mod, "ensure_agent", lambda client: None)

    def fake_migrate(client, path):
        # Exercise the hooks the bridge overrides (mirrors real migrate()).
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
    seen = []
    with client.stream("GET", "/api/migrate") as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            s = line.decode() if isinstance(line, (bytes, bytearray)) else line
            if s and s.startswith("data:"):
                ev = json.loads(s[len("data:"):].strip())
                seen.append(ev.get("type"))
                if ev.get("type") == "done":
                    break

    assert "phase" in seen     # enforced iteration counter + lifecycle
    assert "step" in seen      # live "agent working" trace
    assert "forge" in seen     # forged-skill detected from agent output
    assert "pytest" in seen    # RED/GREEN verdict
    assert "done" in seen      # terminal verdict
