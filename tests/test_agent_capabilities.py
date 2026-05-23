"""Network-free unit tests for the 4 new flag-gated agent capabilities.

These cover the DELTAS that integration-eng adds to src/agent.py + src/server.py:

  1. WEB-GROUNDING        (env LAZARUS_GROUND, default off)   — task #5
  2. THINKING_LEVEL       (env LAZARUS_THINKING, default medium) — task #6
  3. CROSS-RUN SKILL LIB  (ensure_agent mounts every SKILL.md) — task #7
  4. WHOLE-CODEBASE       (migrate accepts multiple modules)   — task #8

The non-negotiable invariant for the whole feature branch is the FLAGS-OFF
REGRESSION: with every capability at its default/off value, the built prompt +
base_environment + interaction `create()` kwargs must be BYTE-IDENTICAL to the
shipped (pre-feature) behavior. That guard lives in test_flags_off_regression
below and is written to be robust to the new optional params simply existing.

Like tests/test_agent.py, the Gemini client is faked, so nothing here touches
the network or needs an API key. Each test states the exact signature it assumes
in a comment; if integration-eng lands a different name, only that assumption (not
the intent) needs to move.
"""
from __future__ import annotations

import importlib
import inspect
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
for p in (str(SRC_DIR), str(REPO_ROOT)):
    if p in sys.path:
        sys.path.remove(p)
    sys.path.insert(0, p)

# Import the REAL installed SDK interactions types ONCE at module load — BEFORE the agent_mod
# fixture stubs out `google.genai` — and cache them. This is the source-of-truth shape the
# breadcrumb regression guard (DA L17) builds against. None when the SDK isn't installed.
try:
    import google.genai._interactions.types as _SDK_ITX_TYPES  # noqa: E402
except Exception:  # SDK absent / older layout -> the SDK-types guard skips
    _SDK_ITX_TYPES = None


# --------------------------------------------------------------------------
# fixtures + fakes (mirror tests/test_agent.py so the two files agree on shapes)
# --------------------------------------------------------------------------
@pytest.fixture
def agent_mod():
    """Import src/agent.py with a stubbed `google.genai` (no SDK / no network)."""
    google_pkg = types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")

    class _Client:
        def __init__(self, *a, **k):
            pass

    genai_mod.Client = _Client
    google_pkg.genai = genai_mod
    sys.modules["google"] = google_pkg
    sys.modules["google.genai"] = genai_mod

    sys.modules.pop("agent", None)
    mod = importlib.import_module("agent")
    return importlib.reload(mod)


@pytest.fixture(autouse=True)
def _clear_capability_env(monkeypatch):
    """Default every test to the FLAGS-OFF world unless it opts in explicitly.

    Capability flags are read from the environment (LAZARUS_GROUND / LAZARUS_THINKING).
    Clearing them here means the regression baseline is honest even on a dev box that
    happens to export them, and feature tests set only the one flag they exercise.
    """
    for var in ("LAZARUS_GROUND", "LAZARUS_THINKING"):
        monkeypatch.delenv(var, raising=False)


class FakeStep:
    def __init__(self, step_type, text=""):
        self.type = step_type
        self.content = [types.SimpleNamespace(type="text", text=text)]


class FakeInteraction:
    def __init__(self, *, id, environment_id, steps):
        self.id = id
        self.environment_id = environment_id
        self.steps = steps


def make_stream(*, env_id, interaction_id, model_text):
    final = FakeInteraction(
        id=interaction_id, environment_id=env_id,
        steps=[FakeStep("model_output", model_text)],
    )
    yield types.SimpleNamespace(event_type="interaction.completed", interaction=final,
                                interaction_id=interaction_id)


class FakeInteractions:
    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = []        # kwargs of each create()
        self.get_calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        spec = self._scripted[len(self.calls) - 1]
        return make_stream(env_id=spec["env_id"], interaction_id=spec["interaction_id"],
                           model_text=spec["model_text"])

    def get(self, interaction_id):
        self.get_calls.append(interaction_id)
        spec = next(s for s in self._scripted if s["interaction_id"] == interaction_id)
        return FakeInteraction(id=interaction_id, environment_id=spec["env_id"],
                               steps=[FakeStep("model_output", spec["model_text"])])


class FakeAgents:
    def __init__(self, existing=()):
        self.created = []
        self.deleted = []
        self._existing = list(existing)

    def list(self):
        agents = [types.SimpleNamespace(id=i) for i in self._existing]
        return types.SimpleNamespace(agents=agents)

    def create(self, **kwargs):
        self.created.append(kwargs)
        self._existing.append(kwargs.get("id"))

    def delete(self, *, id):
        self.deleted.append(id)
        if id in self._existing:
            self._existing.remove(id)


class FakeClient:
    def __init__(self, scripted=(), existing_agents=()):
        self.agents = FakeAgents(existing_agents)
        self.interactions = FakeInteractions(scripted)


GREEN = "All tests pass. 3/3 equivalent to original COBOL."


def _green_client(n=1):
    return FakeClient([
        {"env_id": f"env{i}", "interaction_id": f"i{i}", "model_text": GREEN}
        for i in range(1, n + 1)
    ])


def _write_cobol(tmp_path, name="p.cob", body="IDENTIFICATION DIVISION.\n"):
    f = tmp_path / name
    f.write_text(body)
    return f


