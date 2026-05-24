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
| L2 | Downloaded payroll.py is the agent's REAL sandbox output (Files API) | load-bearing (honesty) | **GAP FOUND (qa) → MITIGATED + mechanism VERIFIED; pending end-to-end live stream.** Live Files-API tarball TIMED OUT → diff+download blanked (see L9). Committed fallback (49cc1d9) scrapes the agent's echoed module (source="model_output"). qa + I independently confirmed the scrape recovers the real module + passes oracle 10/10. Awaiting qa's full live stream (diff fires + download returns it + budget). |
| L3 | Local-oracle pytest presented truthfully (orchestrator IS the harness) | load-bearing (honesty) | **CONFIRMED + WIRED** — server.py:308 uses `oracle_harness_pytest_event` (source="differential_oracle", `oracle_equivalence[...]` case names, honest summary). NOT framed as the agent's own pytest. Tested. |
| L4 | Phase progression is REAL (agent milestones), not faked timing | medium | **FIXED IN CODE (pending live)** — `phase_for_text` drives a forward-only, dedup'd rail off the streamed step text; the iteration counter no longer jumps the rail to TEST. Tested by test_phase_rail_advances_progressively (monotonic). |
| L5 | golden_io.json (local truth) vs agent's own cobc — conflated? | load-bearing (honesty) | **CONFIRMED honest** — golden is the PRIMARY ground truth; agent live-refresh is opportunistic; prompt + oracle code keep them distinct. No conflation. |
| L6 | 2-minute story legible for a judge | demo (45%) | **RESOLVED via L10 → STRICTLY LIVE (user's call).** Not a 2-min story; reframed as "watch a real multi-minute migration + byte-for-byte proof." Live narrative drafted (DEMO_NARRATIVE_live-DRAFT.md). Legibility now hinges on L11 (UI must visibly progress). |
| L10 | LIVE latency (8–12+ min) vs the "2-minute" framing | demo (45%, decisive) | **RESOLVED (user decision): STRICTLY LIVE in-slot, no mock lead** — user accepts the multi-minute reality; value = real work + proof, not speed. Honest live narrative drafted. Mock stays `?mock=1` break-glass only. |
| L11 | Does the live UI visibly PROGRESS during the long run, or look FROZEN? | demo (45%, decisive) | **OPEN — #1 risk for strictly-live.** If the agent streams step text, the banner/trace move (alive). If silent until the end-burst, the screen looks hung for minutes → "watch it work" collapses. qa to confirm; if frozen, add live-progress surfacing (elapsed timer + step.delta streaming) BEFORE the slot. |
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

## L9 — LIVE Files-API tarball TIMES OUT → diff + download blank (qa-found)  — MITIGATED + VERIFIED, pending live stream

- **EVIDENCE (qa-verifier, TWO live runs on the real key, runs 5561f1cf / 1ccbf78f, pre-fix):**
  `_fetch_env_tarball()` TIMED OUT — the whole-environment tarball is too large/slow (30s hard
  timeout failed; even 180s+ never returned). At that commit, on a LIVE demo: `diff` + `download`
  BOTH failed to fire → COBOL↔Python panel EMPTY, Download never armed, GET /api/download → 404.
  Root cause is fundamental: the Files API only documents the WHOLE-ENV tarball
  (`environment-{id}:download`); NO per-file helper (findings-agents.md), and the agent installs a
  conda gnucobol prefix into /workspace, bloating the tarball. qa's read is correct: HONEST failure
  (empty panels), NOT fake success — the module IS correct in the sandbox, just not retrievable.
- **MITIGATION (integration-eng, COMMITTED 49cc1d9 + tested):** tarball-None now falls back to
  `event_transform.python_module_from_output(output)` — the largest python-ish fenced ```python
  block the agent echoes in its own output — tagged `source="model_output"` (honest provenance:
  the agent's REAL code, from its output stream, not the disk image). Files-API tarball stays
  PRIMARY (`source="files_api"`). diff + oracle pytest + download all repopulate. Tests:
  `test_tarball_timeout_falls_back_to_model_output`, `test_tarball_and_output_both_empty_keeps_panels_honest`.
- **INDEPENDENTLY VERIFIED (devils-advocate + qa, deterministic, no key):** qa confirmed the LIVE
  agent echoes a complete 38-line module (Decimal+ROUND_HALF_UP+__main__) and the scrape recovers
  it + passes the oracle 10/10. I REPRODUCED it with the exact server functions: sample module in a
  fenced ```python block amid prose → `python_module_from_output` recovers 55/55 lines byte-identical
  → `prove_equivalence` 10/10 byte-for-byte vs golden → pytest green, source=differential_oracle.
  Negative control: a 3-line truncated block is correctly NOT scraped (≥5-line guard).
- **Verdict: MITIGATED + mechanism VERIFIED — pending only qa's END-TO-END live stream.** The
  scrape works on the agent's REAL echoed output (not just the synthetic test). Remaining: qa's
  in-flight full live stream confirming diff fires + download returns the module + source label +
  wall-clock on the real key. Belt-and-suspenders option if ever flaky: an explicit
  `LAZARUS_MODULE:` marker so recovery doesn't depend on incidental echo; and/or install gnucobol
  outside /workspace to shrink the tarball.

---

## L10 — LIVE latency (8–12+ min) vs the "2-minute" framing  — RESOLVED: STRICTLY LIVE (user's call)

> **DECISION (user, via team-lead):** STRICTLY LIVE in-slot, no mock lead. The user accepts the
> multi-minute reality (consistent with their original "no mock" stance). The value is reframed
> from speed to authenticity: watch a real agent do real work, ending in a byte-for-byte proof.
> The replay-led draft is SUPERSEDED; the honest live narrative is in
> `docs/DEMO_NARRATIVE_live-DRAFT.md`. This is a LEGITIMATE, honest choice — arguably MORE honest
> than replay-led (zero risk of a replay being mistaken for live). The new risk it creates is L11
> (the UI must visibly progress, not look frozen). Mock stays `?mock=1` break-glass ONLY.

- **Claim (v2 plan, throughout):** a "2-minute LIVE demo" on the real key; "Live default;
  `?mock=1` break-glass only" (web/index.html `mode-live`, app.js, mock note).
- **EVIDENCE (qa-verifier, 3 live runs on the real key):** the live end-to-end is NOT a 2-minute
  experience. Measured: run #1 events burst ~444s / done ~501s (~8.3 min); run #3 still on
  iteration 1 at 12+ min. Time-to-first-panel is SEVERAL MINUTES of an empty/working screen (the
  agent runs one long silent interaction, then the panels burst at the end). The scripted
  `mock-run.json` timeline is 22.2s total — it fits a 2-min slot; a live run does not.
- **Verdict: NEEDS FIX — but it's DEMO STRATEGY, not code, and the honest fix already exists.**
  For a timed 2-min slot the realistic vehicle is the `?mock=1` cached replay. This is HONEST
  *iff* it's narrated as what it is — the mock self-documents ("Break-glass fallback... mirrors a
  real LAZARUS migration"), is derived from REAL GnuCOBOL golden bytes (golden_io.json), and the
  UI labels it "BREAK-GLASS · cached run" / clock "cached". So:
  - DO: lead the timed demo with the cached replay, narrated as "a replay of a real run," and show
    the live system as PROOF it's real (e.g. a pre-warmed live run finishing in the background, or
    the live download/verdict shown as evidence). qa already confirmed a real live run ends
    EQUIVALENT with the agent's real module — that's the proof.
  - DON'T: present the cached replay AS a live run, or promise "watch it run live in 2 minutes" —
    the latency makes that false and a judge timing it would catch the empty screen.
  - INVERT the framing in the demo narrative: "live by default" is the right PRODUCT default but
    the WRONG demo-slot default. The README/DEMO_SCRIPT should say the 2-min demo uses the cached
    replay of a real run, with the live path runnable on request (it just takes ~8–12 min).
- **Owners:** team-lead / doc-keeper (demo narrative + DEMO_SCRIPT framing). [Resolved — the
  decision is strictly-live; doc-keeper applies `DEMO_NARRATIVE_live-DRAFT.md` to DEMO_SCRIPT.]

## L11 — Does the live UI visibly PROGRESS during the long run, or look FROZEN?  — OPEN (#1 strictly-live risk)

- **Why this is now decisive:** with the strictly-live decision (L10), the demo IS the multi-minute
  live run. The "watch a real agent work" narrative HOLDS ONLY IF the screen visibly moves during
  the run. qa observed the agent does "one long silent interaction, then bursts at the end."
- **Attack:** if that means the WORKING banner sits on one line for minutes with no movement, a
  judge sees a HUNG app, not a working agent — the whole strictly-live value prop collapses into
  "staring at a frozen screen."
- **Code reality:** server.py's `emit_step` pushes a `step` event per streamed chunk and updates
  `_setWorking({action})`; the renderer advances the banner + trace + phase rail off that. So the
  UI moves IFF the AGENT streams intermediate `step.delta` text during the run. If the agent goes
  dark until the end, the UI is stuck regardless of the wiring.
