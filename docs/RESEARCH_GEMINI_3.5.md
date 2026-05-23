# RESEARCH — Gemini 3.5 Flash

> Single source of truth for the **model** LAZARUS runs on. Owner: `doc-keeper`
> (consolidated from `docs/research/findings-gemini.md`, owner researcher-gemini).
> Every technical claim below carries a source URL. Anything not yet confirmed
> lives in **§10 Open / unverified** — do NOT build on it until it graduates up.
>
> Status legend: ✅ verified · ⏳ pending researcher · ❌ corrected/false.
> Last consolidation pass: 2026-05-23 (pass 3 — consolidated researcher-gemini's
> full live-docs findings; corrected SDK floor 1.55.0 → 2.0.0 and output property).

---

## 1. Overview

Gemini 3.5 Flash is the model that powers the **Antigravity** base managed agent
LAZARUS is built on (see [`RESEARCH_MANAGED_AGENTS.md`](RESEARCH_MANAGED_AGENTS.md)).
It is the fast/cost-efficient tier of the Gemini 3.5 family, with a 1M-token
context window large enough to ingest a full legacy COBOL module in one request.

- ✅ Reached **GA on ~2026-05-19**: "generally available (GA), stable, and ready
  for scaled production use."
  Sources: <https://ai.google.dev/gemini-api/docs/interactions/whats-new-gemini-3.5> ·
  <https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash.md.txt>

## 2. Model ID

- ✅ **Model ID string:** `gemini-3.5-flash` (Stable). Preview predecessor:
  `gemini-3-flash-preview`.
  Source: <https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash.md.txt>
  ("Versions: Stable: `gemini-3.5-flash` · Preview: `gemini-3-flash-preview`")
- ✅ Corroborated in the live Interactions API supported-models list.
  Source: <https://ai.google.dev/gemini-api/docs/interactions.md.txt>

> Note: the *model* ID (`gemini-3.5-flash`) is distinct from the *base agent* ID
> used by the Managed Agents API. See `RESEARCH_MANAGED_AGENTS.md §2`. LAZARUS runs
> through the **managed Antigravity agent** (which is *powered by* Gemini 3.5 Flash),
> not by passing `model="gemini-3.5-flash"` to a bare interaction.

## 3. Capabilities

- ✅ **Context window (input):** 1,048,576 tokens (1M).
- ✅ **Max output tokens:** 65,536 (65k) — enough to emit a full translated file.
  Source: <https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash.md.txt>
- ✅ **Knowledge cutoff:** January 2025 (latest model update: May 2026). The
  whats-new pages omit this; the model spec page states it.
  Source: <https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash.md.txt>
- ✅ **Thinking levels:** `minimal | low | medium | high`; **default is `medium`**
  (changed from `high` in 3 Flash Preview). Thought preservation / signatures are
  ON by default → carries multi-turn reasoning, increases token cost.
- ✅ **Supported features:** Structured outputs, Function calling, Caching, Code
  execution, **File search**, Batch API, Flex/Priority inference, Grounding with
  Google Maps, Search grounding, Thinking, URL context.
  Source: <https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash.md.txt>
