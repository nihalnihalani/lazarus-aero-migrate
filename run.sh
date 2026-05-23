#!/usr/bin/env bash
# ============================================================================
# LAZARUS — run the project end-to-end.
#
#   ./run.sh                 start the live console at http://127.0.0.1:8000
#   PORT=9000 ./run.sh       use a different port
#
# One server (FastAPI/uvicorn) serves BOTH the web UI (at /) and the API
# (/api/*). The LIVE migration needs GEMINI_API_KEY; without it the UI still
# loads and  ?mock=1  replays the cached run (real GnuCOBOL golden bytes).
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
URL="http://127.0.0.1:${PORT}"
VENV=".venv"
PY="${VENV}/bin/python"

bold() { printf "\033[1m%s\033[0m\n" "$1"; }

# ── 1. virtualenv + dependencies ────────────────────────────────────────────
if [ ! -x "$PY" ]; then
  bold "[setup] creating .venv and installing dependencies (first run only)…"
  python3 -m venv "$VENV"
  "${VENV}/bin/pip" install --quiet --upgrade pip
  "${VENV}/bin/pip" install --quiet -r requirements.txt
fi
# idempotent: (re)install if a core import is missing
if ! "$PY" -c "import fastapi, uvicorn, sse_starlette, google.genai" 2>/dev/null; then
  bold "[setup] installing dependencies…"
  "${VENV}/bin/pip" install --quiet -r requirements.txt
fi

# ── 2. environment checks (non-fatal) ───────────────────────────────────────
echo
if [ -n "${GEMINI_API_KEY:-}" ]; then
  echo "✓ GEMINI_API_KEY detected — live migration enabled."
else
  echo "⚠ GEMINI_API_KEY not set — the LIVE agent won't run."
  echo "    export GEMINI_API_KEY=...   then re-run, OR use ?mock=1 (no key needed)."
fi
if command -v cobc >/dev/null 2>&1; then
  echo "✓ GnuCOBOL present — $(cobc --version | head -1)"
else
  echo "ℹ GnuCOBOL (cobc) not found — the oracle uses the committed golden_io.json (fine)."
fi

# ── 3. start the server ─────────────────────────────────────────────────────
echo
bold "starting LAZARUS → ${URL}   (Ctrl+C to stop)"
"$PY" -m uvicorn server:app --app-dir src --host 127.0.0.1 --port "$PORT" &
SERVER_PID=$!
trap 'echo; echo "stopping LAZARUS…"; kill "$SERVER_PID" 2>/dev/null || true; exit 0' INT TERM

# ── 4. wait for health, print instructions, open the browser ────────────────
for _ in $(seq 1 40); do
  curl -fsS "${URL}/api/health" >/dev/null 2>&1 && break
  sleep 0.5
done
echo
echo "────────────────────────────────────────────────────────────"
bold "  LAZARUS is live →  ${URL}"
echo "  • drop a COBOL module, or click 'use the sample — payroll.cob'"
echo "  • no key?  ${URL}/index.html?mock=1   (22s cached replay)"
echo "  • a real live run is ~8–9 min (real sandbox + compiler + proof)"
echo "  • run the tests:  ${PY} -m pytest -q"
echo "────────────────────────────────────────────────────────────"
{ command -v open >/dev/null 2>&1 && open "$URL"; } \
  || { command -v xdg-open >/dev/null 2>&1 && xdg-open "$URL"; } || true

# ── 5. keep running until the server exits / Ctrl+C ─────────────────────────
wait "$SERVER_PID"