- **CONFIRMED FROZEN (qa's full live stream + my raw-stream analysis) → FIX LANDING (task #6).**
  I analyzed `/tmp/sse_full.jsonl` (153 events, 19-min run): the 134 `step` events are all chunks
  of ONE end-block message ("I have completed the recovery, translation, verification, and skill
  forging…") — the agent streams NOTHING incrementally, then bursts at the end. Phases emitted:
  only `ingest, ingest, forge, forge, forge, reload, done` (no recover/translate/oracle/test). So
  the screen WAS effectively frozen for ~19 min, then everything appeared at once. L11 = REAL.
  - **FIX (frontend-eng, working tree, task #6):** the WORKING banner now has an always-advancing
    elapsed timer (`_startHeartbeat`/`_tickHeartbeat`, 1s setInterval, pure clock — renderer.js:136)
    + a reassurance line after 6s of silence ("Real migrations take a few minutes — the agent is
    working in a live sandbox"). HONEST: it doesn't fake phase progress; it proves the app is alive
    with a real clock. The code comment cites this exact root cause.
- **Verdict: RESOLVED (frozen-screen bar cleared) — with an honest caveat.** The heartbeat clears
  the "looks hung" risk (the hard requirement). CAVEAT: it makes the screen ALIVE, not the run
  watchable — the agent genuinely emits no incremental progress, so the experience is ~minutes of
  [spinner + ticking timer + reassurance + static "Iteration 1/4"] then an end-burst. That's honest
  (not frozen, not faked), but it's a long low-information stretch; the "breadcrumbs" half of task #6
  + the narration talk-track must carry it. Acceptable for sign-off IF the heartbeat lands and the
  demo narrative sets the expectation. (A deeper fix — getting the agent to stream incremental
  milestones — is out of scope for the slot; the prompt could ask it to print progress markers, but
  that's not guaranteed.)

## L12 — GET /api/download/{run_id} returns 404 after the stream ends  — CONTAINED (inline path works)

- **EVIDENCE (qa):** server.py:470 pops `_RUNS[run_id]` when the SSE stream completes (one-subscriber
  cleanup, pre-existing design). So after the run, GET /api/download/{run_id} → 404. qa confirmed
  the live UI does NOT hit that endpoint — `live.js` prefers the INLINE `content` carried on the
  `download` event (verified: 2078B inline, byte-identical to the diff's right side), so the Download
  button arms from the event, not the endpoint.
- **Verdict: CONTAINED, not blocking.** The demo's download works (inline). But the endpoint being
  dead post-stream is a latent fragility: any path that relies on GET /api/download (e.g. a judge
  hitting the URL, or contract-B clients) gets 404. Cheap fix if desired: keep `run["download"]` in
  a short-TTL cache after `_RUNS.pop`, or don't pop until download is fetched. Flagging for the
  record; not a sign-off blocker since the live UI uses inline content.

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
verdict provably follows the oracle, not the agent's claim; tests honestly scoped.

---

## FINAL SIGN-OFF (devils-advocate, task #4) — SPLIT: CODE/DoD signed; DEMO open

Split per team-lead, and it matches my own verification cleanly:

**✅ CODE / DEFINITION-OF-DONE — SIGNED OFF (2026-05-23).** A completed real-key live run
drives EVERY panel from REAL agent work: business rules, oracle banner, COBOL↔Python diff
(right-side == download, byte-identical), structured pytest (GREEN, real per-case cases),
forge+reload, download of the agent's REAL runnable module (Decimal+ROUND_HALF_UP; qa ran it →
exact COBOL bytes), verdict EQUIVALENT.
**RUN-ID CORRECTION (per qa):** the DECISIVE fully-populated run to cite is **f9e71470** (env
2b01d46d, on **ea6fe12** — post the tarball-independent fix), confirmed by qa + my independent read
of /tmp/sse_full4.jsonl. An EARLIER run **2f307f10** (pre-ea6fe12) had diff/download EMPTY due to
the tarball gate — do NOT cite it as the complete run. My L11 frozen-screen analysis used a
pre-fix run's raw stream (still valid for that finding); the COMPLETENESS sign-off rests on
f9e71470. Honesty is verified
from every angle: the verdict tracks the differential oracle, NOT the agent's self-report (wrong
module → RED; crash → explicit RED; both tested + independently driven by me); provenance is
truthfully labeled (agent_pytest / differential_oracle / model_output / files_api); no panel shows
fabricated data; C13/C16 honesty fixes hold. The DoD ("a single live run drives the whole UI …
ends EQUIVALENT with a downloadable, runnable payroll.py") is MET. **Nothing material is missing
or misleading on the code/data path.**

**⏳ DEMO READINESS — SIGN-OFF OPEN, pending two in-flight items:**
1. **L11 heartbeat (task #6) — FULLY VERIFIED end-to-end by me (2 servers); just needs COMMIT.**
   Test 1 (:8141, isolated): drove the committed heartbeat logic against the live DOM — timer
   advances once/sec ("0:09" at 9s) and the reassurance line ("Real migrations take a few minutes
   — the agent is working in a live sandbox") reveals after the 6s quiet threshold. Test 2 (:8777,
   team-lead's server, FULL run lifecycle): clicked "use the sample", sampled every 500ms — timer
   ticked the whole run (0:00→0:01→…→0:21, every second present) while WORKING showed, and on `done`
   the WORKING banner + timer HID (workingVisible→false) and the verdict badge showed EQUIVALENT.
   So both (a) ticks at 1s cadence during WORKING and (b) stops on done are CONFIRMED. Clears the
   L11 "looks frozen / hung app" bar honestly (real clock, no faked phase progress). My answer to
   "is the heartbeat sufficient for L11?": YES, verified. Breadcrumbs + phase-rail advancement are
   Phase-2 (engagement), not required for the frozen bar. Only remaining gate: COMMIT the fix.
2. **DEMO_SCRIPT honest strictly-live rewrite (task #7):** must set the multi-minute expectation
   up front, show elapsed time, never fake speed (content in DEMO_NARRATIVE_live-DRAFT.md).

**Non-blocking, flagged → Phase 2:** L12 (GET /api/download 404s after stream; live UI uses inline
content, so contained) + the breadcrumbs/phase-rail enhancement. Neither is a Phase-1 blocker.

**PHASE-1 SCOPE (per team-lead):** the heartbeat satisfies L11; breadcrumbs + L12 are Phase 2
(separate branch, own re-verify). I will convert the DEMO sign-off to ✅ once #6 is COMMITTED
(heartbeat now visually verified) and #7 lands. No unresolved honesty or completeness gaps remain.

---

## L13 — DEMO_SCRIPT claims a LIVE GnuCOBOL compile, but the verified run's ground truth was the PRE-CAPTURED golden bytes  — NEEDS FIX (script honesty; blocks my full DEMO sign-off)

- **Claim (docs/DEMO_SCRIPT.md, ce3de81):** Prove beat — "It compiles & runs the **original COBOL
  with real GnuCOBOL**, captures its real output, generates equivalence tests"; Q&A — "We compile
  and run the original COBOL with real GnuCOBOL in the sandbox and assert byte-for-byte equivalence
  against its output." Presented as happening LIVE on stage.
- **EVIDENCE (my read of qa's shipping run /tmp/sse_full4.jsonl):** on the verified live run the
  UI's ground truth did NOT come from a live in-sandbox compile:
  - the `oracle` event's `compiler`/`note` is the **golden_io.json header** ("Canonical outputs
    captured from the original COBOL binary (ground truth)") — i.e. the PRE-CAPTURED golden bytes,
    not a live compile;
  - the `pytest` is `source="agent_pytest"` (the agent's own marker, cross-checked vs golden by
    qa) — NOT a live `differential_oracle` harness run;
  - the agent's step text shows it only INVESTIGATED a compiler ("I will check if a COBOL compiler
    `cobc` is already installed… check if micromamba or conda are pre-installed") and searched for
    `golden_io.json`; no evidence a live `cobc` compile SUCCEEDED and produced the on-screen oracle.
- **Why it matters:** for a STRICTLY-LIVE demo where the judge watches the actual run, narrating
  "it compiles & runs the original COBOL with real GnuCOBOL" while the on-screen oracle banner is
  actually the pre-captured golden header is a judge-catchable overclaim (same class as C4/C13). A
  COBOL-literate DeepMind judge asking "did it compile that live, or is that cached?" exposes it.
- **It's STILL honest if reworded:** the golden bytes ARE real GnuCOBOL output (captured ahead of
  time = the falsifiable floor, per C4/C5); a live compile, if it happens, is an opportunistic
  refresh. The fix is to match the script to that reality, NOT to claim a guaranteed live compile.
- **Verdict: NEEDS FIX (script wording) — blocks my FULL demo sign-off.** Recommended rewording:
  Prove beat → "It proves equivalence against the **original COBOL's real GnuCOBOL output** (the
  ground-truth bytes), diffing the Python against them byte-for-byte" — and, if the agent does
  install/compile cobc live this run, narrate THAT as the refresh; otherwise don't assert it. Q&A
  "How do you know it's correct?" → "ground truth is the real COBOL's output — captured from real
  GnuCOBOL; the agent also tries to recompile it live in the sandbox to refresh it." Keep it
  truthful to whichever path actually fires on stage. Owner: team-lead/doc-keeper, BEFORE the push.

---

## L13 — RESOLVED (687ca26). FULL DEMO SIGN-OFF GRANTED.

Verified the 687ca26 diff: the Prove beat now says "holds the Python to the original COBOL's real
GnuCOBOL output — ground-truth bytes captured ahead of time" + "(if the agent recompiles cobc live
this run, narrate that as an opportunistic refresh — don't assert it if it doesn't fire)"; both Q&A
answers reworded to "ground truth = the original COBOL's real output captured from real GnuCOBOL;
verdict tracks that oracle, not our tests; live recompile is an opportunistic refresh, not
guaranteed"; de-risking checklist states "ground truth = golden_io.json; the demo does not depend
on a live compile." No remaining claim of a guaranteed live compile producing the on-screen proof.
Honest and accurate to qa's verified run. L13 CLEARED.

## ✅✅ FINAL SIGN-OFF (devils-advocate, task #4) — BOTH parts GRANTED

- **CODE / DoD ✅** — every panel populates from REAL agent work on a completed real-key live run;
  verdict tracks the differential oracle, not the agent (wrong/crash → RED, tested + driven by me);
  diff.right == download (the agent's real runnable module); honest provenance labels; no fabricated
  data. DoD met.
- **DEMO ✅** — strictly-live narrative is honest: multi-minute expectation set up front; measured
  ~8–9 min stated (not "2 min"); elapsed-timer heartbeat (visually verified ticking + stopping on
  done) keeps the screen provably alive; ground-truth/oracle framing accurate (L13 fixed); guardrails
  forbid faked speed; mock is break-glass only, labeled. No overclaims remain.

Honesty posture is STRONG and was made stronger by this review (C13/C16 held; oracle falsifiability
enforced + tested; L13 overclaim caught + fixed pre-push). Phase-2 items (breadcrumbs/phase-rail
dedup, L12 download-endpoint TTL) are correctly deferred and are NOT blockers. team-lead is clear to
push main (HEAD 687ca26, 88/88 green).

---

## L9 — STRENGTHENED post-sign-off (ea6fe12 LAZARUS_MODULE marker) — verified, no reopen

After my Phase-1 sign-off, qa noted (and I verified in code) that ea6fe12 "Make module recovery
tarball-independent" added the explicit `LAZARUS_MODULE:` belt-and-suspenders I'd recommended:
- agent.py:168 instructs the agent to print `LAZARUS_MODULE:` + a single fenced ```python block;
- event_transform.py: `_MODULE_MARKER = "LAZARUS_MODULE:"`; `python_module_from_output` now resolves
  DETERMINISTICALLY (the marker) first, then falls back to the largest fenced block.
So module recovery for diff/download no longer depends on incidental echo. qa empirically confirmed
(live run f9e71470, /tmp/sse_full4.jsonl, which I independently read) the live agent echoes a
complete runnable module that passes the oracle 10/10. L9 is solid on BOTH the deterministic-marker
and scrape-fallback paths. No reopen — this only strengthens the resolution I signed off. L12
(download-404 post-stream) → Phase-2 fix 8f1e7ea (_COMPLETED_DOWNLOADS LRU), qa to confirm on the
Phase-2 run; correctly deferred, not a Phase-1 blocker. Sign-off stands.

---

## RUN-ID CRUX — SETTLED two independent ways (qa + my own git/data check). Sign-off maximally grounded.

The one thing I most wanted certainty on — was the completeness sign-off based on a COMPLETED,
POST-fix, real-key run (not the mechanism alone, not a pre-fix run)? — is now settled definitively.
I verified BOTH of qa's proofs myself:
1. LINEAGE: `git merge-base --is-ancestor ea6fe12 6b0b89d` = YES → 6b0b89d (which f9e71470 ran on)
   contains the model_output fix → f9e71470 is POST-fix.
2. DATA: f9e71470's stream (/tmp/sse_full4.jsonl) contains `"source": "model_output"` — a label
   only the post-fix `python_module_from_output` path can emit. The run data itself proves the fix
   fired on that run.
Earlier pre-fix run 1ccbf78f had diff/download EMPTY (that empty result IS the evidence it predated
the fix). So: f9e71470 = a completed, provably-post-fix, real-key run where diff+download populated
with the agent's real module (oracle 10/10, EQUIVALENT, ~514s). My sign-off rests on real live
evidence, confirmed two ways. Nothing left to verify. DEVIL'S-ADVOCATE REVIEW CLOSED.

---

## L11 — CONFIRMED ALIVE in-browser (qa direct observation) + honest Phase-2 nuance recorded

qa drove a live run in Chrome and observed directly (not inferred): the heartbeat elapsed timer
ticked 0:04 → 0:45 → 0:56 across screenshots; the reassurance line rendered during the silent
stretch; the activity panel populated with real COBOL source; screen visibly alive from ~4s. Backend
cadence on the in-flight run: new `✓ ok` breadcrumb lines streamed at 11/13/21/27/32/39/44/53/55/57/
65/89s — the trace accrues, not stuck on one line. This is the in-browser confirmation behind my
heartbeat sign-off (I'd verified the timer mechanism on :8141/:8777; qa confirms it in a real run).

HONEST NUANCE (qa-disclosed, recorded so it's not a surprise to a judge):
- There is one ~30–60s FLAT stretch on a heavy compute step with no new trace line — but the
  heartbeat keeps ticking + the reassurance line is up, so it reads "working," not "dead." This is
  exactly why the heartbeat (not breadcrumbs) was the load-bearing L11 fix.
- The phase rail does NOT richly march beat-by-beat live — most beats light near the END (it
  advances off end-block prose). The streamed breadcrumbs are only `✓ ok` with NO command text, so
  they can't drive `phase_for_text`. This is the precise Phase-2 limitation (consistent with my L10
  shipping-run note that the rail over-emits oracle / skips recover/translate/test). A Phase-2 fix
  would forward `code_execution_call` command text as breadcrumbs so the rail marches live.
NET: a strictly-live judge sees a live, ticking, accruing screen — not frozen. Phase-1 L11 bar
(never looks hung) is MET in-browser. Richer beat-by-beat progression is Phase-2, not a blocker.

---

## L11 — Phase-2 improvement (8f1e7ea breadcrumbs): trace now accrues incrementally (qa, in-flight)

Phase-2 (8f1e7ea) adds tool breadcrumbs; qa's in-flight run shows 12 `✓ ok` breadcrumbs streaming
at 11/13/21/27/32/39/44/53/55/57/65/89s — the activity log now gets NEW lines THROUGHOUT the run,
not just one end-block burst. So L11 mitigation is now TWO layers: (1) heartbeat timer + reassurance
(browser-confirmed), (2) incremental `✓ ok` breadcrumbs. Strictly better than the run I analyzed for
the original frozen finding.

HONEST LIMITATION (qa-disclosed, recorded): the breadcrumbs are ONLY `✓ ok`
(code_execution_result) — ZERO `$ <command>` (code_execution_call) breadcrumbs. So they show
"something happened" but not WHAT, and `✓ ok` matches no phase keyword so it can't drive the rail
(rail still advances off end-block prose). Net: "agent is doing things," not a rich
play-by-play of the cobc commands. The precise Phase-2 follow-on is to forward code_execution_call
command text as breadcrumbs. This is Phase-2 polish (task #8) — does NOT reopen the Phase-1
sign-off; it improves beyond it. My review remains CLOSED.

---

## L12 — FULLY CLOSED (8f1e7ea merged to main; verified two ways)

qa proved the fix through the REAL server: drove server.py via FastAPI TestClient reproducing the
exact post-stream condition I flagged (POST → drain SSE to completion → _RUNS popped → GET
/api/download/{run_id}) → HTTP 200, text/x-python, served the module. Stronger than a mocked unit —
the full request/stream/teardown/re-request cycle.

I independently confirmed the fix is on MAIN (not just the Phase-2 branch): server.py:72-84 add
`_COMPLETED_DOWNLOADS` (OrderedDict, 32-entry LRU cap, oldest evicted) populated with the module
content; line 519 the download endpoint falls back to `_COMPLETED_DOWNLOADS.get(run_id)` when the
run's _RUNS entry is gone post-stream. Memory-bounded + correct fallback. So GET /api/download now
returns 200 after the stream ends. L12 CLOSED. (Note: 8f1e7ea "Phase 2: live tool breadcrumbs +
post-run download retention" is merged to main — the download-retention half is live; the
breadcrumb/phase-rail polish continues per qa.)

## ALL FINDINGS RESOLVED — devil's-advocate review fully closed
L1–L13 + L12: every item is CONFIRMED, FIXED+verified, or honestly deferred-with-note. Nothing
open that affects honesty or completeness. Phase-1 shipped + signed off; the only continuing work
is Phase-2 phase-rail/breadcrumb polish (engagement, not correctness). Sign-off stands.

---

## L12 — confirmed THREE ways (final): real-key live curl 200. + phase-rail run-to-run inconsistency noted

qa's Phase-2 live run (6467773 on 8f1e7ea) completed; they curled its REAL run_id post-stream →
GET /api/download → HTTP 200, 3031B, real module. So L12 is now confirmed three independent ways:
(1) my read of the merged _COMPLETED_DOWNLOADS LRU on main, (2) qa's real-server TestClient cycle,
(3) qa's real-key live run_id curl. Fully closed. That run also reconfirmed completeness (all 10
types, diff.right == download 3031B, pytest green source=agent_pytest 19 cases, EQUIVALENT).

NEW DATA POINT (phase rail, sharpens the L10 precision note): this 2nd run's live rail was
ingest→recover→forge→reload→done — DIFFERENT from f9e71470's ingest→oracle→forge→reload→done, and
still skips translate/oracle/test. So the rail isn't merely over-emitting one phase; it's
INCONSISTENT run-to-run AND skips beats, because it's prose-driven (end-block) not activity-driven
(the `✓ ok` breadcrumbs carry no command text). This strengthens the case for the Phase-2 fix
(broaden + dedup phase_for_text patterns / forward code_execution_call command text). Phase-2 polish,
not a Phase-1 blocker; sign-off unaffected. Review remains fully closed.

---

## L14 — DEMO_SCRIPT "rail completes the full pipeline in order, verified on real runs" is FALSE on the captured runs (rail still skips translate/oracle/test) — NEEDS FIX

- **Claim (DEMO_SCRIPT, 5d99443, intro + de-risking):** "the phase rail completes the full pipeline
  **in order** (ingest→recover→translate→oracle→test→forge→reload→done — driven by the ordered
  structured events, **verified on real captured runs**)."
- **EVIDENCE — FALSE on every capture, including the POST-fix one.** I checked the actual streams:
  - f9e71470 (pre-87a5572): rail = ingest→oracle→forge→reload→done (skips recover/translate/test).
  - sse_full5.jsonl (captured 21:21, AFTER 87a5572's 21:19 commit): rail =
    ingest→recover→**forge**→reload→done — skips **translate, oracle, test**. The diff/oracle/pytest
    EVENTS all fired (panels populated, EQUIVALENT), but their phase-rail beats did NOT.
- **ROOT CAUSE (found in the trace):** `emit_phase` is forward-only (`if idx < progress.idx:
  return`). The `forge` phase is emitted EARLY from the agent's streamed prose (phase_for_text on the
  step text mentions the skill/forge right after recover) — index 5 — which advances progress.idx
  past translate(2)/oracle(3)/test(4). The later unconditional emit_phase("translate"/"oracle"/
  "test") calls are then SUPPRESSED by the forward-only guard. So 87a5572 fixed the structured
  emission but a SECOND prose-driven forge emission still eats the middle beats.
- **Verdict: NEEDS FIX (script overclaim + a real rail bug).** Two honest options:
  1. CODE FIX (preferred): stop emitting `forge`/any later beat from prose (phase_for_text) — drive
     the rail ONLY from the ordered structured events (the diff→translate, oracle, pytest→test,
     skill→forge emissions), so the forward-only guard sees them in order and the rail actually
     completes ingest→recover→translate→oracle→test→forge→reload→done. THEN the script claim becomes
     true and a fresh capture verifies it.
  2. SCRIPT FIX (if code won't change before ship): reword to the TRUTH — "the rail lights a partial,
     run-variable subset of beats (it currently skips some, e.g. translate/oracle/test, because a
     prose-emitted forge advances the forward-only rail past them); during-run liveness is the
     elapsed timer + ✓ ok breadcrumbs + trace, NOT the rail." Drop "completes the full pipeline in
     order, verified on real captured runs" — that's not what the captures show.
- Owner: integration-eng (the emit_phase/prose bug) + team-lead/doc-keeper (the script line). This
  is the one remaining honesty overclaim; flagging before it's read by a judge. NOT a Phase-1 code
  blocker (panels still populate; verdict honest) — it's a DEMO_SCRIPT accuracy blocker.

---

## L14 — RETRACTED (FALSE POSITIVE). My error: I analyzed a STALE-SERVER capture.

I was WRONG. integration-eng's rebuttal is correct and I verified it two ways myself:
1. The SHIPPED `emit_step` (origin/main 5d99443) has ZERO `phase_for_text` references — it only
   pushes the step; the prose-driven phase emission was removed in 87a5572 (the comment even says
   "DO NOT advance the phase rail from prose"). So the "two phase sources fighting" root cause I
   described does NOT exist on main.
2. I replayed the EXACT sse_full5 prose (the capture I cited as proof of the skip) through the
   SHIPPED code: RAIL = ingest → recover → translate → oracle → test → forge → reload → done,
   forge count = 1, translate/oracle/test ALL present. The full in-order pipeline.
ROOT CAUSE OF MY ERROR: sse_full5.jsonl was captured from a STALE uvicorn started before the
87a5572 fix (commit 21:19; capture mtime 21:21; a server started <21:19 still served OLD code).
Its 4×-forge signature is the OLD-code fingerprint — impossible under shipped code (single
emit_phase per beat). I treated the capture as authoritative WITHOUT confirming the server's commit
— the exact "verify the provenance before claiming" discipline I'd applied elsewhere, not applied
here. My fault.
CONCLUSION: the DEMO_SCRIPT "phase rail completes the full pipeline in order" claim is TRUE against
shipped code (verified by my own replay + integration-eng's replay + qa's TestClient on real
server.py). NO overclaim. NO code change needed (87a5572 already did exactly the fix I'd proposed).
L14 is WITHDRAWN. Lesson recorded: a captured stream is only evidence for the code the capturing
server was running — confirm the server's commit before drawing conclusions from a capture.

---

## L14 — FINAL DISPOSITION (both parts resolved on main; verified)

team-lead split L14 correctly and it's fully resolved on origin/main:
- WORDING (valid catch): "verified on real captured runs" WAS unsupported (no post-fix capture
  exists). FIXED in 72dcbce (in main's history; I confirmed `git merge-base --is-ancestor 72dcbce
  main` = YES). The DEMO_SCRIPT now says the rail completes in order "because the server emits these
  phases in fixed sequence from the ordered structured events, NEVER from prose … deterministic +
  unit-tested" and notes "earlier live captures predate this fix." Honest + accurate.
- RAIL-SKIP (my error): retracted. I re-confirmed on origin/main server.py: `phase_for_text` count
  = 0; the 8 emit_phase calls are hardcoded in fixed order ingest(333)→recover(353)→translate(379)
  →oracle(386)→test(394)→forge(417)→reload(423)→done(430); emit_step (312–319) pushes ONLY a step,
  no phase. Rail is clean by construction. My skip evidence (sse_full5) was probe5/6467773 output
  on 8f1e7ea — PRE the 87a5572 rail fix. Stale capture, my mistake (see
  [[captures-need-commit-provenance]]).
NET: no overclaim remains; the DEMO_SCRIPT rail line is honest; shipped code produces the in-order
rail (my replay + integration's replay + qa's TestClient all agree). Optional: a fresh
rehearsal capture from a confirmed-current server would document it, but the order is deterministic.
L14 CLOSED. ALL findings (L1–L14) now resolved/fixed/retracted — devil's-advocate review complete.

---

## L15 (task #11) — interest.cob golden is GENUINE — independently verified by devils-advocate

Co-owned with qa. I verified the second sample's golden is REAL (not computed/fabricated), zero-key,
by compiling it MYSELF with cobc 3.2.0 (non-circular — compares committed golden vs a fresh binary,
not vs the reference .py):
1. GOLDEN REAL: compiled src/sample/interest.cob with my own cobc 3.2.0; ran all 10 committed
   golden inputs through MY fresh binary → 10/10 byte-for-byte match (incl. truncation cases
   9999999.99→0374999.99, 13.33→0000000.49, 1.00→0000000.03, 50000.50→0001875.01).
2. REFERENCE EQUIVALENT: committed interest.py (Decimal + ROUND_DOWN) → 10/10 match golden.
3. FALSIFIABLE + DISTINCT IDIOM: a naive round() port FAILS exactly 4/10 — the 4 truncation cases
   above (round gives 375000.00/0.50/0.04/1875.02). A naive port CANNOT pass → the idiom is real
   and the OPPOSITE of payroll's ROUND-HALF-UP (payroll naive-round came out too LOW; here too HIGH).
CONCLUSION: no honesty gap. The golden is genuine real-cobc output; the second sample legitimately
demonstrates the differential oracle generalizes to a DIFFERENT idiom (not pattern-matching one
file). The README §2.4 claim ("two samples exercise opposite idioms, each proven against real
GnuCOBOL, each breaks a naive round() port") is INDEPENDENTLY VERIFIED, not just asserted. Matches
qa's verification exactly. L15/task#11 CONFIRMED.

## L15 — CORROBORATION: golden verified GENUINE by THREE independent paths
1. devils-advocate (me): compiled interest.cob with my own cobc 3.2.0 → committed golden == fresh
   binary 10/10 (non-circular); naive round() fails 4/10.
2. qa-verifier: build_samples.sh + independent naive-port falsifiability (4/10).
3. team-lead: ran build_samples.sh on a cobc-equipped box → committed golden == live cobc AND
   reference py == live cobc, 10/10 for BOTH payroll + interest. Shipped origin/main d265bbb, 99
   tests, CI green. Reproducible check: `bash src/sample/build_samples.sh` (read-only).
No fabricated golden. The second-sample honesty bar holds three ways. Task #11 fully CONFIRMED.

---

# ===== feature/agent-capabilities branch — L16+ (devils-advocate merge gate) =====

> Scope: the 4 NEW agent capabilities being added behind flags (web-grounding,
> thinking_level, cross-run skill library, whole-codebase multi-module). My sign-off
> gates merge of feature/agent-capabilities → main. Baseline: branch HEAD == main
> (26f65e4), 99 tests green. The shipped single-module path with ALL flags OFF must
> stay byte-identical. Cross-checked against docs/RESEARCH_MANAGED_AGENTS.md §3.

## L16 — PRE-IMPLEMENTATION GATE + the central trap (SDK acceptance ≠ runtime acceptance)

**The trap I will hold every feature to.** The installed SDK (google-genai 2.6.0) is a
Stainless/OpenAPI-generated client that models the UNION of every Interactions surface —
model path AND agent path. I verified this directly:
- `GenerationConfigParam` (the type `generation_config=` accepts) includes `thinking_level`
  BUT ALSO `temperature`, `top_p`, `max_output_tokens`, `stop_sequences`, `seed` — all of
  which RESEARCH §3 says the Antigravity AGENT rejects/ignores. So the SDK accepting a field
  is NOT evidence the managed agent honors it.
- The `Step` union the SDK can deserialize includes `FunctionCallStep`, `FileSearchCallStep`,
  `GoogleMapsCallStep`, `MCPServerToolCallStep` — none of which the Antigravity agent emits
  (RESEARCH §3). The SDK modeling a step type ≠ the agent producing it.
CONSEQUENCE: "the SDK call didn't error" / "the type exists" is NOT acceptance evidence for
ANY of the 4 features. Acceptance = the managed-agent RUNTIME demonstrably did the thing,
shown in live stream blocks / usage fields. No exceptions.

**Good news — the evidence FIELDS I demanded all exist in the 2.6.0 type model**, so qa CAN
produce real proof (these are the exact things to capture):
- web-grounding: `GoogleSearchCallStep` (type=`google_search_call`, `arguments.queries:[...]`)
  and/or `URLContextCallStep` (type=`url_context_call`, `arguments.urls:[...]`) in the stream,
  PLUS `usage.grounding_tool_count[].type == "google_search"` with count > 0.
- thinking_level: `usage.total_thought_tokens` (a real field on `Usage`) CHANGING between
  levels (e.g. minimal vs high), AND `ThoughtStep` (type=`thought`, `summary:[...]`) blocks.
- cross-run skill library: a forged SKILL.md DISCOVERED on a GENUINELY FRESH run (new
  environment, fork-clean — RESEARCH §4: "every run starts clean"). Surviving in the SAME
  reused env is NOT cross-run; that is the already-shipped FORGE-retry beat, not a new feature.
- whole-codebase multi-module: a rule the agent could ONLY derive by reading 2+ files together
  (a genuine cross-module dependency), not two single-file runs concatenated.

**HARD BLOCK conditions (any one blocks merge):**
1. ANY flag-OFF change to the shipped path: `_build_prompt(cobol)` string, `build_base_environment()`
   output (incl. NOT seeding new SKILL.md into `.agents/skills/` — currently empty, AGENTS.md only),
   or the `interactions.create` kwargs (must remain NO `generation_config`). I diff these directly.
2. Reaching for `function_calling` / structured output / sub-agents / `mcp` / `file_search` /
   `computer_use`, or narrating a model-level capability as an agent-runtime one.
3. A feature claimed VERIFIED on SDK-acceptance / mock evidence alone (the L16 trap).

**Per-feature provisional verdict (pre-evidence): all HOLD** until qa supplies the blocks/tokens
above from a real-key run on the as-shipped flag-gated code. thinking_level is the highest feasibility
risk (generation_config is documented only for the MODEL path with `model=`; never demonstrated on the
AGENT path with `agent=`; §3 rejects the sibling knobs) — it may well be NOT-WORKING (silently ignored
or 400'd). web-grounding is the most likely to genuinely fire (google_search/url_context ARE supported
agent tools per §3).

## L17 — WEB-GROUNDING (Feature 1, b15d07e): flag-off SAFE, but the live-trace PROVABILITY is BROKEN (wrong SDK field names) — NEEDS FIX

- **Flag-OFF regression: CLEAN.** `_build_prompt(cobol, ground=False)` → `preamble=""` → the
  original body string is unchanged (byte-identical); `_build_forge_retry_prompt(..., ground=False)`
  same; `migrate()` defaults `ground=_grounding_enabled()` = False; NO generation_config added; agent
  tools unchanged (still default code_execution+google_search+url_context); base_environment untouched.
  Honest design: the preamble only STEERS the agent toward two SUPPORTED tools (§3) — no unsupported
  surface reached. No regression.
- **Attack:** the feature's whole point of provability is the 🔎/🌐 breadcrumbs (and qa's evidence
  bar) — does the breadcrumb code read the REAL SDK step shapes? I fed `_tool_breadcrumb` actual
  google-genai 2.6.0 typed steps.
- **EVIDENCE (reproduction, real SDK types, not assertion):**
  - `GoogleSearchCallStep(arguments=Arguments(queries=[...]))` → `_tool_breadcrumb` returns **None**.
    Code reads `arguments.query` (singular); the SDK field is `arguments.queries` (List[str], plural).
    The flat fallback `_step_field(step,"query")` also misses `queries`. So when grounding GENUINELY
    fires live, NO 🔎 breadcrumb appears.
  - `URLContextCallStep(arguments=Arguments(urls=[...]))` → **None**. Same bug: code reads
    `arguments.url`; SDK field is `arguments.urls` (List[str]).
  - `GoogleSearchResultStep(result=[Result(search_suggestions=...)])` → `🔎 ✓` with NO snippet.
    `_result_snippet` does `isinstance(result, str)`, but `result` is `List[Result]` (objects), not a
    string → snippet empty.
  - `ThoughtStep(summary=[{text:...}])` → `💭 <summary>` — this one IS correct.
- **Why it matters:** this is the exact L16 trap in miniature — the code was written to a *guessed*
  shape (singular query/url, string result), tests only checked the PROMPT text (preamble present/
  absent), and no test constructs a real grounding step → the bug passed 99-green + the new suite.
  On a live run, grounding could fire perfectly and the live trace would show NOTHING for the
  search/url calls, defeating both the demo value AND qa's ability to show me the call blocks.
- **Verdict: NEEDS FIX (feature-on path).** Two-line fix: read `arguments.queries` (join the list)
  and `arguments.urls`; make `_result_snippet` handle `List[Result]` (pull `.search_suggestions` /
  url-context result text). ADD a real unit test that builds a `GoogleSearchCallStep`/`URLContextCallStep`
  with the SDK types (or the documented dict shape `{"arguments":{"queries":[...]}}`) and asserts the
  🔎/🌐 breadcrumb renders — so this can't silently regress. SEPARATELY, qa should ALSO capture
  `usage.grounding_tool_count[].type=="google_search"` count>0 as the AUTHORITATIVE server-side proof
  (it's a real field on `Usage` and is independent of breadcrumb parsing). Until both the fix lands AND
  qa shows real google_search_call/url_context_call blocks + grounding_tool_count on a live key,
  web-grounding stays **HOLD** (NOT the "completed" the task board shows — task #5 reopened to me).

## L18 — THINKING_LEVEL (Feature 2): flag-off SAFE, but it sends the WRONG generation_config SHAPE → the rejection path would FALSELY blame the runtime — NEEDS FIX

- **Flag-OFF regression: CLEAN.** `_thinking_level()` returns None for unset AND for "medium"/
  sentinels; `_create_interaction_stream` then calls `interactions.create(**base_kwargs)` with the
  EXACT shipped kwargs (agent, input, stream, extra_body) — NO generation_config. The new tests
  (test_thinking_unset_sends_no_generation_config / _sentinel_values) lock this. No regression.
  Honest design touches: graceful-reject → retry-without + THINKING_REJECTED flag + UI line;
  `[thought_tokens=N]` only when usage reports it; unrelated errors re-raised (not swallowed).
- **Attack:** is the generation_config SHAPE the one the INTERACTIONS api accepts? I checked the
  team's OWN research + the installed SDK.
- **EVIDENCE (two independent sources agree, and the impl contradicts BOTH):**
  - Impl sends `generation_config={"thinking_config": {"thinking_level": level}}` (NESTED).
  - RESEARCH_GEMINI_3.5.md §6.1 + findings-gemini.md:112 (verbatim from the live interactions
    thinking docs): the Interactions API shape is FLAT — `generation_config={"thinking_level": "low"}`.
    The NESTED `thinking_config=ThinkingConfig(...)` form is the **generate_content** typed-config
    path (`config=types.GenerateContentConfig(thinking_config=...)`) — a DIFFERENT API surface.
  - Installed SDK `google.genai._interactions.types.generation_config_param.GenerationConfigParam`:
    `thinking_level` is a FLAT key; there is NO `thinking_config` key anywhere in the interactions
    types (`grep -rln thinking_config` over that dir = none). `ThinkingConfig` lives in
    `google/genai/types.py` (the models path), not interactions.
  - So the impl copied the generate_content nesting into the interactions generation_config. The
    agent will receive an unrecognized `thinking_config` key (or silently ignore the nested object).
- **WHY THIS IS WORSE THAN A TYPO — it corrupts the feature's honesty verdict:** if the malformed
  config triggers an "unknown field"/"invalid argument" error, `_looks_like_thinking_rejection`
  MATCHES it (it keys on exactly those words) → sets `THINKING_REJECTED=True` → emits "thinking_level
  rejected by the managed-agent runtime." The team would then record thinking as NOT-WORKING / "the
  runtime doesn't support it" — when the REAL cause is *we sent it wrong and never tested the correct
  flat call.* That's a FALSE provenance: it could (a) wrongly bury a feature that actually works, or
  (b) let us claim "we gracefully handle the runtime's rejection" without ever having made a
  well-formed request. Either way the eventual VERIFIED/NOT-WORKING call would be unfounded.
- **The tests CODIFY the bug:** test_thinking_explicit_level_carries_exact_shape (line 334) asserts
  `cfg == {"thinking_config": {"thinking_level": level}}` — green because it tests the impl against
  the same wrong shape. Pure L16-trap closed loop; proves nothing about runtime acceptance.
- **Verdict: NEEDS FIX before ANY thinking verdict is meaningful.** (1) Send the FLAT interactions
  shape `generation_config={"thinking_level": level}` (per the team's own §6.1 + the SDK type). (2)
  Fix the test to assert the flat shape. (3) THEN the live run is decisive: minimal→high must change
  `usage.total_thought_tokens` AND emit `thought` blocks (accepted), OR a CLEAN flat call gets a
  genuine rejection (then NOT-WORKING is REAL, not an artifact of malformed input). Until the flat
  call is what we send, thinking_level = **HOLD** and the THINKING_REJECTED signal is untrustworthy.
  Task #6 should NOT be "completed."

## L19 — CROSS-RUN SKILL LIBRARY (Feature 3): orchestration is HONEST + CORRECT (I drove it); live verdict hinges on agent ECHO + STARTUP-READ

- **Flag-OFF regression: CLEAN.** With an EMPTY `.agents/skills/` (the shipped world) and no recorded
  fingerprint, `ensure_agent` returns a no-op (existing agent → 0 create / 0 delete; I drove it).
  `build_base_environment` mounts only AGENTS.md → base_environment byte-identical to main.
  `_bank_forged_skill_from_output` is only called on a FAILED iteration AFTER a skill path is detected
  (it can't run on the shipped happy path). `.skill_fingerprint` is gitignored (verified). No regression.
- **Honesty of the mechanism: STRONG — it is exactly the RESEARCH §4 verified-safe pattern, not an
  overclaim.** §4 is explicit: fresh runs fork CLEAN; to make a forged skill durable you re-register
  the agent with the SKILL.md mounted in `base_environment`. Feature 3 does precisely that: bank the
  echoed SKILL.md to `.agents/skills/<slug>/` → `ensure_agent` mounts every on-disk SKILL.md into
  base_environment AND a changed mounted-skill fingerprint forces a delete+recreate so a FRESH
  invocation inherits it. It does NOT claim silent mid-run hot-reload or "persists forever" (the C16/
  §4 overclaim I'd block). Banking returns None if the agent never echoed the body ("we never invent
  skill content") — honest.
- **EVIDENCE — I drove the FULL cross-run flow myself (deterministic, no key):** simulated a run-A
  output that announces + echoes `.agents/skills/sign-overpunch/SKILL.md` → `_bank_forged_skill_from_output`
  wrote the real body to disk → a FRESH `ensure_agent` (agent pre-existing, OLD fingerprint) DELETED +
  RECREATED the agent, and the new base_environment mounted `.agents/skills/sign-overpunch/SKILL.md`
  with the banked body verbatim. The orchestration that turns a forge into a cross-run skill is correct.
- **THE TWO LIVE-ONLY GAPS (qa must prove; this is why #3 is HOLD not VERIFIED):**
  1. Does the live agent ECHO the forged SKILL.md body in its output text? Banking depends on the body
     appearing in a fenced block after the path mention. If the agent only writes it to sandbox disk and
     doesn't echo it, `_bank_forged_skill_from_output` returns None → NOTHING is banked → no cross-run
     skill. (The Files-API tarball is NOT used here, so disk-only writes are not recovered.)
  2. Does a GENUINELY FRESH invocation (new environment) actually READ + USE the mounted skill on
     startup? A skill surviving in the SAME reused env is the already-shipped FORGE-retry beat, NOT a new
     cross-run capability. I require: run A banks; a SEPARATE fresh run discovers the banked skill from
     `.agents/skills/` at startup (visible in its recovered-rules / approach).
- **Verdict: HOLD — code/orchestration VERIFIED honest by my own drive; awaiting qa's two live proofs
  (agent echoes body → banked file on disk; fresh run picks it up). NOT an overclaim in code.**

## L20 — WHOLE-CODEBASE MULTI-MODULE (Feature 4): flag-off CLEAN, multi-prompt is genuinely cross-module; live verdict = a real cross-module rule

- **Flag-OFF / single-file regression: CLEAN.** `migrate(client, "one.cob")` → `_normalize_cobol_paths`
  returns a 1-element list → `len(paths)==1` → uses `_build_prompt` (the byte-identical shipped prompt).
  I verified the single-file (len-1) prompt == `_build_prompt(...)` exactly. The multi path
  (`_build_multi_prompt`) is reached ONLY when `migrate` gets >1 file. `cobol_path` stays the first
  positional arg (backward-compatible signature). No regression.
- **Is it a REAL cross-module capability or just concatenation?** The multi-prompt (verified by reading
  the rendered text): presents all modules at once, instructs "Treat the files as ONE system," and
  asks for rules that SPAN modules — shared COPY record layouts, a computation split across a caller +
  its CALLed subprogram, constants/88-levels defined in one module used by another, lifecycle ordering.
  It reuses the same LAZARUS_RULE/ORACLE_JSON/MODULE markers so the UI panels work unchanged, and writes
  the entrypoint to /workspace/payroll.py (download/diff intact). So the PROMPT genuinely solicits
  cross-module analysis — not a concatenation hack. Honest framing.
- **THE LIVE GAP (qa must prove):** a LAZARUS_RULE the agent could ONLY produce by reading 2+ files
  together (e.g. "TAXRATE constant defined in copybook X is applied in module Y"), not three independent
  single-file rules. Requires a 2+-module sample where a genuine cross-module dependency exists. NOTE:
  golden_io.json is single-module (payroll) ground truth — a multi-module run's ORACLE/equivalence
  proof is only as strong as the golden it diffs against; if the codebase entrypoint still maps to the
  payroll battery, the oracle stays honest, but a NEW multi-module sample would need its own real-cobc
  golden to prove equivalence (don't claim byte-equivalence for modules with no golden). qa should
  state which golden the multi-run was proven against.
- **Verdict: HOLD — code/prompt VERIFIED genuinely cross-module + regression-clean; awaiting qa's one
  live proof (a real cross-module rule from a 2+-file run, + which golden the oracle used).**

## L21 — qa_capture.py captures the RIGHT grounding evidence, but STRUCTURALLY can't prove thinking/cross-run/cross-module — a "verified" report must not rest on it for those

- **Why this matters:** task #3 (live-verify) is marked completed but I found NO evidence artifacts on
  disk, and the only capture tool (scripts/qa_capture.py) can test exactly ONE of the four features. A
  sign-off drawn from a harness that can't exercise a feature is the L16 trap wearing a lab coat.
- **GROUNDING — the harness is GOOD.** It builds a step-type histogram from BOTH the live stream and the
  authoritative `get()` fetch, and captures real `google_search_call`/`url_context_call`/result blocks.
  That's genuine runtime evidence (not SDK-acceptance). Once L17's breadcrumb fix lands AND it also dumps
  `usage.grounding_tool_count` (currently it reads `usage` but only prints thought/total tokens), this is
  sufficient to VERIFY grounding.
- **THINKING — the harness CANNOT test it (two structural reasons):** (1) it never sets `LAZARUS_THINKING`
  (only `LAZARUS_GROUND`); (2) it calls `client.interactions.create(...)` DIRECTLY (line 62), bypassing
  `agent._create_interaction_stream`, so the thinking `generation_config` is never sent at all. Its
  `total_thought_tokens` read therefore only reflects the DEFAULT (medium) thinking. To prove L18's
  question it must route through the agent's stream helper, run minimal vs high, and show the tokens
  DIFFER — and only AFTER the flat-shape fix.
- **CROSS-RUN (#3) / CROSS-MODULE (#4) — NOT covered.** No multi-run banking sequence; no multi-file
  mode (the docstring advertises `--cobol2` but argparse has only `--cobol`). So neither can be evidenced
  by this tool as written.
- **Verdict: harness VERIFIES grounding only (post-L17 + grounding_tool_count). For thinking/cross-run/
  cross-module, demand either harness additions or explicit manual captures — do NOT accept "qa_capture
  ran clean" as proof for those three.** Recorded so the merge gate can't be cleared by an
  under-scoped capture.

## L22 — POST-FIX STATE (HEAD c019274): L17 RESOLVED, L18 shape RESOLVED + thinking LIVE-PROVEN unsupported, regression GREEN

- **L17 (grounding breadcrumbs) — RESOLVED (de85409, verified by me on committed HEAD).** Now reads the
  plural SDK fields: `🔎 COBOL ROUNDED mode` / `🌐 https://ibm.com/docs` against real `GoogleSearchCallStep
  (arguments.queries)` / `URLContextCallStep(arguments.urls)`. A real-SDK regression-guard test
  (`test_grounding_breadcrumbs_use_real_sdk_types`, built via `model_validate`) was added — exactly the
  test whose absence let the bug slip; it's now resilient to the *Step/*Content class-name question
  (c019274). 145 tests green, deterministic over 2 runs.
- **L18 (thinking shape) — code RESOLVED (de85409), AND the deeper truth is LIVE-PROVEN.** The fix sends
  the SDK-correct AGENT-path shape `agent_config={"type":"dynamic","thinking_level": <lvl>}` (flat
  thinking_level, NO nested thinking_config, NO generation_config — verified on HEAD). It also catches
  `agent_config` errors in the rejection heuristic. CROSS-CHECK with the prior real-key session
  (memory [[thinking-level-rejected-live]], 2026-05-24): the managed-agent path REJECTS every
  thinking-control shape — typed kwarg → SDK ValueError "If specifying `agent`, use `agent_config`";
  `extra_body`/`agent_config` nestings → HTTP 400 "Unknown parameter"/"Provide". I confirmed the current
  `_looks_like_thinking_rejection` catches all four of those real error strings. So thinking DEPTH CONTROL
  is genuinely NOT supported on this runtime (a real limitation, not our malformed input — my L18 worry
  is retired BUT the conclusion is the same: thinking_level can't be steered here). The HONEST shippable
  state: LAZARUS_THINKING is a VERIFIED GRACEFUL NO-OP (sends the best shape, catches the reject, retries
  clean, sets THINKING_REJECTED for the UI). Thinking still HAPPENS at the default (usage.total_thought_
  tokens>0 live), it just isn't controllable. **REQUIREMENT for sign-off: README/UI/DEMO must NOT claim
  thinking-depth control — only "the agent thinks (token-visible); depth is the runtime default, not a
  knob we can set."** If any doc claims a thinking-level knob works, I BLOCK it.
- **REGRESSION GATE — GREEN on c019274 (verified definitively):** flags OFF → _build_prompt, forge-retry,
  base_environment, interaction kwargs ({agent,extra_body,input,stream}, no agent_config/generation_config),
  ensure_agent clean-fork no-op — ALL byte-identical to main. 145 tests deterministic.
- **Cross-run skills (#3) corroboration:** memory [[skill-mount-discovery-live]] LIVE-PROVED (ZARFLAX-7731
  sentinel, real key) that a SKILL.md mounted via base_environment.sources IS auto-discovered at a FRESH
  interaction's startup — the exact mechanism Feature 3 banks toward. Combined with my own drive of
  bank→re-register→mount (L19), the cross-run MECHANISM is verified end-to-end. Residual live gap stays:
  on a real forge run, does the agent ECHO the SKILL.md body so banking captures it (else nothing banks)?
  qa to show the banked file on disk from a forge run.

## L23 — WHOLE-CODEBASE (#4) is LIBRARY-ONLY: no server / CLI / UI entry point — a scope-honesty boundary

- **Finding:** Feature 4's multi-module path (`migrate(client, cobol_paths=[...])` → `_build_multi_prompt`)
  is reachable ONLY via a direct Python call. NONE of the shipped surfaces invoke it:
  - `server.py:340` calls `agent_mod.migrate(client, tmp_path)` — single file; `/api/migrate` accepts
    `{cobol, filename}` (ONE cobol string, server.py:11).
  - `web/` (recursive grep) has NO multi-file upload/select path — no `cobol_paths`/multiple/codebase ref.
  - CLI `main()` has a single `--input` with NO `nargs`, then `migrate(client, args.input)` — can't pass
    >1 file even from the command line.
- **Contrast with the other 3 (which ARE reachable):** #1 grounding (env `LAZARUS_GROUND`, read in
  migrate, server path), #2 thinking (env `LAZARUS_THINKING`, server path), #3 banking (automatic in the
  migrate loop, server path). #4 alone has no flag and no entry point — it's a bare function signature.
- **Verdict: NOT an overclaim IN CODE (the function + cross-module prompt are honest and tested), BUT it
  WOULD be an overclaim to present "LAZARUS migrates a whole codebase" as a usable PRODUCT capability —
  no shipped surface can run it.** Two honest options before claiming #4 anywhere user-facing:
  (a) WIRE an entry point (CLI `--input` with `nargs="+"`, or a multi-file UI/endpoint), then qa runs it
  end-to-end; OR (b) label #4 explicitly as a library/API capability ("the migrate() API accepts a module
  set; the demo UI drives single-file") and DON'T show it as a clicked-in-the-UI feature. Either is fine;
  silently demoing it as a product feature is not. Flagged to team-lead. This does NOT affect the
  regression gate (single-file path is byte-identical) and #4's code stays VERIFIED-as-a-function.

### L23 — RESOLVED (7585a41): CLI multi-module entry added (option a). I verified:
integration-eng took option (a): `--input nargs="+"` with `default=["src/sample/payroll.cob"]`. Routing
verified — len==1 → `migrate(cobol_path=...)` (single-file BYTE-IDENTICAL path, incl. the no-arg default
which parses to a 1-element list); len>1 → `migrate(cobol_paths=...)` (multi-module). Only agent.py changed;
server.py + the web live path are deliberately UNTOUCHED (the UI demo stays single-file — the honest split
I asked for). 146 green. So #4 now has a real product entry point (CLI). HONEST CLAIM SHAPE: "the CLI runs
whole-codebase (`--input a.cob b.cob copybook.cpy`); the UI demo is single-file." NOTE: server.py untouched
means the SAFETY-NET in server.py (fetch payroll.py → diff → oracle pytest) is single-module — a multi-file
CLI run produces the entrypoint module + cross-module rules, but its oracle is only as strong as whatever
golden it diffs (golden_io.json is payroll single-module). So a multi-MODULE equivalence CLAIM still needs a
multi-module golden; the cross-module RULE-RECOVERY is the demonstrable part. #4 remaining live gap (qa): a
real cross-module rule from a 2+-file CLI run.

## L24 — CORRECTION to my own L22: the current thinking shape is NOVEL vs the live-proven set → thinking is RE-OPENED (genuinely open, must re-test the EXACT current shape)

- **Self-catch (the discipline I hold others to applies to me).** In L22 I leaned on memory
  [[thinking-level-rejected-live]] to call thinking a "verified graceful no-op." But that memory tested
  `agent_config={"thinking_config":{...}}` and `agent_config={"generation_config":{...}}` (NESTED
  sub-configs) → all 400. The CURRENT code (de85409) sends a DIFFERENT, more-correct shape:
  `agent_config={"type":"dynamic","thinking_level": level}` — a FLAT thinking_level on a
  `DynamicAgentConfigParam`. That exact shape is NOT in the memory's tested set.
- **SDK structural check (I verified):** `BaseCreateAgentInteractionParams` has `agent: Required` AND
  `agent_config: AgentConfig` (= Union[DynamicAgentConfigParam, DeepResearchAgentConfigParam]) as
  SIBLINGS — so `agent_config` is a valid co-param with a registered `agent=` (not a client-side
  ValueError like the typed-kwarg path). `DynamicAgentConfigParam` is `total=False, extra_items=object`,
  so `thinking_level` rides as an extra item. CONSEQUENCE: the SDK will SEND this call (no local reject);
  whether the managed-agent BACKEND honors it, ignores it, or 400s is GENUINELY UNKNOWN and was NOT
  proven by the prior session. (Open sub-question: does sending a `dynamic` agent_config alongside a
  REGISTERED custom agent "lazarus" conflict server-side?)
- **Verdict: thinking_level RE-OPENED — HOLD, genuinely open (not "verified no-op").** qa must re-test
  with the EXACT current shape on the real key and report ONE of:
  * ACCEPTED: `usage.total_thought_tokens` CHANGES minimal vs high (+ ideally `thought` blocks on the
    STREAM, since get() flattens them) → Feature 2 is VERIFIED WORKING (a real upgrade).
  * REJECTED (HTTP 400 / silently ignored — tokens identical minimal vs high) → confirmed graceful no-op,
    and `_looks_like_thinking_rejection` must catch the actual error (it currently keys on
    "agent_config"/"unknown field"/"invalid argument" — confirm the real 400 message matches, else the
    flag would crash the run instead of no-op'ing). Either outcome is shippable IF the docs match it; what
    I will NOT accept is asserting a verdict from the OLD memory's different-shape result. My L22 "verified
    no-op" is WITHDRAWN pending this re-test.

### L24 — RESOLVED (872f190): qa live-tested the exact shape — ACCEPTED-but-IGNORED, now labeled honestly
qa ran the current agent_config={"type":"dynamic","thinking_level":X} on the real key (the THIRD outcome,
not the binary I posed): the runtime ACCEPTS it (no 400) but SILENTLY IGNORES the depth — thought-token
counts do NOT track the requested level (high ≈ minimal, often fewer). 872f190 relabels the live trace to
exactly that ("the agent runtime ACCEPTS the param but does NOT honor depth: thinking runs at the default
and thought-token counts don't track the level") with ZERO implication of control; the thought-token line
is now "evidence the agent THOUGHT, not that the level applied"; the THINKING_REJECTED branch is documented
as defensive-only (not the observed behavior). I VERIFIED on the code: flag-OFF stays byte-identical (no
agent_config); the ON trace makes no false claim; 145 green.
THINKING_LEVEL VERDICT: HONEST + shippable as "documented knob tried, runtime ignores it, trace says so" —
NOT a working depth control. Sign-off conditions: (1) trace/docs imply ZERO control [MET]; (2) qa attach
the raw minimal-vs-high token numbers as the empirical receipt [pending]. STRONG honesty outcome — a
non-working capability surfaced truthfully rather than hidden.

### L24 — RECEIPT IN HAND → THINKING #2 FULLY VERIFIED (accepted-but-ignored, honestly labeled)
qa's raw token numbers (interleaved samples, identical prompt, recorded in memory thinking-level-rejected-live):
the SHIPPED shape `agent_config={"type":"dynamic","thinking_level":X}` returns status=completed, NO error
(ACCEPTED), but **high mean ≈ 2096 thought tokens vs minimal mean ≈ 2408 — high produced FEWER than minimal**
(the OPPOSITE of an honored level; the spread is run-to-run noise on the default). So the level is genuinely
NOT honored. Thinking DOES happen at the default (total_thought_tokens ~1000-2000 trivial; 21122 on a full
grounded migration). `thought` blocks appear only on the STREAM (get() flattens to model_output) — read them
off the stream. I confirmed on SHIPPED HEAD: the ONLY thinking marker is the honest one ("ACCEPTS the param
but does NOT honor depth…"); the bare false `[thinking_level=high]` marker count is 0; flag-off byte-identical;
146 green. NOTE: because the shape is accepted (never 400s), the THINKING_REJECTED fallback is dead code in
practice — correctly documented as defensive-only insurance.
**FEATURE 2 VERDICT: VERIFIED HONEST.** It is a truthfully-labeled accepted-but-ignored knob, NOT depth
control, backed by real interleaved-sample token numbers. Sign-off conditions both MET. Only residual: no
README/UI/DEMO line may imply thinking-depth control (DEMO_SCRIPT.md:54 "Pin thinking level" still needs the
reword — flagged to team-lead).

## L25 — GROUNDING (#1) honesty nuance: in grounding mode the agent MOSTLY compiled cobc live, barely web-researched — claim must not overstate causal contribution

- **What the grounding-mode run ACTUALLY did (from qa_capture_ground.out.txt narration, ~58 step intents):**
  only 2 are genuine WEB-search intents ("search the web for PAYROLL.COB", "search for COBOL display
  formats and de-editing rules"); ~3 more "search" mentions are FILESYSTEM searches (not web). Meanwhile
  ~49 mentions are install-micromamba / install-gnucobol / compile-cobc / generate-its-own-golden. So even
  with LAZARUS_GROUND=1, the agent OVERWHELMINGLY solved the task by compiling the original COBOL live and
  empirically capturing outputs — NOT by web research. This also explains the ZERO `SOURCE:` citations
  (L17-adjacent): the agent barely used the web, so it had little to cite.
- **Why this matters for the claim (not the code):** the grounding preamble says "research the idiom via
  google_search/url_context BEFORE forging." On this task that is NOT what predominantly happened — the
  agent's path was empirical (compile+run), which is arguably the BETTER engineering choice but is NOT
  "grounded research drove the migration." Demoing/claiming "web-grounding researches the dialect before
  forging" would OVERSTATE grounding's causal role on this sample. Honest framing: "with grounding on, the
  agent MAY consult google_search/url_context for an unfamiliar idiom (and we surface 🔎/🌐 + grounding_tool_
  count when it does); on the payroll sample it mostly verified empirically by compiling the original COBOL."
- **Verdict: NOT a code defect — a CLAIM-SCOPING finding.** Two things for sign-off: (1) qa STILL must show
  the histogram/grounding_tool_count so we know whether the 2 web-search intents even FIRED as
  google_search_call steps (if count==0, grounding did NOT fire at all on this run and #1 is unproven-live
  despite the flag); (2) whatever the count, the demo/README must frame grounding as an OPPORTUNISTIC
  consult, not the driver of the migration. If qa picks a sample with a genuinely obscure idiom (where the
  agent CAN'T just compile its way out), grounding's value would show more clearly — worth trying for a
  stronger #1 proof.

## L26 — RECONCILE: function_call/function_result blocks appeared LIVE (4 each) vs RESEARCH §3 "function_calling not supported" — needs the actual tool NAMES before I confirm "internal routing"

- **Apparent contradiction:** qa reports 4 function_call + 4 function_result step blocks on a live run.
  RESEARCH §3 quotes the antigravity doc verbatim: *"file_search, computer_use, google_maps, function_calling
  and mcp are not yet supported."* How do function_call blocks appear if function_calling "isn't supported"?
- **Resolution (almost certainly correct, but MUST be checked against the data, not assumed):**
  "function_calling not supported" = the USER cannot register their own custom functions for the agent to
  call (the user-facing feature). It does NOT mean the runtime never emits the `function_call` STEP TYPE. The
  agent's OWN internal tools can be surfaced over the generic function_call/function_result envelope. SDK
  evidence: `FunctionCallStep.name` = "the name of the TOOL to call"; `FunctionResultStep.name` = "the name
  of the TOOL that was called" + call_id + is_error. code_execution / google_search / url_context each have
  their OWN dedicated step types, so function_call is the generic envelope for whatever lacks a bespoke type.
- **WHAT I REQUIRE BEFORE WRITING THIS INTO DOCS (the L16 discipline, inverted — don't wave "benign"
  through either):** I will NOT assert "internal tool routing, not user-exposed function calling" on a
  relayed conclusion — I have not SEEN the blocks. qa must paste the 4 function_call `name` + `arguments`
  values (and function_result `name`s). Branches:
  * names = INTERNAL ops (filesystem/list/read/search-ish; no user-registered function) → CONFIRMS internal
    routing; our docs stay accurate (we never claimed user function-calling). Add ONE honest clarifying line.
  * names look like USER/CUSTOM functions, or LAZARUS appears to register tools → CONTRADICTS §3 + our
    "explicitly not used" claim → STOP, escalate, fix the claim.
- **Until I see the names: provisional read = internal routing (consistent), but UNCONFIRMED.**

### L26 — LOAD-BEARING HALF CONFIRMED BY ME (independent of seeing the names): LAZARUS registers ZERO user functions
I verified our code never passes `tools=` / `functions=` / `function_declarations` to `agents.create` OR
`interactions.create` (grep clean; ensure_agent omits tools → defaults to code_execution+google_search+
url_context). Therefore ANY function_call block that fired live CANNOT be user-registered function-calling —
it is necessarily the RUNTIME's OWN internal tool envelope. So the honesty-load-bearing claim — "LAZARUS does
NOT use user-facing function calling; RESEARCH §3 'function_calling not supported/used' stays accurate" — is
TRUE regardless of what the internal tool names are. The specific names (qa to paste) only refine an optional
doc line. ALSO: integration-eng added an honest function_call/function_result breadcrumb (working tree, cites
this L26) that SURFACES the tool name in the trace ("🛠 <name> <args>") so the names are auditable live — good
instrumentation, regression-safe (display-only, flags-off kwargs unchanged, 149 green).
**L26 VERDICT: the function_call blocks do NOT contradict §3 — our claim holds (we register no functions; the
envelope is the runtime's internal routing). Optional doc line + qa's name list would make it airtight, but
the claim is already safe to keep. Reconciliation CLEARED at the load-bearing level.**

## L27 — RELAYED "VERIFIED" ≠ EVIDENCE I'VE SEEN: #1 and #3 live proofs are NOT on my filesystem yet
team-lead relays qa's #1 grounding=VERIFIED (real google_search_call/result blocks) and #3=VERIFIED
(sentinel-token fresh-run discovery). My gate requires the BLOCKS, not the conclusion. As of this writing the
ONLY artifact on my box is qa_capture_ground.out.txt (model-output text only — the inconclusive one from
L17/L25; it has 0 google_search prose detail and no histogram). I have NOT seen: the google_search_call
histogram/grounding_tool_count, the sentinel-token discovery transcript, or the function_call names.
- #3 cross-run: the sentinel-token fresh-run discovery IS exactly the proof I asked for AND it matches the
  prior live memory [[skill-mount-discovery-live]] (ZARFLAX-7731) — so I can accept #3's DISCOVERY half on
  that corroboration. Residual: the BANKING half (agent echoes the SKILL.md body on a real forge so
  _bank_forged_skill_from_output captures it) — confirm that fired, or state banking is mechanism-verified
  (my drive) + discovery-verified (sentinel) with the echo dependency noted.
- #1 grounding: I need the actual google_search_call block(s) + grounding_tool_count to move it to VERIFIED.
  A relayed "qa captured real blocks" is encouraging but is not the receipt; given L25 (the agent mostly
  compiles rather than searches on payroll), I specifically need to see count>0 with the tool name.
**Verdict: #2 + #4(code/CLI) + regression are mine-verified; #1, #3-banking, and the L26 function_call
reconciliation are RELAYED-but-unseen → I hold those until the raw blocks land on my filesystem (or qa pastes
them).** Not distrust of qa — it's the difference between "told" and "verified," which is the whole job.

## L28 — THINKING 400-vs-200 CONFLICT: almost certainly an SDK-VERSION provenance issue (1.73.1 vs pinned 2.6.0). Settle with one probe of the EXACT committed shape on 2.6.0.

- **The conflict:** qa's direct messages say the runtime HARD-REJECTS (400) EVERY thinking shape (generation_config,
  extra_body variants, "agent_config nestings", top-level kwarg) — "tested live just now." team-lead's correction +
  memory [[thinking-level-rejected-live]] say the COMMITTED shape `agent_config={"type":"dynamic","thinking_level":X}`
  returns 200 (accepted) and is SILENTLY IGNORED (high≈minimal tokens) — NOT 400.
- **Two reasons these likely DON'T actually contradict:**
  1. SHAPE: qa's list says "agent_config NESTINGS" → 400. The committed shape is NOT a nesting — thinking_level is a
     FLAT key on a `{"type":"dynamic"}` config. qa's probe may simply not have included the exact flat-dynamic shape.
  2. SDK VERSION (the bigger one): team-lead notes the "every shape 400" checks were on **google-genai 1.73.1**;
     the shipped code PINS `>=2.6.0,<3.0.0` (requirements.txt; my env = 2.6.0). 1.73.1 predates the agent
     interactions surface (it's below even the 2.0.0 step.* floor) — its class names/wire shapes differ, so a 400
     there says nothing about 2.6.0. This is the [[captures-need-commit-provenance]] lesson applied to SDK version:
     a probe only proves things about the SDK it ran on.
- **WHY THE LABEL DIFFERS (and why I won't sign off until it's settled on 2.6.0):**
  * If the committed flat shape 400s on 2.6.0 → honest label = "rejected → graceful no-op," THINKING_REJECTED is LIVE.
  * If it returns 200-but-ignored on 2.6.0 → honest label = "accepted but depth NOT honored (silently ignored),"
    and THINKING_REJECTED is effectively DEAD CODE (correctly documented as defensive-only).
  Both yield the SAME user-facing honesty claim ("no thinking-depth control; thinking runs at default") — so the
  MERGE is not blocked on which one it is, BUT the README/verdict/trace WORDING must match the real mechanism, and a
  judge could probe it. The shipped trace already says "ACCEPTS the param but does NOT honor depth," which matches the
  200-ignored reading; if it's actually 400 on 2.6.0, that trace line is wrong and must change.
- **THE SETTLING PROBE (asked of qa):** on `google-genai==2.6.0` (the pin), send `client.interactions.create(
  agent="lazarus", input="hi", agent_config={"type":"dynamic","thinking_level":"high"}, ...)` and paste the RAW
  result: HTTP status (200 vs 400), and if 200, total_thought_tokens for high vs minimal. + the SDK version printed.
- **Verdict: FEATURE 2 label HELD until qa probes the EXACT committed shape on 2.6.0.** Provisional (and most
  likely): accepted-but-ignored on 2.6.0 (matches memory + the shipped trace). The user-facing "no depth control"
  claim is safe either way; the precise mechanism wording + the THINKING_REJECTED-dead-code question hinge on the
  probe. This is the one fact qa and I must AGREE on before I sign #2 (per team-lead's explicit ask).

## L25/L26 — INSTRUMENTATION LANDED (7ad5de2), verified by me — exactly the receipts I asked for
integration-eng's 7ad5de2 added the observability I requested, honestly framed (no behavior change; 149 green;
flags-off byte-identical confirmed):
- L25 grounding count: when grounding is ON, end-of-run emits `[grounding_tool_count=N (google_search=.., 
  url_context=..) — web-grounding fired this run; an opportunistic consult, not the migration driver]` for N>0,
  or `[grounding_tool_count=0 — web-grounding was ENABLED but did NOT fire this run (the agent solved it without
  web research)]` for N==0. This is the histogram/count I needed — AND it honestly reports 0 (can't accidentally
  claim grounding fired when it didn't). Gated on `ground_on` → grounding OFF prints nothing (byte-identical).
- L26 function_call breadcrumb: `🛠 <name>` surfaces the internal tool name live (auditable).
So on qa's NEXT grounding run the count prints in-band — #1's receipt is now self-producing. My L25 honesty
framing ("opportunistic consult, not the driver") is baked into the trace string verbatim. Good.

---

# ===== DEVIL'S-ADVOCATE SIGN-OFF CRITERIA (the exact gate) =====

CLEARED (mine-verified, not relayed):
- [x] REGRESSION: all flags OFF byte-identical to main — _build_prompt, _build_forge_retry_prompt,
      build_base_environment, interaction kwargs {agent,extra_body,input,stream} (no agent_config/
      generation_config), ensure_agent clean-fork no-op, grounding_tool_count gated off. (re-verified each HEAD)
- [x] FALSIFIABILITY: server.py / differential_oracle.py / event_transform.py UNTOUCHED on the branch →
      verdict tracks the oracle, not the agent; the 4 falsifiability tests pass.
- [x] NO unsupported-surface reach: we register ZERO user functions/tools (L26) → function_call blocks are
      runtime-internal routing, §3 "function_calling not used" holds. No structured-output/mcp/file_search/
      computer_use/sub-agents. No model-vs-agent capability conflation.
- [x] SUITE green & deterministic (154 at last check), incl. the real-SDK breadcrumb guard (L17).
- [x] #4 whole-codebase: code + CLI entry verified (L23 opt-a); honest scope caveat recorded (recovery
      showcase, NOT oracle-byte-verified — single-module golden).
- [x] #2 thinking USER-FACING claim: "no depth control; thinking runs at default" is honest; shipped trace
      makes zero control implication; bare false [thinking_level=X] marker is gone.
- [x] Honesty instrumentation (grounding count, 🛠 names) landed, gated, honestly framed.

PENDING (RELAYED → must become SEEN before I sign; all are qa live receipts I can't self-produce):
- [ ] L28: qa probes the EXACT committed shape agent_config={"type":"dynamic","thinking_level":"high"} on
      google-genai 2.6.0 (the pin) → raw HTTP status (200 vs 400) + high-vs-minimal thought tokens + version
      string. Locks the #2 MECHANISM wording (accepted-but-ignored vs rejected; THINKING_REJECTED live/dead).
      [merge not blocked on which; wording must match]
- [ ] #1 grounding: one live run's [grounding_tool_count=N ...] line with N>0 (or an honest N==0 stated).
- [ ] #3 cross-run BANKING half: a forge run where the agent echoes the SKILL.md body → banked
      .agents/skills/<name>/SKILL.md on disk (discovery half already accepted: sentinel == prior ZARFLAX live).
- [ ] #4: the PAYMAIN→TAXSUB cross-module LAZARUS_RULE text + which golden the oracle used.

DOCS PASS (team-lead owns, post-verdict): DEMO_SCRIPT:54 "pin thinking level" reword; README:83 cross-run
framing; grounding-is-opportunistic (L25) line; "#4 is CLI/API, web is single-file" note; function_call-
envelope honesty line (L26); #2 wording = accepted-but-ignored (NOT "400 rejected"), pending L28.

When the 4 PENDING boxes are checked from evidence I've SEEN, I issue FULL per-feature sign-off and the merge
of feature/agent-capabilities → main is cleared.

## L29 — SYSTEMIC: SDK-version provenance has bitten the team TWICE (1.73.1 vs pinned 2.6.0). EVERY live verdict must state the SDK version.

- **Two instances, same root cause:**
  1. L28 thinking "every shape 400s" — checked on google-genai 1.73.1.
  2. test_grounding_breadcrumbs_use_real_sdk_types committed COMMENT (f2978cb) claims "*Step ABSENT, *Content
     real, verified on 1.73.1" — INVERTED for the pin. Ground truth I ran on 2.6.0: *Step EXIST,
     *Content ABSENT (GoogleSearchCallStep/URLContextCallStep/URLContextResultStep all True; *Content all
     False). The test still PASSES only because the _sdk() resolver tries both suffixes; the comment is a
     latent landmine (someone trusting it could drop the *Step candidate → guard silently skips on 2.6.0).
- **THE BROADER IMPLICATION FOR MY GATE:** the shipped code PINS google-genai>=2.6.0,<3.0.0. ANY live finding
  run on a different SDK (esp. 1.73.1) is suspect — class names AND wire shapes differ across that major.
  This now applies to qa's RELAYED #1/#3/#4 "VERIFIED" verdicts too: I must confirm they ran on 2.6.x, not
  just that "blocks appeared." A google_search_call block on 1.73.1 doesn't prove the 2.6.0 shipped path
  works. Escalated to team-lead.
- **GATE RULE (added):** every PENDING live receipt must include the printed `g.__version__` and it must be
  2.6.x (the pin). No version stamp → not accepted as evidence for the shipped path. This is the
  [[captures-need-commit-provenance]] discipline extended to SDK version.
- **Verdict: not a code bug (suite green; resolver robust) — a VERIFICATION-HYGIENE finding that gates the
  trustworthiness of the relayed live verdicts. Fix: frontend corrects the inverted comment; qa stamps SDK
  version on all 4 pending receipts.**

## L28 — DEFINITIVELY SETTLED by qa's re-verification: ACCEPTED-BUT-IGNORED on the shipped shape (matches my L24/L28 prediction)
qa re-ran the SHIPPED `agent_config={"type":"dynamic","thinking_level":<lvl>}` live and RETRACTED their earlier
"rejected→graceful no-op" verdict: it is ACCEPTED (no 400), depth SILENTLY IGNORED — interleaved identical-prompt
samples high mean ≈2096 vs minimal mean ≈2408 thought tokens (high < minimal = noise on default). This is exactly
what I predicted (L24/L28) and matches [[thinking-level-rejected-live]]. The 400s were the OTHER shapes (L29
version/shape confusion). #2 mechanism = ACCEPTED-BUT-IGNORED, SETTLED. The user-facing "no depth control" claim
holds; THINKING_REJECTED is confirmed dead code on the shipped shape (defensive-only).

## L30 — Last Feature-2 honesty hole: agent.py docstring (line ~695) still asserts "rejects EVERY thinking config shape (400)" — FALSE for the shipped shape
- **The hole (qa-flagged + I confirmed on committed HEAD a33324f):** `_looks_like_thinking_rejection`'s docstring
  says "qa LIVE-PROVED the managed-agent runtime rejects every thinking config shape (400)" and frames the shipped
  shape as "if THAT is also rejected." But qa's own re-verification (L28 above) proves the shipped type:dynamic
  shape is ACCEPTED-but-ignored, NOT rejected. So the docstring overclaims "every shape 400s" and tells the wrong
  story about the shape we actually send. (The OTHER functions' docstrings — lines 728/744/767 — correctly say
  accepted-but-ignored, so the file is internally contradictory.)
- **What's ALREADY honest (verified):** no bare `[thinking_level=X]` marker anywhere in src/ or web/ (HOLE 2 from
  qa = already fixed; the live trace says "ACCEPTS the param but does NOT honor depth"). The rejection test is
  ALREADY labeled "DEFENSIVE" (HOLE 1 = documented as insurance, not live behavior — acceptable).
- **Verdict: NEEDS FIX (docstring only, integration-eng lane).** Reword line ~695 to: "The OTHER thinking shapes
  (top-level generation_config / extra_body variants) 400; the shipped agent_config={type:dynamic,thinking_level}
  shape is ACCEPTED but the depth is IGNORED (qa live). This heuristic + the retry are DEFENSIVE-ONLY insurance
  for a future runtime that starts rejecting the param — NOT the observed live behavior." Small, but it's a code
  comment asserting a now-disproven 'rejects every shape' — must match the accepted-but-ignored reality. This is
  the LAST Feature-2 honesty item; once it's reworded, #2 is fully honest end-to-end.

### L30 — RESOLVED (b2ba1ed). Verified: docstring no longer claims "rejects every shape (400)"; now reads "The
OTHER shapes (generation_config/extra_body) 400; the SHIPPED agent_config={type:dynamic,thinking_level} shape is
ACCEPTED but depth IGNORED (qa live: high≈2096 < minimal≈2408) ... DEFENSIVE-ONLY ... NOT observed live." Honest,
cites the numbers, labels the heuristic defensive. **Feature 2 CODE/honesty surface FULLY CLEAN now: honest trace,
corrected docstring, defensive-labeled rejection test, no false marker. Only #2 residual = qa's version-stamped
token receipt (the docstring already quotes the numbers).**

### L17 / L18 — CLOSED (verified by me on committed HEAD, installed google-genai 2.6.0)
- L17: _tool_breadcrumb reads arguments.queries/urls (plural) + List[Result] → 🔎/🌐 render; real-SDK guard test present.
- L18: sends agent_config={"type":"dynamic","thinking_level":lvl} (flat, no nested thinking_config, no generation_config).
- L16 seeding sub-concern: build_base_environment mounts targets==['.agents/AGENTS.md'] with flag off → byte-identity holds.

### _looks_like_thinking_rejection breadth (integration-eng's review Q) — NOT a blocker
DEAD CODE on the shipped path (type:dynamic returns 200, no error — L28). Theoretical residual only if the runtime
ever errors: a TRANSIENT unrelated error containing a matched substring would be swallowed + retried; if the retry
succeeds (transient cleared) a real error is masked + THINKING_REJECTED falsely set. (The "retry re-raises" defense
holds only for DETERMINISTIC errors, not transient.) Cheap optional hardening offered (narrow to specific
agent_config/thinking signatures). Not gating — flagged for the record.

## L29 — RESOLVED with hard evidence from BOTH interpreters: the pin IS satisfied; tests run on 2.6.0
frontend-eng escalated "installed SDK is 1.73.1, below the >=2.6.0 pin → all our SDK-shape claims verified on the
wrong version." I ran BOTH interpreters to settle it:
- `.venv/bin/python` → google-genai 2.6.0 → GoogleSearchCallStep=True, *Content=False
- system `python3`   → google-genai 1.73.1 → GoogleSearchCallStep=False, *Content=True
- `pytest` sys.executable = `.venv/bin/python` → THE SUITE RUNS ON 2.6.0.
CONCLUSION: the .venv HAS the pinned 2.6.0; unit tests + all my L17/L18 static checks ran on 2.6.0 (correct).
frontend read SYSTEM python3 (1.73.1) — the box has BOTH SDKs under different interpreters; the system one is
irrelevant. NO provenance gap under "verified on SDK" claims — they're on the pin. Only stray system-python3
probes (frontend's earlier comment; qa's early "400 every shape") were on 1.73.1. Matches repo memory
[[sdk-version-provenance-gap]]. Do NOT lower the pin or re-verify on 1.73.1. **L29 resolved: shipped path verified
on the pinned SDK. The standing gate rule (qa stamp 2.6.x on LIVE receipts) is now ONLY about confirming qa's LIVE
runs used .venv — the unit tests + my static checks are confirmed on 2.6.0.**

## matcher-breadth (L30 follow-on) — HARDENED + verified (8b0b574, DA opt-a)
integration-eng took my option (a): _looks_like_thinking_rejection now matches ONLY config-field tokens
(thinking_level/thinking_config/agent_config/generation_config), dropping the generic phrases ("invalid
argument"/"not supported"/"unexpected"/"unknown parameter" alone). I verified the narrowing on 2.6.0:
- REAL errors STILL caught (defensive path intact if the runtime ever rejects): "use agent_config",
  "Unknown parameter 'generation_config'", "agent_config.thinking_level" → all True.
- UNRELATED errors now correctly NOT swallowed: "503", "deadline exceeded", "invalid argument:
  temperature out of range", "rate limit exceeded" → all False.
So the transient-error-masking risk I flagged is GONE, and the branch (dead on the shipped accepted path) can
no longer hide a real error if it ever fires. Optional item CLOSED. 154 green. This was the last open
code-quality note on Feature 2; nothing further on the code side.

## CODE-SIDE GATE: FULLY CLOSED. Only qa's 4 version-stamped (.venv/2.6.x) LIVE receipts remain for full sign-off.
Every code/honesty/regression item I raised (L16-L30 incl. the optional matcher hardening) is fixed + verified
on the pinned SDK. The verdict/oracle/falsifiability core is untouched. The merge gate is now PURELY:
(1) #1 grounding_tool_count>0 line, (2) #3 banked SKILL.md on a forge, (3) #4 PAYMAIN→TAXSUB rule + golden,
(4) #2 thinking token stamp — each produced via .venv/2.6.x. I sign off the moment those land.

## L31 — POST-MERGE: "silently ignored / does NOT honor depth (high≈2096<minimal≈2408)" is now an OVERCLAIM — qa's defensible final is INCONCLUSIVE. Soften the shipped wording.
- qa ran the definitive thinking probe ON THE PINNED 2.6.0 (.venv, version printed inline) and RETRACTED BOTH prior
  verdicts. Defensible final: shipped shape ACCEPTED (settled); whether the level is HONORED is INCONCLUSIVE —
  thought-token NOISE (±~1000/call) swamps any effect; interleaved samples NON-MONOTONIC (2 high<min, 6 high>min,
  12 flat; means 2785/2692/2665). Neither "ignored" nor "honored" is provable.
- OVERCLAIM now on main (6504a78): agent.py:697-698 "depth is IGNORED (... high ≈ 2096 < minimal ≈ 2408)";
  agent.py:732/748/772 "does NOT honor depth"; README:103 "accepts the param but SILENTLY IGNORES it." All assert a
  DEMONSTRATED null with cherry-picked high<minimal numbers — but qa says that direction was noise (other samples
  high>minimal). A judge who re-runs and sees high>minimal catches it.
- Honest framing: "request the level via the SDK-correct agent_config shape; runtime ACCEPTS it (no 400); thinking
  runs (large token counts); CANNOT demonstrate the level changes behavior — noise-dominated, non-monotonic. No depth
  control; effect INCONCLUSIVE." Not "silently ignored / does not honor" + numbers.
- Verdict: NEEDS WORDING FIX (post-merge, low-effort, judge-relevant). Replace "silently ignored / does NOT honor
  depth (high≈2096<minimal≈2408)" → "accepted; effect on depth INCONCLUSIVE (noise-dominated, non-monotonic)" in
  README:103 + agent.py docstrings (697/732/748) + trace marker (772). Direction of the error is SAFE (overclaims a
  NEGATIVE, not a capability) → NOT a stop-the-line/unmerge issue; but it IS a catchable inaccuracy. Belongs in
  team-lead's docs pass. User-facing headline ("no depth control / not a knob we can set") stays TRUE either way —
  only the MECHANISM claim (proven-ignored vs unprovable) needs softening. Grounding/skill/multi-module + regression +
  falsifiability unaffected.

## L28/L31 — VERSION-STAMPED RECEIPT LANDED (qa) → thinking 400-vs-200 SETTLED; L29 stamp satisfied for #2
qa pasted the definitive probe WITH full provenance (the L29 version-stamp I required):
  google-genai 2.6.0 · .venv/bin/python · agent_config={'type':'dynamic','thinking_level':'high'} → HTTP 200 ACCEPTED,
  status=completed, total_thought_tokens=927.
So the COMMITTED shape returns 200 (accepted) on the pinned SDK — NOT 400. My L28 SDK-provenance call is confirmed
(the "400 every shape" was 1.73.1 / other shapes). THINKING_REJECTED is dead code on this shape (no error fires) —
confirmed. This converts the #2 thinking item from RELAYED → SEEN (version-stamped on 2.6.0). 
WORDING NUANCE (keep the conservative one): qa's latest phrasing "accepted-but-NOT-honored" still slightly
overclaims a demonstrated null; their OWN sample data (12-sample means 2785/2692/2665 flat; ±1000 noise;
non-monotonic 2 high<min / 6 high>min) supports "accepted; effect on depth INCONCLUSIVE" as the defensible
statement (per L31). Net: #2 = ACCEPTED (200, version-stamped) + depth-effect INCONCLUSIVE + no control claimed.
The L31 docs softening ("silently ignored" → inconclusive) still applies.

## FINAL CLOSURE — L31 fixed in BOTH README + code; #1 grounding receipt SEEN; review CLOSED.
- **L31 RESOLVED (fd62079 + README docs pass):** the "silently ignored / does NOT honor depth / high≈2096<
  minimal≈2408" overclaim is GONE from agent.py (grep empty) AND README:103. Both now say "ACCEPTS the param
  (no 400); effect on reasoning depth is NOT demonstrable / INCONCLUSIVE — noise-dominated." Conservative
  framing applied exactly as recommended. (Skill-library README also corrected to "DISCOVERY live-verified,
  banking is follow-up #9" — 88fa8a7.)
- **#1 GROUNDING — RELAYED→SEEN, VERIFIED:** qa pasted the verbatim stdout histogram from the 884s grounded
  payroll migration (LAZARUS_GROUND=1, real key, .venv/2.6.0): STREAM histogram has google_search_call:3 +
  google_search_result:3 (+ the FETCH flattens to model_output:255 — the inverted-L16 trap, confirmed & handled
  since agent.py reads the STREAM). The search step empirically FIRED on a real migration on the pinned SDK.
  My L16 hold for #1 is CLEARED with version-stamped evidence I've now seen.
- **Per-feature FINAL (version-stamped on .venv/2.6.0):** #1 grounding VERIFIED (3 google_search_call live);
  #2 thinking ACCEPTED(200)+effect-INCONCLUSIVE, no control claimed (honest wording shipped); #3 cross-run
  DISCOVERY verified (sentinel), banking = follow-up #9; #4 multi-module rule-recovery VERIFIED (PAYMAIN→TAXSUB),
  NOT oracle-byte-verified (honest caveat shipped). Regression byte-identical + falsifiability core untouched.
- **README capabilities table is honest on all four** (verified line-by-line). Only outstanding item is the
  documented non-blocking follow-up #9 (bank the raw artifacts into the repo + the #3 banked-file-on-disk live
  assertion). 
**DEVIL'S-ADVOCATE REVIEW CLOSED.** Every finding L16-L31 is fixed/verified/honestly-deferred; no open honesty,
feasibility, or regression issue. Merge (6504a78) stands; #9 is the only follow-up.

## L32 — CORRECTION to my own gate criterion: `usage.grounding_tool_count` is NOT a usable receipt (runtime leaves it None). Use the google_search_call STEP BLOCKS.
- **My earlier criterion was wrong:** in L17/L25 I told qa+team-lead that `usage.grounding_tool_count>0` was an
  "authoritative server-side proof" for grounding. qa empirically DISPROVED that: on a real grounded run (3 searches
  fired) the full usage object had `grounding_tool_count=None` (with total_thought_tokens=4094, total_tokens=153935).
  I cross-checked the SDK: `Usage.grounding_tool_count: Optional[List[GroundingToolCount]] = None` — the field EXISTS
  in the schema but the Antigravity runtime does NOT populate it. So gating on it = a permanent FALSE NEGATIVE.
- **The RELIABLE receipt is the `google_search_call` STEP BLOCKS in the STREAM** (each with a unique id; arguments=null
  at step.start, query populates at step.stop; type is the fixed Literal "google_search_call"). The SHIPPED L25
  instrumentation already counts THESE (agent.py grounding_calls, incremented on step.start) — NOT grounding_tool_count
  — so the shipped code uses the correct signal; only my stated criterion needed fixing. (Same class as the L26
  function_call lesson and the get()-flattening trap: trust the STREAM step blocks, not a derived/aggregate field.)
- **#1 GROUNDING — receipt (a) is the STRONGEST proof and CLOSES L16/L25:** qa ran grounding on a HARDER, un-revealed
  idiom (per my L25 ask) — "OCCURS DEPENDING ON + SYNCHRONIZED COMP-1 slack-byte computation", NOT hinted — on
  .venv/2.6.0, and captured 3 raw google_search_call blocks (ids e8f7lr9u / of6ebqyy / 2dkau3cb). This is better than
  the payroll run (where grounding barely fired) because the idiom forces real research. #1 fully VERIFIED, seen, on
  the pin.
- **Action:** I will NOT re-assert grounding_tool_count anywhere; the README already says "ran 3 google_search_calls"
  (step blocks), not a count field, so the shipped claim is on the reliable signal. No doc change needed beyond this
  record. Lesson logged for future SDK-field gates: verify a field is RUNTIME-POPULATED before gating on it.
- Remaining follow-up #9 items still open (qa in flight): (b) function_call NAMES from a migration-class run
  (the pure-search run had 0 function_call blocks — consistent; the 9 were in the 884s migration), (c) banked SKILL.md
  on disk, (d) cross-module rule TEXT. These are the non-blocking artifact-banking items; #1 grounding does not wait
  on them.

## L26 — FULLY CONFIRMED with the tool NAMES (receipt b): function_call = INTERNAL filesystem ops, NOT user functions
qa pasted the raw function_call NAMES from a tool-use probe (.venv/2.6.0): name='list_files' (×3), 'read_file' (×2),
'write_file' (×1) — each paired with a function_result; arguments={} at step.start, populate at step.stop. These are
the agent's BUILT-IN sandbox filesystem tooling, NOT user/custom function registration. This empirically confirms the
L26 reconciliation BOTH ways now: (1) our code registers ZERO user functions (I verified — no tools=/functions= to
agents.create/interactions.create), AND (2) the names that appear are internal FS ops. So the function_call envelope
does NOT contradict §3 ("managed-agent runtime does not expose user-facing function_calling") — it's the runtime
surfacing its own filesystem I/O as typed steps (alongside code_execution + persistent FS). Docs stay accurate; the
optional doc line can now name them: "the runtime emits function_call envelopes for its OWN internal tools
(list_files/read_file/write_file); LAZARUS registers no user functions." L26 fully closed — relayed→SEEN with names.
Remaining: (c) banked SKILL.md + (d) cross-module rule TEXT = the only open #9 artifacts; both non-blocking.

## L19/L27 #3 BANKING — VERIFIED END-TO-END (receipt c). Cross-run skill library fully closed.
qa ran a REAL forge interaction (.venv/2.6.0, AGENTS_DIR redirected to a temp dir so it never touched the repo):
the agent hit an unknown idiom (SIGN IS TRAILING SEPARATE), stated the path .agents/skills/sign-trailing-separate/
SKILL.md, and ECHOED the complete SKILL.md body in a fenced block. That REAL output flowed through the SHIPPED
banking path (_bank_forged_skill_from_output → _persist_forged_skill) and a 748-byte SKILL.md with valid YAML
frontmatter (name: sign-trailing-separate) landed on disk (temp dir, confirmed not the real repo). This answers the
exact gap I flagged in L19/L27 ("does the live agent ECHO the body so banking captures it, vs disk-only?") — YES,
the agent's real output matches the path-then-fenced-block shape the parser expects. So banking is proven on REAL
agent output, not just synthetic unit input. Combined with the ZARFLAX discovery proof ([[skill-mount-discovery-live]]),
the CROSS-RUN SKILL LIBRARY is VERIFIED END-TO-END: forge+echo → bank-to-disk → (fingerprint change → re-register →
mount) → fresh-run startup discovery. #3 fully CLOSED.

## #9 STATUS — 3 of 4 artifacts SEEN + version-stamped; only (d) cross-module rule text remains
(a) grounding 3× google_search_call on a hard idiom — SEEN (L32). (b) function_call names = list/read/write_file
internal FS ops — SEEN (L26). (c) banking SKILL.md on disk from a real forge — SEEN (this entry). (d) cross-module
rule TEXT (PAYMAIN→TAXSUB) — qa re-running in foreground (the bg runs got reaped). All four FEATURES already had a
verdict; these receipts upgrade #1/#3 from strong-indication to SEEN and confirm L26. (d) will finalize the #4
rule-text receipt but #4's verdict (rule-recovery verified, not oracle-byte-verified) already stands. Nothing in my
gate is open. **DEVIL'S-ADVOCATE REVIEW REMAINS CLOSED; receipts are confirming, not reopening.**

## #4 cross-module rule TEXT — SEEN (receipt d). ALL 4 #9 RECEIPTS NOW SEEN + version-stamped.
qa pasted the raw recovered rule from the 2-file PAYMAIN→TAXSUB system (.venv/2.6.0, read off the STREAM). RULE 1
"Cross-Module Tax Calculation Delegation" has `cobol_ref: PAYMAIN.COB: CALL 'TAXSUB' USING WS-GROSS WS-TAX. and
TAXSUB.COB: PROCEDURE DIVISION USING LK-GROSS LK-TAX.` — ONE rule citing BOTH files; the CALL relationship + the
rate-defined-only-in-the-subprogram fact (RULE 2: WS-TAX-RATE 0.225 in TAXSUB) are invisible from either file alone.
Tool check: `any rule names BOTH PAYMAIN+TAXSUB = True`. Genuine cross-module recovery, NOT two concatenated
single-file analyses — meets my L20/L23 bar. qa shipped the REQUIRED honest caveat (and the README:102 matches it):
RECOVERY only; NO multi-module golden (golden_io.json is single-module payroll) → multi-module OUTPUT is NOT
oracle-byte-verified; must not imply byte-verification. #4 receipt SEEN; verdict unchanged (rule-recovery verified,
honest oracle caveat shipped).

## ✅ FULL PER-FEATURE SIGN-OFF (devils-advocate, task #4) — GRANTED, all evidence SEEN on the pinned SDK
Final verification on merged main (80f69d6): suite 154 green; flags-OFF byte-identical to PRE-FEATURE main 26f65e4
(prompt + base_environment + forge-retry prompt all identical — verified just now); verdict/oracle/falsifiability
core untouched; README capabilities table honest line-by-line. All four live receipts are SEEN + version-stamped
(.venv / google-genai 2.6.0):
- **#1 WEB-GROUNDING — VERIFIED:** 3 raw google_search_call blocks on a hard un-revealed idiom (a).
- **#2 THINKING — ACCEPTED (HTTP 200), depth-effect INCONCLUSIVE, NO control claimed:** L28 locked (200 not 400);
  L31 overclaim softened in code+README; THINKING_REJECTED dead-code labeled defensive; matcher hardened (L30/opt-a).
- **#3 CROSS-RUN SKILL LIBRARY — VERIFIED END-TO-END:** discovery (ZARFLAX) + banking-on-real-forge SKILL.md on disk (c).
- **#4 WHOLE-CODEBASE — rule-recovery VERIFIED:** cross-module PAYMAIN→TAXSUB rule (d); honest "NOT oracle-byte-
  verified" caveat shipped; CLI entry added (L23).
- function_call reconciliation (L26): names = internal FS ops (list/read/write_file); §3 holds.
HONESTY POSTURE: every shipped claim rests on version-stamped evidence I've seen; the one overclaim that reached
main (L31 "silently ignored") was caught and corrected; no capability is claimed beyond what the runtime does; the
core "verdict tracks the oracle, not the agent" guarantee survives all four. The .venv/2.6.0-vs-system/1.73.1
provenance discipline (L29) held throughout and resolved every conflicting finding. **No open honesty, feasibility,
or regression issue. Merge 6504a78 is fully signed off. DEVIL'S-ADVOCATE REVIEW COMPLETE.**

## L33 — POST-SIGN-OFF: qa-found BANKING BUG (migrate() mis-banks the LAZARUS_MODULE python block as the SKILL.md) — VERIFIED FIXED + I added the missing regression guard
- **The bug (qa, filed to integration-eng):** on a REAL migrate() RED iteration the agent prints the
  LAZARUS_MODULE ```python block AFTER the skill path. The OLD _bank_forged_skill_from_output banked the FIRST
  fenced block after the path → it banked payroll.py (the migrated module) AS the SKILL.md, which would then be
  mounted as "idiom guidance" on a fresh run. Real, shipped-path bug; the forge-specific (c) receipt didn't surface
  it because that probe echoed only the skill block.
- **FIX (already in committed HEAD):** _bank_forged_skill_from_output now iterates ALL fenced blocks and banks the
  first that passes _looks_like_skill_md — which HARD-REJECTS python/cobol/json langs + code-ish prefixes
  (#!/usr/bin/env, import, from, def, class) and ACCEPTS YAML-frontmatter / markdown. I DROVE the exact bug shape
  (python block first, then the real ---/name: SKILL.md): banking correctly SKIPS the module and banks the skill
  (verified: banked body has the frontmatter, no python). Fix is robust.
- **GAP I caught + closed:** the fix had NO dedicated regression test — the 3 existing bank tests cover
  happy-path / no-body / no-repo-pollution, none fed a python block. I ADDED
  test_bank_forged_skill_skips_lazarus_module_python_block (committed 5f29d49): feeds the python-block-first shape,
  asserts the module is NOT banked and the SKILL.md IS. 155 green. The bug can no longer silently regress.
- **Impact on sign-off:** NONE adverse — the fix predated my sign-off and is correct; this only HARDENS #3
  (banking solid AND now guarded). Good catch by qa; exactly the kind of real-path bug a forge-specific receipt
  misses. #3 cross-run remains VERIFIED, now with a regression guard.
- **Pending (non-gating, qa offered):** a single continuous bank-in-A → fresh-B-discovers chain (the L19
  methodological gap — proven as two halves so far). Belt-and-suspenders; sign-off does not wait on it. (d) banking
  on the migrate() path is already covered by L33's fix+test.

## L19 GAP CLOSED — CROSS-RUN chain proven in ONE continuous run (qa, version-stamped). #3 maximally grounded.
The last methodological gap I'd noted (L19/L27: discovery + banking proven as two SEPARATE halves, not one
continuous chain) is now closed. qa ran bank-in-A → re-register → SEPARATE-fresh-B-discovers in ONE
version-stamped run (g.__version__=2.6.0):
- RUN A forged + banked .../skills/qwxj-crossrun-idiom/SKILL.md (121 bytes, YAML frontmatter, NOT python — also
  re-confirms the L33 banking-bug fix: banks the markdown body, not the LAZARUS_MODULE python block).
- RE-REGISTER: fingerprint changed=True; banked skill present in the new base_environment mounts.
- RUN B (a SEPARATE FRESH interaction on the re-registered agent) emitted the sentinel QWXJ-CROSSRUN-5582 + "qwxj"
  — tokens that exist ONLY in the skill RUN A banked. A skill surviving in the SAME reused env CANNOT explain a
  fresh agent emitting them (fresh interaction, new mount). So this is genuine cross-run accumulation end-to-end,
  not the same-env FORGE-retry beat.
This is the strongest #3 proof and it directly addresses every condition I set (echo→bank→re-register→fresh-run
discovery, all in one chain, version-stamped). Saved to docs/EVIDENCE.md. #3 cross-run skill library: VERIFIED
END-TO-END, maximally grounded. (Sign-off already stood on the two-halves proof + L33 fix/test; this is the
belt-and-suspenders upgrade I asked for.)

## ===== FINAL STATE (all 4 features + all #9 receipts SEEN, version-stamped on .venv/2.6.0) =====
#1 grounding: VERIFIED (two grounded runs, 3 and 2 google_search_call stream blocks on a hard idiom; L32:
grounding_tool_count unusable/None, use stream blocks). #2 thinking: ACCEPTED (HTTP 200) + depth INCONCLUSIVE,
no control claimed (L28/L31, wording softened in code+README). #3 cross-run: VERIFIED END-TO-END (continuous
chain above; L33 banking bug fixed + regression-tested). #4 multi-module: cross-module rule VERIFIED
(PAYMAIN→TAXSUB), honest "not oracle-byte-verified" caveat shipped, CLI entry. function_call (L26): internal FS
ops, §3 holds. Regression byte-identical to pre-feature main; oracle/falsifiability core untouched; suite 155
green. Findings L16-L33. DEVIL'S-ADVOCATE REVIEW COMPLETE — sign-off granted, now maximally grounded; no open
honesty/feasibility/regression issue.