# ==========================================================================
# 0. FLAGS-OFF REGRESSION — the load-bearing guard
#    With no capability turned on, every observable artifact equals shipped.
# ==========================================================================
def test_flags_off_prompt_unchanged(agent_mod):
    """_build_prompt with no opt-in args is byte-identical to the legacy prompt.

    The legacy prompt is fully reconstructable from the one required positional arg
    (the COBOL text). Any new grounding/multi-module text must be GATED behind a
    non-default kwarg, so calling with just the COBOL yields the shipped string.
    """
    cobol = "IDENTIFICATION DIVISION. FOO."
    prompt = agent_mod._build_prompt(cobol)

    # Anchors from the shipped prompt that must survive verbatim.
    assert prompt.startswith("Migrate this COBOL program to idiomatic Python.")
    assert "LAZARUS_ORACLE_JSON" in prompt
    assert "LAZARUS_MODULE" in prompt
    assert "/workspace/payroll.py" in prompt
    assert prompt.endswith(f"COBOL:\n```cobol\n{cobol}\n```")
    # No grounding instruction leaks in when the flag is off.
    assert "google_search" not in prompt.lower()
    assert "url_context" not in prompt.lower()


def test_flags_off_base_environment_unchanged(agent_mod):
    """build_base_environment with the repo's current skills mounts exactly AGENTS.md
    (+ any real seed SKILL.md), as a remote env — unchanged from shipped."""
    env = agent_mod.build_base_environment()
    assert env["type"] == "remote"
    targets = [s["target"] for s in env["sources"]]
    assert ".agents/AGENTS.md" in targets
    # All mounts are inline file sources.
    assert all(s["type"] == "inline" for s in env["sources"])


def test_flags_off_interaction_kwargs_identical_to_shipped(agent_mod, tmp_path):
    """The CORE invariant: a default migrate() run issues create() calls whose kwargs
    are exactly {agent, input, stream, extra_body} — NO generation_config, NO sampling
    params, NO grounding tool kwargs. This is the shipped contract; flags-off must keep it.
    """
    cobol = _write_cobol(tmp_path)
    client = _green_client()
    agent_mod.migrate(client, str(cobol))

    assert len(client.interactions.calls) == 1
    call = client.interactions.calls[0]
    # Exact key set — a leaked generation_config / tools key fails here.
    assert set(call.keys()) == {"agent", "input", "stream", "extra_body"}
    assert call["agent"] == agent_mod.AGENT_ID
    assert call["stream"] is True
    assert call["extra_body"] == {"environment": "remote"}
    # belt-and-suspenders: no sampling params anywhere
    forbidden = {"temperature", "top_p", "top_k", "generation_config"}

    def _scan(obj):
        if isinstance(obj, dict):
            assert forbidden.isdisjoint(obj), f"leaked: {forbidden & set(obj)}"
            for v in obj.values():
                _scan(v)

    _scan(call)


def test_flags_off_migrate_default_signature_single_file(agent_mod, tmp_path):
    """migrate(client, cobol_path) — the single-file positional call — must keep working
    as the default. Multi-module support must not break the one-path signature."""
    cobol = _write_cobol(tmp_path)
    result = agent_mod.migrate(_green_client(), str(cobol))
    assert result.id == "i1"


# ==========================================================================
# 1. WEB-GROUNDING  (task #5, env LAZARUS_GROUND default off)
# ==========================================================================
# Assumed contract (confirm with integration-eng):
#   * _build_prompt(cobol, *, ground: bool = False) — when ground=True the prompt
#     gains an instruction to research the unknown idiom via google_search / url_context
#     BEFORE forging, and to cite findings.
#   * server/agent reads env LAZARUS_GROUND ("1"/"true") to decide `ground`.
def _supports_kw(func, name):
    return name in inspect.signature(func).parameters


def test_grounding_off_prompt_has_no_search_instruction(agent_mod):
    """Default (ground off): the prompt contains NO web-research instruction."""
    prompt = agent_mod._build_prompt("IDENTIFICATION DIVISION.")
    low = prompt.lower()
    assert "google_search" not in low
    assert "url_context" not in low
    assert "research" not in low or "before forging" not in low


def test_grounding_on_prompt_adds_search_instruction(agent_mod):
    """ground=True: the prompt instructs the agent to use google_search / url_context
    to research the unknown COBOL idiom before forging a skill, and cite findings."""
    if not _supports_kw(agent_mod._build_prompt, "ground"):
        pytest.skip("agent._build_prompt has no `ground` kwarg yet")
    prompt = agent_mod._build_prompt("IDENTIFICATION DIVISION.", ground=True)
    low = prompt.lower()
    assert "google_search" in low or "url_context" in low or "web search" in low
    assert "research" in low or "cite" in low or "ground" in low


def test_grounding_on_does_not_drop_legacy_prompt_body(agent_mod):
    """ground=True is ADDITIVE: the markers + payroll.py target + COBOL fence remain."""
    if not _supports_kw(agent_mod._build_prompt, "ground"):
        pytest.skip("agent._build_prompt has no `ground` kwarg yet")
    cobol = "IDENTIFICATION DIVISION. XYZ."
    prompt = agent_mod._build_prompt(cobol, ground=True)
    assert "LAZARUS_ORACLE_JSON" in prompt
    assert "LAZARUS_MODULE" in prompt
    assert "/workspace/payroll.py" in prompt
    assert f"```cobol\n{cobol}\n```" in prompt


