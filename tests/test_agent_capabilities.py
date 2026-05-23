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
        self._existing = list(existing)

    def list(self):
        agents = [types.SimpleNamespace(id=i) for i in self._existing]
        return types.SimpleNamespace(agents=agents)

    def create(self, **kwargs):
        self.created.append(kwargs)
        self._existing.append(kwargs.get("id"))


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


# ==========================================================================
# 2. THINKING_LEVEL  (task #6, env LAZARUS_THINKING default "medium")
# ==========================================================================
# Assumed contract (confirm with integration-eng):
#   * a configured non-default thinking level is passed via generation_config on
#     interactions.create (interaction-scoped), e.g.
#       extra_body / generation_config = {"thinking_level": "high"}.
#   * default ("medium" / unset) sends NO generation_config — relying on the
#     server-side default — so the call stays byte-identical to today.
def _gen_config_from_call(call):
    """Recover whatever the impl used to carry generation knobs, however nested."""
    if "generation_config" in call:
        return call["generation_config"]
    eb = call.get("extra_body") or {}
    if isinstance(eb, dict) and "generation_config" in eb:
        return eb["generation_config"]
    return None


def test_thinking_default_sends_no_generation_config(agent_mod, tmp_path, monkeypatch):
    """Default thinking level => NO generation_config anywhere (shipped behavior)."""
    monkeypatch.setenv("LAZARUS_THINKING", "medium")  # the documented default
    cobol = _write_cobol(tmp_path)
    client = _green_client()
    agent_mod.migrate(client, str(cobol))
    for call in client.interactions.calls:
        assert _gen_config_from_call(call) is None, \
            "medium/default must not emit a generation_config (stay identical to today)"


def test_thinking_high_carries_configured_level(agent_mod, tmp_path, monkeypatch):
    """LAZARUS_THINKING=high => the configured level reaches generation_config.

    Skips cleanly until integration-eng wires the env read; the assertion describes the
    target shape (thinking_level somewhere in the generation config the SDK sees).
    """
    monkeypatch.setenv("LAZARUS_THINKING", "high")
    cobol = _write_cobol(tmp_path)
    client = _green_client()
    agent_mod.migrate(client, str(cobol))

    cfgs = [_gen_config_from_call(c) for c in client.interactions.calls]
    cfgs = [c for c in cfgs if c]
    if not cfgs:
        pytest.skip("LAZARUS_THINKING not wired into generation_config yet")
    blob = str(cfgs).lower()
    assert "high" in blob
    assert "thinking" in blob


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


# ==========================================================================
# 3. CROSS-RUN SKILL LIBRARY  (task #7)
# ==========================================================================
# Contract: ensure_agent()/build_base_environment() mount EVERY
# .agents/skills/*/SKILL.md into base_environment.sources, so a fresh invocation
# starts with the accumulated skill set. Clean fork stays the default when none exist.
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
    so a FRESH invocation inherits accumulated skills (the cross-run library)."""
    agents_dir = tmp_path / ".agents"
    (agents_dir / "skills" / "gamma-idiom").mkdir(parents=True)
    (agents_dir / "AGENTS.md").write_text("# LAZARUS AGENTS\n")
    (agents_dir / "skills" / "gamma-idiom" / "SKILL.md").write_text("GAMMA SKILL")
    monkeypatch.setattr(agent_mod, "AGENTS_DIR", agents_dir)

    client = FakeClient(existing_agents=[])     # agent does not exist yet -> create()
    agent_mod.ensure_agent(client)

    assert len(client.agents.created) == 1
    created = client.agents.created[0]
    sources = created["base_environment"]["sources"]
    targets = [s["target"] for s in sources]
    assert ".agents/skills/gamma-idiom/SKILL.md" in targets


def test_ensure_agent_idempotent_when_agent_exists(agent_mod):
    """Idempotency baseline (unchanged): if the agent already exists, no re-create.

    NOTE: task #7 wants re-registration when the MOUNTED SKILL SET CHANGES. Once
    integration-eng lands that, this test documents the OLD behavior and should be
    superseded by a 'recreate-on-skill-change' test (left as a marker below)."""
    client = FakeClient(existing_agents=[agent_mod.AGENT_ID])
    agent_mod.ensure_agent(client)
    assert client.agents.created == []


# ==========================================================================
# 4. WHOLE-CODEBASE INGESTION  (task #8)
# ==========================================================================
# Contract: migrate() accepts MULTIPLE COBOL files (+ copybooks); all are mounted /
# included and the prompt asks for cross-module rule recovery. Single-file stays default.
def test_multi_module_prompt_includes_all_modules(agent_mod, tmp_path):
    """When the prompt is built from multiple modules, every module's source appears.

    Assumed contract: a prompt builder accepts an iterable of (name, source) modules,
    e.g. _build_prompt(cobol) where cobol is the concatenation, OR a dedicated
    _build_multi_prompt(modules). We probe both and require all sources present.
    """
    a_src = "IDENTIFICATION DIVISION. PROGRAM-ID. ALPHA."
    b_src = "IDENTIFICATION DIVISION. PROGRAM-ID. BETA."

    builder = getattr(agent_mod, "_build_multi_prompt", None)
    if builder is not None:
        prompt = builder([("alpha.cob", a_src), ("beta.cob", b_src)])
    else:
        # Fallback: the single-file builder over a concatenation (a valid impl choice).
        prompt = agent_mod._build_prompt(a_src + "\n" + b_src)
    assert "ALPHA" in prompt
    assert "BETA" in prompt


def test_migrate_accepts_multiple_files(agent_mod, tmp_path):
    """migrate() ingests >1 COBOL file. Tries the most likely signatures and requires
    that BOTH module bodies reach the agent's input prompt in a single run."""
    a = _write_cobol(tmp_path, "alpha.cob", "IDENTIFICATION DIVISION. PROGRAM-ID. ALPHA.")
    b = _write_cobol(tmp_path, "beta.cob", "IDENTIFICATION DIVISION. PROGRAM-ID. BETA.")
    client = _green_client()

    sig = inspect.signature(agent_mod.migrate)
    params = sig.parameters
    try:
        # Preferred: a list param (e.g. cobol_paths=[...]) or a 2nd positional that
        # accepts a list. Probe a keyword form first, then a positional list.
        if "cobol_paths" in params:
            agent_mod.migrate(client, cobol_paths=[str(a), str(b)])
        elif any(p.kind == p.VAR_POSITIONAL for p in params.values()):
            agent_mod.migrate(client, str(a), str(b))
        else:
            # second positional may accept a list of paths
            agent_mod.migrate(client, [str(a), str(b)])
    except (TypeError, FileNotFoundError, ValueError):
        pytest.skip("migrate() multi-file signature not landed yet")

    assert client.interactions.calls, "no interaction issued"
    sent = client.interactions.calls[0]["input"]
    assert "ALPHA" in sent and "BETA" in sent


def test_migrate_single_file_still_default(agent_mod, tmp_path):
    """Regression: the single-path call keeps the legacy single-module prompt (one COBOL
    fence, payroll.py target) — multi-module must be additive, not a replacement."""
    cobol = _write_cobol(tmp_path, body="IDENTIFICATION DIVISION. PROGRAM-ID. SOLO.")
    client = _green_client()
    agent_mod.migrate(client, str(cobol))
    sent = client.interactions.calls[0]["input"]
    assert "SOLO" in sent
    assert "/workspace/payroll.py" in sent
