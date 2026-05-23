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

What this bridge derives TODAY from agent.py's stream: `phase` (enforced
iteration counter + lifecycle), `step` (live trace), `forge` (detected skill),
`pytest` (RED/GREEN verdict), `download`, `done`. The richer semantic panels
(`business_rule`, `diff`, structured per-case `pytest`, `oracle`) are parsed from
the agent's real tool outputs and wired against the LIVE API on the day — the
agent isn't reachable from a dev box without the provisioned key. Validate the
whole live path with `scripts/smoke_test.py` the instant the key exists.

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


def _run_migration(run_id: str, cobol: str, filename: str) -> None:
    """Worker thread: drive the real agent, pushing canonical events to the run's queue.

    Uses a thread-safe queue.Queue (NOT asyncio.Queue) so it is independent of
    which event loop the POST and GET-stream requests run on.
    """
    run = _RUNS[run_id]
    q: queue.Queue = run["queue"]

    def push(ev) -> None:
        q.put(ev)

    orig_emit, orig_iter = agent_mod.emit_to_ui, agent_mod.emit_iteration
    agent_mod.emit_to_ui = lambda text: push({"type": "step", "kind": "output", "text": text})
    agent_mod.emit_iteration = lambda c, t: push(
        {"type": "phase", "phase": "test", "iteration": c,
         "iteration_cap": t, "label": f"Iteration {c}/{t}"}
    )
    tmp_path = None
    try:
        push({"type": "phase", "phase": "ingest",
              "label": f"Provisioning sandbox + reading {filename}"})
        with tempfile.NamedTemporaryFile("w", suffix=".cob", delete=False) as fh:
            fh.write(cobol)
            tmp_path = fh.name

        client = agent_mod.genai.Client()  # reads GEMINI_API_KEY
        agent_mod.ensure_agent(client)
        result = agent_mod.migrate(client, tmp_path)

        output = agent_mod.extract_output_text(result)
        skill = agent_mod._forged_skill_path(output)
        if skill:
            push({"type": "forge", "skill": skill,
                  "reason": "Unknown idiom: numeric DISPLAY format + ROUND-HALF-UP."})
            push({"type": "reload",
                  "label": f"Re-reading {skill} in the reused environment"})
        passed = agent_mod._tests_passed(output)
        push({"type": "pytest", "result": "green" if passed else "red",
              "summary": output[-500:]})

        env_id = agent_mod.extract_environment_id(result)
        migrated = _download_migrated(env_id)
        run["download"] = migrated
        if migrated is not None:
            push({"type": "download", "name": "payroll.py",
                  "mime": "text/x-python", "content": migrated})
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