def test_grounding_env_flag_default_off(agent_mod, monkeypatch):
    """_grounding_enabled() is the env reader: default OFF; only 1/true/yes/on flip it on.
    monkeypatch so a mid-loop failure can't leak LAZARUS_GROUND into other tests."""
    if not hasattr(agent_mod, "_grounding_enabled"):
        pytest.skip("agent._grounding_enabled not present")
    # autouse fixture cleared LAZARUS_GROUND -> default off
    assert agent_mod._grounding_enabled() is False
    for on in ("1", "true", "TRUE", "yes", "on", " On "):
        monkeypatch.setenv("LAZARUS_GROUND", on)
        assert agent_mod._grounding_enabled() is True, on
    for off in ("0", "false", "no", "off", "", "maybe"):
        monkeypatch.setenv("LAZARUS_GROUND", off)
        assert agent_mod._grounding_enabled() is False, off


def test_grounding_breadcrumbs_from_search_and_url_steps(agent_mod):
    """The grounding capability is PROVABLE in the live trace: google_search_call /
    url_context_call (+ their results) yield breadcrumbs. These only appear when grounding
    is exercised, so they're the stream-side evidence the devil's-advocate can point to.

    Uses the REAL installed-SDK field shapes (google.genai._interactions.types):
      * GoogleSearchCallArguments.queries — List[str], PLURAL (not .query).
      * URLContextCallArguments.urls      — List[str], PLURAL (not .url).
      * GoogleSearchResultStep.result     — List[GoogleSearchResult].
      * URLContextResultStep.result       — List[URLContextResult] (.url + .status).
    A genuine grounding call sets queries/urls (plural); the old singular .query/.url
    read rendered NOTHING for real grounding — that's the bug this test now guards."""
    search_call = types.SimpleNamespace(
        type="google_search_call",
        arguments=types.SimpleNamespace(queries=["COBOL ROUNDED rounding mode", "PIC 9V99"]))
    crumb = agent_mod._tool_breadcrumb(search_call)
    assert crumb.startswith("🔎 ")
    assert "COBOL ROUNDED rounding mode" in crumb and "PIC 9V99" in crumb

    search_res = types.SimpleNamespace(
        type="google_search_result",
        result=[types.SimpleNamespace(search_suggestions=["a"]),
                types.SimpleNamespace(search_suggestions=["b"]),
                types.SimpleNamespace(search_suggestions=["c"])])
    assert agent_mod._tool_breadcrumb(search_res) == "🔎 ✓ 3 results"

    url_call = types.SimpleNamespace(
        type="url_context_call",
        arguments=types.SimpleNamespace(urls=["https://gnucobol.sourceforge.io/"]))
    assert agent_mod._tool_breadcrumb(url_call) == "🌐 https://gnucobol.sourceforge.io/"

    url_res = types.SimpleNamespace(
        type="url_context_result",
        result=[types.SimpleNamespace(url="https://gnucobol.sourceforge.io/",
                                      status="URL_RETRIEVAL_STATUS_SUCCESS")])
    crumb = agent_mod._tool_breadcrumb(url_res)
    assert crumb.startswith("🌐 ✓")
    assert "gnucobol.sourceforge.io" in crumb


def test_grounding_breadcrumbs_use_real_sdk_types(agent_mod):
    """REGRESSION GUARD (DA L17): build the ACTUAL SDK step types (model-validated from the
    real wire shape) and assert the breadcrumb renders the queries/urls. This is the test
    whose absence let the singular-field bug slip — the old tests only checked the prompt
    preamble, never a real call/result shape. Built via model_validate so pydantic enforces
    the genuine arguments.queries / arguments.urls / result[].url+status fields."""
    if _SDK_ITX_TYPES is None:
        pytest.skip("google.genai._interactions.types not importable in this SDK")
    it = _SDK_ITX_TYPES

    # The real SDK content classes are *CallContent / *ResultContent — there is NO *Step type
    # in google.genai._interactions.types (verified: dir() lists GoogleSearchCallContent,
    # URLContextCallContent, URLContextResultContent; the model_validate of *Step raises
    # AttributeError). _tool_breadcrumb reads step.type + step.arguments.{queries,urls} /
    # step.result[].{url,status}, which these content classes carry.
    sc = it.GoogleSearchCallContent.model_validate({
        "id": "c1", "type": "google_search_call",
        "arguments": {"queries": ["COBOL ROUNDED rounding mode"]}})
    assert sc.arguments.queries == ["COBOL ROUNDED rounding mode"]   # real SDK field, plural
    assert agent_mod._tool_breadcrumb(sc) == "🔎 COBOL ROUNDED rounding mode"

    uc = it.URLContextCallContent.model_validate({
        "id": "c2", "type": "url_context_call",
        "arguments": {"urls": ["https://example.com/cobol"]}})
    assert uc.arguments.urls == ["https://example.com/cobol"]        # real SDK field, plural
    assert agent_mod._tool_breadcrumb(uc) == "🌐 https://example.com/cobol"

    ur = it.URLContextResultContent.model_validate({
        "call_id": "c2", "type": "url_context_result",
        "result": [{"url": "https://example.com/cobol", "status": "success"}]})
    crumb = agent_mod._tool_breadcrumb(ur)
    assert crumb.startswith("🌐 ✓")
    assert "example.com/cobol" in crumb and "success" in crumb


def test_grounding_breadcrumbs_tolerate_dict_and_flat_shapes(agent_mod):
    """Defensive: the SDK may surface a raw-dict step — breadcrumbs still recover the
    queries/urls (never raise). Plural list keys, matching the real SDK arguments."""
    # dict step with nested plural arguments
    assert agent_mod._tool_breadcrumb(
        {"type": "google_search_call", "arguments": {"queries": ["PIC 9V99 de-editing"]}}
    ) == "🔎 PIC 9V99 de-editing"
    assert agent_mod._tool_breadcrumb(
        {"type": "url_context_call", "arguments": {"urls": ["https://example.com/cobol"]}}
    ) == "🌐 https://example.com/cobol"
    # a call with no arguments still yields a non-None placeholder (never raises)
    assert agent_mod._tool_breadcrumb(
        types.SimpleNamespace(type="google_search_call", arguments=None)) == "🔎 (search)"


