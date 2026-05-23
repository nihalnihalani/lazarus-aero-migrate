# Findings — Managed Agents + Interactions API (owner: researcher-agents)

> Append verified facts here, each with a **source URL** and a verbatim quote where
> possible. Mark anything uncertain `[UNVERIFIED]`. Lead reconciles into
> `docs/RESEARCH_MANAGED_AGENTS.md` via doc-keeper.

> **STATUS: ALL CRITICAL ITEMS RESOLVED (2026-05-23, researcher-agents).** Every fact has a
> source + verbatim quote, or is marked `[UNVERIFIED]`.

## Sources (all real, fetched 2026-05-23)
- Agents overview: https://ai.google.dev/gemini-api/docs/agents.md.txt
- Managed Agents quickstart: https://ai.google.dev/gemini-api/docs/managed-agents-quickstart.md.txt
- Custom agents: https://ai.google.dev/gemini-api/docs/custom-agents.md.txt
- Agent environment: https://ai.google.dev/gemini-api/docs/agent-environment.md.txt
- Antigravity agent: https://ai.google.dev/gemini-api/docs/antigravity-agent.md.txt
- Antigravity model card: https://ai.google.dev/gemini-api/docs/models/antigravity-preview-05-2026.md.txt
- Interactions API: https://ai.google.dev/gemini-api/docs/interactions.md.txt
- Interactions quickstart: https://ai.google.dev/gemini-api/docs/interactions/quickstart.md.txt
- Interactions API reference (SSE/step shapes): https://ai.google.dev/static/api/interactions.md.txt
- Managed Agents launch blog: https://blog.google/innovation-and-ai/technology/developers-tools/managed-agents-gemini-api/
- **Official runnable cookbook (source of truth for working code):**
  https://github.com/google-gemini/cookbook/blob/main/quickstarts/Get_started_managed_agents.ipynb
- Official Python SDK README: https://github.com/googleapis/python-genai

## ⚠️ TOP RECONCILIATION NOTES (read first)
1. **`interactions.create` takes `environment` via `extra_body`, NOT a top-level kwarg.** Docs
   *pages* show top-level `environment="remote"`, but the SDK doesn't expose it typed yet; the
   cookbook (runnable) + SDK README confirm `extra_body={"environment": ...}`. `agents.create`
   IS different — `base_environment` is a real top-level typed param.
2. **Pin `google-genai>=2.0.0`** for managed agents (cookbook). The `1.55.0` in interactions docs
   is the model-interactions path.
3. **Base agent ID still has `-preview-`:** `antigravity-preview-05-2026`. Repo string is correct.
4. **FORGE caveat (C3):** a runtime-authored `SKILL.md` persists on disk when the environment is
   reused (verified); auto-RELOAD into the agent's instruction context mid-flight is `[UNVERIFIED]`
   — use the safe pattern below.

## Seed-fact corrections
- Two base managed agents: **Antigravity** (Gemini 3.5 Flash) + **Deep Research**. ✅ correct.
- One API call provisions an **Ubuntu** sandbox: **Python 3.12, Node.js 22, 4 CPU cores, 16 GB RAM**,
  ~5s cold provision. ✅ (agent-environment.md.txt).
- ❌ CORRECTION to the seed tool list: that list is the *generic platform* tools. The **Antigravity
  agent specifically does NOT support `computer_use`, `file_search`, `google_maps`, `function_calling`,
  `mcp`**. It supports only `code_execution`, `google_search`, `url_context`, Filesystem. (See C4.)
- ❌ CORRECTION: environments are **auto-snapshot+stopped after 15 min idle** and **retained 7 days
  since last active** (resumable by ID) — not "permanently deleted after 7 days of *inactivity*"
  loosely. Up to 1,000 agents ✅.

## CRITICAL — RESOLVED

### C1 — Base agent ID ✅ `antigravity-preview-05-2026`
Verbatim across antigravity-agent.md.txt, custom-agents.md.txt, managed-agents-quickstart.md.txt,
and the cookbook (`AGENT = "antigravity-preview-05-2026"`). Same string for `agent=` (interactions)
and `base_agent=` (agents.create). The `-preview-` is still present as of 2026-05-23.

