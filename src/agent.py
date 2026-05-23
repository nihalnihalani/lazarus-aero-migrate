"""
LAZARUS — Managed Agent driver.

Single Gemini 3.5 Flash Managed Agent (Antigravity) that migrates COBOL -> tested
Python, proves equivalence against the original COBOL (differential oracle), and
forges its own SKILL.md when it meets an unknown idiom.

Verified against the live Gemini API docs (May 2026):
  - Interactions API requires  google-genai >= 1.55.0
  - Managed agent id:          "antigravity-preview-05-2026"  (powered by Gemini 3.5 Flash)
  - Create custom agent:       client.agents.create(id, base_agent, system_instruction, base_environment)
  - Run:                       client.interactions.create(agent, input, environment, [previous_interaction_id], [stream])
  - environment:               "remote" (fresh sandbox) -> reuse interaction.environment_id thereafter
  - Sandbox:                   Ubuntu, Python 3.12, Node 22; pip/npm install at runtime; files persist per env id
  - Unsupported by this agent: mcp, computer_use, function_calling, file_search, structured output
Refs: ai.google.dev/gemini-api/docs/{managed-agents-quickstart, custom-agents, agent-environment, antigravity-agent}
"""
from __future__ import annotations

import argparse
import pathlib

from google import genai  # pip install "google-genai>=1.55.0"

AGENT_ID = "lazarus"
BASE_AGENT = "antigravity-preview-05-2026"   # Gemini 3.5 Flash managed agent
MAX_ITERATIONS = 4                            # hard cap — never loop forever on stage

AGENTS_DIR = pathlib.Path(".agents")


def build_base_environment() -> dict:
    """Mount AGENTS.md + any seed SKILL.md files into a fresh remote sandbox.

    base_environment must be an object (not a bare string); `sources` mounts files
    at the paths the agent auto-discovers (.agents/AGENTS.md, .agents/skills/*/SKILL.md).
    """
    sources = [
        {
            "type": "inline",
            "target": ".agents/AGENTS.md",
            "content": (AGENTS_DIR / "AGENTS.md").read_text(),
        }
    ]
    for skill_md in (AGENTS_DIR / "skills").glob("*/SKILL.md"):
        sources.append(
            {
                "type": "inline",
                "target": f".agents/skills/{skill_md.parent.name}/SKILL.md",
                "content": skill_md.read_text(),
            }
        )
    return {"type": "remote", "sources": sources}


def ensure_agent(client: genai.Client) -> None:
    """Create the reusable custom agent once (mounts skills via base_environment)."""
    client.agents.create(
        id=AGENT_ID,
        base_agent=BASE_AGENT,
        system_instruction="You are LAZARUS, an autonomous COBOL->Python migration agent. "
        "Follow .agents/AGENTS.md exactly.",
        base_environment=build_base_environment(),
        # tools omitted -> defaults to code_execution + google_search + url_context.
    )


def _build_prompt(cobol: str) -> str:
    return (
        "Migrate this COBOL program to idiomatic Python. Work in the sandbox.\n"
        "0. If GnuCOBOL (cobc) is missing, install it (apt-get install -y gnucobol; "
        "fall back to src/sample/golden_io.json if network/apt is unavailable).\n"
        "1. Recover and print the business rules in plain English.\n"
        "2. Translate to Python (write payroll.py).\n"
        "3. DIFFERENTIAL ORACLE: compile + run the ORIGINAL COBOL with cobc over the "
        "input battery; capture canonical outputs (ground truth).\n"
        "4. Generate equivalence tests asserting python_output == cobol_output "
        "byte-for-byte; run pytest.\n"
        "5. On failure from an UNKNOWN COBOL idiom, write "
        ".agents/skills/<idiom>/SKILL.md teaching yourself, commit it, and retry.\n"
        f"Stop when tests pass or after {MAX_ITERATIONS} iterations.\n\n"
        f"COBOL:\n```cobol\n{cobol}\n```"
    )


def migrate(client: genai.Client, cobol_path: str, environment: str = "remote",
            previous_interaction_id: str | None = None):
    """Run the write -> run -> prove -> self-heal loop, streaming steps to the UI.

    Returns the completed interaction (carries .id, .environment_id, .output_text, .steps).
    """
    cobol = pathlib.Path(cobol_path).read_text()

    stream = client.interactions.create(
        agent=AGENT_ID,
        input=_build_prompt(cobol),
        environment=environment,                        # "remote" first; reuse env id next
        previous_interaction_id=previous_interaction_id,
        stream=True,
    )

    final = None
    for event in stream:
        # Live trace: forward incremental deltas to the front-end (SSE/WebSocket).
        if getattr(event, "event_type", None) == "step.delta":
            delta = event.delta
            if getattr(delta, "type", None) == "text":
                emit_to_ui(delta.text)
        final = event   # terminal event exposes the completed interaction fields

    return final


def emit_to_ui(text: str) -> None:
    """Forward streamed text/steps to the front-end live trace. Wire to SSE/WebSocket."""
    print(text, end="", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="src/sample/payroll.cob")
    args = ap.parse_args()

    client = genai.Client()  # reads GEMINI_API_KEY
    ensure_agent(client)
    result = migrate(client, args.input)

    # Persist the environment id so follow-up turns reuse the same sandbox + forged skills:
    env_id = getattr(result, "environment_id", None)
    print(f"\n[done] environment_id={env_id} interaction_id={getattr(result, 'id', None)}")


if __name__ == "__main__":
    main()