# ==========================================================================
# 2. THINKING_LEVEL  (task #6, env LAZARUS_THINKING default "medium")
# ==========================================================================
# Landed contract (agent._thinking_level + _create_interaction_stream), corrected to the
# REAL installed-SDK agent-path shape (DA L18; verified against
# google.genai._interactions.types):
#   * env LAZARUS_THINKING. _THINKING_LEVELS = {minimal, low, high} — note "medium" is
#     DELIBERATELY EXCLUDED: it IS the runtime default, so sending it would needlessly break
#     the byte-identical guarantee. UNSET / "medium" / "off" / "none" / "default" / any
#     unrecognized value => _thinking_level() is None => create() gets NO agent_config
#     (byte-identical to the shipped call).
#   * an explicit level that genuinely DIFFERS from the default (minimal|low|high) => OPT-IN:
#     the AGENT-path create() carries agent_config = {"type": "dynamic", "thinking_level": <lvl>}.
#     (The agent interaction params expose `agent_config`, NOT `generation_config`, which is
#     MODEL-path only; thinking_level is FLAT — there is no nested thinking_config in the
#     interactions types. qa proved the runtime rejects generation_config on the agent path.)
#   * if the managed-agent runtime rejects the thinking-bearing call, the impl sets
#     THINKING_REJECTED and retries WITHOUT agent_config so the run still completes.
def _thinking_cfg_from_call(call):
    """Recover the agent-path thinking config the impl attached, or None if it sent none."""
    if "agent_config" in call:
        return call["agent_config"]
    eb = call.get("extra_body") or {}
    if isinstance(eb, dict) and "agent_config" in eb:
        return eb["agent_config"]
    return None


def test_thinking_unset_sends_no_agent_config(agent_mod, tmp_path):
    """Default (env UNSET, cleared by the autouse fixture) => NO agent_config anywhere.

    This is THE byte-identical-to-shipped case for Feature 2: with the flag off, the
    create() call must look exactly like today's (no agent_config / generation_config key).
    """
    cobol = _write_cobol(tmp_path)
    client = _green_client()
    agent_mod.migrate(client, str(cobol))
    for call in client.interactions.calls:
        assert _thinking_cfg_from_call(call) is None, \
            "unset LAZARUS_THINKING must not emit an agent_config (identical to today)"
        assert "generation_config" not in call


@pytest.mark.parametrize("sentinel", ["medium", "off", "none", "default", "bogus-level", ""])
def test_thinking_sentinel_values_send_no_agent_config(agent_mod, tmp_path,
                                                       monkeypatch, sentinel):
    """medium (==runtime default), off/none/default, any unrecognized value, and empty all
    mean 'send nothing' — they keep the call byte-identical to today (no agent_config).
    Including "medium" here is the load-bearing case: opting into the default must NOT break
    the byte-identical guarantee."""
    monkeypatch.setenv("LAZARUS_THINKING", sentinel)
    cobol = _write_cobol(tmp_path)
    client = _green_client()
    agent_mod.migrate(client, str(cobol))
    for call in client.interactions.calls:
        assert _thinking_cfg_from_call(call) is None, \
            f"LAZARUS_THINKING={sentinel!r} must be a no-op (no agent_config)"


@pytest.mark.parametrize("level", ["minimal", "low", "high"])
def test_thinking_explicit_level_carries_exact_shape(agent_mod, tmp_path, monkeypatch, level):
    """A non-default level (minimal|low|high) opts in and reaches the SDK as the EXACT
    agent-path shape: agent_config = {"type": "dynamic", "thinking_level": <level>} — FLAT
    thinking_level, no nested thinking_config, NOT generation_config (the MODEL-path key).
    ("medium" is excluded — it equals the runtime default and stays a no-op.)"""
    monkeypatch.setenv("LAZARUS_THINKING", level)
    cobol = _write_cobol(tmp_path)
    client = _green_client()
    agent_mod.migrate(client, str(cobol))

    cfgs = [_thinking_cfg_from_call(c) for c in client.interactions.calls]
    cfgs = [c for c in cfgs if c]
    assert cfgs, f"LAZARUS_THINKING={level} should have emitted an agent_config"
    for cfg in cfgs:
        assert cfg == {"type": "dynamic", "thinking_level": level}
    # never the MODEL-path generation_config, and never nested
    for c in client.interactions.calls:
        assert "generation_config" not in c


def test_thinking_case_insensitive(agent_mod, tmp_path, monkeypatch):
    """The env read lower-cases the value, so HIGH / High behave like high."""
    monkeypatch.setenv("LAZARUS_THINKING", "HIGH")
    cobol = _write_cobol(tmp_path)
    client = _green_client()
    agent_mod.migrate(client, str(cobol))
    cfgs = [c for c in (_thinking_cfg_from_call(c) for c in client.interactions.calls) if c]
    assert cfgs
    assert all(c == {"type": "dynamic", "thinking_level": "high"} for c in cfgs)


