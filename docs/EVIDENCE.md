# LAZARUS — live capability evidence (qa-verifier receipts)

Raw artifacts from live verification of the four opt-in agent capabilities, captured
**2026-05-24** against the real Gemini Managed Agents API.

- **SDK (provenance):** `google-genai 2.6.0` — the pinned/deployed version, run via
  `.venv/bin/python` (NOT system `python3`, which is `1.73.1` and uses different class
  names AND wire shapes; see `RESEARCH_MANAGED_AGENTS.md`). **Every receipt below was
  captured on a run that printed `import google.genai as g; g.__version__` inline and
  showed `2.6.0`** (DA L29 gate — a block captured on 1.73.1 does not prove the shipped
  `>=2.6.0` path). A receipt with no `2.6.x` stamp is not accepted.
- **Harness:** `scripts/qa_capture.py` + ad-hoc probes. Reads `GEMINI_API_KEY` from env.

```
=== SDK PROVENANCE (verbatim, prepended to the re-verification run) ===
import google.genai as g; g.__version__ = 2.6.0
module: .../.venv/lib/python3.14/site-packages/google/genai/__init__.py
python: .../.venv/bin/python
```

> **Method note (load-bearing):** rich tool blocks (`google_search_call`, `thought`,
> `code_execution_*`, `function_call`) appear **only in the live STREAM** of
> `step.start`/`step.stop` events. `client.interactions.get(id).steps` **flattens**
> everything to `model_output`, so capability evidence must be read from the stream, not
> the fetched object.

---

## 1 · Web-grounding (`LAZARUS_GROUND`) — VERIFIED

Real `google_search_call` blocks fired on both a full grounded migration and a hard,
un-revealed idiom.

**884s grounded payroll migration — stream step-type histogram:**

```
STREAM step-type histogram: {'model_output': 50, 'function_call': 9, 'function_result': 9,
  'code_execution_call': 37, 'code_execution_result': 37, 'thought': 18,
  'google_search_call': 3, 'google_search_result': 3}
FETCH  step-type histogram: {'model_output': 255}      # get() flattens — note the contrast
usage.total_thought_tokens = 21122
```

**Harder un-revealed idiom (OCCURS DEPENDING ON + SYNCHRONIZED COMP-1) — raw blocks:**

```
step.start google_search_call: {"id": "e8f7lr9u", "type": "google_search_call", "search_type": <web_search|image_search|enterprise_web_search>, "arguments": null}
step.start google_search_call: {"id": "of6ebqyy", "type": "google_search_call", ...}
step.start google_search_call: {"id": "2dkau3cb", "type": "google_search_call", ...}
```

> **Gate-metric caveat:** `usage.grounding_tool_count` returned **`None`** even on a run
> with 3 real searches — the field exists in the schema but the runtime does not populate
> it. **Do not gate on `grounding_tool_count > 0`.** The reliable receipt is the
> `google_search_call` step blocks (unique ids above). `arguments` is `null` at
> `step.start`; the query populates at `step.stop`.

---

## 2 · Thinking level (`LAZARUS_THINKING`) — ACCEPTED, effect not demonstrable

The exact committed shape `agent_config={"type":"dynamic","thinking_level": <lvl>}`:

```
=== agent_config={'type':'dynamic','thinking_level':'high'} (SDK 2.6.0) ===
HTTP OUTCOME: 200 ACCEPTED   status=completed   high total_thought_tokens=2476
second call minimal:         status=completed   minimal total_thought_tokens=3401
```

- **HTTP 200, not 400** on the pinned SDK. (Other shapes — `generation_config`,
  bare `agent_config` without `type:dynamic` — DO `400` on 2.6.0; the committed flat shape
  does not.) The prior "every shape 400s" reading was on `1.73.1` and does not apply.
- **Effect not demonstrable:** thought-token counts do not track the level. `high < minimal`
  here; a 12-sample interleaved run was flat (means 2785 / 2692 / 2665). Per-call variance
  (±~1000) swamps any level effect.
- **Honest label:** *runtime accepts `thinking_level` (HTTP 200) but we cannot demonstrate
  it changes reasoning depth — no depth control claimed.* The `THINKING_REJECTED` fallback
  branch never fires on this shape (defensive-only).

---

## 3 · Cross-run skill library — VERIFIED (discovery + banking)

**Discovery (mounted skill auto-discovered on a FRESH interaction — sentinel test):** an
agent built with a mounted `.agents/skills/cobol-zarflax-idiom/SKILL.md` (containing a
fictional rule + the sentinel token `ZARFLAX-7731`) summarized that rule and echoed the
sentinel on a neutral prompt that never mentioned the skill — proving startup
auto-discovery surfaces the mounted skill into context.

**Banking (real forge output → SKILL.md on disk):**

```
banking target redirected to: <temp dir>     # NOT the real repo
stream done: 36 events, 2022 chars
output mentions skill path: True
banked path returned: <temp>/skills/sign-trailing-separate/SKILL.md
file exists on disk: True
under temp dir (not real repo): True
body length: 748
body head: ---\nname: sign-trailing-separate\n---\n\n# Handling SIGN IS TRAILING SEPARATE in Python ...
VERDICT: BANKING LIVE-VERIFIED
```

The agent's real forge output (path mention + fenced `SKILL.md` body) flows through the
shipped `_bank_forged_skill_from_output` → `_persist_forged_skill` and lands a valid
`SKILL.md` on disk. The mounted-skill fingerprint (`_mounted_skill_fingerprint`) changes
when a skill is added/edited, triggering agent re-registration on the next run.

---

## 4 · Whole-codebase / multi-module — VERIFIED (recovery only)

Two-file system: `PAYMAIN.COB` does `CALL 'TAXSUB' USING WS-GROSS WS-TAX`; the 22.5% rate +
`ROUNDED` live only in `TAXSUB` (via `LINKAGE`). Recovered rule (from the stream):

```
RULE 1 — Cross-Module Tax Calculation Delegation
plain: PAYMAIN accepts a gross pay value and delegates the tax calculation to the
       subprogram TAXSUB via a CALL USING reference, passing WS-GROSS and WS-TAX. TAXSUB
       receives these via its LINKAGE SECTION (LK-GROSS and LK-TAX) and updates the tax
       value in-place, which is then returned to the caller.
cobol_ref: PAYMAIN.COB: CALL 'TAXSUB' USING WS-GROSS WS-TAX.
           and TAXSUB.COB: PROCEDURE DIVISION USING LK-GROSS LK-TAX.
```

The single rule's `cobol_ref` cites **both files** — genuine cross-module recovery (the CALL
relationship and rate-in-the-subprogram fact are invisible from either file alone).

> **Honest caveat:** there is **no multi-module golden** — `golden_io.json` is single-module
> (payroll). A multi-module migration's output is therefore **NOT oracle-byte-verified**.
> Feature 4 is a cross-module **recovery/translation** showcase, not an equivalence-proven
> path.

---

## Bonus — `function_call` block names are internal filesystem ops

The `function_call`/`function_result` blocks seen in migration streams are the agent's
built-in sandbox tooling, not user/custom function registration:

```
function_call: name='list_files'   arguments={}
function_call: name='read_file'    arguments={}
function_call: name='write_file'   arguments={}
```

This confirms `RESEARCH_MANAGED_AGENTS.md` §3 (the managed-agent runtime does not expose
user-facing function calling) — these are internal routing for filesystem I/O.
