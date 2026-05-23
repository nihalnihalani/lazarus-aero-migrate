# LAZARUS — Live Trace Console (`web/`)

The demo surface. A CRT-phosphor ops console that renders the agent resurrecting
COBOL into tested Python, live. **Live Demo is 45% of the score — this UI is the
demo.**

It runs **fully standalone** off a scripted mock event stream
(`mock/mock-run.json`), so it rehearses with no API, no network, no backend.

## Run it

Zero build. Any static file server works (ES modules + `fetch` need `http://`,
not `file://`):

```bash
cd web
python3 -m http.server 8000
# open http://localhost:8000
```

Or, equivalently:

```bash
npx serve web        # from repo root
```

Then click **"load golden sample · payroll.cob"** (or drop a `.cob` file). The
scripted migration auto-plays: business rules stream in → Python is written →
the original COBOL is compiled & run as the oracle → pytest goes **RED** →
the agent **forges a `SKILL.md`** (git diff types in) → hot-reload → pytest goes
**GREEN** → byte-for-byte equivalence → **Download** unlocks.

## Controls (rehearsal-friendly)

| Key / button | Action |
|---|---|
| `Space` / ▶ | play / pause |
| `r` / ↺ | restart the run |
| `f` / ⇥ | skip to the end (fires all events instantly) |
| `0.5× 1× 2× 4×` | playback speed |

## What's where

| File | Role |
|---|---|
| `index.html` | panel layout (dropzone, trace, rules, diff, terminal, forge, download) |
| `style.css` | the "Mainframe Necromancy" aesthetic |
| `src/app.js` | entry: drop-zone, preload, transport controls, download |
| `src/player.js` | `MockPlayer` (timeline) / `LivePlayer` (push) — same interface |
| `src/renderer.js` | turns canonical Events into DOM updates per panel |
| `src/adapter.js` | **the only file that knows real API field names** (live ↔ canonical) |
| `src/highlight.js` | tiny COBOL / Python / Bash syntax highlighter |
| `mock/mock-run.json` | the scripted RED→GREEN→forge→GREEN demo |
| `STREAM_CONTRACT.md` | the canonical event shape every panel consumes |

## Going live (when the real API is wired)

The renderer only ever sees the **canonical Event shape** in
[`STREAM_CONTRACT.md`](./STREAM_CONTRACT.md). To switch from mock to live:

1. researcher-agents sends the real `interaction.steps` JSON.
2. Update the mapping table + `adaptInteractionStep()` in `src/adapter.js`
   (the only place that references API field names — a ~20-line change).
3. Construct a `LivePlayer` instead of `MockPlayer` and `player.push(adapted)`
   for each step as it streams from SSE.

Nothing in `renderer.js` / `style.css` / `index.html` changes.