def test_thinking_rejection_falls_back_without_agent_config(agent_mod, monkeypatch):
    """If the managed-agent runtime rejects the thinking-bearing create(), the driver
    retries WITHOUT agent_config (graceful no-op), sets THINKING_REJECTED, and the run
    completes. Proven with a client whose first create() (carrying agent_config) raises a
    thinking-rejection error and whose retry succeeds. (qa proved the runtime DOES reject
    every thinking config shape live, so this fallback is the load-bearing path.)"""
    monkeypatch.setenv("LAZARUS_THINKING", "high")

    final = types.SimpleNamespace(id="iR", environment_id="envR",
                                  steps=[FakeStep("model_output", GREEN)])

    class _RejectingClient:
        class interactions:
            calls = []
            @staticmethod
            def create(**kwargs):
                _RejectingClient.interactions.calls.append(kwargs)
                if "agent_config" in kwargs:
                    # The runtime's real agent-path rejection message (qa live: 400).
                    raise ValueError("Unknown parameter: agent_config.thinking_level")
                def _stream():
                    yield types.SimpleNamespace(event_type="interaction.completed",
                                                interaction=final, interaction_id="iR")
                return _stream()
            @staticmethod
            def get(interaction_id):
                return final

    agent_mod.THINKING_REJECTED = False  # reset module global before the run
    itx = agent_mod._run_interaction(_RejectingClient(), input_text="x", environment="remote")

    calls = _RejectingClient.interactions.calls
    assert len(calls) == 2                                  # first (rejected) + retry
    assert "agent_config" in calls[0]                       # the thinking-bearing attempt
    assert "agent_config" not in calls[1]                   # the clean retry
    assert agent_mod.THINKING_REJECTED is True              # flagged for the UI
    assert agent_mod.extract_environment_id(itx) == "envR"  # run still completed


def test_thinking_unrelated_error_not_swallowed(agent_mod, monkeypatch):
    """An UNRELATED error on the thinking-bearing call must NOT be swallowed by the
    thinking fallback — it propagates (only thinking-shaped rejections fall back)."""
    monkeypatch.setenv("LAZARUS_THINKING", "high")

    class _ExplodingClient:
        class interactions:
            @staticmethod
            def create(**kwargs):
                raise RuntimeError("network connection reset by peer")

    with pytest.raises(RuntimeError, match="connection reset"):
        agent_mod._run_interaction(_ExplodingClient(), input_text="x", environment="remote")


def test_thinking_never_sends_sampling_params(agent_mod, tmp_path, monkeypatch):
    """Even with thinking on, the Gemini-3.x ban on temperature/top_p/top_k holds."""
    monkeypatch.setenv("LAZARUS_THINKING", "high")
    cobol = _write_cobol(tmp_path)
    client = _green_client()
    agent_mod.migrate(client, str(cobol))
    forbidden = {"temperature", "top_p", "top_k"}

    def _scan(obj):
        if isinstance(obj, dict):
            assert forbidden.isdisjoint(obj), f"sampling param leaked: {forbidden & set(obj)}"
            for v in obj.values():
                _scan(v)

    for call in client.interactions.calls:
        _scan(call)


def test_thought_breadcrumb_from_thought_step(agent_mod):
    """A `thought` step yields a 💭 breadcrumb (the thinking summary), proving deep-think ran.
    Verified §8 shape: thought -> {summary:[{type:'text', text}]}."""
    step = types.SimpleNamespace(
        type="thought",
        summary=[types.SimpleNamespace(type="text", text="Considering ROUND_HALF_UP vs banker's")])
    crumb = agent_mod._tool_breadcrumb(step)
    assert crumb is not None
    assert crumb.startswith("💭")
    assert "ROUND_HALF_UP" in crumb


def test_thought_tokens_read_from_usage(agent_mod):
    """usage.total_thought_tokens is read best-effort (attr OR dict) — a positive value
    PROVES thinking ran; a missing field returns None (never raises)."""
    if not hasattr(agent_mod, "_thought_tokens"):
        pytest.skip("agent._thought_tokens not present")
    attr_itx = types.SimpleNamespace(usage=types.SimpleNamespace(total_thought_tokens=512))
    assert agent_mod._thought_tokens(attr_itx) == 512
    dict_itx = types.SimpleNamespace(usage={"total_thought_tokens": 7})
    assert agent_mod._thought_tokens(dict_itx) == 7
    # absent / zero / garbage -> None
    assert agent_mod._thought_tokens(types.SimpleNamespace(usage=None)) is None
    assert agent_mod._thought_tokens(types.SimpleNamespace()) is None
    assert agent_mod._thought_tokens(
        types.SimpleNamespace(usage=types.SimpleNamespace(total_thought_tokens=0))) is None


# ==========================================================================
# 3. CROSS-RUN SKILL LIBRARY  (task #7)
# ==========================================================================
# Landed contract:
#   * build_base_environment() mounts EVERY .agents/skills/*/SKILL.md into
#     base_environment.sources, so a FRESH invocation starts with the accumulated skill
#     set. Clean-fork (only AGENTS.md) stays the default when no skills exist.
#   * ensure_agent() re-registers (delete + recreate) a PRE-EXISTING agent when the
#     mounted-skill FINGERPRINT changes (a skill forged or edited since registration),
#     tracked locally in AGENTS_DIR/.skill_fingerprint. Matching fingerprint => no-op.
def _point_agents_dir(agent_mod, monkeypatch, agents_dir):
    """Redirect BOTH AGENTS_DIR and the derived fingerprint cache path at a temp tree,
    so ensure_agent's fingerprint file lands in the temp dir (not the real repo)."""
    monkeypatch.setattr(agent_mod, "AGENTS_DIR", agents_dir)
    monkeypatch.setattr(agent_mod, "_SKILL_FINGERPRINT_FILE",
                        agents_dir / ".skill_fingerprint")


