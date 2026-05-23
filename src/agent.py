"""
LAZARUS — Managed Agent driver.

Single Gemini 3.5 Flash Managed Agent (Antigravity) that migrates COBOL -> tested
Python, proves equivalence against the original COBOL (differential oracle), and
forges its own SKILL.md when it meets an unknown idiom.

Reconciled to the VERIFIED Managed Agents / Interactions API surface (see
docs/RESEARCH_MANAGED_AGENTS.md, consolidated 2026-05-23). Key facts this code
depends on:
  - SDK:               google-genai >= 2.4.0 floor (client.agents + Environment API ship in
                       2.4.0; step.* SSE in 2.0.0; output_text in 2.3.0). We pin >= 2.6.0.
  - Base agent id:     "antigravity-preview-05-2026"  (Gemini 3.5 Flash; same string for
                       agent= and base_agent=)
  - Gemini 3.x config: BREAKING — do NOT send temperature / top_p / top_k anywhere; they
                       are rejected/ignored on Gemini 3.x. The only generation knob is
                       thinking_level (str: minimal|low|medium|high; default now "medium").
                       We pass NO generation_config and rely on the "medium" default, so
                       there is nothing to break here — keep it that way.
  - Capability note:   The MANAGED-AGENT runtime does not expose function_calling,
                       structured output, mcp, computer_use, or file_search. (This is an
                       agent-runtime limitation, NOT a model limitation — the underlying
                       gemini-3.5-flash model DOES support function calling & structured
                       output; the Antigravity agent simply doesn't surface them.)
  - Create agent:      client.agents.create(id, base_agent, system_instruction, base_environment)
  - Run interaction:   client.interactions.create(agent=..., input=..., stream=...,
                       extra_body={"environment": "remote" | <env_id> | {type,sources}})
                       -> environment is passed via extra_body, NOT a top-level kwarg.
  - State threading:   reuse interaction.environment_id (files + packages persist).
                       previous_interaction_id is the MODEL path's state carrier and is
                       UNVERIFIED on the agent path, so we thread state via environment_id.
  - Streaming events:  event.event_type in {step.start, step.delta, step.stop,
                       interaction.created, interaction.completed, interaction.status_update,
                       error}; step.delta carries event.delta.text; the completed event
                       carries the final interaction (with .steps, .id, .environment_id).
  - Reading output:    iterate interaction.steps for the model_output step (the agent
                       resource has no guaranteed .output_text attr).

FORGE beat (SAFE pattern — do NOT rely on silent mid-run auto-reload of an
agent-authored SKILL.md, which is UNVERIFIED):
  1. The agent writes .agents/skills/<idiom>/SKILL.md and commits it (persists on disk
     IN THIS environment).
  2. The retry interaction REUSES the same environment_id so the file is present.
  3. The retry prompt EXPLICITLY instructs the agent to re-read .agents/skills/ before
     retrying — we never assume the forged skill is already in context.
  Persistence scope: the forged skill lives in the reused environment, NOT forever. A
  fresh agent invocation forks a clean base_environment; carrying a forged skill into
  future runs permanently means re-registering the agent with that SKILL.md mounted.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re

from google import genai  # pip install -U "google-genai>=2.6.0"

AGENT_ID = "lazarus"
BASE_AGENT = "antigravity-preview-05-2026"   # Gemini 3.5 Flash managed agent (verified)
MAX_ITERATIONS = 4                            # hard cap — never loop forever on stage

AGENTS_DIR = pathlib.Path(__file__).resolve().parent.parent / ".agents"

# ---------------------------------------------------------------------------
# OPT-IN CAPABILITY FLAGS (each DEFAULT OFF — with all flags off the prompt,
# base_environment, and interaction config are byte-identical to the shipped
# single-module live path). Read from the environment on every call so the
# behavior is per-run and unit-testable via monkeypatching os.environ.
# ---------------------------------------------------------------------------
#   LAZARUS_GROUND   — web-grounding: research an unknown idiom via
#                      google_search / url_context BEFORE forging (Feature 1).
#   LAZARUS_THINKING — interaction-scoped thinking level (Feature 2).
# Set when the managed-agent runtime rejects an interaction-scoped thinking
# config (graceful no-op): the driver retries WITHOUT it and records the fact
# so the UI / operator can see the capability isn't actually supported there.
THINKING_REJECTED = False


def _grounding_enabled() -> bool:
    """True when web-grounding (Feature 1) is opted in via LAZARUS_GROUND.

    Accepts 1/true/yes/on (case-insensitive). DEFAULT OFF: any other value (or
    unset) keeps the byte-identical, non-grounded prompt + stream behavior.
    """
    return os.environ.get("LAZARUS_GROUND", "").strip().lower() in {"1", "true", "yes", "on"}


_THINKING_LEVELS = {"minimal", "low", "high"}   # "medium" is the runtime default (no-op)


def _thinking_level() -> str | None:
    """The interaction-scoped thinking level to request, or None to send nothing.

    LAZARUS_THINKING (Feature 2). The shipped path sends NO generation_config and relies
    on the agent's "medium" default (docs/RESEARCH §3: thinking_level default is "medium").
    So the DEFAULT VALUE — and "medium" specifically — must keep sending nothing, staying
    byte-identical to today. We return a level ONLY for a value that genuinely DIFFERS from
    the default (minimal|low|high). "medium"/"default"/"off"/"none"/unset/unrecognized all
    return None (no-op, never an error).
    """
    raw = os.environ.get("LAZARUS_THINKING", "").strip().lower()
    return raw if raw in _THINKING_LEVELS else None

# Heuristics for reading the agent's terminal message (the demo also shows this on screen).
_PASS_RE = re.compile(
    r"(all\s+(\d+\s+)?(equivalence\s+)?tests?\b[^.\n]{0,40}\bpass"  # "All 30 Equivalence Tests: PASS"
    r"|\ball\s+tests?\s+pass(ed)?\b"
    r"|\b0\s+failed\b"
    r"|\b\d+\s+passed,\s*0\s+failed\b"
    r"|\b100\s*%\s*(success|pass)"
    r"|\bequivalent to (the )?original cobol\b"
    r"|\bbyte[\s\-]for[\s\-]byte\s+(identical|equivalent)\b)",
    re.I,
)
# Clear failure signals VETO a pass (handles negations like "not equivalent").
_FAIL_RE = re.compile(
    r"\b([1-9]\d*\s+(tests?\s+)?failed"
    r"|did\s*n[o']?t\s+pass"
    r"|not\s+(byte[\s\-]for[\s\-]byte\s+)?(equivalent|identical)"
    r"|still\s+(red|failing)"
    r"|could\s+not\s+(reach|achieve|pass))",
    re.I,
)
_FORGE_RE = re.compile(r"(\.agents/skills/[\w\-./]+SKILL\.md)", re.I)


def build_base_environment() -> dict:
    """Mount AGENTS.md + any seed SKILL.md files into a fresh remote sandbox.

    base_environment is an object (not a bare string); `sources` mounts files at the
    paths the agent auto-discovers on startup (.agents/AGENTS.md, .agents/skills/*/SKILL.md).
    """
    sources = [
        {
            "type": "inline",
            "target": ".agents/AGENTS.md",
            "content": (AGENTS_DIR / "AGENTS.md").read_text(),
        }
    ]
    for skill_md in sorted((AGENTS_DIR / "skills").glob("*/SKILL.md")):
        sources.append(
            {
                "type": "inline",
                "target": f".agents/skills/{skill_md.parent.name}/SKILL.md",
                "content": skill_md.read_text(),
            }
        )
    return {"type": "remote", "sources": sources}


# Where we remember which mounted skill set the registered agent was built from, so a
# FRESH invocation can re-register when the on-disk skill library has changed (Feature 3:
# cross-run skill accumulation). The registry doesn't report an agent's mounted skills, so
# we track the fingerprint locally. Lives under .agents/ (gitignored line in .gitkeep dir
# is fine) — it's a cache, not source of truth.
_SKILL_FINGERPRINT_FILE = AGENTS_DIR / ".skill_fingerprint"


def _mounted_skill_fingerprint() -> str:
    """A stable hash of the skill set build_base_environment() will mount RIGHT NOW.

    Covers each skill's discovery target AND its content (so editing a forged SKILL.md
    re-registers too), plus AGENTS.md. Sorted for determinism. Used to decide whether a
    pre-existing agent must be re-registered to pick up newly-forged/changed skills.
    """
    import hashlib
    h = hashlib.sha256()
    try:
        h.update(b"AGENTS.md\0")
        h.update((AGENTS_DIR / "AGENTS.md").read_bytes())
        h.update(b"\0")
    except OSError:
        pass
    for skill_md in sorted((AGENTS_DIR / "skills").glob("*/SKILL.md")):
        h.update(f"{skill_md.parent.name}\0".encode())
        try:
            h.update(skill_md.read_bytes())
        except OSError:
            pass
        h.update(b"\0")
    return h.hexdigest()


def _read_registered_fingerprint() -> str | None:
    try:
        return _SKILL_FINGERPRINT_FILE.read_text().strip() or None
    except OSError:
        return None


def _write_registered_fingerprint(fp: str) -> None:
    try:
        _SKILL_FINGERPRINT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SKILL_FINGERPRINT_FILE.write_text(fp)
    except OSError:
        pass  # best-effort cache; a miss just means we may re-register next run


def _create_lazarus_agent(client: genai.Client) -> None:
    client.agents.create(
        id=AGENT_ID,
        base_agent=BASE_AGENT,
        system_instruction="You are LAZARUS, an autonomous COBOL->Python migration agent. "
        "Follow .agents/AGENTS.md exactly.",
        base_environment=build_base_environment(),
        # tools omitted -> defaults to code_execution + google_search + url_context.
    )


def ensure_agent(client: genai.Client) -> None:
    """Create the reusable custom agent, mounting EVERY .agents/skills/*/SKILL.md into
    base_environment so a FRESH invocation starts with the accumulated skill library
    (Feature 3: cross-run skills). Clean-fork stays the default when no skills exist.

    Re-registration on skill change: build_base_environment() already mounts whatever
    skills are on disk, but a PRE-EXISTING agent was registered with an OLDER skill set
    and the registry won't tell us which. So we track the mounted-skill fingerprint
    locally; if the agent exists but the on-disk skill set has CHANGED (a skill was forged
    or edited since it was registered), we delete + recreate it so the new skill is mounted.
    When the fingerprint matches, this stays a no-op (idempotent — unchanged behavior).
    """
    try:
        existing = {a.id for a in client.agents.list().agents}
    except Exception:
        existing = set()

    current_fp = _mounted_skill_fingerprint()
    has_forged_skills = any((AGENTS_DIR / "skills").glob("*/SKILL.md"))

    if AGENT_ID in existing:
        recorded = _read_registered_fingerprint()
        # Idempotent (unchanged behavior) when nothing skill-related has changed:
        #   * no forged skills on disk AND no recorded fingerprint -> the shipped clean-fork
        #     world (the agent has no accumulated skills to miss), OR
        #   * the recorded fingerprint already matches the current skill set.
        # Only re-register when forged skills exist whose fingerprint differs from what the
        # agent was registered with -> a NEW/CHANGED skill the running agent wouldn't have.
        if recorded == current_fp or (recorded is None and not has_forged_skills):
            return
        # Skill set changed since the agent was registered -> re-register to mount it.
        try:
            client.agents.delete(id=AGENT_ID)
        except Exception:
            pass  # if delete is unavailable, create() below may still upsert; best-effort

    _create_lazarus_agent(client)
    _write_registered_fingerprint(current_fp)


# Opt-in research preamble (Feature 1). Prepended ONLY when grounding is enabled, so
# the un-grounded prompt stays byte-identical. The Antigravity agent already defaults to
# google_search + url_context tools (ensure_agent leaves tools at default), so this is a
# pure instruction change steering the agent to research an unfamiliar idiom and cite it.
_GROUNDING_PREAMBLE = (
    "WEB-GROUNDING IS ON. When you hit a COBOL idiom you are NOT certain about, do NOT "
    "guess and do NOT forge a SKILL.md from memory. FIRST research it: use the "
    "google_search tool for the idiom (e.g. \"COBOL ROUNDED rounding mode\", "
    "\"COBOL PIC 9V99 DISPLAY de-editing\") and the url_context tool to read the most "
    "authoritative source you find (IBM Enterprise COBOL language reference, GnuCOBOL "
    "docs, ISO COBOL standard). Cite each finding inline as `SOURCE: <url> — <one-line "
    "fact>` BEFORE you write the skill, and base the forged .agents/skills/<idiom>/SKILL.md "
    "on those cited findings. Grounded research precedes the forge, never replaces the "
    "byte-for-byte differential oracle.\n\n"
)


def _build_prompt(cobol: str, *, ground: bool = False) -> str:
    preamble = _GROUNDING_PREAMBLE if ground else ""
    return preamble + (
        "Migrate this COBOL program to idiomatic Python. Work in the sandbox.\n"
        "1. Recover and print the business rules in plain English.\n"
        "2. Translate to Python and write the final module to /workspace/payroll.py "
        "(the orchestrator fetches exactly that path from the environment — write it "
        "there, not just to a notebook cell).\n"
        "3. DIFFERENTIAL ORACLE (ground truth = the ORIGINAL COBOL's REAL output):\n"
        "   - PRIMARY: src/sample/golden_io.json holds real GnuCOBOL outputs captured "
        "ahead of time. Use these as ground truth. Do NOT try to install a COBOL "
        "compiler (the sandbox has no root/package manager); the diff must not depend "
        "on a live compile.\n"
        "   - LIVE REFRESH: install real GnuCOBOL WITHOUT root via micromamba + "
        "conda-forge (`micromamba create -p /workspace/cobol -c conda-forge gnucobol` — "
        "the conda package brings its own compiler), or use `cobc` if already present, then "
        "compile + run the ORIGINAL COBOL over the battery to confirm golden_io.json is "
        "still fresh — but the equivalence check stays byte-for-byte against the golden bytes.\n"
        "4. Generate equivalence tests asserting python_output == golden_cobol_output "
        "byte-for-byte; run pytest.\n"
        "5. On failure, diagnose the TRUE idiom from the byte diff and write "
        ".agents/skills/<idiom>/SKILL.md teaching yourself how to handle it, commit it, "
        "and report the path you wrote. For this module the divergence is numeric DISPLAY "
        "de-editing (PIC 9(7)V99 -> zero-padded 7 int digits + '.' + 2 decimals) plus "
        "COBOL `ROUNDED` = round-half-UP (use Decimal.quantize(ROUND_HALF_UP), NOT Python "
        "round()/banker's). It is NOT the COMP-3 storage (USAGE DISPLAY emits identical "
        "bytes). Name the skill for the real idiom (e.g. numeric-display-rounding).\n"
        "6. EMIT MACHINE-READABLE MARKERS for the live UI. These are REQUIRED, one per "
        "line, with the EXACT prefix, as plain text in your output (not inside a code "
        "cell). The UI parses these prefixes verbatim:\n"
        "   - For EACH recovered rule (emit at least 3): `LAZARUS_RULE: {\"title\":..., "
        "\"plain\":..., \"cobol_ref\":..., \"severity\":\"rule|edge_case|gotcha\"}`\n"
        "   - After running the oracle, exactly ONE line: `LAZARUS_ORACLE_JSON: "
        "[{\"input\":..., \"cobol\":..., \"python\":..., \"match\":true|false}, ...]` "
        "covering EVERY golden input (the per-input COBOL-vs-Python byte values — this is "
        "the test panel's money shot).\n"
        "   - As your FINAL step, print the COMPLETE final payroll.py exactly once, on the "
        "line `LAZARUS_MODULE:` immediately followed by a single fenced ```python block "
        "containing the WHOLE module verbatim (the same bytes you wrote to "
        "/workspace/payroll.py). The orchestrator recovers the module from this block to "
        "render the diff + arm Download, so it must be the entire runnable file — no "
        "elisions, no '...'.\n"
        "Emit the markers even on a failing iteration (the UI shows RED then GREEN). "
        "When done, state clearly whether all equivalence tests PASS.\n"
        f"Stop when tests pass or after {MAX_ITERATIONS} iterations.\n\n"
        f"COBOL:\n```cobol\n{cobol}\n```"
    )


def _render_modules(modules: list[tuple[str, str]]) -> str:
    """Fence every (name, source) module so the agent sees the whole codebase at once."""
    blocks = []
    for name, source in modules:
        label = name or "module.cob"
        blocks.append(f"=== {label} ===\n```cobol\n{source}\n```")
    return "\n\n".join(blocks)


def _build_multi_prompt(modules: list[tuple[str, str]], *, ground: bool = False) -> str:
    """Whole-codebase prompt (Feature 4): migrate a SET of COBOL modules (+ copybooks)
    together, recovering CROSS-MODULE business rules (shared copybook layouts, a rule split
    across a caller + its CALLed subprogram, a constant defined in one module and used in
    another). All modules are presented at once so the agent can reason across them.

    Reuses the single-file marker + oracle contract verbatim (so the live UI's panels work
    unchanged), but the recover/translate steps are scoped to the whole module set. Used
    ONLY when migrate() is given >1 file; the single-file path still calls _build_prompt and
    stays byte-identical.
    """
    preamble = _GROUNDING_PREAMBLE if ground else ""
    names = ", ".join(name or "module.cob" for name, _ in modules)
    return preamble + (
        f"Migrate this COBOL CODEBASE ({len(modules)} files: {names}) to idiomatic Python. "
        "Treat the files as ONE system, not in isolation. Work in the sandbox.\n"
        "1. CROSS-MODULE RECOVERY: read EVERY module + copybook below and recover the "
        "business rules across the whole set in plain English — including rules that span "
        "modules: shared copybook record layouts (COPY), a computation split across a "
        "calling program and the subprogram it CALLs, constants/88-levels defined in one "
        "module and relied on by another, and any ordering/lifecycle dependency between "
        "modules. Print the recovered cross-module rules.\n"
        "2. Translate to idiomatic, well-structured Python (one cohesive package/module set "
        "preserving the cross-module structure) and write the primary entrypoint module to "
        "/workspace/payroll.py (the orchestrator fetches exactly that path).\n"
        "3. DIFFERENTIAL ORACLE (ground truth = the ORIGINAL COBOL's REAL output):\n"
        "   - PRIMARY: src/sample/golden_io.json holds real GnuCOBOL outputs captured "
        "ahead of time. Use these as ground truth. Do NOT try to install a COBOL "
        "compiler; the diff must not depend on a live compile.\n"
        "   - LIVE REFRESH: install real GnuCOBOL WITHOUT root via micromamba + conda-forge "
        "(`micromamba create -p /workspace/cobol -c conda-forge gnucobol`) or use `cobc` if "
        "present, then compile + run the ORIGINAL COBOL system over the battery to confirm "
        "golden_io.json is fresh — but the equivalence check stays byte-for-byte.\n"
        "4. Generate equivalence tests asserting python_output == golden_cobol_output "
        "byte-for-byte; run pytest.\n"
        "5. On failure, diagnose the TRUE idiom from the byte diff and write "
        ".agents/skills/<idiom>/SKILL.md teaching yourself how to handle it, commit it, and "
        "report the path you wrote. Common COBOL idioms across modules: numeric DISPLAY "
        "de-editing + `ROUNDED` round-half-UP (use Decimal.quantize(ROUND_HALF_UP), not "
        "Python round()), REDEFINES, OCCURS DEPENDING ON, sign overpunch, shared COPY "
        "layouts. Name the skill for the real idiom.\n"
        "6. EMIT MACHINE-READABLE MARKERS for the live UI. These are REQUIRED, one per "
        "line, with the EXACT prefix, as plain text in your output (not inside a code "
        "cell). The UI parses these prefixes verbatim:\n"
        "   - For EACH recovered rule (emit at least 3, including the CROSS-MODULE ones): "
        "`LAZARUS_RULE: {\"title\":..., \"plain\":..., \"cobol_ref\":..., "
        "\"severity\":\"rule|edge_case|gotcha\"}`\n"
        "   - After running the oracle, exactly ONE line: `LAZARUS_ORACLE_JSON: "
        "[{\"input\":..., \"cobol\":..., \"python\":..., \"match\":true|false}, ...]` "
        "covering EVERY golden input.\n"
        "   - As your FINAL step, print the COMPLETE final payroll.py exactly once, on the "
        "line `LAZARUS_MODULE:` immediately followed by a single fenced ```python block "
        "containing the WHOLE entrypoint module verbatim (the same bytes you wrote to "
        "/workspace/payroll.py) — no elisions, no '...'.\n"
        "Emit the markers even on a failing iteration (the UI shows RED then GREEN). "
        "When done, state clearly whether all equivalence tests PASS.\n"
        f"Stop when tests pass or after {MAX_ITERATIONS} iterations.\n\n"
        f"COBOL CODEBASE:\n{_render_modules(modules)}"
    )


def _build_forge_retry_prompt(skill_path: str, *, ground: bool = False) -> str:
    """Follow-up prompt for the FORGE retry turn (SAFE re-read pattern).

    The forged SKILL.md persists on disk in the reused environment, but we do NOT
    assume it has been auto-reloaded into the agent's instruction context. So we
    explicitly tell the agent to re-read it (and the rest of .agents/skills/) before
    re-attempting the translation.

    When grounding is on, prepend the research preamble so a DIFFERENT unknown idiom
    surfacing on the retry is researched-then-forged, never guessed.
    """
    preamble = _GROUNDING_PREAMBLE if ground else ""
    return preamble + (
        "Your previous attempt failed on an unknown COBOL idiom and you forged a new "
        f"skill at {skill_path}.\n"
        "That file is on disk in this SAME environment, but it is NOT yet loaded into "
        "your instructions. Before retrying:\n"
        f"1. Re-read {skill_path} (e.g. `cat {skill_path}`), and also re-scan "
        ".agents/skills/ for any other skills you have authored.\n"
        "2. Apply the technique from that skill to fix the Python translation.\n"
        "3. Re-run the differential oracle + pytest and report whether all equivalence "
        "tests now PASS.\n"
        "If a DIFFERENT unknown idiom appears, forge another "
        ".agents/skills/<idiom>/SKILL.md and report its path."
    )


def _model_output_text(step) -> str:
    """Pull text from a model_output step's content (verified shape §8:
    model_output -> {type, content:[{type:"text", text}]})."""
    if getattr(step, "type", None) != "model_output":
        return ""
    return "".join(
        part.text
        for part in (getattr(step, "content", None) or [])
        if getattr(part, "type", None) == "text"
    )


def _tool_breadcrumb(step) -> str | None:
    """Human one-liner for a tool step, or None if the step carries no tool detail.

    DEFENSIVE (the agent runtime's exact step shape for tool calls is not fully verified
    from a dev box): we read the documented Managed-Agents shapes
    (web/STREAM_CONTRACT.md adapter table) but tolerate anything missing —
      * code_execution_call   -> `$ <arguments.code>` (the command/code the agent ran),
      * code_execution_result -> a short status line (`✗ error` / `✓ ok`) + any result text,
      * google_search_call    -> `🔎 <q1; q2>` (arguments.QUERIES is a List[str], plural),
      * google_search_result  -> `🔎 ✓ <N results>` (result is a List[GoogleSearchResult]),
      * url_context_call      -> `🌐 <u1; u2>` (arguments.URLS is a List[str], plural),
      * url_context_result    -> `🌐 ✓ <url (status)>` (result is a List[URLContextResult]),
      * thought               -> `💭 <summary>` (a thinking-summary block, Feature 2).
    The field names are the REAL installed-SDK shapes (google.genai._interactions.types:
    GoogleSearchCallArguments.queries / URLContextCallArguments.urls / GoogleSearchResult.
    search_suggestions / URLContextResult.status+url) — NOT singular .query/.url, which a
    real grounding call never sets (that bug rendered nothing for genuine grounding).
    The grounding/thought breadcrumbs make web-grounding + thinking PROVABLE in the live
    trace (they only ever appear when those opt-in capabilities are exercised).
    Returns None when the step isn't a tool step or exposes no usable detail, so the caller
    simply emits nothing — breadcrumbs are a live-UX bonus, never required. These breadcrumbs
    feed phase_for_text (server side) so the rail lights recover/translate/oracle/test off
    real tool activity (`cobc`, `pytest`, `payroll.py`) instead of only end-block prose.
    """
    stype = getattr(step, "type", None)
    if stype is None and isinstance(step, dict):
        stype = step.get("type")   # tolerate a raw-dict step (defensive; SDK normally types it)
    if stype == "code_execution_call":
        args = getattr(step, "arguments", None)
        code = getattr(args, "code", None) if args is not None else None
        if not code and isinstance(args, dict):
            code = args.get("code")
        if code:
            first = code.strip().splitlines()[0][:200] if code.strip() else ""
            return f"$ {first}" if first else None
        return None
    if stype == "code_execution_result":
        is_error = bool(getattr(step, "is_error", False))
        result = getattr(step, "result", None)
        snippet = ""
        if isinstance(result, str) and result.strip():
            snippet = " " + result.strip().splitlines()[-1][:160]
        mark = "✗ error" if is_error else "✓ ok"
        return f"{mark}{snippet}".rstrip() or None
    if stype == "google_search_call":
        queries = _as_str_list(_step_field(step, "arguments", "queries"))
        return f"🔎 {'; '.join(queries)[:200]}" if queries else "🔎 (search)"
    if stype == "google_search_result":
        results = _as_list(_step_field(step, "result"))
        n = len(results)
        return f"🔎 ✓ {n} result{'s' if n != 1 else ''}" if n else "🔎 ✓"
    if stype == "url_context_call":
        urls = _as_str_list(_step_field(step, "arguments", "urls"))
        return f"🌐 {'; '.join(urls)[:200]}" if urls else "🌐 (fetch)"
    if stype == "url_context_result":
        return _url_context_result_crumb(step)
    if stype == "thought":
        summary = _thought_summary_text(step)
        return f"💭 {summary[:200]}" if summary else None
    return None


def _step_field(step, *path):
    """Read a (possibly nested) attr/dict field off a step, tolerating either shape.

    e.g. _step_field(step, "arguments", "queries") reads step.arguments.queries, or
    step.arguments["queries"] — returning None on any miss. Lets the grounding breadcrumbs
    work whether the SDK surfaces typed objects or raw dicts.
    """
    obj = step
    for key in path:
        if obj is None:
            return None
        nxt = getattr(obj, key, None)
        if nxt is None and isinstance(obj, dict):
            nxt = obj.get(key)
        obj = nxt
    return obj


def _as_list(val):
    """Normalize a value into a list (SDK result fields are List[...]); None/scalar -> []/[v]."""
    if val is None:
        return []
    if isinstance(val, (list, tuple)):
        return list(val)
    return [val]


def _as_str_list(val) -> list[str]:
    """A list of non-empty stripped strings from a List[str] field (queries/urls)."""
    return [s.strip() for s in (str(x) for x in _as_list(val)) if s.strip()]


def _url_context_result_crumb(step) -> str:
    """`🌐 ✓ <url> (<status>); …` from a url_context_result step.

    result is a List[URLContextResult] where each item carries .url + .status (the real
    SDK shape). Best-effort: shows the first couple of fetched URLs + their status.
    """
    results = _as_list(_step_field(step, "result"))
    if not results:
        return "🌐 ✓"
    parts = []
    for item in results[:2]:
        url = _step_field(item, "url")
        status = _step_field(item, "status")
        if url and status:
            parts.append(f"{str(url).strip()} ({str(status).strip()})")
        elif url:
            parts.append(str(url).strip())
    detail = "; ".join(parts)
    return f"🌐 ✓ {detail}"[:200] if detail else f"🌐 ✓ {len(results)} fetched"


def _thought_tokens(interaction) -> int | None:
    """usage.total_thought_tokens off a (completed) interaction, or None if absent.

    The data model exposes usage.total_thought_tokens (gemini-interactions-api skill); we
    read it best-effort (attr OR dict) so a positive value PROVES thinking ran, and a
    missing field never errors.
    """
    usage = getattr(interaction, "usage", None)
    if usage is None and isinstance(interaction, dict):
        usage = interaction.get("usage")
    if usage is None:
        return None
    tok = getattr(usage, "total_thought_tokens", None)
    if tok is None and isinstance(usage, dict):
        tok = usage.get("total_thought_tokens")
    try:
        return int(tok) if tok else None
    except (TypeError, ValueError):
        return None


def _thought_summary_text(step) -> str:
    """Join the text parts of a `thought` step's summary (verified §8 shape:
    thought -> {type, summary:[{type:"text", text}], signature}). Best-effort."""
    summary = getattr(step, "summary", None)
    if summary is None and isinstance(step, dict):
        summary = step.get("summary")
    parts = []
    for part in (summary or []):
        text = getattr(part, "text", None)
        if text is None and isinstance(part, dict):
            text = part.get("text")
        if text:
            parts.append(text)
    return " ".join(parts).strip()


def extract_output_text(interaction, client: genai.Client | None = None) -> str:
    """Return the agent's terminal model output text.

    Resolution order (live-path safe — the completed event ships EMPTY outputs):
      1. text accumulated from the stream during _run_interaction (the live trace),
      2. the interaction object's own model_output steps (a fetched/non-streaming object),
      3. an authoritative client.interactions.get(id) fetch, when a client is available
         and nothing above produced text (the completed event was empty + no deltas).
    `output_text` is intentionally NOT trusted as the primary source (not a documented
    field below SDK 2.3.0; empty on the completed event).
    """
    streamed = getattr(interaction, "_lazarus_output_text", None)
    if streamed:
        return streamed

    from_steps = "".join(
        _model_output_text(step) for step in (getattr(interaction, "steps", None) or [])
    )
    if from_steps:
        return from_steps

    fetch_client = client or getattr(interaction, "_lazarus_client", None)
    itx_id = getattr(interaction, "id", None)
    if fetch_client is not None and itx_id is not None \
            and hasattr(fetch_client, "interactions") \
            and hasattr(fetch_client.interactions, "get"):
        try:
            fetched = fetch_client.interactions.get(itx_id)
            return "".join(
                _model_output_text(s) for s in (getattr(fetched, "steps", None) or [])
            )
        except Exception:
            return ""
    return ""


def extract_environment_id(interaction) -> str | None:
    """The env id to reuse on the next turn (carries files + forged skills)."""
    return getattr(interaction, "environment_id", None)


def _tests_passed(output_text: str) -> bool:
    # A clear failure signal vetoes a pass (e.g. "2 failed", "not equivalent").
    if _FAIL_RE.search(output_text):
        return False
    return bool(_PASS_RE.search(output_text))


def _forged_skill_path(output_text: str) -> str | None:
    m = _FORGE_RE.search(output_text)
    return m.group(1) if m else None


# A forged skill's body, if the agent echoed it in a fenced block right after announcing the
# path (so we can BANK it locally). Tolerant: matches ```...``` (any/no language tag).
_SKILL_BODY_RE = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.S)


