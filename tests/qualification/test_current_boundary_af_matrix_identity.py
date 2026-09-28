"""The AF matrix must read each candidate's own identity, never a leaked one.

`expected_engine_commit` was assigned in the per-candidate assembly loop and then
read in the AF matrix loop, which runs afterwards. It therefore held the LAST
candidate's commit for both candidates, so XMage's AF00 was compared against
Forge's expected commit and reported FAIL for a reason that had nothing to do with
XMage. Both gates are PASS once the identity is read per candidate.

These tests pin the binding structurally, because the value looked plausible: a
40-hex string from the right file, just the wrong one.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ASSEMBLER = REPO / "scripts/assemble_current_boundary_evidence.py"
SOURCE = ASSEMBLER.read_text(encoding="utf-8")


def test_af_matrix_reads_the_per_candidate_identity() -> None:
    assert '"results_runtime_identity"' in SOURCE
    assert 'data["results_runtime_identity"].get(' in SOURCE


def test_af_matrix_does_not_read_a_loop_carried_identity() -> None:
    """No `results[...]` reference may leak into the AF matrix body."""
    start = SOURCE.index("for candidate, data in per_candidate.items():")
    body = SOURCE[start:]
    assert "expected_engine_commit = results[" not in body, (
        "the AF matrix must not read the previous loop's `results` variable"
    )


def test_candidate_identity_is_bound_per_candidate() -> None:
    start = SOURCE.index("per_candidate[candidate] = {")
    entry = SOURCE[start : start + 600]
    assert '"results_runtime_identity": results["runtime_identity"]' in entry


def test_source_lock_verdict_is_still_the_af00_derivation() -> None:
    assert "source_lock_verdict(af01, expected_engine_commit)" in SOURCE


def test_af00_compares_reported_against_expected_not_the_reverse() -> None:
    start = SOURCE.index("def source_lock_verdict(")
    body = SOURCE[start : start + 1200]
    assert "reported != expected" in body or "reported == expected" in body
    # Absent identity is UNKNOWN, never PASS and never FAIL.
    assert "if not reported:" in body
    assert 'return "UNKNOWN"' in body
