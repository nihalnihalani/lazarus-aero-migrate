# Findings — Gemini 3.5 Flash (owner: researcher-gemini)

> Append verified facts here, each with a **source URL** and a verbatim quote where
> possible. Mark anything uncertain `[UNVERIFIED]`. Lead reconciles into
> `docs/RESEARCH_GEMINI_3.5.md` via doc-keeper.

## Seed facts (verified by lead, 2026-05-23)
- Model ID: `gemini-3.5-flash` — GA (~2026-05-19).
  Source: https://ai.google.dev/gemini-api/docs/interactions/whats-new-gemini-3.5
- 1M token context, 65k max output tokens.
- Thinking levels: `minimal | low | medium | high`; default shifted to `medium`.
- "Thought preservation": intermediate reasoning maintained across multi-turn.
- All Gemini 3 family features EXCEPT Computer Use.

## Verified (researcher-gemini, 2026-05-23 — live docs)
- [x] Exact pricing (input/output/cached) — §4
- [x] Rate limits / quotas (free tier vs paid; hackathon temp accounts) — §5
- [x] Multimodal inputs supported (image/audio/video/pdf) + limits — §6
- [x] How to set thinking level via SDK (param name + values) + verbatim code — §7
- [x] Structured output / function calling support + how — §9
- [x] Knowledge cutoff / training date — §3
- [x] Differences vs `gemini-3-flash-preview` — §11
- [x] Quickstart code (Python `google-genai`) verified against docs — §8
- [x] Minimum `google-genai` version — §10

---

## 1. Model identity & status
- **Model ID:** `gemini-3.5-flash`. Status: "generally available (GA), stable, and ready
  for scaled production use." Release ~2026-05-19. Preview predecessor: `gemini-3-flash-preview`.
- Sources: https://ai.google.dev/gemini-api/docs/interactions/whats-new-gemini-3.5 ·
  https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash.md.txt
  (spec: "Versions: Stable: `gemini-3.5-flash` · Preview: `gemini-3-flash-preview`")

## 2. Context / output token limits
- Input (context window): **1,048,576** (1M). Output: **65,536** (65k).
- Source: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash.md.txt

## 3. Knowledge cutoff
- **January 2025.** Latest update: May 2026.
- Source: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash.md.txt
  (The whats-new pages do NOT state a cutoff; the model spec page does.)

## 4. Pricing (per 1M tokens) — verified
Source: https://ai.google.dev/gemini-api/docs/pricing.md.txt (no explicit date on page)

### gemini-3.5-flash
| | Standard (paid) | Batch (paid) | Free tier |
|---|---|---|---|
| Input | **$1.50** | $0.75 | Free of charge |
| Output (incl. thinking tokens) | **$9.00** | $4.50 | Free of charge |
| Context caching | $0.15 | $0.075 | — |
| Cache storage | $1.00 / 1M tokens / hour | $1.00 / 1M tokens / hour | — |

- Output price "includes thinking tokens" (verbatim) → thinking is billed as output.

### gemini-3-flash-preview (comparison)
- Input $0.50 (text/image/video), $1.00 (audio); Output $3.00; Caching $0.05/$0.10.
- **Cost impact:** 3.5 is **3x** preview on both input ($1.50 vs $0.50 text) and output ($9.00 vs $3.00).
- `[UNVERIFIED]` whether 3.5 has a separate audio-input surcharge (preview did; 3.5 page showed flat $1.50).

## 5. Rate limits / quotas
Source: https://ai.google.dev/gemini-api/docs/rate-limits.md.txt
- Exact RPM/TPM/RPD **not published**: "Rate limits depend on a variety of factors (such as
  your usage tier) and can be viewed in Google AI Studio." → https://aistudio.google.com/rate-limit
- Tiers: Free ("Active project or free trial"); Tier 1 (link billing acct, $250 cap);
  Tier 2 ($100 paid + 3 days, $2,000 cap); Tier 3 ($1,000 paid + 30 days, $20k–$100k+ cap).
- Batch enqueued-token limits (3.5-flash): T1 = 3,000,000 · T2 = 400,000,000 · T3 = 1,000,000,000.
- Free tier: 3.5-flash listed "Free of charge" → a free AI Studio key CAN call it (free-tier rate caps apply).
- Hackathon/temp accounts: no dedicated note in docs. `[UNVERIFIED]` — assume Free-tier limits; verify the issued key in AI Studio.

## 6. Multimodal inputs
- Inputs: "Text, Image, Video, Audio, and PDF". Output: Text only.
- Source: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash.md.txt
- Per-file size/resolution caps: `[UNVERIFIED]` → https://ai.google.dev/gemini-api/docs/interactions/media-resolution

## 7. Thinking levels + EXACT SDK param
Sources: https://ai.google.dev/gemini-api/docs/interactions/thinking.md.txt ·
https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.5.md.txt
- **Param:** `thinking_level` (string). Replaces deprecated numeric `thinking_budget`.
- **Values:** `"minimal" | "low" | "medium" | "high"`. **Default = `medium`**
  ("The default thinking effort is now `medium`, changed from `high` in Gemini 3 Flash Preview";
  "`medium` yields very good results... while being faster and more cost-efficient").
