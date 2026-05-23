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


def _make_tar_bytes(members: dict[str, str]) -> bytes:
    """Build an in-memory tar (path -> text content) for download-extraction tests."""
    import io
    import tarfile
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for path, text in members.items():
            data = text.encode()
            info = tarfile.TarInfo(name=path)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_extract_migrated_pulls_payroll_py_from_workspace():
    """The migrated module is extracted from /workspace/payroll.py inside the env tarball."""
    tar = _make_tar_bytes({
        "workspace/payroll.py": "print('migrated')\n",
        "workspace/other.txt": "ignore me\n",
    })
    content = server._extract_migrated_from_tar(tar, "payroll.py")
    assert content == "print('migrated')\n"


def test_extract_migrated_returns_none_when_absent():
    tar = _make_tar_bytes({"workspace/notes.md": "no python here\n"})
    assert server._extract_migrated_from_tar(tar, "payroll.py") is None


def test_download_migrated_uses_injected_fetcher(monkeypatch):
    """_download_migrated fetches the env tarball (injected here) + extracts the module —
    no network/key needed for the unit test."""
    tar = _make_tar_bytes({"workspace/payroll.py": "X = 1\n"})
    out = server._download_migrated(
        env_id="env-xyz", fetch_tarball=lambda env_id: tar
    )
    assert out == "X = 1\n"


def test_download_migrated_none_without_env_id():
    assert server._download_migrated(env_id=None) is None


def test_download_migrated_none_on_fetch_error():
    def boom(env_id):
        raise RuntimeError("network down")
    assert server._download_migrated(env_id="e", fetch_tarball=boom) is None


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


def test_stream_emits_structured_pytest_and_oracle(monkeypatch):
    """The #1 money shot: server derives a STRUCTURED pytest event (per-case
    cobol-vs-python) + an oracle banner from the agent's LAZARUS_ORACLE_JSON marker."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(agent_mod.genai, "Client", lambda *a, **k: object())
    monkeypatch.setattr(agent_mod, "ensure_agent", lambda client: None)
    monkeypatch.setattr(agent_mod, "migrate", lambda client, path: SimpleNamespace())
    agent_output = (
        'LAZARUS_RULE: {"title": "Progressive tax", "plain": "22.5% withheld", "severity": "rule"}\n'
        'LAZARUS_ORACLE_JSON: [{"input": "1.00\\n", "cobol": "0000000.77\\n", '
        '"python": "0000000.78\\n", "match": false}, '
        '{"input": "1000.00\\n", "cobol": "0000775.00\\n", "python": "0000775.00\\n", "match": true}]\n'
        "1 failed, 1 passed"
    )
    monkeypatch.setattr(agent_mod, "extract_output_text", lambda r: agent_output)
    monkeypatch.setattr(agent_mod, "extract_environment_id", lambda r: "env-xyz")

    client = TestClient(server.app)
    run_id = client.post("/api/migrate", json={"cobol": "X", "filename": "p.cob"}).json()["run_id"]

    events = []
    with client.stream("GET", f"/api/stream/{run_id}") as resp:
        for line in resp.iter_lines():
            s = line.decode() if isinstance(line, (bytes, bytearray)) else line
            if s and s.startswith("data:"):
                ev = json.loads(s[len("data:"):].strip())
                events.append(ev)
                if ev.get("type") in ("done", "error"):
                    break

    by_type = {e["type"]: e for e in events}
    assert "oracle" in by_type and "GnuCOBOL" in by_type["oracle"]["compiler"]
    assert "business_rule" in by_type
    pt = by_type["pytest"]
    assert pt["result"] == "red"
    assert len(pt["cases"]) == 2
    fail = next(c for c in pt["cases"] if c["status"] == "fail")
    assert fail["cobol"] == "0000000.77\n" and fail["python"] == "0000000.78\n"  # the diff!


# --------------------------------------------------------------------------
# The DETERMINISTIC SAFETY NET: even with ZERO markers, the live path fetches the
# agent's payroll.py and drives the diff + a structured per-case pytest from the
# orchestrator's differential oracle (agent python vs real-cobc golden bytes).
# --------------------------------------------------------------------------
def _tar_with_module(module_text: str, *, path: str = "env-x/workspace/payroll.py") -> bytes:
    return _make_tar_bytes({path: module_text})


def _collect_events(client, run_id):
    events = []
    with client.stream("GET", f"/api/stream/{run_id}") as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            s = line.decode() if isinstance(line, (bytes, bytearray)) else line
            if s and s.startswith("data:"):
                ev = json.loads(s[len("data:"):].strip())
                events.append(ev)
                if ev.get("type") in ("done", "error"):
                    break
    return events


def _stub_markerless_agent(monkeypatch, *, output, env_id="env-x", emit=None):
    """Stub the agent so migrate() emits no markers — exercises the safety net path."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(agent_mod.genai, "Client", lambda *a, **k: object())
    monkeypatch.setattr(agent_mod, "ensure_agent", lambda client: None)

    def fake_migrate(client, path):
        agent_mod.emit_iteration(1, agent_mod.MAX_ITERATIONS)
        for line in (emit or ["Reading COBOL", "Writing payroll.py", "Running pytest"]):
            agent_mod.emit_to_ui(line)
        return SimpleNamespace()

    monkeypatch.setattr(agent_mod, "migrate", fake_migrate)
    monkeypatch.setattr(agent_mod, "extract_output_text", lambda r: output)
    monkeypatch.setattr(agent_mod, "extract_environment_id", lambda r: env_id)


