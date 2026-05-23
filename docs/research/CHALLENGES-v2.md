# CHALLENGES v2 — Devil's Advocate on the LIVE demo (owner: devils-advocate)

> Scope: the v2 completion plan (docs/plans/2026-05-23-completion-v2.md). A skeptical
> DeepMind judge AND an investor watch the 2-minute LIVE run on the real key and fact-check
> everything. The question is not "does the mock look done" — it's "does a LIVE run on the
> provisioned key drive EVERY panel from REAL agent work, honestly."
>
> Format per item: **claim / attack / evidence / verdict** (CONFIRMED · NEEDS FIX · FALSE).
> Stop-the-line items go to team-lead immediately.
>
> v1 challenges C1–C16 live in CHALLENGES.md and are not re-litigated here unless the live
> path changes the verdict.

---

## SCOREBOARD

> **UPDATE — wiring now COMMITTED (64d8579 "Wire LIVE path to populate all panels").** Verified
> HEAD's server.py carries the wiring (not reverted). Two follow-on improvements landed (working
> tree) that close my two minor nits: (a) `to_pytest_event` now sets `source:"agent_pytest"` so
> the UI distinguishes the agent's own marker-pytest from the orchestrator's `differential_oracle`
> harness — honest symmetry; (b) `.agents/AGENTS.md` reinforces the L8 path pin ("write the final
> module to /workspace/payroll.py … writing it elsewhere leaves those panels empty"). 77/77 pass.
>
> **UPDATE 18:37 — the wiring LANDED (uncommitted working tree).** server.py grew 277→419
> lines; integration-eng wired every helper. All of L1/L3/L4/L7/L8 are now FIXED IN CODE and
> covered by 10 new tests (77/77 pass). The only remaining gate is LIVE EVIDENCE (L2/L6),
> which I cannot produce (no key). Verdicts below updated; the original NEEDS-FIX analysis is
> kept for the record under each item.

| # | Item | Severity | Verdict |
|---|---|---|---|
| L1 | LIVE run populates EVERY panel (not just the mock) | stop-the-line | **FIXED IN CODE (pending live)** — server.py now emits `diff`, runs the local differential-oracle pytest fallback, fallback rules, and progressive phases. Tested by test_safety_net_populates_every_panel_without_markers (no markers → diff + 10-case oracle pytest + ≥3 rules + banner). |
| L2 | Downloaded payroll.py is the agent's REAL sandbox output (Files API) | load-bearing (honesty) | **PENDING LIVE** — code path is real (Files-API tarball extract of `/workspace/payroll.py`, now pinned in the prompt); never exercised on a key. Needs qa live evidence. |
| L3 | Local-oracle pytest presented truthfully (orchestrator IS the harness) | load-bearing (honesty) | **CONFIRMED + WIRED** — server.py:308 uses `oracle_harness_pytest_event` (source="differential_oracle", `oracle_equivalence[...]` case names, honest summary). NOT framed as the agent's own pytest. Tested. |
| L4 | Phase progression is REAL (agent milestones), not faked timing | medium | **FIXED IN CODE (pending live)** — `phase_for_text` drives a forward-only, dedup'd rail off the streamed step text; the iteration counter no longer jumps the rail to TEST. Tested by test_phase_rail_advances_progressively (monotonic). |
| L5 | golden_io.json (local truth) vs agent's own cobc — conflated? | load-bearing (honesty) | **CONFIRMED honest** — golden is the PRIMARY ground truth; agent live-refresh is opportunistic; prompt + oracle code keep them distinct. No conflation. |
| L6 | 2-minute story legible for a judge | demo (45%) | **PENDING LIVE** — wiring removes the empty-panel risk; final legibility + weakest moment need qa's real stream. |
| L7 | Missing `diff` made the COBOL→Python card VANISH (reveal-gated) | demo (45%) | **FIXED IN CODE** — `diff_event(cobol, migrated)` emitted from real sources → translate card reveals. Tested (diff right-side == the agent's real module). |
| L8 | Live download/diff/oracle depended on an UNPINNED payroll.py path | load-bearing (honesty) | **FIXED IN CODE (pending live)** — agent.py:136 now pins "write the final module to /workspace/payroll.py", matching the extractor. qa to confirm the agent honors it live. |

### THE falsifiability guarantee — now ENFORCED + TESTED
`test_safety_net_goes_red_when_module_diverges`: a naive port (banker's rounding) that FAILS the
tie cases makes the orchestrator's differential oracle go **RED** with per-case bytes and the
verdict **INCOMPLETE** — *even when the agent's prose claims "all tests pass."* The verdict is
gated on the orchestrator's real byte-comparison (server.py:312, `passed = pytest_ev["result"]
== "green"`), not the agent's self-report. This is the project's core honesty claim, and it is
now provably true: the agent cannot fake equivalence past the oracle. STRONG.

---

## L1 — Does the LIVE run populate EVERY panel, or only the mock?  — NEEDS FIX (STOP-THE-LINE)

- **Claim (v2 plan, Definition of Done):** "A single LIVE run on the real key drives the whole
  UI — phases advance; rules, diff, oracle, per-case RED→GREEN, forge, and Download all
  populate from REAL agent work."
- **Attack:** read what `src/server.py::_run_migration` actually pushes on the live path, panel
  by panel, and find the ones that stay empty when the agent doesn't print perfect markers.
- **Evidence (committed `src/server.py`, lines 116–195, verified against disk):**
  - **`diff` (COBOL↔Python viewer): NEVER EMITTED.** No `diff` event is pushed anywhere in
    `_run_migration`. `event_transform.diff_event()` exists (event_transform.py:147) but is not
    called. The renderer has a full `on_diff` panel (renderer.js:218) and STREAM_CONTRACT §4
    documents it — so on a live run this panel sits EMPTY. This is plan root-cause #4, unfixed.
  - **`pytest` per-case: marker-only, EMPTY fallback.** server.py:166–174 builds the structured
    pytest ONLY from the agent's `LAZARUS_ORACLE_JSON` marker. If the agent omits it (the plan
    itself says the agent "doesn't reliably print" markers), the fallback pushes
    `{"result": ..., "cases": []}` — an EMPTY test terminal with no RED→GREEN. The local
    differential-oracle fallback the plan mandates ("run differential_oracle locally against
    golden_io.json to produce the structured pytest + diff deterministically") is NOT wired.
    `oracle_harness_pytest_event()` exists for exactly this but is uncalled.
  - **`business_rule`: marker-only.** server.py:148–150 emits rules only from `LAZARUS_RULE`
    markers. `business_rules_fallback()` (event_transform.py:209, ≥3 real rules) is NOT called,
    so the archaeology panel is empty if the agent omits markers.
  - **`phase` progression: not progressive.** Only `ingest` (server.py:136) + a per-iteration
    `test` phase (server.py:130) fire. `recover / translate / oracle / forge / done` never
    advance off the stream. `phase_for_text()` exists (event_transform.py:135) but is unwired.
    This is plan root-causes #1 and #3, unfixed.
  - **What IS wired and real:** the `oracle` banner (from golden_io.json), `forge`/`reload`
    (when the agent prints a SKILL.md path), the Files-API `download`, and `done`.
- **Verdict: NEEDS FIX — STOP-THE-LINE.** The honest, deterministic building blocks integration-eng
  wrote in `event_transform.py` (diff_event, oracle_harness_pytest_event, phase_for_text,
  business_rules_fallback) are correct and truthful — but `src/server.py` does not call them.
  As committed, a LIVE run with an imperfect-marker agent shows: empty diff panel, empty (or
  prose-only) test terminal, possibly empty rules, and a phase rail that jumps to "test". That
  is the mock looking complete while the live run is not. Wiring required in `_run_migration`:
  (1) fetch payroll.py (already have `_download_migrated`), emit `diff_event(cobol, payroll.py)`;
  (2) run `differential_oracle.prove_equivalence(payroll.py, golden_io.json)` and emit
  `oracle_harness_pytest_event(records)` as the deterministic pytest (markers stay the fast path);
  (3) `business_rules_fallback()` when no markers; (4) drive `phase_for_text()` from the streamed
  step text for progressive phases. Escalated to team-lead / integration-eng (task #1).

## L3 — Is the local-oracle pytest presented HONESTLY (not as the agent's own test run)?  — CONFIRMED (design), UNWIRED

- **Claim (my brief #3):** integration-eng will derive the structured pytest by running the
  differential oracle LOCALLY (agent's python vs golden_io.json real-cobc bytes). Is that
  truthful (the orchestrator IS the oracle harness) or misleadingly framed as the agent's own
  test run?
- **Attack:** if the UI labels orchestrator-run results as "the agent ran pytest and got
  RED→GREEN," that's a fabricated provenance a judge can puncture.
- **Evidence:** `event_transform.oracle_harness_pytest_event()` (event_transform.py:160) is
  written for exactly this and is HONEST:
  - case names → `oracle_equivalence[...]` (not `test_...`, so it doesn't masquerade as the
    agent's pytest);
  - sets `ev["source"] = "differential_oracle"`;
  - summary appends "(differential oracle: agent python vs real-cobc golden bytes)".
  - Its docstring states the intent verbatim: "these records come from src/differential_oracle.py
    running the agent's payroll.py against the real-cobc golden bytes, NOT from the agent's own
    pytest stdout. Truthful labeling keeps the demo honest."
- **Verdict: CONFIRMED honest BY DESIGN — but UNWIRED (see L1) and the UI must SHOW the
  provenance.** Two conditions for sign-off: (a) server.py actually calls this function (not
  `to_pytest_event`, which uses generic `test_equivalence[...]` names with no source label);
  (b) the renderer surfaces `source`/the honest summary so a judge SEES it's the oracle harness,
  not a claimed agent self-test. Today renderer.js `on_pytest` ignores `ev.source` — it would
  render `oracle_equivalence[...]` rows (good) but drop the "differential oracle" provenance
  unless it's in `summary` (it is — the summary carries it). Acceptable if server.py uses the
  harness event; flag to frontend-eng to keep the summary visible. No overclaim found in code;
  the risk is purely that the wrong (unlabeled) event ships.

## L5 — golden_io.json (local truth) vs the agent's own cobc — conflated? Is "differential oracle = real COBOL" still honest?  — CONFIRMED honest

- **Claim:** golden_io.json is LOCAL pre-captured ground truth; the agent independently installs
  cobc + generates its own. My brief asks whether these are conflated and whether the end-to-end
  "real COBOL" claim survives.
- **Evidence:**
  - golden_io.json self-documents its role unambiguously: "PRIMARY ORACLE GROUND TRUTH … does
    NOT require a live compiler … When cobc OR a mounted Linux binary IS available,
    verify_golden_against_binary() re-confirms these bytes are fresh — but the equivalence diff
    never depends on it." capture_status: "REAL — compiled + run with live cobc, not computed."
  - The agent prompt (agent.py:137–146) keeps them distinct: PRIMARY = golden_io.json as ground
    truth; LIVE REFRESH = micromamba/conda-forge gnucobol to "confirm golden_io.json is still
    fresh — but the equivalence check stays byte-for-byte against the golden bytes."
  - v1 C5 independently verified all 10 golden cases byte-for-byte against a real GnuCOBOL 3.2.0
    compile, and payroll.py 10/10 byte-equivalent. (CHALLENGES.md C5.)
- **Verdict: CONFIRMED honest.** No conflation: golden is the deterministic floor (real cobc
  bytes captured ahead of time); a live cobc run is opportunistic freshness only. The
  "differential oracle = real COBOL output" claim is true either way — the bytes ARE real
  compiler output, captured earlier or refreshed live. This is the project's strongest honesty
  position; protect it. (One residual: if the live run claims "the agent just compiled COBOL in
  the sandbox," that needs qa live evidence — L2-adjacent — since the demo's deterministic path
  is golden, not a live compile.)

---

## PENDING — require qa-verifier LIVE evidence (no GEMINI_API_KEY on the devils-advocate box)

- **L2 (download is the agent's real sandbox output):** `_download_migrated` →
  `_fetch_env_tarball` (Files-API `environment-<id>:download`) → `_extract_migrated_from_tar`
  looks for `workspace/payroll.py`. Real path, never run on a key. Need: qa confirms
  GET /api/download/{run_id} returns a runnable payroll.py pulled from the sandbox, and that the
  agent actually wrote it to `/workspace/payroll.py` (the prompt says "write payroll.py" but does
  NOT pin `/workspace/` — possible path mismatch with the extractor's `workspace/` filter).
- **L4 (phase realness):** confirm live phases advance through recover/translate/oracle/forge,
  not just ingest+test — contingent on the L1 wiring landing.
- **L6 (2-min legibility + weakest moment):** assessed once a real run exists.

> I cannot run the live path (no key). All PENDING items need qa-verifier's captured live stream.

---

## L7 — The missing `diff` event makes the headline panel VANISH (not just empty)  — NEEDS FIX

- **Claim:** the UI degrades gracefully — empty panels just don't show.
- **Attack:** trace what the progressive-reveal renderer does when an event never arrives.
- **Evidence:** `renderer.js` reveals a flow card only when its handler fires `_revealCard`:
  `on_diff` → `_revealCard('translate')` (renderer.js:269); `on_business_rule` → `'recover'`
  (263); `on_pytest`/`on_oracle` → `'test'` (303/350); `on_forge` → `'forge'` (363). Because
  server.py never emits `diff`, `on_diff` never fires, so the **`card-translate` (COBOL→Python
  side-by-side) never reveals at all** — the single most compelling "migration" beat is ABSENT
  from a live run, while it's front-and-center in the mock. Same mechanism shrinks the rules and
  proof cards when markers are absent.
- **Verdict: NEEDS FIX.** This is the concrete demo-coherence cost of L1: the live demo is not
  just "a bit empty," it's MISSING its headline translation panel. The reveal logic itself is
  honest (no faked empty cards) — the fix is to actually emit `diff` (L1).

## L8 — Live download/diff/oracle all depend on an UNPINNED payroll.py path  — NEEDS FIX (cheap)

- **Claim:** the downloaded payroll.py is the agent's real sandbox output (Files API).
- **Attack:** the extractor (`_extract_migrated_from_tar`, server.py:91–93) looks for
  `workspace/payroll.py` (or `.../workspace/.../payroll.py`). But the agent prompt (agent.py:136)
  only says "Translate to Python (write payroll.py)" — it does NOT pin `/workspace/payroll.py`,
  and `.agents/AGENTS.md` doesn't either. The only `/workspace` reference in the prompt is the
  conda env path. If the agent writes payroll.py to its CWD (which may not be `/workspace`) or a
  repo subdir, the extractor's `"workspace" in path` requirement fails → `_download_migrated`
  returns None → Download stays un-armed AND (once L1 lands) the local oracle + diff have no
  payroll.py to run against → those panels stay empty for the WRONG reason.
- **Verdict: NEEDS FIX (cheap, high-leverage).** Pin the path in the prompt + AGENTS.md: "write
  the migration to `/workspace/payroll.py`." Then download, diff, and the local oracle all find
  the real artifact deterministically. qa to confirm live the agent honors it (NEEDS-VERIFY).

---

## Honesty WINS confirmed this pass (lean into these with the judge)

- **C13 (COMP-3) — LANDED CORRECTLY in the live surface.** The #1 v1 honesty fix is done:
  `web/mock/mock-run.json:49` now states verbatim "(COMP-3 storage is irrelevant — DISPLAY
  de-edits identically regardless.)" and attributes the RED to banker's-vs-half-up rounding.
  The forge is named `numeric-display-rounding`. server.py:160 + agent.py:154 carry the same
  honest framing. Remaining COMP-3 mentions are legitimate (the COBOL source genuinely declares
  COMP-3 fields; the syntax highlighter lists it as a keyword) — not the false "COMP-3 is what
  fails" claim. Verified by grep across web/ + src/ + docs.
- **C16 (hot-reload) — GONE from the live surface.** STREAM_CONTRACT.md:108 now says "(no
  mid-run hot-reload — that's unverified)"; README:28 explicitly disclaims "mid-run hot-reload
  or cross-run accumulation." No "Hot-reloading" label remains in the UI path.
- **Test suite is HONESTLY scoped.** All 67 tests pass. test_server.py is explicit: "all
  runnable WITHOUT a key … The live Gemini path itself is validated by scripts/smoke_test.py."
  Crucially, the tests do NOT falsely assert the diff/local-oracle fallback works — they only
  exercise the marker path that server.py actually implements. So a green test run does NOT
  imply a complete live path (the gap in L1 is real, not hidden by a passing test).
- **L3/L5 oracle honesty (design) is sound** — the orchestrator-as-harness labeling and the
  golden-vs-live distinction are both truthful; the only risk is shipping the unlabeled event
  (L1 wiring must use `oracle_harness_pytest_event`, not `to_pytest_event`).

---

## INDEPENDENT DRIVE (devils-advocate, no API key) — the wired path, verified by my own hand

I drove the wired server.py end-to-end myself via TestClient, stubbing ONLY the network
boundary (genai client + agent.migrate + Files-API fetch); diff/oracle/phases/rules/download
all ran the REAL server code. Two runs:

1. **No-marker safety net** (agent prints no LAZARUS_* markers, ships the correct sample
   payroll.py): event stream =
   `phase×ingest, step…, recover, translate, oracle, test, business_rule×3, oracle, diff, pytest,
   download, done`. Phases advance ingest→recover→translate→oracle→test→done. `diff` present
   with the agent's real module on the right. `pytest`: result=green, source="differential_oracle",
   10 cases, summary "10 passed, 0 failed (differential oracle: agent python vs real-cobc golden
   bytes)". download = the agent module. verdict EQUIVALENT. EVERY panel populated from real
   output with ZERO markers — the mock-only-completeness risk is gone.

2. **Falsifiability (the one that matters)** — agent OVER-claims "All equivalence tests pass"
   but ships a banker's-rounding module: oracle result=**RED** (source=differential_oracle),
   failing cases `oracle_equivalence[1.00]` (0000000.77 vs 0000000.78) and
   `oracle_equivalence[5.00]` (0000003.87 vs 0000003.88), verdict **INCOMPLETE**. The verdict
   follows the ORACLE, not the agent's claim. **The agent cannot fake equivalence past the
   oracle.** This is the project's strongest honesty position, verified independently.

3. **Crash path now HONEST (my nit #1 closed) — verified + COMMITTED (cdafd8c).** Agent
   over-claims "All equivalence tests pass" but ships a module that RAISES on run:
   `_run_oracle_pytest` now returns an EXPLICIT RED ("differential oracle could not run the
   agent's payroll.py: …", source=differential_oracle) instead of None→coarse-prose-verdict,
   so verdict=**INCOMPLETE**. None is now reserved ONLY for an unreadable golden capture. I
   independently drove it (crash module + agent claiming pass → RED + INCOMPLETE). Test:
   `test_crashing_module_goes_red_not_falsely_green`.

4. **Provenance symmetry (my nit #2 closed) — COMMITTED (cdafd8c).** `to_pytest_event` now
   tags `source="agent_pytest"` (names `test_equivalence[...]`); `oracle_harness_pytest_event`
   overrides to `source="differential_oracle"` (names `oracle_equivalence[...]`). UI can
   distinguish the two on BOTH paths. Tests: `test_agent_marker_pytest_is_labeled_agent_source`,
   `test_to_pytest_event_labels_agent_source`.

**Final backend state:** HEAD f6e568f (L8 AGENTS.md pin) atop cdafd8c (both nits). Python
working tree clean; 80/80 tests pass. All of L1-L8 + both nits resolved and COMMITTED. Only
remaining gate: qa's live evidence (L2/L6).

## Bottom line for sign-off (devils-advocate, task #4)

**GATE 1 — WIRING — CLEARED.** server.py now emits diff + local-oracle pytest + fallback rules
+ progressive phases; the prompt pins /workspace/payroll.py. 77/77 tests pass and I independently
drove BOTH the happy path (every panel populates, no markers needed) and the falsifiability path
(over-claiming agent + wrong module → oracle RED → verdict INCOMPLETE). Code is complete AND honest.

**GATE 2 — LIVE EVIDENCE — STILL OPEN (the only thing between here and sign-off).** qa-verifier
must run on the real key (post-wiring) and show: the full ordered stream with a real `diff`,
populated `pytest` cases, and a real downloaded `/workspace/payroll.py` pulled via the Files API,
within the 2-min budget. I have NO key; my drive stubs the network boundary, so it proves the
ORCHESTRATION is correct but NOT that the live Gemini agent honors the contract. Residual
live-only risks: L2 (real download), L8 (agent honors the pinned path), L6 (2-min legibility +
weakest moment).

Honesty posture is STRONG: C13/C16 landed; oracle framing truthful and provenance-labeled; the
verdict provably follows the oracle, not the agent's claim; tests honestly scoped. The remaining
risk is purely whether the LIVE agent behaves as the (now-correct) orchestrator expects.