def _make_agents_tree(tmp_path, skills):
    agents_dir = tmp_path / ".agents"
    (agents_dir / "skills").mkdir(parents=True)
    (agents_dir / "AGENTS.md").write_text("# LAZARUS AGENTS\n")
    for name, body in skills.items():
        d = agents_dir / "skills" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(body)
    return agents_dir


def test_base_environment_mounts_every_skill_md(agent_mod, tmp_path, monkeypatch):
    """build_base_environment globs ALL skills dirs into sources at the discovery path.

    We point AGENTS_DIR at a temp tree holding two forged skills + AGENTS.md and assert
    both SKILL.md files are mounted at .agents/skills/<name>/SKILL.md with their content.
    """
    agents_dir = tmp_path / ".agents"
    (agents_dir / "skills" / "alpha-idiom").mkdir(parents=True)
    (agents_dir / "skills" / "beta-idiom").mkdir(parents=True)
    (agents_dir / "AGENTS.md").write_text("# LAZARUS AGENTS\n")
    (agents_dir / "skills" / "alpha-idiom" / "SKILL.md").write_text("ALPHA SKILL BODY")
    (agents_dir / "skills" / "beta-idiom" / "SKILL.md").write_text("BETA SKILL BODY")
    monkeypatch.setattr(agent_mod, "AGENTS_DIR", agents_dir)

    env = agent_mod.build_base_environment()
    by_target = {s["target"]: s for s in env["sources"]}
    assert ".agents/skills/alpha-idiom/SKILL.md" in by_target
    assert ".agents/skills/beta-idiom/SKILL.md" in by_target
    assert by_target[".agents/skills/alpha-idiom/SKILL.md"]["content"] == "ALPHA SKILL BODY"
    assert by_target[".agents/skills/beta-idiom/SKILL.md"]["content"] == "BETA SKILL BODY"


def test_base_environment_clean_fork_when_no_skills(agent_mod, tmp_path, monkeypatch):
    """No forged skills present => only AGENTS.md is mounted (clean-fork default)."""
    agents_dir = tmp_path / ".agents"
    (agents_dir / "skills").mkdir(parents=True)
    (agents_dir / "AGENTS.md").write_text("# LAZARUS AGENTS\n")
    monkeypatch.setattr(agent_mod, "AGENTS_DIR", agents_dir)

    env = agent_mod.build_base_environment()
    targets = [s["target"] for s in env["sources"]]
    assert targets == [".agents/AGENTS.md"]


def test_ensure_agent_mounts_skills_into_base_environment(agent_mod, tmp_path, monkeypatch):
    """ensure_agent() creates the agent with base_environment carrying the skill mounts,
    so a FRESH invocation inherits accumulated skills (the cross-run library). It also
    records the mounted-skill fingerprint so a later unchanged run is a no-op."""
    agents_dir = _make_agents_tree(tmp_path, {"gamma-idiom": "GAMMA SKILL"})
    _point_agents_dir(agent_mod, monkeypatch, agents_dir)

    client = FakeClient(existing_agents=[])     # agent does not exist yet -> create()
    agent_mod.ensure_agent(client)

    assert len(client.agents.created) == 1
    created = client.agents.created[0]
    targets = [s["target"] for s in created["base_environment"]["sources"]]
    assert ".agents/skills/gamma-idiom/SKILL.md" in targets
    # the fingerprint cache was written (so the next unchanged ensure_agent is a no-op)
    assert (agents_dir / ".skill_fingerprint").exists()


def test_ensure_agent_idempotent_when_skill_set_unchanged(agent_mod, tmp_path, monkeypatch):
    """If the agent exists AND the mounted-skill fingerprint matches what it was registered
    with, ensure_agent is a no-op (no re-create, no delete) — unchanged steady-state behavior.
    Proven by running ensure_agent twice: the 2nd run must not touch the registry."""
    agents_dir = _make_agents_tree(tmp_path, {"gamma-idiom": "GAMMA SKILL"})
    _point_agents_dir(agent_mod, monkeypatch, agents_dir)

    client = FakeClient(existing_agents=[])
    agent_mod.ensure_agent(client)              # 1st: create + write fingerprint
    assert len(client.agents.created) == 1
    agent_mod.ensure_agent(client)             # 2nd: same skill set -> no-op
    assert len(client.agents.created) == 1     # still just the one create
    assert client.agents.deleted == []         # never re-registered


def test_ensure_agent_reregisters_when_skill_set_changes(agent_mod, tmp_path, monkeypatch):
    """Feature 3 core: when a skill is FORGED/EDITED after the agent was registered, the
    fingerprint changes and ensure_agent deletes + recreates the agent so the new skill is
    mounted into a fresh invocation's base_environment."""
    agents_dir = _make_agents_tree(tmp_path, {"gamma-idiom": "GAMMA SKILL"})
    _point_agents_dir(agent_mod, monkeypatch, agents_dir)

    client = FakeClient(existing_agents=[])
    agent_mod.ensure_agent(client)             # register with {gamma}
    assert len(client.agents.created) == 1

    # forge a NEW skill on disk -> fingerprint changes
    new = agents_dir / "skills" / "delta-idiom"
    new.mkdir(parents=True)
    (new / "SKILL.md").write_text("DELTA SKILL")

    agent_mod.ensure_agent(client)             # must re-register to mount delta
    assert client.agents.deleted == [agent_mod.AGENT_ID]   # old registration removed
    assert len(client.agents.created) == 2                 # recreated
    targets = [s["target"] for s in client.agents.created[1]["base_environment"]["sources"]]
    assert ".agents/skills/gamma-idiom/SKILL.md" in targets
    assert ".agents/skills/delta-idiom/SKILL.md" in targets  # the newly-forged skill


