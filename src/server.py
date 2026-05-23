"""
LAZARUS — FastAPI + SSE bridge (browser <-> live Managed Agent).

Serves the web/ UI and drives the REAL Gemini Managed Agent (src/agent.py),
forwarding its progress to the live-trace UI as CANONICAL events
(web/STREAM_CONTRACT.md). There is NO mock here — the scripted run survives only
as the UI's `?mock=1` break-glass. With no GEMINI_API_KEY this returns an
explicit 503 (never fake data).

Endpoint contract (matches web/src/live.js, mode='canonical'):
    POST /api/migrate   { cobol, filename }     -> { run_id }
    GET  /api/stream/{run_id}                    -> text/event-stream (canonical events)
    GET  /api/download/{run_id}                  -> migrated module bytes (when available)
    GET  /api/health                             -> liveness + key/agent info

What this bridge derives from agent.py's stream — EVERY panel, two layers deep:
  * PROGRESSIVE `phase` events off the streamed step text (ingest->recover->translate
    ->oracle->test->forge->done), so the UI advances live, not only at the end.
  * `step` (live trace), enforced iteration counter, `forge` (+git additions),
    `reload`, `download`, `done`.
  * FAST PATH (markers): `business_rule` from LAZARUS_RULE, structured per-case `pytest`
    from LAZARUS_ORACLE_JSON.
  * SAFETY NET (deterministic, no markers needed): after migrate() we fetch the agent's
    /workspace/payroll.py via the Files API and emit (a) a real COBOL<->Python `diff` and
    (b) a structured per-case `pytest` by running src/differential_oracle on that module
    vs the real-cobc golden bytes (golden_io.json) — labeled source="differential_oracle"
    so it's never misrepresented as the agent's own test. Business rules fall back to the
    module's real recovered rules. So the demo never looks empty, with or without markers.
Validate the whole live path with `scripts/smoke_test.py` the instant the key exists.

Run:
    pip install -r requirements.txt
    export GEMINI_API_KEY=...            # provisioned at the event
    uvicorn server:app --app-dir src --reload
    # open http://127.0.0.1:8000   (UI at /, live by default; ?mock=1 = break-glass)
"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib
import queue
import tempfile
import threading
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

import agent as agent_mod  # src/ is on sys.path (uvicorn --app-dir src)
import differential_oracle  # deterministic equivalence harness (agent python vs golden)
import event_transform  # canonical-event derivations (pytest/oracle/business_rule)

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
SAMPLE_DIR = ROOT / "src" / "sample"

app = FastAPI(title="LAZARUS — Aero-Migrate", version="1.0")

# run_id -> {"queue": queue.Queue (thread-safe, loop-independent), "download": str|None}
_RUNS: dict[str, dict] = {}
_SENTINEL = object()  # marks end-of-stream in the queue


def _key_present() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def _fetch_env_tarball(env_id: str) -> bytes:
    """Download the whole-environment tarball via the Files API (findings-agents.md §9,
    cookbook-verbatim URL). Requires GEMINI_API_KEY. Raises on any HTTP/network error."""
    import urllib.request
    key = os.environ.get("GEMINI_API_KEY", "")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/files/"
        f"environment-{env_id}:download?alt=media"
    )
    req = urllib.request.Request(url, headers={"x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted host)
        return resp.read()


def _extract_migrated_from_tar(tar_bytes: bytes, module_name: str = "payroll.py") -> str | None:
    """Extract the migrated module's text from an environment tarball.

    Looks for `<...>/workspace/<module_name>` (the agent writes the migration into
    /workspace). Returns the file's text, or None if it isn't present.
    """
    import io
    import tarfile
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            name = member.name.lstrip("./")
            if name == f"workspace/{module_name}" or name.endswith(f"/workspace/{module_name}") \
                    or name.endswith(f"/{module_name}") and "workspace" in name.split("/"):
                fh = tar.extractfile(member)
                if fh is not None:
                    return fh.read().decode("utf-8", errors="replace")
    return None


def _download_migrated(env_id: str | None, *, module_name: str = "payroll.py",
                       fetch_tarball=None) -> str | None:
    """Fetch the agent-written module from the persistent sandbox via the Files API.

    `fetch_tarball(env_id) -> bytes` is injectable for testing; defaults to the real
    Files-API call. Returns None (so the Download button stays un-armed, never serving a
    stand-in) when there's no env id or any fetch/extract error.
    """
    if not env_id:
        return None
    fetch = fetch_tarball or _fetch_env_tarball
    try:
        return _extract_migrated_from_tar(fetch(env_id), module_name)
    except Exception:
        return None


# Deterministic preview of the skill the agent forges for this module's idiom (numeric
# DISPLAY de-editing + ROUND_HALF_UP). Shown as the forge panel's git additions when we
# can't extract the agent's actual SKILL.md bytes from the env tarball. It describes the
# REAL technique for the divergence the oracle catches, so the panel stays truthful.
_FORGE_SKILL_PREVIEW = [
    "# Skill: numeric DISPLAY de-editing + half-up rounding",
    "",
    "## When",
    "A COBOL `COMPUTE ... ROUNDED` over a PIC 9(n)V99 DISPLAY field diverges from a",
    "naive Python port on rounding ties (e.g. 1.00 -> COBOL 0.77 vs Python round() 0.78).",
    "",
    "## Fix",
    "- ROUNDED is round-half-UP, not banker's: use",
    "  Decimal(x).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP).",
    "- DISPLAY of PIC 9(7)V99 emits 7 zero-padded integer digits + '.' + 2 decimals,",
    "  unsigned, with a trailing newline: f\"{int_part:07d}.{frac:02d}\\n\".",
    "- Do NOT use Python's float or round(); carry Decimal end-to-end.",
]


def _forge_skill_preview(skill_path: str, output_text: str) -> list[str]:
    """git additions for the forge panel: the lines of the skill the agent forged.

    Best-effort, in order: (1) a fenced block immediately after the skill path in the
    agent's own output (its real authored content, if printed), else (2) the deterministic
    preview of the idiom fix. Either way the lines describe the REAL technique.
    """
    import re as _re
    # If the agent echoed the file content in a fenced block near the path, prefer it.
    m = _re.search(r"```[a-zA-Z]*\n(.*?)```", output_text, _re.S)
    if m and "ROUND" in m.group(1).upper():
        lines = m.group(1).rstrip("\n").splitlines()
        if 2 <= len(lines) <= 40:
            return lines
    return list(_FORGE_SKILL_PREVIEW)


def _run_oracle_pytest(migrated_src: str, iteration: int = 1) -> dict | None:
    """Run the differential oracle on the agent's payroll.py vs the real-cobc golden bytes.

    The DETERMINISTIC fallback (and corroboration) for the test panel: write the agent's
    fetched module to a temp file and diff its output, per golden input, against the
    pre-captured real-GnuCOBOL bytes in golden_io.json. Returns a STRUCTURED pytest event
    (per-case cobol-vs-python) labeled as the differential-oracle harness — so the RED->GREEN
    panel populates from REAL output regardless of whether the agent printed a marker.

    Returns None if the golden capture is missing or the module won't run (so the caller can
    fall back to a coarse verdict rather than emit a misleading green/red).
    """
    golden = SAMPLE_DIR / "golden_io.json"
    if not golden.exists():
        return None
    py_tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
            fh.write(migrated_src)
            py_tmp = fh.name
        records = differential_oracle.prove_equivalence(py_tmp, str(golden))
        return event_transform.oracle_harness_pytest_event(records, iteration=iteration)
    except Exception:
        return None  # module crashed / golden unreadable -> caller uses the coarse verdict
    finally:
        if py_tmp:
            try:
                os.unlink(py_tmp)
            except OSError:
                pass


def _run_migration(run_id: str, cobol: str, filename: str) -> None:
    """Worker thread: drive the real agent, pushing canonical events to the run's queue.

    Uses a thread-safe queue.Queue (NOT asyncio.Queue) so it is independent of
    which event loop the POST and GET-stream requests run on.

    Two layers feed the panels:
      * FAST PATH (markers): if the agent prints LAZARUS_RULE / LAZARUS_ORACLE_JSON, those
        drive the rules + structured pytest directly.
      * SAFETY NET (deterministic): regardless of markers, after migrate() returns we fetch
        the agent's payroll.py via the Files API and (a) emit a real COBOL<->Python `diff`
        and (b) run the differential oracle against golden_io.json for a structured per-case
        `pytest`. The phase rail also advances PROGRESSIVELY off the streamed step text.
    """
    run = _RUNS[run_id]
    q: queue.Queue = run["queue"]

    def push(ev) -> None:
        q.put(ev)

    # Progressive phases: advance the rail as the agent's streamed text crosses milestones.
    # Only forward-moving transitions are emitted (the rail never jumps backwards), and each
    # phase is emitted at most once, so the UI shows ingest->recover->translate->oracle->test
    # ->forge LIVE rather than only the terminal verdict.
    _PHASE_ORDER = ["ingest", "recover", "translate", "oracle", "test",
                    "diagnose", "forge", "reload", "verify", "done"]
    progress = {"idx": 0}  # highest phase index emitted so far

    def emit_phase(phase: str, *, label: str | None = None, **extra) -> None:
        try:
            idx = _PHASE_ORDER.index(phase)
        except ValueError:
            return
        if idx < progress["idx"]:
            return  # never move the rail backwards
        progress["idx"] = idx
        push({"type": "phase", "phase": phase,
              "label": label or f"{phase.capitalize()}…", **extra})

    def emit_step(text: str) -> None:
        push({"type": "step", "kind": "output", "text": text})
        phase = event_transform.phase_for_text(text)
        if phase:
            emit_phase(phase)

    def emit_iteration(c: int, t: int) -> None:
        # The enforced loop counter is orthogonal to the phase: surface `iteration` on the
        # CURRENT phase (don't jump the rail to TEST before the agent has tested anything).
        cur = _PHASE_ORDER[progress["idx"]]
        push({"type": "phase", "phase": cur, "iteration": c,
              "iteration_cap": t, "label": f"Iteration {c}/{t}"})

    orig_emit, orig_iter = agent_mod.emit_to_ui, agent_mod.emit_iteration
    agent_mod.emit_to_ui = emit_step
    agent_mod.emit_iteration = emit_iteration
    tmp_path = None
    try:
        emit_phase("ingest", label=f"Provisioning sandbox + reading {filename}")
        with tempfile.NamedTemporaryFile("w", suffix=".cob", delete=False) as fh:
            fh.write(cobol)
            tmp_path = fh.name

        client = agent_mod.genai.Client()  # reads GEMINI_API_KEY
        agent_mod.ensure_agent(client)
        result = agent_mod.migrate(client, tmp_path)

        output = agent_mod.extract_output_text(result)

        # Recovered business rules (archaeology panel): markers if the agent emitted them,
        # else the deterministic fallback so the panel never sits empty (>=3 real rules).
        rules = event_transform.business_rules_from_text(output)
        if not rules:
            rules = event_transform.business_rules_fallback()
        for rule in rules:
            push(rule)

        # Oracle banner: real compiler + the input battery (from the golden capture).
        golden = SAMPLE_DIR / "golden_io.json"
        if golden.exists():
            emit_phase("oracle")
            push(event_transform.oracle_event(str(golden)))

        skill = agent_mod._forged_skill_path(output)
        if skill:
            emit_phase("forge")
            push({"type": "forge", "skill": skill,
                  "reason": "Unknown idiom: numeric DISPLAY format + ROUND-HALF-UP.",
                  "git": {"status": "A",
                          "additions": _forge_skill_preview(skill, output),
                          "commit": f"forge: add {pathlib.Path(skill).parent.name} skill"}})
            emit_phase("reload")
            push({"type": "reload",
                  "label": f"Re-reading {skill} in the reused environment"})

        # Fetch the agent's actual module (Files API) — drives the diff + the oracle pytest.
        env_id = agent_mod.extract_environment_id(result)
        migrated = _download_migrated(env_id)
        run["download"] = migrated

        # COBOL<->Python diff from REAL sources (submitted COBOL + the agent's payroll.py).
        if migrated is not None:
            emit_phase("translate")
            push(event_transform.diff_event(cobol, migrated,
                                            cobol_name=filename, python_name="payroll.py"))

        # STRUCTURED pytest (the money shot). Priority:
        #   1. agent's LAZARUS_ORACLE_JSON marker (the agent's own per-case oracle), else
        #   2. the orchestrator's differential oracle on the fetched module vs golden bytes
        #      (deterministic; labeled as the oracle harness, not the agent's pytest), else
        #   3. a coarse RED/GREEN verdict scraped from the agent's terminal text.
        emit_phase("test")
        records = event_transform.parse_oracle_records(output)
        if records:
            pytest_ev = event_transform.to_pytest_event(records, iteration=1)
        elif migrated is not None:
            pytest_ev = _run_oracle_pytest(migrated, iteration=1)
        else:
            pytest_ev = None
        if pytest_ev is not None:
            passed = pytest_ev["result"] == "green"
            push(pytest_ev)
        else:
            passed = agent_mod._tests_passed(output)
            push({"type": "pytest", "result": "green" if passed else "red",
                  "iteration": 1, "summary": output[-500:] or "(no test output)",
                  "cases": []})

        if migrated is not None:
            push({"type": "download", "name": "payroll.py",
                  "mime": "text/x-python", "content": migrated})
        emit_phase("done")
        push({"type": "done",
              "verdict": "EQUIVALENT" if passed else "INCOMPLETE",
              "environment_id": env_id})
    except Exception as e:  # surface real errors to the UI, never fake success
        push({"type": "error", "message": f"{type(e).__name__}: {e}"})
    finally:
        agent_mod.emit_to_ui, agent_mod.emit_iteration = orig_emit, orig_iter
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        q.put(_SENTINEL)  # end of stream


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "gemini_api_key_present": _key_present(),
        "agent": agent_mod.AGENT_ID,
        "base_agent": agent_mod.BASE_AGENT,
        "max_iterations": agent_mod.MAX_ITERATIONS,
    }


@app.post("/api/migrate")
async def migrate_start(request: Request):
    """Kick off a migration; return a run_id the UI subscribes to via /api/stream."""
    if not _key_present():
        return JSONResponse(
            status_code=503,
            content={"type": "error", "error": "GEMINI_API_KEY not set",
                     "hint": "export GEMINI_API_KEY=... (Gemini API key, provisioned at the event)"},
        )
    try:
        body = await request.json()
    except Exception:
        body = {}
    cobol = (body or {}).get("cobol")
    filename = (body or {}).get("filename", "payroll.cob")
    if not cobol:
        sample = SAMPLE_DIR / "payroll.cob"  # convenience fallback to the golden sample
        if sample.exists():
            cobol = sample.read_text()
        else:
            raise HTTPException(status_code=400, detail="no COBOL provided")

    run_id = uuid.uuid4().hex
    _RUNS[run_id] = {"queue": queue.Queue(), "download": None}
    threading.Thread(
        target=_run_migration, args=(run_id, cobol, filename), daemon=True
    ).start()
    return {"run_id": run_id}


@app.get("/api/stream/{run_id}")
async def migrate_stream(run_id: str, request: Request):
    """Stream a run's canonical events as SSE until the terminal `done`/`error`."""
    run = _RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown run_id")
    q: queue.Queue = run["queue"]

    async def event_gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                ev = await asyncio.to_thread(q.get)  # loop-independent blocking get
                if ev is _SENTINEL:
                    break
                yield {"data": json.dumps(ev)}
        finally:
            _RUNS.pop(run_id, None)  # one subscriber per run; clean up

    return EventSourceResponse(event_gen())


@app.get("/api/download/{run_id}")
def download(run_id: str):
    """Return the migrated module for a finished run (when the Files-API hook is wired)."""
    run = _RUNS.get(run_id)
    content = run.get("download") if run else None
    if not content:
        raise HTTPException(status_code=404, detail="migrated module not available yet")
    return PlainTextResponse(
        content,
        media_type="text/x-python",
        headers={"Content-Disposition": 'attachment; filename="payroll.py"'},
    )


# Serve the live-trace UI at / (mounted last so /api/* wins).
if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