### C2 — `client.agents.create(...)` ✅
Verbatim (custom-agents.md.txt):
```python
agent = client.agents.create(
    id="data-analyst",
    base_agent="antigravity-preview-05-2026",
    system_instruction="You are a data analyst. Always include visualizations and export results as PDF.",
    base_environment={"type": "remote", "sources": [
        {"type": "inline", "target": ".agents/AGENTS.md", "content": "..."},
        {"type": "inline", "target": ".agents/skills/slide-maker/SKILL.md",
         "content": "---\nname: slide-maker\n---\n# Slide Maker\n..."},
        {"type": "repository", "source": "https://github.com/my-org/analysis-templates",
         "target": "/workspace/templates"}]},
)
```
Cookbook fork-from-environment variant (useful for FORGE):
```python
client.agents.create(id="my-forked-agent", base_agent="my-gemini-api-agent",
    system_instruction="...", base_environment={"env_id": interaction.environment_id})
```
- **Params:** `id`, `base_agent`, `system_instruction`, `base_environment`.
- **`base_environment`:** `{type:"remote", sources:[...], network?}` OR `{env_id:"<existing>"}` (fork).
- **Source object:** `type` (`"inline"`|`"repository"`), `target` (path), `content` (inline) | `source` (git URL).
- **Lifecycle:** `client.agents.list().agents` (iter `.id`); `client.agents.get(id=...)`;
  `client.agents.delete(id=...)`.

### C3 — AGENTS.md / SKILL.md real? ✅ YES (one honest caveat)
- Blog (verbatim): *"define everything in markdown files like AGENTS.md and SKILL.md and register
  them as a managed agent"*.
- custom-agents.md.txt (verbatim): *"The agent automatically loads `.agents/AGENTS.md`
  (or `/.agents/AGENTS.md`) from the environment as system instructions on startup."*;
  *"Place them under `.agents/skills/<skill-name>/SKILL.md` and the harness auto-discovers and
  registers them."*; *"Skills loaded from `.agents/skills/` and `/.agents/skills/` are both
  discovered automatically."* SKILL.md = YAML frontmatter (`---\nname:\n---`) + markdown body.
- **Persistence VERIFIED.** Blog: *"Each interaction creates or receives an environment, which you
  can use in follow-up calls to resume the session with all files and state intact."*
  agent-environment.md.txt: *"Packages installed during an interaction persist when you reuse the
  same `environment_id`."* Cookbook: agent writes `knowledge.md` in turn 1, recalls it in turn 2.

**⚠️ FORGE CAVEAT (be honest on stage):** auto-load is documented as a **startup** event. There is
**NO documented statement** that a SKILL.md *authored by the agent during a run* is *auto-reloaded
into its instruction context* on a continued interaction (confirmed ABSENT in custom-agents,
agent-environment, blog, cookbook). `[UNVERIFIED]`. **SAFE PATTERN:** (1) agent writes
`/.agents/skills/<idiom>/SKILL.md` into the env; (2) file persists on disk (verified); (3) next run
starts as a *fresh startup against that env* — either reuse `extra_body={"environment": env_id}` and
tell the agent to read `/.agents/skills/`, OR fork a refreshed agent with
`base_environment={"env_id": env_id}` so startup discovery re-registers the forged skill. Do **not**
claim mid-interaction hot-reload.

### C4 — computer_use / file_search ✅ NOT supported (repo honesty claim accurate)
antigravity-agent.md.txt (verbatim): **Supported** = `code_execution`, `google_search`,
`url_context`, Filesystem (via `environment`). **NOT supported** = `file_search`, `computer_use`,
`google_maps`, `function_calling`, `mcp`. Also unsupported: temperature/top_p/top_k/stop_sequences/
max_output_tokens, **structured outputs**, audio/video/doc inputs (**text+image only**).
`background=True` requires `store=True`.

## Interactions API — usage (RESOLVED)
Runnable forms (cookbook, verbatim):
```python
from google import genai
client = genai.Client(api_key=GEMINI_API_KEY)
AGENT = "antigravity-preview-05-2026"

interaction = client.interactions.create(agent=AGENT, input="...",
    extra_body={"environment": "remote"})                       # single shot
turn2 = client.interactions.create(agent=AGENT, input="...",
    extra_body={"environment": turn1.environment_id})           # reuse env (persists)
client.interactions.create(agent=AGENT, input="Read /workspace/data.csv...",
    extra_body={"environment": {"type": "remote", "sources": [  # inject file at call time
        {"type": "inline", "content": csv_data, "target": "/workspace/data.csv"}]}})
client.interactions.create(agent=AGENT, input="curl the Gemini API...",
    extra_body={"environment": {"type": "remote", "network": {"allowlist": [  # net allowlist+creds
        {"domain": "generativelanguage.googleapis.com",
         "transform": [{"x-goog-api-key": GEMINI_API_KEY}]}]}}})
```
- `extra_body` is a **direct kwarg** to `create()` (not in `http_options`/`config`).
- `environment_id` → `interaction.environment_id`.
- Read result: `interaction.output_text` (convenience, quickstart) — BUT API reference says no
  `output_text` on the resource; safest is to iterate steps for the final `model_output` content.