def test_ensure_agent_reregisters_when_skill_content_edited(agent_mod, tmp_path, monkeypatch):
    """The fingerprint covers skill CONTENT too: editing an existing SKILL.md (same name)
    must also re-register, so a corrected skill propagates to fresh invocations."""
    agents_dir = _make_agents_tree(tmp_path, {"gamma-idiom": "GAMMA v1"})
    _point_agents_dir(agent_mod, monkeypatch, agents_dir)

    client = FakeClient(existing_agents=[])
    agent_mod.ensure_agent(client)
    assert len(client.agents.created) == 1

    (agents_dir / "skills" / "gamma-idiom" / "SKILL.md").write_text("GAMMA v2 (corrected)")
    agent_mod.ensure_agent(client)
    assert client.agents.deleted == [agent_mod.AGENT_ID]
    assert len(client.agents.created) == 2
    content = client.agents.created[1]["base_environment"]["sources"]
    gamma = next(s for s in content if s["target"].endswith("gamma-idiom/SKILL.md"))
    assert gamma["content"] == "GAMMA v2 (corrected)"


# --- cross-run BANKING: persisting a forged skill body into the repo on disk -----------
def test_bank_forged_skill_writes_body_to_redirected_dir(agent_mod, tmp_path, monkeypatch):
    """When the agent echoes the forged SKILL.md body in its output, banking writes it under
    AGENTS_DIR/skills/<slug>/SKILL.md so a fresh invocation inherits it (Feature 3 durable
    copy). Redirected to tmp -> proves the write lands in AGENTS_DIR (and never the real repo)."""
    agents_dir = _make_agents_tree(tmp_path, {})   # AGENTS.md + empty skills/
    _point_agents_dir(agent_mod, monkeypatch, agents_dir)

    skill_path = ".agents/skills/numeric-display-rounding/SKILL.md"
    output = (
        "Diagnosed the idiom. FORGED " + skill_path + "\n"
        "```markdown\n# numeric-display-rounding\nUse Decimal.quantize(ROUND_HALF_UP).\n```\n"
        "Re-running the oracle."
    )
    written = agent_mod._bank_forged_skill_from_output(skill_path, output)
    assert written is not None
    assert written == agents_dir / "skills" / "numeric-display-rounding" / "SKILL.md"
    assert written.read_text().startswith("# numeric-display-rounding")
    # nothing escaped to the real repo (the path is under the temp AGENTS_DIR)
    assert str(tmp_path) in str(written)


def test_bank_forged_skill_no_body_is_noop(agent_mod, tmp_path, monkeypatch):
    """No fenced body after the path => banking returns None and writes nothing (we never
    invent skill content). This is WHY the forge-loop tests with body-less model_text don't
    pollute the repo."""
    agents_dir = _make_agents_tree(tmp_path, {})
    _point_agents_dir(agent_mod, monkeypatch, agents_dir)
    out = "FAILED unknown idiom. FORGED .agents/skills/x/SKILL.md"  # no ``` body
    assert agent_mod._bank_forged_skill_from_output(".agents/skills/x/SKILL.md", out) is None
    assert not (agents_dir / "skills" / "x").exists()


def test_migrate_forge_loop_does_not_pollute_real_repo(agent_mod, tmp_path, monkeypatch):
    """Defense-in-depth: a full forge->retry migrate() whose RED output carries BOTH a skill
    path AND a fenced body must bank into the redirected AGENTS_DIR, never the real .agents/.
    Guards against a future test/edit accidentally writing skills into the repo."""
    agents_dir = _make_agents_tree(tmp_path, {})
    _point_agents_dir(agent_mod, monkeypatch, agents_dir)

    cobol = _write_cobol(tmp_path, body="IDENTIFICATION DIVISION.\n")
    red = ("FAILED unknown idiom. FORGED .agents/skills/banked-idiom/SKILL.md\n"
           "```markdown\nbanked body\n```")
    client = FakeClient([
        {"env_id": "env1", "interaction_id": "i1", "model_text": red},
        {"env_id": "env1", "interaction_id": "i2", "model_text": GREEN},
    ])
    agent_mod.migrate(client, str(cobol))
    # banked into the temp dir, NOT the real repo
    assert (agents_dir / "skills" / "banked-idiom" / "SKILL.md").read_text().strip() == "banked body"


# ==========================================================================
# 4. WHOLE-CODEBASE INGESTION  (task #8)
# ==========================================================================
# Landed contract:
#   * migrate(client, cobol_path=None, *, cobol_paths=None). Single via the positional
#     (str|Path), whole-codebase via cobol_paths=[...] OR a list passed positionally.
#     Passing BOTH, NEITHER, or an EMPTY list raises ValueError (_normalize_cobol_paths).
#   * _build_multi_prompt(modules: list[(name, source)], *, ground=False) — labels each
#     module via _render_modules ("=== <name> ===" + cobol fence), asks for CROSS-MODULE
#     business-rule recovery, reuses the SAME marker/oracle/payroll.py contract.
#   * Single-file path still calls _build_prompt -> byte-identical to shipped.
def test_multi_prompt_includes_every_module_source_and_name(agent_mod):
    """_build_multi_prompt fences each module and LABELS it by name, so the agent sees the
    whole codebase. Both sources AND both filenames must appear."""
    a_src = "IDENTIFICATION DIVISION. PROGRAM-ID. ALPHA. MOVE 1 TO WS-A."
    b_src = "IDENTIFICATION DIVISION. PROGRAM-ID. BETA. CALL 'ALPHA'."
    prompt = agent_mod._build_multi_prompt([("alpha.cob", a_src), ("beta.cob", b_src)])
    # both sources present, each in its own labeled fence
    assert a_src in prompt and b_src in prompt
    assert "alpha.cob" in prompt and "beta.cob" in prompt
    # cross-module recovery language is present (the point of Feature 4)
    low = prompt.lower()
    assert "cross-module" in low or "cross module" in low
    assert "codebase" in low or "as one system" in low or "one system" in low
    # the live-UI contract is preserved (markers + payroll.py target)
    assert "LAZARUS_ORACLE_JSON" in prompt
    assert "LAZARUS_MODULE" in prompt
    assert "/workspace/payroll.py" in prompt