def _persist_forged_skill(name: str, content: str) -> pathlib.Path | None:
    """Bank a forged SKILL.md into the repo at .agents/skills/<name>/SKILL.md (Feature 3).

    This is what turns a session-scoped forge into a CROSS-RUN skill: once on disk here,
    ensure_agent() mounts it into base_environment on the next FRESH invocation (and the
    changed fingerprint triggers a re-register). `name` is sanitized to a safe dir slug.
    Returns the written path, or None on a bad name / write error (best-effort — banking a
    skill must never crash a migration).
    """
    slug = re.sub(r"[^\w\-]+", "-", (name or "").strip().lower()).strip("-")
    if not slug or not (content or "").strip():
        return None
    try:
        dest = AGENTS_DIR / "skills" / slug / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
        return dest
    except OSError:
        return None


def _bank_forged_skill_from_output(skill_path: str, output_text: str) -> pathlib.Path | None:
    """If the agent echoed the forged SKILL.md body in `output_text`, bank it locally.

    `skill_path` is the announced path (…/skills/<name>/SKILL.md); we derive <name> from it
    and pull the skill body from the first fenced block following the path mention. No body
    found -> None (we never invent skill content). Best-effort; cross-run banking is a bonus.
    """
    name = pathlib.PurePosixPath(skill_path).parent.name
    tail = output_text[output_text.find(skill_path) + len(skill_path):]
    m = _SKILL_BODY_RE.search(tail)
    if not m:
        return None
    return _persist_forged_skill(name, m.group(1).rstrip("\n") + "\n")


