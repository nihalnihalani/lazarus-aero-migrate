# LAZARUS — Aero-Migrate

> **Autonomous Legacy Modernization Engine** · Google I/O 2026 Hackathon · Gemini 3.5 Flash + Managed Agents API
>
> *Raising dead code back to life.*

LAZARUS ingests legacy **COBOL**, translates it to modern **tested Python**, and — crucially — **proves the translation is correct by running the original COBOL as a ground-truth oracle**. When it meets a COBOL idiom it doesn't understand, it **writes itself a new skill (`SKILL.md`)** into its live sandbox and **re-reads it on the next pass of the same session** — repeating until the migrated code is byte-for-byte equivalent.

---

## 1. The Problem

Government agencies and financial institutions still run on 40-year-old mainframes written in COBOL. When demand spikes, they fail catastrophically — and the engineers who can fix them have retired.

- **April 2020:** New Jersey Gov. Phil Murphy **publicly called for volunteer COBOL programmers** after the state's 40-year-old mainframe buckled under a **1,600% surge** in unemployment claims — **over 362,000 new claims in two weeks** (NJ Dept. of Labor, *New UI Claims Top 362K for Past Two Weeks*, Apr 2, 2020; CNBC, WHYY).
- **U.S. tech debt cost ~$2.41 trillion in 2022** (CISQ/Synopsys, *Cost of Poor Software Quality in the US: A 2022 Report*). Developers waste **18–23%** of their time on bad code (**Stripe**, *Developer Coefficient*, 2018).

Manual line-by-line migration (Accenture/IBM-style) is slow, expensive, and risky. The institutional knowledge encoded in these systems is **undocumented** and dying with the people who wrote it.

## 2. The Solution

LAZARUS is a **single autonomous agent** (no fragile multi-agent orchestration) running on the **Gemini 3.5 Flash Managed Agents API**. In one hosted Linux sandbox it:

1. **Reads** the whole module in one shot — and because Gemini 3.5 Flash has a **1M-token context**, the *same* loop scales from the curated demo slice to a **50k-line** real-world program without chunking.
2. **Recovers the lost business logic** — explains, in plain English, the undocumented rules the COBOL encodes (the "archaeology" that makes this more than a transpiler).
3. **Translates** COBOL → idiomatic Python in the sandbox.
4. **Proves equivalence** — **real GnuCOBOL** is installed into the sandbox via **micromamba / conda-forge userland** (no root needed; the sandbox has unrestricted outbound network) during a **pre-warm** step, into one long-lived `environment_id` that's reused on stage — so the on-stage run needs **no network**. The agent then compiles & runs the *original* COBOL with that real `cobc` to produce canonical ground-truth output, and generates equivalence tests asserting the Python output matches it **byte-for-byte**. A `golden_io.json` captured from the same real `cobc` run is the deterministic fallback if the live run stalls.
5. **Self-heals via FORGE** — on an unsupported idiom (e.g. COBOL **numeric `DISPLAY` formatting + `ROUND-HALF-UP` equivalence**, `REDEFINES`, `OCCURS DEPENDING ON`), it authors a new `SKILL.md` into its live sandbox; the next pass reuses the **same environment** and the skill is **re-discovered at startup**, and it re-runs until tests go **red → green**. (Within a session the skill stays live; a *fresh* invocation forks the base env and starts clean — to bank a skill permanently you re-register the agent with it mounted in `base_environment`. Auto-discovery + env-reuse persistence are documented; we do *not* claim mid-run hot-reload or cross-run accumulation.)

### Why this wins (the differentiators)

| Differentiator | Why it matters |
|---|---|
| **Differential oracle (runs real COBOL)** | Defeats the #1 judge objection: "green tests on agent-written code prove nothing." We diff against the *actual* legacy output. |
| **Self-authored `SKILL.md` (FORGE graft)** | Uses the documented `.agents/skills/*/SKILL.md` auto-discovery primitive. The on-stage "agent upgrades itself" beat — write the skill, re-discover it on the next pass of the same live session — is unforgettable and locks the **$5k Managed Agents bonus**. |
| **Business-rule recovery** | Reframes the project from "code translator" (seen 100×) to "institutional-knowledge archaeology" (never seen). |
| **Single-agent honesty** | Uses only documented Managed Agents features: code execution + file persistence. No unsupported sub-agent/MCP claims. |

## 3. How it maps to judging

| Criterion | Weight | LAZARUS |
|---|---|---|
| **Live Demo** | 45% | Visible `red → green` loop + self-authored skill + a *verifiable* diff against real COBOL. Deterministic, single sandbox call, no network. |
| **Creativity / Originality** | 35% | Business-rule recovery + differential equivalence + live self-authoring lift it well above the generic SWE-agent genre. |
| **Impact** | 20% | Best on the board — $2.41T tech debt (CISQ/Synopsys 2022), the NJ unemployment crisis, a real **$30B+** legacy-modernization market (Mordor $29.39B / Grand View ~$30B, 2026). |
| **$5k Managed Agents bonus** | — | Textbook: model writes & runs its own code, persists files, and forges its own skills, all in the hosted sandbox. |

## 4. Tech Stack

- **Model:** Gemini 3.5 Flash (`antigravity-preview-05-2026` base agent)
- **Agent runtime:** Gemini API **Managed Agents** via the **Interactions API** (Python `google-genai >= 2.0.0`)
- **Oracle:** real GnuCOBOL installed via micromamba/conda-forge userland (no root) into a reused long-lived environment, compiling & running the original COBOL in-sandbox; `golden_io.json` (captured from the same `cobc` run) as the deterministic fallback
- **UI:** lightweight web front-end rendering the live `step.*` event stream (the agent "working"), the diff viewer, and the test terminal
- **Skills:** `.agents/AGENTS.md` + `.agents/skills/<name>/SKILL.md` (auto-discovered at startup)

## 5. Repository Layout

```
lazarus-aero-migrate/
├── README.md                    # this file
├── docs/
│   ├── ARCHITECTURE.md          # system design, data flow, API usage, the oracle
│   ├── DEMO_SCRIPT.md           # the 2-minute live-demo script + de-risking
│   ├── BUILD_PLAN.md            # 6.5-hr timeline, 4 roles, task breakdown
│   └── JUDGING_STRATEGY.md      # scoring map, judge tailoring, $5k strategy
├── src/
│   ├── agent.py                 # Managed Agent setup + write/run/verify loop (skeleton)
│   ├── differential_oracle.py   # GnuCOBOL run + byte-diff harness (skeleton)
│   └── sample/payroll.cob       # golden COBOL demo module
├── .agents/
│   ├── AGENTS.md                # agent definition
│   └── skills/                  # forged skills land here
├── requirements.txt
└── .gitignore
```

## 6. Quick Start

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...        # provisioned at the event
python src/agent.py --input src/sample/payroll.cob
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design and [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) for the stage plan.

---

## ⚠️ Hackathon notes

- **Repo must be PUBLIC at submission** (hackathon rule). It is private now for development — flip to public before the 5:00 PM deadline.
- Interactions API + Managed Agents are **beta** (`-preview-05-2026`). **Pin versions** and re-test the morning of.
- The demo must show **only what we build that day**. Keep the golden sample + the forged skill clearly attributable to event work.