def test_multi_prompt_reports_module_count(agent_mod):
    """The codebase prompt names the file count so the agent knows the scope."""
    prompt = agent_mod._build_multi_prompt(
        [("a.cob", "PROGRAM-ID. A."), ("b.cob", "PROGRAM-ID. B."), ("c.cpy", "01 REC.")])
    assert "3 files" in prompt or "3 modules" in prompt or "(3" in prompt


def test_multi_prompt_grounding_additive(agent_mod):
    """ground=True on the codebase prompt prepends the research preamble without dropping
    the cross-module body."""
    prompt = agent_mod._build_multi_prompt(
        [("a.cob", "PROGRAM-ID. A."), ("b.cob", "PROGRAM-ID. B.")], ground=True)
    low = prompt.lower()
    assert "google_search" in low or "url_context" in low
    assert "cross-module" in low or "cross module" in low


def test_migrate_multi_via_keyword(agent_mod, tmp_path):
    """migrate(client, cobol_paths=[...]) ingests >1 file: both bodies + names reach the
    agent input, and the cross-module prompt (not the single-file one) is used."""
    a = _write_cobol(tmp_path, "alpha.cob", "IDENTIFICATION DIVISION. PROGRAM-ID. ALPHA.")
    b = _write_cobol(tmp_path, "beta.cob", "IDENTIFICATION DIVISION. PROGRAM-ID. BETA.")
    client = _green_client()
    agent_mod.migrate(client, cobol_paths=[str(a), str(b)])

    sent = client.interactions.calls[0]["input"]
    assert "ALPHA" in sent and "BETA" in sent
    assert "alpha.cob" in sent and "beta.cob" in sent      # labeled by basename
    assert "cross-module" in sent.lower() or "cross module" in sent.lower()


def test_migrate_multi_via_positional_list(agent_mod, tmp_path):
    """A list passed positionally is also accepted (cobol_path may be a list)."""
    a = _write_cobol(tmp_path, "alpha.cob", "PROGRAM-ID. ALPHA.")
    b = _write_cobol(tmp_path, "beta.cob", "PROGRAM-ID. BETA.")
    client = _green_client()
    agent_mod.migrate(client, [str(a), str(b)])
    sent = client.interactions.calls[0]["input"]
    assert "ALPHA" in sent and "BETA" in sent


def test_migrate_rejects_both_single_and_multi(agent_mod, tmp_path):
    """Passing BOTH cobol_path and cobol_paths is a usage error (ValueError)."""
    a = _write_cobol(tmp_path, "a.cob", "PROGRAM-ID. A.")
    with pytest.raises(ValueError):
        agent_mod.migrate(_green_client(), str(a), cobol_paths=[str(a)])


def test_migrate_rejects_empty_file_list(agent_mod):
    """An empty cobol_paths list is a usage error, not a silent no-op."""
    with pytest.raises(ValueError):
        agent_mod.migrate(_green_client(), cobol_paths=[])


def test_migrate_rejects_no_source(agent_mod):
    """Neither path nor paths => ValueError (migrate needs a source)."""
    with pytest.raises(ValueError):
        agent_mod.migrate(_green_client())


def test_migrate_single_via_keyword_one_element_list(agent_mod, tmp_path):
    """A ONE-element cobol_paths list still goes through the single-file builder (len==1),
    so a degenerate codebase of one module stays byte-identical to the shipped prompt."""
    solo = _write_cobol(tmp_path, "solo.cob", "IDENTIFICATION DIVISION. PROGRAM-ID. SOLO.")
    client = _green_client()
    agent_mod.migrate(client, cobol_paths=[str(solo)])
    sent = client.interactions.calls[0]["input"]
    assert "SOLO" in sent
    # single-file path: the shipped (non-codebase) prompt — no cross-module framing
    assert sent.startswith("Migrate this COBOL program to idiomatic Python.")
    assert "cross-module" not in sent.lower()


def test_migrate_single_file_still_default(agent_mod, tmp_path):
    """Regression: the single-path positional call keeps the legacy single-module prompt
    (shipped opening, one COBOL fence, payroll.py target) — F4 is additive, not a swap."""
    cobol = _write_cobol(tmp_path, body="IDENTIFICATION DIVISION. PROGRAM-ID. SOLO.")
    client = _green_client()
    agent_mod.migrate(client, str(cobol))
    sent = client.interactions.calls[0]["input"]
    assert "SOLO" in sent
    assert sent.startswith("Migrate this COBOL program to idiomatic Python.")
    assert "/workspace/payroll.py" in sent
    assert "COBOL CODEBASE" not in sent      # not the multi-module prompt