- Thought preservation/signatures ON by default → carries multi-turn reasoning, increases token cost.

### Verified Python — generate_content (typed config)
Source: https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.5.md.txt (verbatim)
```python
from google import genai
from google.genai import types

client = genai.Client()
response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents="Prove that the square root of 2 is irrational.",
    config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level="high")
    ),
)
print(response.text)
```

### Verified Python — Interactions API (recommended for agents)
Source: https://ai.google.dev/gemini-api/docs/interactions/thinking.md.txt (model → 3.5 per quickstart)
```python
from google import genai

client = genai.Client()
interaction = client.interactions.create(
    model="gemini-3.5-flash",
    input="List 3 famous physicists and their key contributions",
    generation_config={"thinking_level": "low"},
)
print(interaction.output_text)
```

## 8. Quickstart (Interactions API) — verified
Source: https://ai.google.dev/gemini-api/docs/interactions/quickstart.md.txt
```python
from google import genai

client = genai.Client()  # reads AI Studio API key from env
interaction = client.interactions.create(
    model="gemini-3.5-flash",
    input="Explain how AI works in a few words",
)
print(interaction.output_text)
```
- Install: `pip install -q -U google-genai` (docs recommend `>=2.0.0`, §10).
- API key: https://aistudio.google.com/app/apikey . REST uses `$GEMINI_API_KEY`; SDK reads env.
- Output props on interaction: `output_text`, `output_image`, `output_audio`.
- `interactions.create()` params: `model`, `input` (str|list of parts), `generation_config`
  (holds `thinking_level`), `previous_interaction_id`, `tools`, `system_instruction`,
  `store` (default true), `background`, `stream`.
  Source: https://ai.google.dev/gemini-api/docs/interactions.md.txt

## 9. Structured output & function calling
Source: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash.md.txt
- **Structured outputs: Supported. Function calling: Supported.**
- Also supported: Caching, Code execution, File search, Batch API, Flex inference,
  Priority inference, Grounding with Google Maps, Search grounding, Thinking, URL context.
- 3.x function-calling convention (breaking): responses must include `id`, match `name`,
  match response counts. Multimodal results go INSIDE function-response parts.
  Source: https://ai.google.dev/gemini-api/docs/interactions/whats-new-gemini-3.5
- **NOT supported by 3.5-flash:** Computer use ("Computer Use is not supported at this moment"),
  Image generation, Audio generation, Live API.

## 10. Minimum google-genai SDK version
- Docs: "We strongly recommend updating to `google-genai` SDK **v2.0.0 or later**."
  Source: https://ai.google.dev/gemini-api/docs/interactions/whats-new-gemini-3.5
- PyPI cross-check (2026-05-23): 2.0.0 exists; latest **2.6.0**. JS `@google/genai` latest v2.0.1.
- **ACTION:** bump repo `requirements.txt` `google-genai>=1.55.0` → **`>=2.0.0`** (prefer `>=2.6.0`).

## 11. Differences vs gemini-3-flash-preview (migration)
Sources: https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.5.md.txt + interactions/whats-new
1. Model string `gemini-3-flash-preview` → `gemini-3.5-flash`.
2. Default thinking `high` → `medium` (re-test prompts).
3. `thinking_budget` (numeric) → `thinking_level` (string enum).
4. **Remove `temperature`, `top_p`, `top_k`** — "no longer recommended" for Gemini 3.x.
5. Pricing ~3x higher (§4).
6. Thought preservation ON by default → more tokens/cost.
7. Stricter function-calling conventions (id/name/count).
8. Computer Use not yet on 3.5 (stay on 3 Flash Preview for it).
9. Knowledge cutoff January 2025.
10. SDK floor → `>=2.0.0`.

---

## CONTRADICTIONS WITH CURRENT REPO (for team-lead / backend-eng)
1. **`requirements.txt` pins `google-genai>=1.55.0`** — docs require **`>=2.0.0`** for 3.5-flash.
   MUST bump. `src/agent.py` lines 9 & 23 repeat `>=1.55.0`.
2. **`src/agent.py` header (lines 14–15)** says the LAZARUS agent doesn't support
   `function_calling`/structured output. That's a *managed-agent config* claim, NOT a model
   limit — the **model `gemini-3.5-flash` DOES support both** (spec page §9). Flagging the
   wording; whether the Antigravity managed agent exposes them is task #2/#5's lane.
3. `src/agent.py` uses the managed-agent shape (`interactions.create(agent=..., environment=...,
   stream=True)`, `agents.create(...)`). I could NOT confirm that surface from the model/interactions
   docs I fetched — owned by task #2 (researcher-agents). No contradiction found; just unverified by me.

## OPEN / UNVERIFIED
- Exact RPM/TPM/RPD per tier (AI Studio dashboard only).
- Hackathon/temp-account quota specifics.
- Separate audio-input pricing for 3.5 (preview had one; 3.5 page showed flat $1.50).
- Per-file multimodal size/resolution caps (see media-resolution guide).
