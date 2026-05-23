"""
LAZARUS — Managed Agent driver (skeleton).

Single Gemini 3.5 Flash Managed Agent that migrates COBOL -> tested Python,
proves equivalence against the original COBOL (differential oracle), and forges
its own SKILL.md when it meets an unknown idiom.

Pin the beta version and re-test the morning of the event.
NOTE: API surface is preview (-preview-05-2026); confirm names against
https://ai.google.dev/gemini-api/docs/agents before the build.
"""
from __future__ import annotations

import argparse
import pathlib

from google import genai  # pip install google-genai

AGENT_ID = "lazarus"
BASE_AGENT = "antigravity-preview-05-2026"   # Gemini 3.5 Flash managed agent
ENVIRONMENT_ID = "lazarus-env"               # persistent sandbox (GnuCOBOL pre-warmed)
MAX_ITERATIONS = 4                           # hard cap — never loop forever on stage

SYSTEM_INSTRUCTION = pathlib.Path(".agents/AGENTS.md").read_text()


def ensure_agent(client: genai.Client) -> None:
    """Create the reusable custom agent once. Idempotent in practice."""
    client.agents.create(
        id=AGENT_ID,
        base_agent=BASE_AGENT,
        system_instruction=SYSTEM_INSTRUCTION,
        base_environment=ENVIRONMENT_ID,
    )


def migrate(client: genai.Client, cobol_path: str):
    """Run the write -> run -> prove -> self-heal loop, streaming steps to the UI."""
    cobol = pathlib.Path(cobol_path).read_text()
    prompt = (
        "Migrate this COBOL program to idiomatic Python.\n"
        "1. First, recover and print the business rules in plain English.\n"
        "2. Translate to Python in the sandbox.\n"
        "3. Build a DIFFERENTIAL ORACLE: compile and run the ORIGINAL COBOL with "
        "GnuCOBOL (cobc) over the input battery, capture canonical outputs.\n"
        "4. Generate equivalence tests asserting python_output == cobol_output "
        "byte-for-byte. Run pytest.\n"
        "5. On failure due to an UNKNOWN COBOL idiom, write a new "
        ".agents/skills/<idiom>/SKILL.md teaching yourself to handle it, commit it, "
        "reload, and retry.\n"
        f"Stop when tests pass or after {MAX_ITERATIONS} iterations.\n\n"
        f"COBOL:\n```cobol\n{cobol}\n```"
    )

    interaction = None
    for step in client.interactions.create(
        agent=AGENT_ID,
        input=prompt,
        environment=ENVIRONMENT_ID,   # keep files/skills across turns
        stream=True,
    ):
        # Each step is a thought / tool call / code execution -> push to the UI (SSE).
        emit_to_ui(step)
        interaction = step

    return interaction


def emit_to_ui(step) -> None:
    """Forward interaction.steps to the front-end live trace. Wire to SSE/WebSocket."""
    # TODO(front-end): serialize step.type, step.thought, step.tool_call, step.output
    print(getattr(step, "type", step))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="src/sample/payroll.cob")
    args = ap.parse_args()

    client = genai.Client()  # reads GEMINI_API_KEY
    ensure_agent(client)
    migrate(client, args.input)


if __name__ == "__main__":
    main()