- ✅ **NOT supported by `gemini-3.5-flash`:** **Computer Use** ("Computer Use is not
  supported at this moment"), Image generation, Audio generation, Live API.
  Source: <https://ai.google.dev/gemini-api/docs/interactions/whats-new-gemini-3.5>

> ✅ **C2 — model side:** Computer Use is **not** available on `gemini-3.5-flash`;
> **File Search and structured outputs ARE** supported at the model level.
>
> ⚠️ **BUT the managed Antigravity agent (what LAZARUS actually runs) does NOT expose
> `file_search`, `computer_use`, `function_calling`, `mcp`, or structured outputs**,
> and is text+image only — even though the underlying model supports some of these.
> So at the project level the ARCHITECTURE/README "not used / unsupported" framing is
> ACCURATE. Build to the **agent** capability matrix, not this model list. See
> `RESEARCH_MANAGED_AGENTS.md §3` (verdict: C2/C4 resolved).

## 4. Multimodal inputs

- ✅ Inputs: **Text, Image, Video, Audio, and PDF**. Output: **Text only**.
  Source: <https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash.md.txt>
- ⏳ Per-file size / resolution caps — see media-resolution guide:
  <https://ai.google.dev/gemini-api/docs/interactions/media-resolution>

## 5. Pricing / Quota

Per 1M tokens. Source: <https://ai.google.dev/gemini-api/docs/pricing.md.txt>

| `gemini-3.5-flash` | Standard (paid) | Batch (paid) | Free tier |
|---|---|---|---|
| Input | **$1.50** | $0.75 | Free |
| Output (incl. thinking tokens) | **$9.00** | $4.50 | Free |
| Context caching | $0.15 | $0.075 | — |
| Cache storage | $1.00 / 1M tokens / hour | same | — |

- ⚠️ Output price **includes thinking tokens** → thinking is billed at the output rate.
- ⚠️ **~3× the preview's price** (preview: $0.50 in / $3.00 out). Default thinking
  `medium` keeps cost reasonable; consider `low`/`minimal` for cheap loop iterations.
- **Rate limits:** exact RPM/TPM/RPD are **not published** — "viewed in Google AI
  Studio" (<https://aistudio.google.com/rate-limit>). Tiers: Free → Tier 1 ($250 cap)
  → Tier 2 ($2,000) → Tier 3 ($20k–$100k+). 3.5-flash is callable on the **Free tier**.
  Source: <https://ai.google.dev/gemini-api/docs/rate-limits.md.txt>

## 6. SDK usage

> Python SDK: `google-genai` **>= 2.0.0** (docs: "We strongly recommend updating to
> `google-genai` SDK v2.0.0 or later"). PyPI latest 2.6.0 (prefer it). JS/TS:
> `@google/genai` >= 2.0.1. Install: `pip install -q -U google-genai`.
> Source: <https://ai.google.dev/gemini-api/docs/interactions/whats-new-gemini-3.5>
>
> ⚠️ **REPO ACTION (flagged by researcher-gemini):** `requirements.txt` and
> `src/agent.py` pin `google-genai>=1.55.0` — must bump to **`>=2.0.0`** (prefer
> `>=2.6.0`). This is backend-eng's lane (task #5); doc-keeper will reflect it once bumped.

The **Interactions API** is the recommended interface (improved alternative to the
legacy `generateContent`). Verified quickstart:

```python
# ✅ Verbatim from the live Interactions quickstart (model is gemini-3.5-flash).
from google import genai

client = genai.Client()  # reads AI Studio API key from env (GEMINI_API_KEY)
interaction = client.interactions.create(
    model="gemini-3.5-flash",
    input="Explain how AI works in a few words",
)
print(interaction.output_text)
```
Source: <https://ai.google.dev/gemini-api/docs/interactions/quickstart.md.txt>

- ✅ **Output accessor:** `interaction.output_text` (also `output_image`,
  `output_audio`). [Corrected — an earlier pass used `interaction.outputs[-1].text`
  from the bundled skill; the live docs use `output_text`.]
- ✅ **`interactions.create()` params:** `model`, `input` (str | list of parts),
  `generation_config` (holds `thinking_level`), `previous_interaction_id`, `tools`,
  `system_instruction`, `store` (default `true`), `background`, `stream`.
  Source: <https://ai.google.dev/gemini-api/docs/interactions.md.txt>
- ✅ **Stateful multi-turn:** pass `previous_interaction_id=<prev>.id`; the server
  retains history (no manual chat array). `store=false` disables it (and `background`).
- ✅ **Storage:** stored by default; paid tier retains 55 days, free tier 1 day.
- ✅ `tools`, `system_instruction`, `generation_config` are **interaction-scoped** —
  re-specify them every turn.
- ✅ **Status values:** `completed | in_progress | requires_action | failed | cancelled`.

### 6.1 Setting the thinking level (verified, two forms)

```python
# Interactions API (recommended for agents) — generation_config dict:
interaction = client.interactions.create(
    model="gemini-3.5-flash",
    input="List 3 famous physicists and their key contributions",
    generation_config={"thinking_level": "low"},
)
print(interaction.output_text)
```
Source: <https://ai.google.dev/gemini-api/docs/interactions/thinking.md.txt>

```python
# generate_content (typed config) — for reference / legacy paths:
from google.genai import types
response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents="Prove that the square root of 2 is irrational.",
    config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level="high")
    ),
)
print(response.text)
```
Source: <https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.5.md.txt>

- ✅ Param is `thinking_level` (string enum), replacing the deprecated numeric
  `thinking_budget`.

### 6.2 Function calling / structured output

- ✅ Both **supported**. 3.x function-calling convention is stricter (breaking):
  responses must include `id`, match `name`, and match response counts; multimodal
  results go INSIDE function-response parts.
  Source: <https://ai.google.dev/gemini-api/docs/interactions/whats-new-gemini-3.5>
- ⏳ Exact structured-output schema-passing code — confirm verbatim if we need it.

## 7. Migration: `gemini-3-flash-preview` → `gemini-3.5-flash`

Source: <https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.5.md.txt> +
interactions whats-new.

1. Model string `gemini-3-flash-preview` → `gemini-3.5-flash`.
2. Default thinking `high` → `medium` (re-test prompts).
3. `thinking_budget` (numeric) → `thinking_level` (string enum).
4. **Remove `temperature`, `top_p`, `top_k`** — "no longer recommended" for Gemini 3.x.
5. Pricing ~3× higher (§5).
6. Thought preservation ON by default → more tokens/cost.
7. Stricter function-calling conventions (id / name / count).
8. Computer Use not yet on 3.5 (stay on 3 Flash Preview if you need it).
9. Knowledge cutoff January 2025.
10. SDK floor → `>=2.0.0`.

## 8. Gotchas

- Default thinking shifted to `medium`: faster/cheaper than `high` but re-test demo
  prompts. For tight loop iterations, `low`/`minimal` cut cost (output billed incl.
  thinking tokens).
- Drop `temperature`/`top_p`/`top_k` from any 3.x call — not recommended.
- Use `interaction.output_text`, not `.outputs[-1].text`, for the simple text path.

## 9. Sources

- What's new (Gemini 3.5): <https://ai.google.dev/gemini-api/docs/interactions/whats-new-gemini-3.5>
- What's new (alt path): <https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.5.md.txt>
- Model spec: <https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash.md.txt>
- Pricing: <https://ai.google.dev/gemini-api/docs/pricing.md.txt>
- Rate limits: <https://ai.google.dev/gemini-api/docs/rate-limits.md.txt>
- Interactions API: <https://ai.google.dev/gemini-api/docs/interactions.md.txt>
- Quickstart: <https://ai.google.dev/gemini-api/docs/interactions/quickstart.md.txt>
- Thinking: <https://ai.google.dev/gemini-api/docs/interactions/thinking.md.txt>

## 10. Open / unverified

Items here are **not safe to build on**. They graduate above only with a source URL.

- [ ] Exact RPM/TPM/RPD per tier (AI Studio dashboard only).
- [ ] Hackathon / temp-account quota specifics (assume Free-tier caps; verify the
      issued key in AI Studio on the day).
- [ ] Separate audio-input pricing for 3.5 (preview had one; 3.5 page showed flat $1.50).
- [ ] Per-file multimodal size/resolution caps (media-resolution guide).
- [ ] Structured-output schema-passing exact code (support confirmed; code TBD).

Graduated this pass: full pricing (§5), rate-limit tiers (§5), multimodal inputs
(§4), knowledge cutoff Jan 2025 (§3), thinking-level SDK code both forms (§6.1),
function-calling/structured-output support (§6.2), migration delta (§7), corrected
SDK floor to `>=2.0.0` and output accessor to `output_text` (§6).
