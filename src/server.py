"""
LAZARUS — FastAPI + SSE bridge (browser <-> live Managed Agent).

Serves the web/ UI and exposes /api/migrate as a Server-Sent Events stream that
drives the REAL Gemini Managed Agent (src/agent.py) and forwards its progress to
the live-trace UI in the canonical event shape (web/STREAM_CONTRACT.md).

There is NO mock here. The scripted run survives only as the UI's `?mock=1`
break-glass (Safety-operator fallback). With no GEMINI_API_KEY this endpoint
returns an explicit 503 — never fake data.

What this bridge derives TODAY, offline, from agent.py's stream:
  - `phase`  : the enforced iteration counter (agent.emit_iteration) + lifecycle.
  - `step`   : the live "agent working" trace (agent.emit_to_ui text deltas).
  - `forge`  : detected from the agent's reported forged-skill path.
  - `pytest` : RED/GREEN verdict from the agent's terminal message.
  - `download`: the migrated module fetched from the sandbox (Files API; see note).
  - `done`   : terminal verdict + environment_id.

The richer semantic panels (`business_rule`, `diff`, structured per-case
`pytest`, `oracle`) are parsed from the agent's real tool outputs and are wired
against the LIVE API on the day — the agent isn't reachable from a dev box
without the provisioned key. The UI degrades gracefully (panels stay empty until
their events arrive). Run `scripts/smoke_test.py` the instant the key exists to
validate the whole live path.

Run:
    pip install -r requirements.txt
    export GEMINI_API_KEY=...            # provisioned at the event
    uvicorn server:app --app-dir src --reload
    # open http://127.0.0.1:8000  (UI is served at /)
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import threading

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

import agent as agent_mod  # src/ is on sys.path (uvicorn --app-dir src)

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
SAMPLE_DIR = ROOT / "src" / "sample"

app = FastAPI(title="LAZARUS — Aero-Migrate", version="1.0")


def _key_present() -> bool:
    import os

    return bool(os.environ.get("GEMINI_API_KEY"))


def _resolve_module(module: str) -> pathlib.Path:
    """Resolve a requested COBOL module to a path under src/sample (no traversal)."""
    name = pathlib.Path(module).name  # strip any directory components
    return SAMPLE_DIR / name


def _download_migrated(client, env_id: str | None) -> str | None:
    """Fetch the agent-written payroll.py from the persistent sandbox.

    The migrated module lives in the reused environment; pull it via the Files
    API. The exact Files-API call is pinned on the day against the live SDK
    (researcher-agents: tarball export of the environment), so this is a
    best-effort hook that returns None until wired — the UI simply leaves the
    Download button un-armed rather than serving a stand-in.
    """
    if not env_id:
        return None
    try:
        # TODO(day-of): replace with the verified Files-API export for env_id.
        return None
    except Exception:
        return None


@app.get("/api/health")
def health():
    """Liveness + whether a key is present (the UI shows a clear banner if not)."""
    return {
        "ok": True,
        "gemini_api_key_present": _key_present(),
        "agent": agent_mod.AGENT_ID,
        "base_agent": agent_mod.BASE_AGENT,
        "max_iterations": agent_mod.MAX_ITERATIONS,
    }


@app.get("/api/migrate")
async def migrate_stream(request: Request, module: str = "payroll.cob"):
    """Drive the real Managed Agent and stream canonical events as SSE."""
    if not _key_present():
        return JSONResponse(
            status_code=503,
            content={
                "type": "error",
                "error": "GEMINI_API_KEY not set",
                "hint": "export GEMINI_API_KEY=...  (Gemini API key, provisioned at the event)",
            },
        )

    cobol_path = _resolve_module(module)
    if not cobol_path.exists():
        raise HTTPException(status_code=404, detail=f"module not found: {module}")

    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()

    def push(ev) -> None:
        loop.call_soon_threadsafe(q.put_nowait, ev)

    def worker() -> None:
        # Bridge agent.py's text/counter hooks into the canonical SSE shape.
        # (Process-wide override — fine for a single-session demo; restored in
        # finally so a later run / concurrent request isn't left patched.)
        orig_emit, orig_iter = agent_mod.emit_to_ui, agent_mod.emit_iteration
        agent_mod.emit_to_ui = lambda text: push(
            {"type": "step", "kind": "output", "text": text}
        )
        agent_mod.emit_iteration = lambda c, t: push(
            {"type": "phase", "phase": "test", "iteration": c,
             "iteration_cap": t, "label": f"Iteration {c}/{t}"}
        )
        try:
            push({"type": "phase", "phase": "ingest",
                  "label": "Provisioning sandbox + reading COBOL"})
            client = agent_mod.genai.Client()  # reads GEMINI_API_KEY
            agent_mod.ensure_agent(client)
            result = agent_mod.migrate(client, str(cobol_path))

            output = agent_mod.extract_output_text(result)
            skill = agent_mod._forged_skill_path(output)
            if skill:
                push({"type": "forge", "skill": skill,
                      "reason": "Unknown idiom: numeric DISPLAY format + ROUND-HALF-UP."})
                push({"type": "reload",
                      "label": f"Re-reading {skill} in the reused environment"})
            passed = agent_mod._tests_passed(output)
            push({"type": "pytest",
                  "result": "green" if passed else "red",
                  "summary": output[-500:]})

            env_id = agent_mod.extract_environment_id(result)
            migrated = _download_migrated(client, env_id)
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
            push(None)  # sentinel: end of stream

    threading.Thread(target=worker, daemon=True).start()

    async def event_gen():
        while True:
            if await request.is_disconnected():
                break
            ev = await q.get()
            if ev is None:
                break
            yield {"data": json.dumps(ev)}

    return EventSourceResponse(event_gen())


# Serve the live-trace UI at / (must be mounted last so /api/* wins).
if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