def test_safety_net_populates_every_panel_without_markers(monkeypatch):
    """No LAZARUS_* markers at all: the server still drives diff + a structured oracle
    pytest from the fetched payroll.py, plus fallback rules + the oracle banner."""
    sample_py = (ROOT / "src" / "sample" / "payroll.py").read_text()
    monkeypatch.setattr(server, "_fetch_env_tarball",
                        lambda env_id: _tar_with_module(sample_py))
    _stub_markerless_agent(
        monkeypatch,
        output="All equivalence tests pass. byte-for-byte equivalent to original COBOL.",
    )

    client = TestClient(server.app)
    run_id = client.post("/api/migrate", json={
        "cobol": (ROOT / "src" / "sample" / "payroll.cob").read_text(),
        "filename": "payroll.cob",
    }).json()["run_id"]
    events = _collect_events(client, run_id)
    by_type = {e["type"]: e for e in events}

    # Every panel populated from REAL output, no markers required.
    assert sum(1 for e in events if e["type"] == "business_rule") >= 3   # fallback rules
    assert "oracle" in by_type
    diff = by_type["diff"]
    assert diff["left"]["name"] == "payroll.cob" and diff["right"]["name"] == "payroll.py"
    assert "IDENTIFICATION DIVISION" in diff["left"]["code"]              # real submitted COBOL
    assert diff["right"]["code"] == sample_py                            # the agent's real module
    pt = by_type["pytest"]
    assert pt["source"] == "differential_oracle"                        # truthful labeling
    assert pt["result"] == "green" and len(pt["cases"]) == 10           # all golden cases
    assert all(c["name"].startswith("oracle_equivalence[") for c in pt["cases"])
    assert by_type["download"]["content"] == sample_py
    assert by_type["done"]["verdict"] == "EQUIVALENT"


def test_safety_net_goes_red_when_module_diverges(monkeypatch):
    """A naive port using banker's rounding fails the tie cases — the oracle pytest goes
    RED with per-case cobol-vs-python bytes, even though the agent claimed success."""
    naive_py = (
        "import sys\n"
        "from decimal import Decimal\n"
        "g = Decimal(sys.stdin.readline().strip())\n"
        "tax = round(g * Decimal('0.225'), 2)\n"   # banker's rounding -> wrong on ties
        "net = g - tax\n"
        "print(f'{int(net):07d}.{int((net % 1) * 100):02d}')\n"
    )
    monkeypatch.setattr(server, "_fetch_env_tarball",
                        lambda env_id: _tar_with_module(naive_py))
    _stub_markerless_agent(monkeypatch, output="all tests pass")  # agent OVER-claims

    client = TestClient(server.app)
    run_id = client.post("/api/migrate", json={
        "cobol": (ROOT / "src" / "sample" / "payroll.cob").read_text(),
        "filename": "payroll.cob",
    }).json()["run_id"]
    by_type = {e["type"]: e for e in _collect_events(client, run_id)}

    pt = by_type["pytest"]
    assert pt["source"] == "differential_oracle"
    assert pt["result"] == "red"                 # the oracle catches the divergence
    assert any(c["status"] == "fail" for c in pt["cases"])
    assert by_type["done"]["verdict"] == "INCOMPLETE"   # verdict follows the REAL oracle


def test_crashing_module_goes_red_not_falsely_green(monkeypatch):
    """A fetched payroll.py that CRASHES under the oracle must show an explicit RED with a
    diagnostic note — never fall through to a prose-only green just because the agent claimed
    success. Otherwise a broken module + an over-claiming agent slips through."""
    broken_py = "import sys\nraise SystemExit('boom')\n"   # exits non-zero on every input
    monkeypatch.setattr(server, "_fetch_env_tarball",
                        lambda env_id: _tar_with_module(broken_py))
    _stub_markerless_agent(monkeypatch, output="All tests pass! Equivalent to COBOL.")

    client = TestClient(server.app)
    run_id = client.post("/api/migrate", json={"cobol": "X", "filename": "p.cob"}).json()["run_id"]
    by_type = {e["type"]: e for e in _collect_events(client, run_id)}

    pt = by_type["pytest"]
    assert pt["result"] == "red"                       # NOT a false green
    assert pt["source"] == "differential_oracle"
    assert "could not run" in pt["summary"]
    assert by_type["done"]["verdict"] == "INCOMPLETE"   # verdict follows the failed oracle


