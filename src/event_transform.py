"""
LAZARUS — transform the agent's raw tool output into CANONICAL UI events.

server.py forwards the agent's live `step.*` stream as `step` events directly, but
the seven SEMANTIC panels (business_rule, diff, pytest, oracle, forge, reload,
download) are DERIVED from the agent's tool outputs, not from raw interaction.steps
(web/STREAM_CONTRACT.md). This module holds the pure, unit-testable derivations.

Contract with the agent: to make the richest panels deterministic instead of
scraping prose, the agent emits machine-readable marker lines in its output:
  - `LAZARUS_ORACLE_JSON: [{"input","cobol","python","match"}, ...]`  (the diff!)
  - `LAZARUS_RULE: {"title","plain","cobol_ref"?,"severity"?}`        (one per rule)
We parse those when present; everything degrades gracefully when they're absent.
"""
from __future__ import annotations

import json
import pathlib
import re

_ORACLE_MARKER = "LAZARUS_ORACLE_JSON:"
_RULE_MARKER = "LAZARUS_RULE:"


def _parse_marker_payloads(text: str, marker: str) -> list:
    """Return the parsed JSON payload after each `marker` line; skip malformed ones."""
    out = []
    for line in text.splitlines():
        idx = line.find(marker)
        if idx == -1:
            continue
        payload = line[idx + len(marker):].strip()
        try:
            out.append(json.loads(payload))
        except (json.JSONDecodeError, ValueError):
            continue
    return out


def parse_oracle_records(text: str) -> list[dict]:
    """Extract the differential-oracle records ({input,cobol,python,match}) the agent
    printed via the LAZARUS_ORACLE_JSON marker. Returns [] if absent/malformed."""
    records: list[dict] = []
    for payload in _parse_marker_payloads(text, _ORACLE_MARKER):
        if isinstance(payload, list):
            records.extend(r for r in payload if isinstance(r, dict))
        elif isinstance(payload, dict):
            records.append(payload)
    return records


def _case_name(record: dict) -> str:
    inp = (record.get("input") or "").strip()
    return f"test_equivalence[{inp}]"


def _mismatch_message(record: dict) -> str:
    return (
        "AssertionError: byte mismatch — COBOL "
        f"{record.get('cobol')!r} != Python {record.get('python')!r} "
        "(COBOL DISPLAY de-editing + ROUND-HALF-UP)"
    )


def to_pytest_event(records: list[dict], iteration: int = 1) -> dict:
    """Build the canonical `pytest` event with STRUCTURED per-case cobol-vs-python
    values (the #1 demo money shot), from the oracle records."""
    cases = []
    passed = failed = 0
    for r in records:
        ok = bool(r.get("match"))
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        case = {
            "name": _case_name(r),
            "status": "pass" if ok else "fail",
            "cobol": r.get("cobol"),
            "python": r.get("python"),
        }
        if not ok:
            case["message"] = _mismatch_message(r)
        cases.append(case)
    result = "green" if failed == 0 and cases else ("red" if failed else "green")
    summary = (f"{passed} passed, {failed} failed" if failed == 0
               else f"{failed} failed, {passed} passed")
    return {
        "type": "pytest",
        "result": result,
        "iteration": iteration,
        "summary": summary,
        "cases": cases,
    }


def oracle_event(golden_path: str) -> dict:
    """The differential-oracle banner: real compiler + the input battery, from the
    golden capture (real cobc output, available offline)."""
    data = json.loads(pathlib.Path(golden_path).read_text())
    return {
        "type": "oracle",
        "compiler": data.get("captured_with", "GnuCOBOL cobc"),
        "inputs": [(c.get("input") or "").strip() for c in data.get("cases", [])],
        "note": "Canonical outputs captured from the original COBOL binary (ground truth).",
    }


def business_rules_from_text(text: str) -> list[dict]:
    """Recovered business rules (the archaeology panel) from LAZARUS_RULE markers."""
    rules = []
    for payload in _parse_marker_payloads(text, _RULE_MARKER):
        if not isinstance(payload, dict):
            continue
        rule = {"type": "business_rule"}
        rule.update(payload)
        rules.append(rule)
    return rules