- `previous_interaction_id`: model path only / `[UNVERIFIED]` for agent path (agent path uses
  environment reuse; ABSENT from agents cookbook).
- Status enum (reference, verbatim): `in_progress | requires_action | completed | failed |
  cancelled | incomplete | budget_exceeded`.

## Streaming / `interaction.steps` shape (RESOLVED — live UI)
Stream loop (cookbook, verbatim):
```python
stream = client.interactions.create(agent=AGENT, input="...", stream=True,
    extra_body={"environment": "remote"})
for event in stream:
    if event.event_type in ("interaction.created","step.start","step.stop","interaction.completed"):
        print(f"[{event.event_type}]")
    elif event.event_type == "step.delta":
        if hasattr(event.delta, "text") and event.delta.text:
            print(event.delta.text, end="", flush=True)
```
- **event types** (`event.event_type`, reference): `step.start`, `step.delta`, `step.stop`,
  `interaction.created`, `interaction.completed`, `interaction.status_update`, `error`.
- **chunk fields**: `event_type`, `event_id` (resume token), `interaction_id`, `status`, `index`,
  `step` (full Step on start/stop), `delta` (`{type, text}` on step.delta).
- **step types** (`event.step.type`, reference verbatim shapes):
  - `user_input` → `{type, content:[{type:"text", text}]}`
  - `thought` → `{type, summary:[{type:"text", text}], signature}`
  - `code_execution_call` → `{type, id, arguments:{code, language}, signature}`
  - `code_execution_result` → `{type, call_id, result, is_error, signature}`
  - `model_output` → `{type, content:[{type:"text", text}]}`
- ⚠️ The `gemini-interactions-api` SKILL shows an OLDER model-path shape (`content.delta`); use the
  `step.*` shape above for the agent path.
- ⚠️ TERMINAL EVENT: `interaction.completed` carries `event.interaction` but **"with empty outputs to
  reduce the payload size"** (API reference, verbatim). The completed event does NOT contain full
  text/steps. To get the authoritative final object after a stream, call
  `client.interactions.get(event.interaction_id)` (every event carries `event.interaction_id`), OR
  accumulate text from `step.delta` + build the timeline from `step.start`/`step.stop` as they arrive
  (cookbook approach). `output_text` is NOT a documented resource field — read final text from the last
  `model_output` step's `content[].text`; read env id from `interaction.environment_id`.
- **`interaction.steps` IS a real field** — but on the RETURNED/fetched interaction OBJECT
  (non-streaming), not a stream event name. Cookbook (verbatim, non-streaming):
  `for step in interaction.steps: step.type / step.name / step.arguments / step.content[].text`.
  So the repo's "interaction.steps as the demo surface" is VALID for the final/fetched object; for
  LIVE streaming assemble the same picture from `step.start` / `step.delta` / `step.stop`.

## Environment lifecycle (RESOLVED)
- Provision via `extra_body={"environment":"remote"}`; ~5s cold start; env id `interaction.environment_id`.
- Reuse: `extra_body={"environment": env_id}`. Persists files + installed packages (verbatim above).
- Idle (verbatim): *"Auto-snapshot and stopped after 15 minutes of inactivity."*
- Retention (verbatim): *"Retained for 7 days since last active. Can be resumed by passing its ID."*
- Resources (verbatim): *"CPU: 4 cores; Memory: 16 GB"*; Ubuntu + Py3.12 + Node22. Compute free in preview.

## Download produced files (RESOLVED)
Whole-env tarball via Files API (cookbook, verbatim):
```python
url = f"https://generativelanguage.googleapis.com/v1beta/files/environment-{env_id}:download?alt=media"
# curl -L -s -o snapshot.tar -H "x-goog-api-key: {KEY}" {url}
import tarfile
with tarfile.open("snapshot.tar") as tar: tar.extractall("extracted")
```
Extract `/workspace/...` for the migrated module. No `client.environments.download()` helper.

