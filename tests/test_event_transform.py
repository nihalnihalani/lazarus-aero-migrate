"""Tests for src/event_transform.py — turning the agent's raw tool output into the
CANONICAL UI events (web/STREAM_CONTRACT.md). The #1 money shot is structured
per-case pytest results carrying the COBOL-vs-Python byte values, NOT raw stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
for p in (str(SRC_DIR), str(REPO_ROOT)):
    if p in sys.path:
        sys.path.remove(p)
    sys.path.insert(0, p)

import event_transform as et


# --------------------------------------------------------------------------
# parse_oracle_records — pull the structured {input,cobol,python,match} list out
# of the agent's output (it prints a LAZARUS_ORACLE_JSON: marker line)
# --------------------------------------------------------------------------
def test_parse_oracle_records_from_marker_line():
    out = (
        "...agent chatter...\n"
        'LAZARUS_ORACLE_JSON: [{"input": "1.00\\n", "cobol": "0000000.77\\n", '
        '"python": "0000000.78\\n", "match": false}]\n'
        "...more chatter...\n"
    )
    records = et.parse_oracle_records(out)
    assert len(records) == 1
    assert records[0]["cobol"] == "0000000.77\n"
    assert records[0]["python"] == "0000000.78\n"
    assert records[0]["match"] is False


def test_parse_oracle_records_returns_empty_when_absent():
    assert et.parse_oracle_records("no marker here, just prose") == []


def test_parse_oracle_records_ignores_malformed_json():
    assert et.parse_oracle_records("LAZARUS_ORACLE_JSON: {not valid json") == []


# --------------------------------------------------------------------------
# to_pytest_event — structured cases (the money shot)
# --------------------------------------------------------------------------
def test_to_pytest_event_red_with_per_case_cobol_vs_python():
    records = [
        {"input": "1.00\n", "cobol": "0000000.77\n", "python": "0000000.78\n", "match": False},
        {"input": "1000.00\n", "cobol": "0000775.00\n", "python": "0000775.00\n", "match": True},
    ]
    ev = et.to_pytest_event(records, iteration=1)
    assert ev["type"] == "pytest"
    assert ev["result"] == "red"          # at least one mismatch
    assert ev["iteration"] == 1
    assert ev["summary"] == "1 failed, 1 passed"
    assert len(ev["cases"]) == 2
    c0 = ev["cases"][0]
    assert c0["status"] == "fail"
    assert c0["cobol"] == "0000000.77\n" and c0["python"] == "0000000.78\n"
    assert "1.00" in c0["name"]
    assert c0["message"]                  # non-empty mismatch explanation
    assert ev["cases"][1]["status"] == "pass"


def test_to_pytest_event_green_when_all_match():
    records = [
        {"input": "1000.00\n", "cobol": "0000775.00\n", "python": "0000775.00\n", "match": True},
    ]
    ev = et.to_pytest_event(records, iteration=2)
    assert ev["result"] == "green"
    assert ev["summary"] == "1 passed, 0 failed"
    assert all(c["status"] == "pass" for c in ev["cases"])


# --------------------------------------------------------------------------
# oracle_event — the differential-oracle banner (real compiler + inputs)
# --------------------------------------------------------------------------
def test_oracle_event_from_golden(tmp_path):
    golden = tmp_path / "golden.json"
    golden.write_text(json.dumps({
        "program": "payroll.cob",
        "captured_with": "GnuCOBOL 3.2.0 (cobc -x), 2026-05-23",
        "cases": [{"input": "1000.00\n", "cobol": "0000775.00\n"},
                  {"input": "0.01\n", "cobol": "0000000.01\n"}],
    }))
    ev = et.oracle_event(str(golden))
    assert ev["type"] == "oracle"
    assert "GnuCOBOL" in ev["compiler"]
    assert ev["inputs"] == ["1000.00", "0.01"]   # newline-stripped, display-ready
    assert ev["note"]


# --------------------------------------------------------------------------
# business_rules_from_text — recovered rules for the archaeology panel
# --------------------------------------------------------------------------
def test_business_rules_from_marker_lines():
    out = (
        "LAZARUS_RULE: {\"title\": \"Progressive tax\", \"plain\": \"22.5% withheld\", "
        "\"cobol_ref\": \"COMPUTE WS-TAX ROUNDED\", \"severity\": \"rule\"}\n"
        "LAZARUS_RULE: {\"title\": \"Half-up rounding\", \"plain\": \"ROUNDED is half-up\", "
        "\"severity\": \"gotcha\"}\n"
    )
    rules = et.business_rules_from_text(out)
    assert len(rules) == 2
    assert rules[0]["type"] == "business_rule"
    assert rules[0]["title"] == "Progressive tax"
    assert rules[1]["severity"] == "gotcha"


def test_business_rules_empty_when_absent():
    assert et.business_rules_from_text("no rules emitted") == []
