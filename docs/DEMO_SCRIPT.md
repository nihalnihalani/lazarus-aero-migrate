# LAZARUS — 2-Minute Live Demo Script

> Live Demo is **45%** of the score. This path is rehearsed, deterministic, and judge-proof. Run the **exact** sequence below. Never improvise on stage.

## Roles during the demo
- **Driver** (Agent engineer): one machine, sandbox pre-warmed, types the golden inputs.
- **Narrator** (BizDev/presenter): points at the visible moment, delivers the impact line, handles judges.
- **Safety** (Utility/QA): second laptop + hotspot, finger on the fallback-cache toggle.

## The script (target 1:55, leaves ~5s buffer)

| Time | On screen | Narration |
|---|---|---|
| **0:00–0:12** | App open, sandbox pre-warmed (GnuCOBOL already installed). Drop `payroll.cob`. | "This COBOL ran a state unemployment system. In 2020, New Jersey's governor *begged* on live TV for people who could still read it." |
| **0:12–0:35** | Agent reads the whole file (1M context). **Plain-English business logic panel** fills in — the rounding rule, the tax edge-case. | "First, it recovers the rules — the institutional knowledge that retired with the people who wrote it." |
| **0:35–0:55** | Agent writes `payroll.py`. Then compiles & runs the **original COBOL** via GnuCOBOL, captures real output, generates equivalence tests, runs `pytest`. Terminal goes **RED** (3 failures). | "It doesn't grade its own homework — it runs the *real* COBOL as the source of truth, and diffs against it. Right now they don't match." |
| **0:55–1:25** | Agent diagnoses: unsupported `COMP-3` packed-decimal. **It writes a new `SKILL.md`** — the git diff animates in — commits, hot-reloads. | "Instead of failing, watch — it's teaching *itself* a new skill, live, and saving it forever." |
| **1:25–1:45** | Re-run. Python output now matches COBOL **byte-for-byte → GREEN.** Side-by-side COBOL↔Python diff shown. | "Red to green. Proven equivalent to the mainframe — not approximated." |
| **1:45–1:55** | Click **Download** → migrated, tested module pulled from the persistent sandbox. | "Sixty years of code, modernized *and verified*, while I talked. That's a $2.4 trillion problem, solved autonomously." |

## The three "money shots" (make sure each is unmistakable)
1. **The oracle diff** — real COBOL output vs Python output (kills the verifiability objection before it's asked).
2. **The self-authored `SKILL.md`** — the agent visibly upgrading itself (the $5k + creativity beat).
3. **RED → GREEN** — binary, legible, no explanation needed.

## De-risking checklist (lock in the final 2 hours)
- [ ] **Pre-warm** the sandbox; keep alive with a `background=true` heartbeat so 0:00 isn't a cold start.
- [ ] **GnuCOBOL pre-installed** into the persistent `base_environment` (verify `cobc --version` survives a reconnect). Fallback: `golden_io.json`.
- [ ] **Golden COBOL module** hand-picked: ~150 lines, one reproducible bug class (decimal/rounding) the model fixes in 1–2 iterations. Rehearse **10×**.
- [ ] **Hard-cap iterations at 4** with a visible counter — an infinite loop on stage is death.
- [ ] **Pin** model + thinking level + seed; disable silent auto-retries that can hang.
- [ ] **Fallback cache:** pre-recorded asciinema/PNG of the exact golden run. If `pytest` stalls >8s or exceeds 4 loops, Safety cuts to the cached green run (identical-looking).
- [ ] **No live network** in the demo path — pure local code execution. (No `google_search`/`url_context` in this flow.)
- [ ] **Backup video** of a perfect run recorded the morning of, in case the laptop dies.

## Q&A prep (judges WILL ask)
- **"How do you know the translation is correct?"** → "We run the original COBOL with GnuCOBOL and assert byte-for-byte equivalence. The oracle is the real program, not our tests."
- **"Is this multi-agent?"** → "No — one Managed Agent in one sandbox. We deliberately avoided unsupported sub-agent orchestration."
- **"What did you build today vs the platform?"** → "The migration loop, the differential oracle harness, the live trace UI, and the self-authoring skill mechanism. Gemini provides the model + sandbox."
- **"Does it scale to a real mainframe?"** → "1M-token context handles large modules; the persistent environment + forged skills accumulate dialect coverage across runs."
