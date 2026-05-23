"""Tests for the LAZARUS differential oracle harness.

The oracle is the judge-proofing core: it proves migrated Python is equivalent
to the ORIGINAL COBOL by running real GnuCOBOL and diffing byte-for-byte. These
tests exercise the harness with tiny local fixtures (no network) and the golden
fallback path used when GnuCOBOL is unavailable on stage.

Subprocess-backed tests are marked `requires_cobc` and skip cleanly when cobc is
absent; the golden-fallback and pure-logic tests always run.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import requires_cobc

import differential_oracle as oracle


# --------------------------------------------------------------------------
# compile_cobol / run_binary  (real GnuCOBOL, tiny fixture)
# --------------------------------------------------------------------------
@requires_cobc
def test_compile_cobol_produces_runnable_binary(fixtures_dir, tmp_path):
    binary = oracle.compile_cobol(str(fixtures_dir / "twice.cob"), str(tmp_path / "dbl"))
    assert Path(binary).exists()
    assert oracle.run_binary(binary, "10\n") == "00020\n"


@requires_cobc
def test_compile_cobol_raises_on_bad_source(tmp_path):
    bad = tmp_path / "bad.cob"
    bad.write_text("this is not cobol at all\n")
    with pytest.raises(Exception):
        oracle.compile_cobol(str(bad), str(tmp_path / "out"))


# --------------------------------------------------------------------------
# run_python  (real interpreter, tiny fixture)
# --------------------------------------------------------------------------
def test_run_python_correct_translation_matches_padding(fixtures_dir):
    out = oracle.run_python(str(fixtures_dir / "twice_correct.py"), "10\n")
    assert out == "00020\n"


def test_run_python_wrong_translation_differs(fixtures_dir):
    out = oracle.run_python(str(fixtures_dir / "twice_wrong.py"), "10\n")
    assert out == "20\n"  # missing COBOL zero-padding


# --------------------------------------------------------------------------
# differential_test  (full COBOL-vs-Python diff)
# --------------------------------------------------------------------------
@requires_cobc
def test_differential_test_all_match_for_correct_translation(fixtures_dir):
    results = oracle.differential_test(
        str(fixtures_dir / "twice.cob"),
        str(fixtures_dir / "twice_correct.py"),
        ["1\n", "10\n", "999\n"],
    )
    assert len(results) == 3
    assert all(r["match"] for r in results)
    # each record carries the fields the UI diff viewer renders
    for r in results:
        assert set(r) >= {"input", "cobol", "python", "match"}


@requires_cobc
def test_differential_test_flags_mismatch_for_wrong_translation(fixtures_dir):
    results = oracle.differential_test(
        str(fixtures_dir / "twice.cob"),
        str(fixtures_dir / "twice_wrong.py"),
        ["10\n"],
    )
    assert results[0]["match"] is False
    assert results[0]["cobol"] == "00020\n"
    assert results[0]["python"] == "20\n"


# --------------------------------------------------------------------------
# load_golden_fallback  (pre-captured COBOL I/O pairs)
# --------------------------------------------------------------------------
def test_load_golden_fallback_returns_pairs(tmp_path):
    p = tmp_path / "golden.json"
    p.write_text(json.dumps({"cases": [{"input": "1\n", "cobol": "00002\n"}]}))
    data = oracle.load_golden_fallback(str(p))
    assert data["cases"][0]["cobol"] == "00002\n"


def test_load_golden_fallback_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        oracle.load_golden_fallback("/nonexistent/golden_io.json")


def test_shipped_golden_io_is_wellformed(repo_root):
    """The real demo fallback must parse and carry input/cobol pairs."""
    data = oracle.load_golden_fallback(str(repo_root / "src/sample/golden_io.json"))
    assert data["cases"], "golden_io.json has no cases"
    for case in data["cases"]:
        assert "input" in case and "cobol" in case
        assert case["cobol"], "captured COBOL output must be non-empty"


# --------------------------------------------------------------------------
# differential_test_golden  (Python-vs-golden, the no-cobc demo path)
# --------------------------------------------------------------------------
def test_differential_test_golden_passes_for_correct_translation(fixtures_dir, tmp_path):
    golden = tmp_path / "golden.json"
    golden.write_text(json.dumps({"cases": [
        {"input": "1\n", "cobol": "00002\n"},
        {"input": "10\n", "cobol": "00020\n"},
    ]}))
    results = oracle.differential_test_golden(
        str(fixtures_dir / "twice_correct.py"), str(golden)
    )
    assert all(r["match"] for r in results)
    assert [r["input"] for r in results] == ["1\n", "10\n"]


def test_differential_test_golden_flags_wrong_translation(fixtures_dir, tmp_path):
    golden = tmp_path / "golden.json"
    golden.write_text(json.dumps({"cases": [{"input": "10\n", "cobol": "00020\n"}]}))
    results = oracle.differential_test_golden(
        str(fixtures_dir / "twice_wrong.py"), str(golden)
    )
    assert results[0]["match"] is False
    assert results[0]["cobol"] == "00020\n"
    assert results[0]["python"] == "20\n"


# --------------------------------------------------------------------------
# reference payroll.py  (known-good Python baseline for the demo + run())
# --------------------------------------------------------------------------
def test_reference_payroll_py_matches_golden(repo_root):
    """The shipped reference translation must be byte-for-byte equivalent to the
    captured COBOL outputs across the full input battery — including the
    half-up rounding-tie cases that a naive round() would get wrong."""
    results = oracle.differential_test_golden(
        str(repo_root / "src/sample/payroll.py"),
        str(repo_root / "src/sample/golden_io.json"),
    )
    failures = [r for r in results if not r["match"]]
    assert not failures, f"reference payroll.py diverges from COBOL: {failures}"


def test_run_dispatches_to_an_equivalence_check(repo_root):
    """run() returns diff records whether cobc is present (live) or not (golden)."""
    golden = str(repo_root / "src/sample/golden_io.json")
    battery = [c["input"] for c in oracle.load_golden_fallback(golden)["cases"]]
    results = oracle.run(
        str(repo_root / "src/sample/payroll.cob"),
        str(repo_root / "src/sample/payroll.py"),
        battery,
        golden,
    )
    assert len(results) == len(battery)
    assert all(r["match"] for r in results)


def test_shipped_golden_io_matches_live_cobc_when_available(repo_root, tmp_path):
    """If cobc is present, the shipped golden_io.json must equal a live recompile
    of payroll.cob — proving the fallback is a faithful capture, not stale."""
    import shutil
    if shutil.which("cobc") is None:
        pytest.skip("cobc not installed; cannot revalidate golden capture")
    data = oracle.load_golden_fallback(str(repo_root / "src/sample/golden_io.json"))
    binary = oracle.compile_cobol(
        str(repo_root / "src/sample/payroll.cob"), str(tmp_path / "payroll")
    )
    for case in data["cases"]:
        live = oracle.run_binary(binary, case["input"])
        assert live == case["cobol"], (
            f"golden capture stale for input {case['input']!r}: "
            f"shipped={case['cobol']!r} live={live!r}"
        )
