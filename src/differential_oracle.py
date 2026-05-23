"""
LAZARUS — Differential oracle.

The judge-proofing core: prove the migrated Python is equivalent to the ORIGINAL
COBOL by running the real COBOL via GnuCOBOL and diffing outputs byte-for-byte.

Runs inside the Managed Agent sandbox (the agent invokes this), but is kept as a
standalone module so the harness logic is reviewable and testable locally.

Two modes:
  * differential_test()        — live: compile + run real COBOL as ground truth.
  * differential_test_golden() — fallback: diff Python against pre-captured COBOL
                                 outputs (src/sample/golden_io.json) when GnuCOBOL
                                 is unavailable on stage. Same falsifiable guarantee.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys


def compile_cobol(cobol_path: str, binary_out: str = "/tmp/legacy") -> str:
    """Compile COBOL to a native binary with GnuCOBOL. Returns binary path.

    Raises RuntimeError if `cobc` is not installed, or CalledProcessError if the
    source fails to compile.
    """
    if shutil.which("cobc") is None:
        raise RuntimeError(
            "GnuCOBOL (cobc) not found. Install it (apt-get install -y gnucobol / "
            "brew install gnucobol) or use the golden_io.json fallback."
        )
    subprocess.run(
        ["cobc", "-x", "-o", binary_out, cobol_path],
        check=True,
        capture_output=True,
        text=True,
    )
    return binary_out


def run_binary(binary: str, stdin_text: str) -> str:
    """Run a compiled program on one input, return stdout (the canonical output)."""
    proc = subprocess.run(
        [binary], input=stdin_text, capture_output=True, text=True, check=True
    )
    return proc.stdout


def run_python(py_path: str, stdin_text: str) -> str:
    """Run a Python translation on one input, return stdout.

    Uses sys.executable (the running interpreter) rather than a bare "python",
    which may not exist on every host.
    """
    proc = subprocess.run(
        [sys.executable, py_path],
        input=stdin_text,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout


def _diff_record(stdin_text: str, cobol_out: str, py_out: str) -> dict:
    """One row for the UI diff viewer; `match` is the falsifiable equivalence check."""
    return {
        "input": stdin_text,
        "cobol": cobol_out,
        "python": py_out,
        "match": cobol_out == py_out,
    }


def differential_test(cobol_path: str, py_path: str, input_battery: list[str]) -> list[dict]:
    """
    For each input: COBOL output is GROUND TRUTH; assert Python matches byte-for-byte.
    Returns a list of {input, cobol, python, match} for the UI diff viewer.
    """
    binary = compile_cobol(cobol_path)
    return [
        _diff_record(stdin_text, run_binary(binary, stdin_text), run_python(py_path, stdin_text))
        for stdin_text in input_battery
    ]


def differential_test_golden(py_path: str, golden_path: str = "src/sample/golden_io.json") -> list[dict]:
    """
    Fallback equivalence check used when GnuCOBOL is unavailable live.

    Diffs the Python translation's output against pre-captured COBOL outputs
    (the ground truth recorded from a real `cobc` run). Same {input, cobol,
    python, match} record shape as differential_test, so the UI is identical.
    """
    golden = load_golden_fallback(golden_path)
    return [
        _diff_record(case["input"], case["cobol"], run_python(py_path, case["input"]))
        for case in golden["cases"]
    ]


def load_golden_fallback(path: str = "src/sample/golden_io.json") -> dict:
    """Load pre-captured COBOL I/O pairs (the demo fallback when GnuCOBOL is gated).

    Returns the parsed JSON object: {"program", "captured_with", "cases": [...]}.
    Raises FileNotFoundError if the file is missing.
    """
    return json.loads(pathlib.Path(path).read_text())


def run(cobol_path: str, py_path: str, input_battery: list[str],
        golden_path: str = "src/sample/golden_io.json") -> list[dict]:
    """Run the live oracle if GnuCOBOL is available, else the golden fallback.

    This is the single entry point the agent/UI calls: it transparently degrades
    to the captured-output path so the demo never hard-fails on a missing compiler.
    """
    if shutil.which("cobc") is not None:
        return differential_test(cobol_path, py_path, input_battery)
    return differential_test_golden(py_path, golden_path)


if __name__ == "__main__":
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    cobol = str(repo_root / "src/sample/payroll.cob")
    py = str(repo_root / "src/sample/payroll.py")
    golden = str(repo_root / "src/sample/golden_io.json")

    if not pathlib.Path(py).exists():
        # No migrated module yet (the agent writes it at run time). Demonstrate the
        # harness end-to-end by diffing the golden capture against itself.
        data = load_golden_fallback(golden)
        mode = "live cobc" if shutil.which("cobc") else "golden fallback"
        print(f"[oracle] no payroll.py yet; smoke-checking golden capture ({mode})")
        print(f"[oracle] loaded {len(data['cases'])} captured COBOL I/O pairs "
              f"from {data.get('program', '?')}")
        for c in data["cases"]:
            print(f"    IN={c['input']!r:>14}  ->  COBOL={c['cobol']!r}")
        raise SystemExit(0)

    battery = [c["input"] for c in load_golden_fallback(golden)["cases"]]
    results = run(cobol, py, battery, golden)
    passed = sum(r["match"] for r in results)
    for r in results:
        flag = "OK " if r["match"] else "XX "
        print(f"{flag} IN={r['input']!r:>14}  COBOL={r['cobol']!r}  PY={r['python']!r}")
    print(f"\n{passed}/{len(results)} equivalent to original COBOL")
    raise SystemExit(0 if passed == len(results) else 1)