## SDK / install (RESOLVED)
`pip install -U 'google-genai>=2.0.0'` (cookbook). `from google import genai` →
`client = genai.Client(api_key=...)`.

## Pricing / quota (RESOLVED)
- agents.md.txt/blog: *"pay-as-you-go ... based on Gemini model tokens and tool usage"*, *"typically
  consuming 100k to 3M tokens"* per run; *"up to 1,000 managed agents"*; env compute not billed in preview.
- Interaction storage: paid 55 days / free 1 day (interactions.md.txt; `store=true` default).
- Exact $ per token for the Antigravity agent: `[UNVERIFIED]` — defer to gemini-3.5-flash token
  pricing in findings-gemini.md.

## Underlying model (RESOLVED)
Antigravity *"built on Gemini 3.5 Flash"* (blog). Context window: input 1,048,576 (compacted ~135k),
output 65,536; inputs text+image, output text (model card).

## Cookbook / reference examples
- Managed agents quickstart notebook (all code above):
  https://github.com/google-gemini/cookbook/blob/main/quickstarts/Get_started_managed_agents.ipynb
- Skills repo mounted as a `repository` source: https://github.com/google-gemini/gemini-skills
  (target `/.agents/skills`).
- Community Antigravity-compatible SKILL.md skills: https://github.com/cnemri/google-genai-skills

## ⚠️ PRODUCT DISTINCTION — ai.google.dev vs docs.cloud.google.com (RESOLVED 2026-05-23)
There are TWO different Managed-Agents products. **Do not mix their docs.**

| | **ai.google.dev Gemini API Managed Agents (Antigravity)** ← HACKATHON | docs.cloud.google.com **Gemini Enterprise Agent Platform** |
|---|---|---|
| Auth | **API key** (hackathon hands out Gemini API keys) | **GCP project** (`projects/{id}/locations/{loc}`) |
| Python / Node | **3.12 / 22** | 3.11 / 20 |
| Network default | **Unrestricted outbound** | **Isolation ON by default** (allowlist to enable) |
| Retention | "7 days since last active" | 7-day TTL, reset each interaction |
| Root/sudo | not documented (assume none) | verbatim: *"The container lacks privileged administrative credentials or permissions."* |

**The hackathon API key is governed by the ai.google.dev docs.** (devils-advocate's "Python 3.11 /
Node 20 / network-off" came from the Enterprise GCP product — the wrong product for us.)
- Enterprise sandbox doc: https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/managed-agents/sandbox-environment

## Sandbox capability facts for the LIVE-COMPILE / GnuCOBOL beat (RESOLVED)
- **code_execution = real bash** (antigravity-agent.md.txt, verbatim): *"Run Bash, Python, and
  Node.js commands. Install packages, run tests, build apps."* and *"Run shell commands (bash,
  Python, Node) with stdout/stderr capture."* curl & wget pre-installed.
- **Network** (agent-environment.md.txt, verbatim): *"By default, environments have unrestricted
  outbound network access."* → can reach pip/npm/conda/apt mirrors.
- **Runtime install**: documented = `pip install` / `npm install`; "Install packages ... build apps".
  **Root/sudo NOT documented → `apt-get` is the RISKY path; do not rely on it.**
- **Binary mount via `sources` is BLOCKED** (agent-environment.md.txt, verbatim): *"The agent is
  currently constrained to reading text and image files. Binary file support is not yet available."*
  Source types: `inline` (text, ≤1MB/file, ≤2MB total), `repository` (git, ≤500MB), `gcs` (≤2GB).
  → CANNOT base64-mount a precompiled `cobc`. The "ship a prebuilt binary via sources" escape hatch is dead.
- **VERDICT — live-compile SURVIVES** via code_execution(bash) at runtime + unrestricted network,
  NOT via sources. Recommended no-root install of GnuCOBOL: **micromamba/conda from conda-forge into
  a `/workspace` prefix** (userland, persists in env); ALT = build from source `--prefix=/workspace`
  (needs gcc+gmp, likely present, `[UNVERIFIED]`). Build a FALLBACK: pre-capture COBOL ground-truth
  output offline and ship as inline TEXT sources to keep the differential-oracle claim honest if
  live `cobc` install ever fails. (Detailed verification = task #8.)

## Could not fetch
- YouTube https://www.youtube.com/watch?v=OdrOmc_RX8A — not retrievable as text via WebFetch
  (video page, no transcript). `[UNVERIFIED]` — not used as a source.
