# LAZARUS — Architecture

## 1. System Overview

LAZARUS is a **single Managed Agent** running in one Google-hosted Linux sandbox. There is **no multi-agent orchestration** — the Managed Agents API does not expose sub-agent deployment (that lives in Antigravity 2.0 / ADK, not the Gemini API). Everything below happens as a stateful tool-use loop driven by Gemini 3.5 Flash.

```
┌──────────────────────────────────────────────────────────────────────┐
│  Front-end (browser)                                                   │
│   • drop-zone for COBOL          • live interaction.steps trace        │
│   • plain-English logic panel    • COBOL↔Python diff viewer            │
│   • pytest terminal (red→green)  • forged-skill / git-diff panel       │
└───────────────▲───────────────────────────────────────────────┬──────┘
                │ SSE stream (interaction.steps)                  │ user input
                │                                                 ▼
┌───────────────┴───────────────────────────────────────────────────────┐
│  Orchestrator (FastAPI)  src/agent.py                                   │
│   client.interactions.create(agent="lazarus", input=..., stream=True)  │
│   resumes via previous_interaction_id + environment=<id>               │
└───────────────▲───────────────────────────────────────────────────────┘
                │ Interactions API
┌───────────────┴───────────────────────────────────────────────────────┐
│  MANAGED AGENT  (base: antigravity-preview-05-2026 · Gemini 3.5 Flash) │
│  Persistent Ubuntu sandbox (Python 3.12, Node 22, GnuCOBOL pre-warmed) │
│                                                                        │
│   Tools used:  code_execution · filesystem (persistent)               │
│   Skills:      .agents/AGENTS.md + .agents/skills/*/SKILL.md           │
│                                                                        │
│   LOOP:  read COBOL → recover business rules → write Python →          │
│          run ORIGINAL COBOL via GnuCOBOL (oracle) → gen equ. tests →   │
│          pytest → on fail: diagnose → (forge SKILL.md if new idiom) →  │
│          patch → re-run → until GREEN                                  │
└────────────────────────────────────────────────────────────────────────┘
```

## 2. The core loop (write → run → **prove** → self-heal)

1. **Ingest.** The whole COBOL module is sent in one request (Gemini 3.5 Flash 1M-token context, 65,536-token max output for full-file generation).
2. **Recover business logic.** The agent emits a human-readable spec of the rules the COBOL encodes — tax/rounding/edge-cases. This is shown on screen (the "archaeology" beat) and used as the translation contract.
3. **Translate.** The agent writes `payroll.py` to the sandbox filesystem.
4. **Build the oracle.** The agent compiles the *original* COBOL with `cobc -x` and runs it on a battery of inputs, capturing canonical outputs. **This is the ground truth** — not agent-invented assertions.
5. **Generate equivalence tests.** `test_equivalence.py` asserts `python_output == cobol_output` byte-for-byte across the input battery.
6. **Run + iterate.** `pytest` runs; failures stream into the UI (RED). The agent reads the traceback and patches.
7. **FORGE self-heal.** If the failure is an *unknown idiom* (e.g. `COMP-3` packed decimal, `REDEFINES`, `OCCURS DEPENDING ON`), the agent writes a new `.agents/skills/<idiom>/SKILL.md` describing how to handle it, commits it, hot-reloads the agent, and re-runs. Tests go **GREEN**.

## 3. Why the differential oracle matters (the judge-proofing)

The strongest attack on any "AI migrates code" demo: *"The agent wrote the code AND the tests, so passing proves internal consistency, not correctness."* (A DeepMind judge will ask exactly this.)

LAZARUS answers it structurally: the **oracle is the original COBOL program's real output**, produced by a real compiler (GnuCOBOL) the agent did not write. Equivalence is therefore *falsifiable*. If the Python rounds a packed-decimal differently than the mainframe would, the diff is non-zero and the test is RED — visibly, on stage.

```
   COBOL source ──cobc──> native binary ──run(inputs)──> canonical_output  ┐
                                                                           ├─ assert ==
   COBOL source ──Gemini──> payroll.py    ──run(inputs)──> python_output   ┘
```

**Fallback if `apt`/network for GnuCOBOL is gated in preview:** ship a pre-computed `golden_io.json` (input→output pairs captured from a real COBOL run before the event) and diff against that. Same guarantee, no live compile.

## 4. Managed Agents configuration

```python
from google import genai
client = genai.Client()

# One-time: create the reusable custom agent
client.agents.create(
    id="lazarus",
    base_agent="antigravity-preview-05-2026",   # Gemini 3.5 Flash managed agent
    system_instruction=open(".agents/AGENTS.md").read(),
    base_environment="lazarus-env",              # persistent: GnuCOBOL + repo skeleton
)
```

- **State dimensions are independent:** `previous_interaction_id` carries chat history; `environment=<id>` carries the sandbox files. We keep the environment (so forged skills + the oracle binary persist) while threading the conversation.
- **Skills are config:** `.agents/AGENTS.md` (persona + loop policy) and `.agents/skills/<name>/SKILL.md` (auto-loaded idiom handlers). FORGE writes new ones at runtime.
- **Observable steps:** every thought / tool call / code run streams via `interaction.steps` → rendered as the live "agent working" UI (this *is* the demo surface).

### Supported features we rely on (and ONLY these)
✅ `code_execution` (Bash/Python) · ✅ persistent filesystem · ✅ `AGENTS.md`/`SKILL.md` · ✅ `interaction.steps`

### Explicitly NOT used (documented as unsupported via Managed Agents API)
❌ sub-agent orchestration · ❌ `mcp` · ❌ `computer_use` · ❌ `function_calling` · ❌ `file_search`

## 5. Components to build

| Component | File | Owner role |
|---|---|---|
| Managed agent setup + loop driver | `src/agent.py` | Agent engineer |
| GnuCOBOL oracle + byte-diff harness | `src/differential_oracle.py` | Agent engineer |
| Live trace UI (steps + diff + terminal) | `web/` | Front-end engineer |
| `AGENTS.md` + seed skills | `.agents/` | Agent engineer |
| Golden COBOL sample + input battery | `src/sample/` | Utility/QA |
| Fallback cache (`golden_io.json`, recorded run) | `src/sample/` | Utility/QA |

## 6. Data flow for the live demo

`drop payroll.cob` → `interactions.create(stream=True)` → steps stream to UI → sandbox writes Python + compiles COBOL + runs both + pytest → RED → forge `SKILL.md` (git diff animates) → reload → pytest GREEN → `download` migrated module from the persistent environment.

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Auto-iteration non-deterministic / loops forever | Hard cap iterations (≤4) with a visible counter; cached green run as fallback |
| GnuCOBOL install gated in preview | Pre-warm install into `base_environment` (persists) **or** `golden_io.json` fallback |
| Cold-start latency at 0:00 | Pre-warm sandbox with a `background=true` heartbeat before walking on |
| COBOL too large for clean 2-min run | Curated ~150-line module with one reproducible bug class (decimal/rounding) |
| Beta API breaking change | Pin `-preview-05-2026`; smoke-test the morning of; record backup video |