def _looks_like_thinking_rejection(exc: Exception) -> bool:
    """Heuristic: did this error come from sending the agent-path thinking config?

    qa LIVE-PROVED the managed-agent runtime rejects every thinking config shape (400):
    a top-level generation_config -> "use agent_config"; generation_config in extra_body ->
    "Unknown parameter". We now send the SDK-correct agent_config={"type":"dynamic",
    "thinking_level": …}; if THAT is also rejected we still want a graceful no-op. We can't
    rely on a specific exception type from a dev box, so we match the message defensively and
    treat a thinking-shaped error as "retry without it" — the retry re-raises if it ALSO
    fails, so a genuine unrelated error still surfaces (it won't recur once we drop
    agent_config).
    """
    msg = str(exc).lower()
    return any(k in msg for k in (
        "thinking", "agent_config", "agentconfig", "generation_config", "generationconfig",
        "unknown field", "unknown parameter", "unexpected", "invalid argument",
        "not supported", "unsupported",
    ))


def _thinking_agent_config(level: str) -> dict:
    """The agent-path thinking config the SDK actually accepts (Feature 2).

    SOURCE OF TRUTH = the installed SDK types (google.genai._interactions.types), NOT the
    generate_content shape:
      * The AGENT interaction params (BaseCreateAgentInteractionParams) expose `agent_config`,
        NOT `generation_config` (which is MODEL-path only). A top-level generation_config
        kwarg is rejected ("use agent_config"); generation_config in extra_body is rejected
        ("Unknown parameter"). qa confirmed both live.
      * `thinking_level` is a FLAT key (interactions GenerationConfigParam.thinking_level —
        there is NO nested thinking_config in the interactions types), a lowercase Literal
        ['minimal','low','medium','high'] matching our env values directly.
      * DynamicAgentConfigParam requires {"type": "dynamic"} and allows extra items
        (TypedDict total=False, extra_items=object), so the flat thinking_level rides on it.
    """
    return {"type": "dynamic", "thinking_level": level}


