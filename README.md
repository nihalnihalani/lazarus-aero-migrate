# LAZARUS — Aero-Migrate

> **Autonomous Legacy Modernization Engine** · Google I/O 2026 Hackathon · Gemini 3.5 Flash + Managed Agents API
>
> *Raising dead code back to life.*

LAZARUS ingests legacy **COBOL**, translates it to modern **tested Python**, and — crucially — **proves the translation is correct by running the original COBOL as a ground-truth oracle**. When it meets a COBOL idiom it doesn't understand, it **writes itself a new skill (`SKILL.md`) live**, reloads, and continues until the migrated code is byte-for-byte equivalent.

---

## 1. The Problem

Government agencies and financial institutions still run on 40-year-old mainframes written in COBOL. When demand spikes, they fail catastrophically — and the engineers who can fix them have retired.

- **April 2020:** New Jersey Gov. Phil Murphy publicly **begged for volunteer COBOL programmers** after the state's 40-year-old mainframe buckled under a **1,600% surge** in unemployment claims, leaving **575,000+ filings backlogged** in weeks.
- **U.S. technical debt costs ~$2.41 trillion / year.** Developers waste **18–23%** of their time managing bad code.

Manual line-by-line migration (Accenture/IBM-style) is slow, expensive, and risky. The institutional knowledge encoded in these systems is **undocumented** and dying with the people who wrote it.

## 2. The Solution

LAZARUS is a **single autonomous agent** (no fragile multi-agent orchestration) running on the **Gemini 3.5 Flash Managed Agents API**. In one hosted Linux sandbox it:

1. **Reads** an entire legacy module using Gemini 3.5 Flash's **1M-token context**.
2. **Recovers the lost business logic** — explains, in plain English, the undocumented rules the COBOL encodes (the "archaeology" that makes this more than a transpiler).
3. **Translates** COBOL → idiomatic Python in the sandbox.
4. **Proves equivalence** — compiles & runs the *original* COBOL via **GnuCOBOL** inside the sandbox, captures real outputs, and generates equivalence tests asserting the Python output matches **byte-for-byte**.
5. **Self-heals via FORGE** — on an unsupported idiom (e.g. `COMP-3` packed-decimal, `REDEFINES`), it authors a new `SKILL.md`, commits it, hot-reloads, and re-runs until tests go **red → green**.

### Why this wins (the differentiators)

| Differentiator | Why it matters |
|---|---|
| **Differential oracle (runs real COBOL)** | Defeats the #1 judge objection: "green tests on agent-written code prove nothing." We diff against the *actual* legacy output. |
| **Self-authored `SKILL.md` (FORGE graft)** | The newest, least-used Managed Agents primitive. The on-stage "agent upgrades itself" beat is unforgettable and locks the **$5k Managed Agents bonus**. |
| **Business-rule recovery** | Reframes the project from "code translator" (seen 100×) to "institutional-knowledge archaeology" (never seen). |
| **Single-agent honesty** | Uses only documented Managed Agents features: code execution + file persistence. No unsupported sub-agent/MCP claims. |

## 3. How it maps to judging

| Criterion | Weight | LAZARUS |
|---|---|---|
| **Live Demo** | 45% | Visible `red → green` loop + self-authored skill + a *verifiable* diff against real COBOL. Deterministic, single sandbox call, no network. |
| **Creativity / Originality** | 35% | Business-rule recovery + differential equivalence + live self-authoring lift it well above the generic SWE-agent genre. |
| **Impact** | 20% | Best on the board — $2.41T tech debt, the NJ unemployment crisis, a real $30B+ modernization market. |
| **$5k Managed Agents bonus** | — | Textbook: model writes & runs its own code, persists files, and forges its own skills, all in the hosted sandbox. |

## 4. Tech Stack

- **Model:** Gemini 3.5 Flash (`antigravity-preview-05-2026` base agent)
- **Agent runtime:** Gemini API **Managed Agents** via the **Interactions API** (Python `google-genai`)
- **Oracle:** GnuCOBOL (`cobc`) pre-installed in the persistent sandbox environment
- **UI:** lightweight web front-end rendering live `interaction.steps` (the agent "working"), the diff viewer, and the test terminal
- **Skills:** `.agents/AGENTS.md` + `.agents/skills/<name>/SKILL.md`

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
