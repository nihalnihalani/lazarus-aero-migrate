"""
LAZARUS — Differential oracle (skeleton).

The judge-proofing core: prove the migrated Python is equivalent to the ORIGINAL
COBOL by running the real COBOL via GnuCOBOL and diffing outputs byte-for-byte.

Runs inside the Managed Agent sandbox (the agent invokes this), but is kept as a
standalone module so the harness logic is reviewable and testable locally.
"""
from __future__ import annotations

import json
import pathlib
import subprocess


def compile_cobol(cobol_path: str, binary_out: str = "/tmp/legacy") -> str:
    """Compile COBOL to a native binary with GnuCOBOL. Returns binary path."""
    subprocess.run(["cobc", "-x", "-o", binary_out, cobol_path], check=True)
    return binary_out


def run_binary(binary: str, stdin_text: str) -> str:
    """Run a compiled program on one input, return stdout (the canonical output)."""
    proc = subprocess.run(
        [binary], input=stdin_text, capture_output=True, text=True, check=True
    )
    return proc.stdout


def run_python(py_path: str, stdin_text: str) -> str:
    proc = subprocess.run(
        ["python", py_path], input=stdin_text, capture_output=True, text=True, check=True
    )
    return proc.stdout


def differential_test(cobol_path: str, py_path: str, input_battery: list[str]) -> list[dict]:
    """
    For each input: COBOL output is GROUND TRUTH; assert Python matches byte-for-byte.
    Returns a list of {input, cobol, python, match} for the UI diff viewer.
    """
    binary = compile_cobol(cobol_path)
    results = []
    for stdin_text in input_battery:
        cobol_out = run_binary(binary, stdin_text)
        py_out = run_python(py_path, stdin_text)
        results.append(
            {
                "input": stdin_text,
                "cobol": cobol_out,
                "python": py_out,
                "match": cobol_out == py_out,   # the falsifiable check
            }
        )
    return results


def load_golden_fallback(path: str = "src/sample/golden_io.json") -> list[dict]:
    """Fallback if GnuCOBOL/apt is gated in preview: pre-captured COBOL I/O pairs."""
    return json.loads(pathlib.Path(path).read_text())


if __name__ == "__main__":
    battery = ["1000.00\n", "0.01\n", "999999.99\n"]  # decimal/rounding edge cases
    out = differential_test("src/sample/payroll.cob", "payroll.py", battery)
    passed = sum(r["match"] for r in out)
    print(f"{passed}/{len(out)} equivalent to original COBOL")