def _create_interaction_stream(client: genai.Client, *, input_text: str, environment):
    """interactions.create(stream=True), optionally with an interaction-scoped thinking
    level (Feature 2). DEFAULT (LAZARUS_THINKING unset / medium): sends NO agent_config —
    byte-identical to the shipped call. When a non-default level IS configured we attach the
    SDK-correct agent-path shape agent_config={"type":"dynamic","thinking_level": <lvl>}
    (flat thinking_level, NOT generation_config — see _thinking_agent_config). If the agent
    runtime rejects it (graceful no-op — qa proved it does, 400), we set THINKING_REJECTED
    and retry WITHOUT it so the run still completes. Returns the stream iterator.
    """
    base_kwargs = dict(
        agent=AGENT_ID,
        input=input_text,
        stream=True,
        extra_body={"environment": environment},   # env via extra_body (verified surface)
    )
    level = _thinking_level()
    if level is None:
        return client.interactions.create(**base_kwargs)

    # Opt-in: request the thinking level via the agent-path agent_config (flat thinking_level).
    thinking_kwargs = dict(base_kwargs)
    thinking_kwargs["agent_config"] = _thinking_agent_config(level)
    try:
        stream = client.interactions.create(**thinking_kwargs)
        emit_to_ui(f"[thinking_level={level}]\n")
        return stream
    except Exception as exc:
        if not _looks_like_thinking_rejection(exc):
            raise  # an unrelated failure — don't swallow it behind the thinking flag
        global THINKING_REJECTED
        THINKING_REJECTED = True
        emit_to_ui(
            "[thinking_level rejected by the managed-agent runtime — proceeding without it "
            f"(requested {level})]\n"
        )
        return client.interactions.create(**base_kwargs)