def test_agent_marker_pytest_is_labeled_agent_source(monkeypatch):
    """When the per-case pytest comes from the agent's OWN LAZARUS_ORACLE_JSON marker, it's
    labeled source='agent_pytest' (distinct from the orchestrator's differential_oracle), so
    the UI can show provenance honestly."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(agent_mod.genai, "Client", lambda *a, **k: object())
    monkeypatch.setattr(agent_mod, "ensure_agent", lambda client: None)
    monkeypatch.setattr(agent_mod, "migrate", lambda client, path: SimpleNamespace())
    monkeypatch.setattr(
        agent_mod, "extract_output_text",
        lambda r: ('LAZARUS_ORACLE_JSON: [{"input": "1000.00\\n", "cobol": "0000775.00\\n", '
                   '"python": "0000775.00\\n", "match": true}]\n1 passed'),
    )
    monkeypatch.setattr(agent_mod, "extract_environment_id", lambda r: "env-xyz")

    client = TestClient(server.app)
    run_id = client.post("/api/migrate", json={"cobol": "X", "filename": "p.cob"}).json()["run_id"]
    by_type = {e["type"]: e for e in _collect_events(client, run_id)}

    pt = by_type["pytest"]
    assert pt["source"] == "agent_pytest"              # the agent's own oracle, not ours
    assert pt["cases"][0]["name"].startswith("test_equivalence[")  # agent's case naming


def test_phase_rail_advances_progressively(monkeypatch):
    """Phases advance off the streamed step text (ingest->recover->translate->oracle->test)
    and never move backwards — the rail shows the journey live, not just the verdict."""
    sample_py = (ROOT / "src" / "sample" / "payroll.py").read_text()
    monkeypatch.setattr(server, "_fetch_env_tarball",
                        lambda env_id: _tar_with_module(sample_py))
    _stub_markerless_agent(
        monkeypatch,
        output="all tests pass",
        emit=[
            "Reading the COBOL source and provisioning the sandbox",
            "Recovering the business rules in plain English",
            "Writing payroll.py translation",
            "Compiling original with cobc for the differential oracle",
            "Running pytest equivalence tests",
        ],
    )

    client = TestClient(server.app)
    run_id = client.post("/api/migrate", json={"cobol": "IDENTIFICATION DIVISION.",
                                              "filename": "payroll.cob"}).json()["run_id"]
    events = _collect_events(client, run_id)

    order = ["ingest", "recover", "translate", "oracle", "test",
             "diagnose", "forge", "reload", "verify", "done"]
    seen_phases = [e["phase"] for e in events if e["type"] == "phase"]
    idxs = [order.index(p) for p in seen_phases]
    assert idxs == sorted(idxs)                       # monotonic non-decreasing (never back)
    assert {"ingest", "recover", "translate", "oracle", "test", "done"} <= set(seen_phases)

    # Every phase event carries a human, non-generic label — the WORKING banner shows it
    # during the multi-minute live wait (frontend reads phase.label). A bare capitalized
    # phase name (e.g. "Recover…") would be the lazy fallback; assert we did better.
    phase_events = [e for e in events if e["type"] == "phase"]
    assert all(e.get("label") for e in phase_events)
    labeled = {e["phase"]: e["label"] for e in phase_events if "iteration" not in e}
    assert labeled["recover"] != "Recover…" and "rule" in labeled["recover"].lower()
    assert "oracle" in labeled["oracle"].lower() or "differential" in labeled["oracle"].lower()


def test_forge_event_carries_git_additions(monkeypatch):
    """When the agent forges a skill, the forge event carries git.additions so the
    'writing itself' panel types in real content (renderer requires ev.git.additions)."""
    sample_py = (ROOT / "src" / "sample" / "payroll.py").read_text()
    monkeypatch.setattr(server, "_fetch_env_tarball",
                        lambda env_id: _tar_with_module(sample_py))
    _stub_markerless_agent(
        monkeypatch,
        output="Forged .agents/skills/numeric-display-rounding/SKILL.md. all tests pass",
    )

    client = TestClient(server.app)
    run_id = client.post("/api/migrate", json={"cobol": "X", "filename": "p.cob"}).json()["run_id"]
    by_type = {e["type"]: e for e in _collect_events(client, run_id)}

    forge = by_type["forge"]
    assert forge["skill"].endswith("SKILL.md")
    assert isinstance(forge["git"]["additions"], list) and len(forge["git"]["additions"]) >= 2
    assert forge["git"]["status"] == "A" and forge["git"]["commit"]
    assert "reload" in by_type
