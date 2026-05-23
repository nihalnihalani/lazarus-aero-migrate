# CHALLENGES — Devil's Advocate Log (owner: devils-advocate)

> Every load-bearing assumption gets attacked here. For each: state the claim, the
> attack, evidence (with URL), and a verdict: **CONFIRMED** / **NEEDS FIX** / **FALSE —
> redesign** / **ACCEPTED RISK**. Escalate FALSE/NEEDS-FIX to the lead immediately.

**Posture:** assume a skeptical Google DeepMind judge AND a skeptical AI Futures Fund
investor are in the room and will fact-check every number and every platform claim.

---

## SCOREBOARD (read this first)

| # | Item | Severity | Verdict |
|---|---|---|---|
| C1 | Runtime self-authored `SKILL.md` is a real primitive | load-bearing ($5k) | **CONFIRMED (mechanism)** — but cross-run persistence is overclaimed (see C1b) |
| C1b | Forged skills "persist forever / accumulate across runs" | load-bearing (moat) | **NEEDS FIX** — fresh invocations fork clean |
| C2 | "computer_use / file_search NOT used (unsupported)" honesty claim | load-bearing (honesty) | **CONFIRMED** — both genuinely unsupported; seed premise was wrong |
| C3 | Base agent ID `antigravity-preview-05-2026` | load-bearing (it runs) | **CONFIRMED** — exact + only supported value |
| C4 | Agent compiles + runs real COBOL via GnuCOBOL live | load-bearing (#1 anti-objection) | **NEEDS FIX** (downgraded from FALSE — product mix-up corrected; Gemini API has network ON by default; "pre-installed" is still false; apt/root pending). Falsifiability INTACT via golden_io.json / mounted binary. |
| C5 | "byte-for-byte" diff is robust | load-bearing (demo) | **NEEDS FIX (TESTED)** — zero-pad format + half-up rounding fail naively; proven fix = Decimal/HALF_UP + `{:07d}.{:02d}` (9/9 byte-exact) |
| C6 | Sandbox spec (Python 3.12 / Node 22 / 4CPU·16GB / 15-min snapshot) | medium | **MOSTLY RETRACTED** — I cited wrong product; on the Gemini API, 3.12/Node22/15-min-snapshot are CORRECT. Only "4CPU/16GB" still unsourced. |
| C7 | NJ impact stats (1600%, 575k, "begged on live TV") | medium (Impact = 20%) | **MIXED** — 1600% CONFIRMED; 575k UNVERIFIED; "live TV" embellished |
| C8 | $2.41T tech debt; 18–23% wasted; $30B market | medium (Impact = 20%) | **CONFIRMED** (with date caveats) |
| C9 | "1M-token context" relevance to a ~150-line module | low (framing) | **NEEDS FIX** — non-sequitur a judge will needle |
| C10 | `MAX_ITERATIONS = 4` "hard cap" + "visible counter" | medium (demo safety) | **NEEDS FIX** — not enforced in code; only prompt text |
| C11 | agent.py streaming/SDK field names | medium (it runs) | **NEEDS FIX** — guessed schema; verify or it crashes |
| C12 | Demo determinism / cold-start | medium (Demo = 45%) | **ACCEPTED RISK** — mitigations exist; tighten |
| C13 | Demo blames "COMP-3" but COMP-3 isn't what fails | medium (signature beat honesty) | **NEEDS FIX (PROVEN)** — COMP-3 and USAGE-DISPLAY give byte-identical output; re-label the forged idiom |
| C14 | BUILD_PLAN "install GnuCOBOL" + "no network" contradiction | medium (build day) | **NEEDS FIX** — impossible task + self-contradiction; resolve with C4 |
| C15 | `google-genai>=1.55.0` minimum version | low (it installs) | **VERIFY** — unconfirmed from primary source |

---

## Priority targets (the project dies if these are wrong)

### C1. Does `AGENTS.md` / `SKILL.md` self-authoring actually exist?  — CONFIRMED (mechanism)
- **Claim:** the agent writes a new `.agents/skills/<idiom>/SKILL.md` at runtime, it
  auto-loads, and persists — the demo's signature "agent upgrades itself" beat ($5k bonus).
- **Attack:** if SKILL.md is only read at `agents.create()` time, a file the agent writes
  mid-run never takes effect, and the centerpiece is fabricated.
- **Evidence:** AGENTS.md/SKILL.md are a real, documented primitive. Skills are
  *discovered automatically from the filesystem during execution*: "Skills loaded from
  `.agents/skills/` and `/.agents/skills/` are both discovered automatically." The
  custom-agent flow is "define everything in markdown files like AGENTS.md and SKILL.md."
  - https://ai.google.dev/gemini-api/docs/custom-agents
  - https://ai.google.dev/gemini-api/docs/antigravity-agent
  - https://blog.google/innovation-and-ai/technology/developers-tools/managed-agents-gemini-api/
- **Verdict: CONFIRMED** that runtime skill discovery exists. **OPEN SUB-QUESTION (asked
  researcher-agents):** confirm a SKILL.md written *mid-interaction* is re-discovered
  *within the same turn*, vs requiring the next interaction. If it needs a fresh turn, the
  demo must show forge → (new turn, same env) → green, NOT one continuous turn. Either is
  honest, but the DEMO_SCRIPT implies one continuous beat — adjust if needed.

### C1b. Do forged skills "persist forever" and "accumulate across runs"?  — NEEDS FIX
- **Claim:** README Q&A "the persistent environment + forged skills accumulate dialect
  coverage across runs"; AGENTS.md step 5 "These persist for future runs"; the investor
  moat = "accumulated dialect skills."
- **Attack:** persistence is scoped to ONE environment lineage, not the saved agent.
- **Evidence:** Quickstart, verbatim: *"Each invocation forks the base environment, so
  every run starts clean."* Files persist only when the SAME `environment_id` is reused;
  a fresh `interactions.create(agent="lazarus", environment="remote")` starts WITHOUT the
  forged skill. To make a skill permanent you must re-register the agent with it mounted.
  - https://ai.google.dev/gemini-api/docs/managed-agents-quickstart
- **Verdict: NEEDS FIX.** Reword to: "forged skills persist for the life of the
  environment (reused via `environment_id`); to make them permanent across new agents we
  re-register the agent with the skill mounted." (Escalated to lead.)

### C2. Is the "single-agent / no computer_use / no file_search" honesty claim true?  — CONFIRMED
- **Claim:** ARCHITECTURE §4 lists `computer_use`, `file_search`, `mcp`,
  `function_calling`, sub-agents as "Explicitly NOT used / unsupported."
- **Attack (from seed):** "the live agents tool list INCLUDES Computer Use and File
  Search" → honesty framing would be misleading.
- **Evidence:** the seed premise is **WRONG**. Antigravity agent doc, verbatim:
  *"Unavailable tools: `file_search`, `computer_use`, `google_maps`, `function_calling`
  and `mcp` are not yet supported."* Defaults are `code_execution`, `google_search`,
  `url_context`; filesystem auto-enabled by the `environment` param. There is no
  sub-agent deployment in the Managed Agents API (that's Antigravity 2.0 / ADK).
  - https://ai.google.dev/gemini-api/docs/antigravity-agent
- **Verdict: CONFIRMED.** Our honesty framing is accurate and is actually a *strength*
  with a DeepMind judge. No fix. (One precision nit: ARCHITECTURE §4 says defaults are
  "code_execution + google_search + url_context" — correct. agent.py comment claims
  "structured output" is unsupported — the doc doesn't list structured output among the
  unavailable tools, so drop that specific word to avoid an unsourced claim.)

### C3. Is the base agent ID real?  — CONFIRMED
- **Claim:** `antigravity-preview-05-2026`.
- **Attack:** the `-preview-05-2026` suffix could be invented; a wrong ID = nothing runs.
- **Evidence:** doc, verbatim: *"Only `antigravity-preview-05-2026` is supported as
  `base_agent`."* Used consistently across all code examples. Powered by Gemini 3.5 Flash.
  - https://ai.google.dev/gemini-api/docs/antigravity-agent
- **Verdict: CONFIRMED.** Exact string is right and is the only accepted value.

### C4. Can the agent compile + run REAL COBOL via GnuCOBOL in the sandbox?  — NEEDS FIX (was FALSE; re-scoped after product correction)
- **Claim:** README §2.4 "compiles & runs the *original* COBOL via GnuCOBOL inside the
  sandbox"; ARCHITECTURE "GnuCOBOL pre-warmed / pre-installed into base_environment";
  DEMO 0:35 "compiles & runs the original COBOL via GnuCOBOL." This is the **#1
  anti-objection**: "we run the real program, not self-graded tests."
- **Attack:** GnuCOBOL (`cobc`) is a system binary normally installed via `apt`. Question is
  whether the **Gemini API** sandbox permits that (network + apt + root).
- **SELF-CORRECTION (the lead caught a product mix-up — important).** My first pass cited
  `docs.cloud.google.com` (**Enterprise Agent Platform**), which says network is *disabled by
  default* and there's *no root*. That is the WRONG product. The hackathon uses the **Gemini
  API** at `ai.google.dev`, where the facts are materially different:
  - **Network is ON by default:** *"By default, environments have unrestricted outbound
    network access."* (Opposite of what I first reported.) So a network-gated apt is NOT the
    blocker on this product.
  - Runtime install is still documented only as `pip install` / `npm install`.
  - **apt / sudo / root: NOT MENTIONED** on any ai.google.dev page (antigravity-agent,
    quickstart, agent-environment). Neither confirmed nor denied. (Asked researcher-agents to
    grep the .md.txt docs for apt/sudo/root — pending.)
  - Preinstalled list: Python 3.12, Node 22, Unix tools (curl/git/jq/gcloud/ripgrep/…),
    google-genai, numpy, pandas. **`cobc` is NOT in it.**
  - https://ai.google.dev/gemini-api/docs/agent-environment
  - https://ai.google.dev/gemini-api/docs/antigravity-agent
- **Verdict: NEEDS FIX (downgraded from FALSE), pending the apt/root confirmation.** The
  claim "GnuCOBOL is **pre-installed/pre-warmed in base_environment**" is still FALSE — it
  isn't preinstalled and there's no base-image customization. But "the agent installs +
  runs GnuCOBOL **live**" is now PLAUSIBLE *if* apt+root work (network is on). Three paths,
  in order of confidence:
  - **A (safe baseline, recommended, DE-RISKED TODAY):** `golden_io.json` captured from REAL
    GnuCOBOL pre-event. Falsifiable (it's the real compiler's output, just pre-captured),
    network-free, deterministic. I already generated a real one (see C5). Lock this as the
    floor.
  - **B (mount a prebuilt binary):** ship a statically linked `cobc`+`libcob` and execute it
    live (no apt, no root). The "real COBOL runs on stage" claim survives. Needs end-to-end
    verification (task #8) — execute-bit, glibc/musl, runtime libs.
  - **C (live apt):** IF researcher-agents confirms apt+root exist on the Gemini API sandbox
    (network is already on), `apt-get install -y gnucobol` could work live — the strongest
    demo beat. Do NOT rely on it until confirmed AND smoke-tested the morning of; treat as
    upside over A.
  - **Honesty bottom line:** the FALSIFIABILITY of the oracle is INTACT under all three —
    it's the real compiler's output either way. Only "**live** compile on stage" is at risk,
    and that risk is now smaller than I first stated (network-on changes the picture). The
    docs as written overclaim "pre-installed" (fix that word) but the core anti-objection
    survives. Claim-as-written = NEEDS FIX; core falsifiability = INTACT via A/B(/C).

### C5. Is the "byte-for-byte" diff robust, or does it fail for formatting reasons?  — NEEDS FIX
> **EMPIRICALLY TESTED** — I compiled `src/sample/payroll.cob` with the real GnuCOBOL 3.2.0
> (`cobc -x`) and ran it against naive + correct Python. Outputs below are real bytes, not
> speculation. (Workspace: `/tmp/lazarus_oracle_test`.)
- **Claim:** ARCHITECTURE §3 + oracle code assert `python_output == cobol_output`
  byte-for-byte; a non-zero diff is shown as RED on stage.
- **TWO independent failure layers, both REPRODUCED:**
  1. **FORMAT (fails on EVERY input).** `DISPLAY WS-NET` (PIC `9(7)V99`) emits the full
     PICTURE width: 7 integer digits **zero-padded**, the decimal point, 2 decimals, then
     `\n`. Measured bytes: gross 1000.00 → `0000775.00\n`; gross 0.01 → `0000000.01\n`;
     gross 999999.99 → `0774999.99\n`. Naive Python `print(net)` emits `775.0`. Never
     byte-equal. (CORRECTION to an earlier note in this log: GnuCOBOL 3.2 *does* print the
     `.` for this PIC — the divergence is the **zero-padding + the `775.0` vs `775.00`
     decimals**, not a missing point.)
  2. **ROUNDING (fails on half-cent inputs).** `COMPUTE WS-TAX ROUNDED` = round-half-UP.
     Python's default `round()` = banker's (half-EVEN). On `gross=5.00`: tax_raw =
     1.12500 → COBOL tax 1.13 → net **`0000003.87`**; naive Python `round()` → tax 1.12 →
     net **`3.88`**. The VALUES differ by a cent (not just format). Reproduced for gross ∈
     {0.20, 1.00, 1.80, 2.60, 3.40, 4.20, 5.00, …} (any gross where gross×0.225 lands on an
     exact half-cent).
- **THREE more divergence sources REPRODUCED** (will go RED if the input battery isn't curated):
  - **Silent high-order truncation:** the field is `9(7)` so values > 9999999.99 wrap.
    gross 12345678.99 → COBOL uses `2345678.99`, net `1817901.22`. Naive Python wouldn't truncate.
  - **Unsigned field eats the sign:** field has no `S`. gross `-100.00` → COBOL net
    `0000077.50` (same as +100.00). Naive Python would produce a negative number.
  - **`NUMVAL` of garbage → 0:** input `abc` or empty → COBOL `0000000.00`. Naive Python
    `Decimal("abc")` raises. Battery must be clean numeric strings.
- **Bonus (kills C13):** I compiled a `USAGE DISPLAY` variant (COMP-3 removed) — DISPLAY
  output is **byte-identical** to the COMP-3 version. So COMP-3 storage has ZERO effect on
  the diff (see C13).
- **Evidence:** local GnuCOBOL 3.2.0 run, hexdumped. Corroborating:
  - https://gnucobol.sourceforge.io/HTML/gnucobpg.html
  - COBOL `ROUNDED` defaults to ROUND-HALF-UP; Python `round()` is round-half-even.
    https://www.ibm.com/docs/en/cobol-zos (arithmetic / ROUNDED); Python docs `round()`.
- **Verdict: NEEDS FIX.** The diff IS falsifiable (good) but brittle. **PROVEN-CORRECT
  oracle pattern (I verified 9/9 byte-exact):**
  1. Python math in `decimal.Decimal`, `.quantize(Decimal("0.01"), ROUND_HALF_UP)` for the
     tax (matches COBOL `ROUNDED`). NEVER float / default `round()`.
  2. Format Python to the COBOL PICTURE: `f"{int(net):07d}.{cents:02d}"` so it emits
     `0000775.00`. Then byte-for-byte `==` against COBOL stdout passes exactly.
  3. Compare with the trailing `\n` included, or `.rstrip("\n")` both sides and SAY so.
  4. **Curate the input battery** to non-negative values ≤ 9999999.99 with clean numeric
     strings — OR have the Python replicate truncation/abs/NUMVAL-zero semantics (harder).
     The current battery (`1000.00`, `0.01`, `999999.99`) is safe; do NOT add overflow /
     negative / garbage unless intentionally demonstrating those idioms.
  5. The RED→GREEN beat should be the rounding-mode + zero-pad-format fix (the real idiom,
     see C13), NOT "COMP-3". Rehearse that the forged SKILL.md content produces exactly this.
  (Sent backend-eng the proven pattern + battery guidance.)

---

## New challenges (found while attacking)

### C6. Sandbox spec drift  — ~~NEEDS FIX~~ → MOSTLY RETRACTED (I cited the wrong product)
> **SELF-CORRECTION.** My original C6 evidence came from `docs.cloud.google.com`
> (**Gemini Enterprise Agent Platform** — an enterprise product). The hackathon uses the
> **Gemini API** at `ai.google.dev`, which is a DIFFERENT product with DIFFERENT specs. The
> lead caught this. Re-verified against the correct product:
- **Claim:** ARCHITECTURE §4: "Python 3.12, Node 22"; "4 CPU / 16 GB (free during
  preview)"; "Sandboxes auto-snapshot after 15 min idle and are retained 7 days."
- **Evidence (CORRECT product — ai.google.dev Gemini API):**
  - Python **3.12** + Node.js **22** — **our docs are CORRECT.** (The 3.11/Node20 I cited is
    the *Enterprise Agent Platform*, not this product.)
  - Lifecycle: Idle → "**Auto-snapshot and stopped after 15 minutes of inactivity**";
    Offline → "**Retained for 7 days** since last active." **Our docs are CORRECT** — the
    "15-min idle snapshot, 7-day retention" line I called "invented" is verbatim accurate.
  - https://ai.google.dev/gemini-api/docs/agent-environment
- **Verdict: RETRACTED on Python/Node/lifecycle** (those were right; my error). **Only
  remaining nit:** "4 CPU / 16 GB (free during preview)" — still not found in the
  ai.google.dev docs either. Keep ONLY if researcher-agents has a primary source; otherwise
  soften to "generous preview limits" or drop. (Escalation correction sent to lead.)
- **LESSON:** every sandbox/network/spec claim must be sourced to `ai.google.dev`
  (Gemini API), NOT `docs.cloud.google.com` (Enterprise Agent Platform). Re-audited C4 on
  this basis below.

### C7. New Jersey impact stats  — MIXED (one number unverified)
- **Claim:** README §1 "1,600% surge" + "575,000+ filings backlogged in weeks" + governor
  "publicly begged"; DEMO 0:00 "the governor *begged* on live TV."
- **Evidence:**
  - **1,600% surge — CONFIRMED.** Widely reported; "1,600% increase in volume in
    unemployment claims" first week.
    - https://www.govtech.com/computing/As-Unemployment-Claims-Spike-New-Jersey-Seeks-COBOL-Coders.html
    - https://whyy.org/articles/why-n-j-wants-coders-fluent-in-a-60-year-old-language-in-the-middle-of-a-pandemic/
  - **Governor's COBOL call — CONFIRMED** (Murphy press briefing; many volunteers responded).
    - https://www.cnbc.com/2020/04/06/new-jersey-seeks-cobol-programmers-to-fix-unemployment-system.html
  - **"575,000+ backlogged in weeks" — UNVERIFIED.** Sources cite **362,000** in week one
    and **~1 million** over two months. I found NO source for "575,000 backlogged." Looks
    fabricated or mis-transcribed.
  - **"begged on live TV" — EMBELLISHED.** It was a press briefing / news appeal, not a
    dramatic live-TV plea. Minor, but a journalist-minded judge could call it.
- **Verdict: MIXED → NEEDS FIX on the 575k number.** Replace "575,000+ filings backlogged"
  with a sourced figure: "362,000 claims in the first week" or "over 1 million in two
  months." Soften "begged on live TV" to "publicly appealed for COBOL programmers."

### C8. Macro impact stats  — CONFIRMED (with date caveats)
- **$2.41T tech debt — CONFIRMED.** CISQ/Synopsys "Cost of Poor Software Quality in the
  US: A 2022 Report" — exact figure $2.41T (of which ~$1.52T is accumulated tech debt).
  Caveat: it's a **2022 total annual estimate**, so "~$2.41T/year" is fair but cite the year.
  - https://www.it-cisq.org/the-cost-of-poor-quality-software-in-the-us-a-2022-report/
  - https://news.synopsys.com/2022-12-06-Software-Quality-Issues-in-the-U-S-Cost-an-Estimated-2-41-Trillion-in-2022
- **18–23% time on bad code — CONFIRMED.** Stripe 2018 "Developer Coefficient" report.
  Caveat: 2018 data; say "Stripe found."
  - https://stripe.com/files/reports/the-developer-coefficient.pdf
- **$30B+ modernization market — CONFIRMED.** Mordor: $29.39B (2026); Grand View ~$30B
  (2026); convergent across 5 firms. "$30B+" is accurate.
  - https://www.mordorintelligence.com/industry-reports/legacy-modernization-market
- **Verdict: CONFIRMED.** Add the source/year inline so a judge's spot-check passes.

### C9. "1M-token context" used on a ~150-line module  — NEEDS FIX (framing)
- **Claim:** README/DEMO repeatedly tout reading "the entire module using the 1M-token
  context window." Gemini 3.5 Flash's 1,048,576-token context is real (CONFIRMED) — but the
  golden demo module is **~150 lines (~600 tokens)** per ARCHITECTURE §7 / DEMO checklist.
- **Attack:** Touting a 1M context for a 600-token file is a non-sequitur. A sharp DeepMind
  judge asks "why does 1M context matter for 150 lines?" and the live demo can't show it.
- **Verdict: NEEDS FIX (framing).** Either (a) demote the 1M line in the *demo* narration
  and reposition it as the *scalability* answer ("the SAME loop ingests a 50k-line module in
  one shot"), with a real large-file artifact to point to; or (b) drop the claim from the
  live beats entirely. Don't lead the demo with a feature the demo doesn't exercise.

### C10. `MAX_ITERATIONS = 4` "hard cap" + "visible counter"  — NEEDS FIX
- **Claim:** ARCHITECTURE §7 + DEMO checklist: "Hard-cap iterations at 4 with a visible
  counter — an infinite loop on stage is death."
- **Attack:** in `src/agent.py`, `MAX_ITERATIONS = 4` is only **string-interpolated into the
  prompt** ("Stop ... after 4 iterations"). There is NO orchestrator-side loop, NO counter,
  NO kill switch. The model can ignore the instruction and loop; the "visible counter" UI
  does not exist. The single safety net the demo leans on is not actually enforced.
- **Verdict: NEEDS FIX.** Enforce a real cap: drive the loop turn-by-turn from the
  orchestrator (re-issue `interactions.create` per iteration, count in Python, hard-stop at
  4 and cut to the cached green run), and render the counter in the UI. A prompt suggestion
  is not a hard cap. (Coordinate with backend-eng / frontend-eng.)

### C11. agent.py uses unverified SDK / streaming field names  — NEEDS FIX
- **Claim:** agent.py reads `event.event_type == "step.delta"`, `event.delta`, `delta.type
  == "text"`, `delta.text`, and `interaction.environment_id` / `.output_text` / `.steps`.
- **Attack:** these field/enum names are guessed, not quoted from the SDK. If the real SSE
  schema differs (e.g. `event.type`, `chunk.text`, a different terminal-event shape), the UI
  shows nothing or the script crashes at 0:12 on stage. Also `client.agents.create` is shown
  with `base_environment=` — confirm the param name (some docs show `environment` for runs vs
  `base_environment` for create) and that `interactions.create` accepts `environment="remote"`.
- **Evidence:** the public examples emphasize `interaction.steps` and `environment_id`
  reuse, but the exact streaming event/delta schema must be read from the live SDK reference.
  - https://ai.google.dev/gemini-api/docs/managed-agents-quickstart
  - https://ai.google.dev/gemini-api/docs/custom-agents
- **Verdict: NEEDS FIX (verify).** backend-eng/researcher-agents must reconcile every field
  name against the live `google-genai` reference before the UI is wired. Don't ship guessed
  attribute names into the 45%-weighted live demo. (This overlaps task #5.)

### C12. Demo determinism + cold-start  — ACCEPTED RISK (tighten)
- **Claim:** "Deterministic, single sandbox call, no network." DEMO mitigations: pre-warm,
  pin seed, cached fallback, backup video.
- **Attack:** LLM agents are NOT deterministic even with a fixed seed once tool-use branches;
  "pin seed" does not guarantee identical tool sequences. Cold-start (~fresh sandbox) +
  model latency can blow the 1:55 budget. "No network" conflicts with C4 if the agent must
  `pip install` anything (network must be ON for that) — pick one story.
- **Verdict: ACCEPTED RISK,** *given* the cached-green fallback + backup video are real and
  rehearsed. Tighten: (1) rehearse 10× and MEASURE p95 runtime vs the 1:55 budget; (2) make
  the Safety cutover to cached-green instant and visually identical; (3) resolve the
  "no network" vs "pip install" contradiction (if the oracle is golden_io.json + a mounted
  binary, you genuinely need no network — say that). The fallback being indistinguishable
  from the live run is doing the real de-risking here; protect it.

### C13. The demo's central beat MISATTRIBUTES why the test fails  — NEEDS FIX (narrative honesty)
- **Claim:** DEMO 0:55 + payroll.cob header + ARCHITECTURE §7: the agent "diagnoses:
  unsupported `COMP-3` packed-decimal" as the reason tests are RED, then forges a COMP-3
  SKILL.md to fix it. COMP-3 is presented as "the unknown idiom that triggers the forge."
- **Attack:** COMP-3 is a *storage* encoding (BCD packed). A competent translator just reads
  a COMP-3 field as a decimal — the packed representation never leaves the COBOL runtime and
  has NO effect on `DISPLAY` output. GnuCOBOL `DISPLAY` of an unedited numeric **de-edits**
  the value to its raw PICTURE form identically whether it's `COMP-3` or `USAGE DISPLAY`. So
  the ACTUAL cause of a RED diff on payroll.cob is (i) DISPLAY de-editing (`0077500` vs
  `775.00`/`775.0`) and (ii) ROUNDED rounding-mode mismatch — NOT "we don't understand
  COMP-3." A DeepMind/COBOL-literate judge asking "is COMP-3 really what broke it?" punctures
  the story.
- **Evidence — EMPIRICALLY PROVEN.** I compiled `payroll.cob` twice with real GnuCOBOL
  3.2.0: once as-is (COMP-3) and once with `COMP-3` stripped (`USAGE DISPLAY`). The DISPLAY
  output is **byte-identical** across both (gross 1000.00 → `0000775.00` either way; gross
  5.00 → `0000003.87` either way). The packed storage has ZERO effect on what DISPLAY emits.
  The real RED comes from format + rounding (see C5), which COMP-3 does not cause.
  Corroborating sources:
  - https://www.mainframestechhelp.com/tutorials/cobol/comp-3.htm
  - https://gnucobol.sourceforge.io/HTML/gnucobpg.html
  - http://www.simotime.com/datapk01.htm
- **Verdict: NEEDS FIX (narrative honesty).** Two honest options:
  1. **Re-label the forged skill** to the TRUE idiom it fixes — e.g. a "COBOL numeric
     output formatting + ROUND-HALF-UP equivalence" skill (de-edit the DISPLAY, match the
     rounding mode). This is the real institutional-knowledge gap and is genuinely
     non-obvious — a stronger, more defensible story than "COMP-3."
  2. If you keep COMP-3 as the headline idiom, make the COBOL actually exercise something
     COMP-3-specific that DOES change behavior (e.g. a `REDEFINES` over the packed bytes, or
     `OCCURS DEPENDING ON` with packed elements) so the failure is genuinely attributable to
     packed-decimal handling. Harder to build in time.
  - Recommendation: option 1. The forge beat survives intact; only the LABEL of the idiom
    changes to one that's actually true. (Coordinate with backend-eng on payroll.cob +
    the seed/forged SKILL.md content.)

### C14. BUILD_PLAN / requirements assume the impossible install + a self-contradiction  — NEEDS FIX
- **Claim:** BUILD_PLAN.md 11:00–11:30 "install + pin GnuCOBOL into `base_environment`;
  verify it persists." requirements.txt line 6: "`apt-get install -y gnucobol`." DEMO/BUILD
  also insist "**No network** in the demo path."
- **Attack:** (1) Same as C4 — apt install of a system package can't run (no root, network off
  by default, no documented base_environment pre-bake). The 11:00–11:30 milestone is a task
  that cannot complete; it will silently eat 30 min on the build day. (2) **Internal
  contradiction:** "install gnucobol at runtime" REQUIRES network ON; "no network in the
  demo path" REQUIRES it OFF. You can't have both. If GnuCOBOL must be installed live, the
  demo is NOT network-free; if the demo is network-free, GnuCOBOL must already be present
  (which the docs don't support).
- **Evidence:** see C4 sources. **Note after product correction:** the Gemini API sandbox
  has network ON by default, so "no network in demo" is a self-imposed CHOICE, not a platform
  limit — the contradiction is now between *our own demo rule* and a live apt, not between the
  docs. The "apt-get won't work" half is also softened (network is on; only apt/root is
  unconfirmed, task #8).
- **Verdict: NEEDS FIX.** Resolve in lockstep with the C4 decision. If Option A
  (golden_io.json primary): delete the "install GnuCOBOL" milestone, keep "no network"
  (true and intentional), build-day task = "capture golden_io.json from a real cobc run
  before the event." If Option B (mounted binary): demo stays network-free (mounted file,
  not a download); rewrite requirements.txt line 6 + the milestone to "mount prebuilt cobc
  binary," not apt. If Option C (live apt, IF task #8 confirms apt+root): then DROP the "no
  network in demo path" rule — you can't live-install with network off; pick one story.

### C15. `google-genai>=1.55.0` version pin is unverified  — VERIFY
- **Claim:** agent.py + requirements.txt assert the Interactions API needs
  `google-genai >= 1.55.0`.
- **Attack:** if the real minimum differs, `pip install -r requirements.txt` could pull a
  version missing `client.interactions` / `client.agents`, and nothing runs. The number
  reads precise but I have not seen it in a primary source.
- **Verdict: VERIFY** (asked researcher-agents). Pin to the exact version the live SDK
  changelog/quickstart states; don't ship a guessed floor into the 45%-weighted demo.

---

## Summary for the lead

- **Stop-the-line:** **C4** (live GnuCOBOL is not achievable — redesign the oracle path) and
  **C5** (byte-for-byte will fail on COMP-3 DISPLAY/rounding unless normalized). These two
  hit the single most important differentiator and the on-stage RED→GREEN beat.
- **Honesty fixes (a DeepMind judge will catch):** **C1b** (skills don't persist across fresh
  runs), **C6** (wrong sandbox specs), **C7** (575k number unsourced), **C9** (1M context
  irrelevant to the demo file), **C13** (the signature forge beat blames "COMP-3" but COMP-3
  is not what makes the test fail — re-label it to the real idiom).
- **Engineering gaps:** **C10** (the "hard cap" isn't enforced), **C11** (guessed SDK fields).
- **Holding up well — lean into these:** **C2** (honesty framing is genuinely accurate),
  **C3** (correct agent ID), **C8** (macro stats check out), **C1 mechanism** (runtime skill
  discovery is real). The differential-oracle CONCEPT is sound and falsifiable; only the
  *live-compile* execution and the *raw byte* comparison need rework.