def _run_interaction(client: genai.Client, *, input_text: str, environment):
    """One streamed interaction. Forwards step.delta text to the UI and accumulates the
    model output FROM THE STREAM.

    LIVE-PATH NOTE (verified, findings-agents.md): the `interaction.completed` event ships
    `event.interaction` "with empty outputs to reduce the payload size" — its .steps /
    output_text are EMPTY on the real API. So we (1) accumulate text from step.delta /
    step.stop during the stream (the live trace), and (2) after the stream, fetch the
    AUTHORITATIVE final object via client.interactions.get(interaction_id). We return that
    fetched object (carrying real .steps + .environment_id), with the streamed text
    attached as `_lazarus_output_text` and the client attached so extract_output_text can
    do a get() fallback if needed.
    """
    stream = _create_interaction_stream(
        client, input_text=input_text, environment=environment
    )

    completed = None
    interaction_id = None
    env_id = None
    output_parts: list[str] = []
    for event in stream:
        # Every event carries interaction_id (resume/fetch token).
        interaction_id = getattr(event, "interaction_id", None) or interaction_id
        et = getattr(event, "event_type", None)
        if et == "step.delta":
            text = getattr(getattr(event, "delta", None), "text", None)
            if text:
                emit_to_ui(text)
                output_parts.append(text)
        elif et in ("step.start", "step.stop"):
            step = getattr(event, "step", None)
            # ACTIVITY BREADCRUMB (defensive): if this is a tool step (code execution),
            # forward a one-line breadcrumb so the live UI shows real activity during the
            # silent multi-minute tool stretches (conda/compile/pytest) and the phase rail
            # advances off it. No-op when the step carries no tool detail.
            crumb = _tool_breadcrumb(step)
            if crumb:
                emit_to_ui(crumb + "\n")
            if et == "step.stop":
                # Terminal text of a completed step (verified §8 carries the full Step here).
                output_parts.append(_model_output_text(step))
        elif et == "interaction.completed":
            completed = getattr(event, "interaction", None)
            # env id is still present on the (otherwise-empty) completed interaction.
            env_id = extract_environment_id(completed) or env_id
            interaction_id = getattr(completed, "id", None) or interaction_id
            # Surface thinking token usage (Feature 2) if the runtime reports it — proves
            # the thinking config actually took effect. No-op when usage/field is absent.
            tok = _thought_tokens(completed)
            if tok:
                emit_to_ui(f"[thought_tokens={tok}]\n")

    # Authoritative final fetch: the completed event's payload is empty, so re-fetch the
    # full interaction object when we can. Fall back to the completed event if get() fails.
    final = completed
    if interaction_id is not None and hasattr(client, "interactions") \
            and hasattr(client.interactions, "get"):
        try:
            fetched = client.interactions.get(interaction_id)
            if fetched is not None:
                final = fetched
        except Exception:
            pass  # network/SDK hiccup -> use the completed event + streamed text

    if final is not None:
        accumulated = "".join(output_parts)
        if not accumulated:  # nothing streamed -> use the fetched object's steps
            accumulated = "".join(
                _model_output_text(s) for s in (getattr(final, "steps", None) or [])
            )
        try:
            final._lazarus_output_text = accumulated
            final._lazarus_client = client
        except (AttributeError, TypeError):
            pass  # immutable object; extract_output_text(client=) can still fetch
        # Make sure env id survives even if the fetched object lacks it.
        if env_id and not extract_environment_id(final):
            try:
                final.environment_id = env_id
            except (AttributeError, TypeError):
                pass
    return final


def _normalize_cobol_paths(cobol_path, cobol_paths) -> list[str]:
    """Resolve migrate()'s single-or-multi inputs into an ordered list of paths.

    Accepts the single-file positional (str or pathlib.Path), a list passed positionally,
    or the cobol_paths= keyword (Feature 4). Exactly one source must be given.
    """
    if cobol_paths is not None and cobol_path is not None:
        raise ValueError("pass either cobol_path or cobol_paths, not both")
    src = cobol_paths if cobol_paths is not None else cobol_path
    if src is None:
        raise ValueError("migrate() requires a COBOL path (or list of paths)")
    if isinstance(src, (str, pathlib.Path)):
        return [str(src)]
    paths = [str(p) for p in src]
    if not paths:
        raise ValueError("migrate() got an empty file list")
    return paths


def migrate(client: genai.Client, cobol_path=None, *, cobol_paths=None):
    """Run the write -> run -> prove -> self-heal loop, streaming steps to the UI.

    Single-file (default, UNCHANGED): migrate(client, "path.cob") reads that one module and
    uses the byte-identical _build_prompt. Whole-codebase (Feature 4): pass cobol_paths=[...]
    (or a list positionally) to ingest MULTIPLE COBOL files + copybooks at once and recover
    CROSS-MODULE business rules via _build_multi_prompt.

    The MAX_ITERATIONS cap is ENFORCED here in code (C10): a real per-turn counter is
    emitted to the UI via emit_iteration() and the loop hard-stops at MAX_ITERATIONS —
    the prompt text is only a hint, never the safety net (an infinite loop on stage is
    death). State threads across forge->retry turns via environment_id. Returns the
    final completed interaction (carries .id, .environment_id, .steps).
    """
    paths = _normalize_cobol_paths(cobol_path, cobol_paths)
    interaction = None
    ground = _grounding_enabled()   # opt-in web-grounding (Feature 1); default off

    # Single file -> the byte-identical shipped prompt. Multiple -> the cross-module prompt.
    if len(paths) == 1:
        first_prompt = _build_prompt(pathlib.Path(paths[0]).read_text(), ground=ground)
    else:
        modules = [(pathlib.Path(p).name, pathlib.Path(p).read_text()) for p in paths]
        first_prompt = _build_multi_prompt(modules, ground=ground)

    for iteration in range(1, MAX_ITERATIONS + 1):
        emit_iteration(iteration, MAX_ITERATIONS)   # visible counter (UI renders this)

        if iteration == 1:
            interaction = _run_interaction(
                client, input_text=first_prompt, environment="remote"
            )
        else:
            # Reuse the SAME environment so the forged SKILL.md is on disk, and explicitly
            # instruct the agent to re-read it (SAFE pattern; no silent auto-reload).
            interaction = _run_interaction(
                client,
                input_text=_build_forge_retry_prompt(_pending_skill_path, ground=ground),
                environment=extract_environment_id(interaction),
            )

        output = extract_output_text(interaction)
        if _tests_passed(output):
            break
        _pending_skill_path = _forged_skill_path(output)
        if not _pending_skill_path:
            # Failed but no new skill was forged -> nothing new to re-read; stop early.
            break
        # CROSS-RUN banking (Feature 3): if the agent echoed the forged SKILL.md body, write
        # it into this repo's .agents/skills/ so a FUTURE fresh invocation inherits it (via
        # ensure_agent mounting it + the changed fingerprint re-registering the agent). The
        # SAME-environment re-read below is unchanged; banking is an ADDITIONAL durable copy.
        _bank_forged_skill_from_output(_pending_skill_path, output)

    return interaction


def emit_to_ui(text: str) -> None:
    """Forward streamed text/steps to the front-end live trace. Wire to SSE/WebSocket."""
    print(text, end="", flush=True)


def emit_iteration(current: int, total: int) -> None:
    """Surface the enforced iteration counter to the UI (C10's visible counter).

    Called once per loop turn before the interaction runs. Wire to the same SSE/
    WebSocket channel so the front-end can render e.g. "Iteration 2 / 4".
    """
    print(f"\n[iteration {current}/{total}]", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="src/sample/payroll.cob")
    args = ap.parse_args()

    client = genai.Client()  # reads GEMINI_API_KEY
    ensure_agent(client)
    result = migrate(client, args.input)

    # Persist the environment id so follow-up turns reuse the same sandbox + forged skills:
    env_id = extract_environment_id(result)
    itx_id = getattr(result, "id", None)
    print(f"\n[done] environment_id={env_id} interaction_id={itx_id}")


if __name__ == "__main__":
    main()
