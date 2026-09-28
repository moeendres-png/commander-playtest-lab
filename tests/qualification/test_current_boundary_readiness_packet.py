"""The readiness packet must agree with the artifacts it summarises.

A narrative packet drifts from its evidence unless something checks it. These
tests recompute the packet's load-bearing figures from the artifacts and require
the packet to state them, so a future evidence change that is not reflected in
the packet fails rather than silently shipping a stale claim.

They also pin the three things the packet must never do: name a winner, claim a
freeze, or claim a selection.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACKET = REPO / "docs/pre_freeze_completion_20260927/PROVIDER_READINESS_PACKET_20260928.md"
OUT = REPO / "qualification/final-current-boundary-20260927"
DENOMINATOR = 107

TEXT = PACKET.read_text(encoding="utf-8")


def _results(candidate: str) -> dict:
    return json.loads((OUT / f"FULL107_{candidate}_RESULTS.json").read_text(encoding="utf-8"))


def _matrix(candidate: str) -> dict[str, str]:
    document = json.loads((OUT / f"AF00_AF11_{candidate}.json").read_text(encoding="utf-8"))
    return {gate["gate"]: gate["verdict"] for gate in document["gates"]}


def _receipts() -> list[dict]:
    return [
        (path, json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((OUT / "receipts").glob("*.json"))
    ]


def test_packet_exists_and_is_substantial() -> None:
    assert len(TEXT) > 4000
    for heading in ("Source lock", "FULL107", "Semantic comparison", "AF00", "Blocker register"):
        assert heading in TEXT, heading


def test_full107_row_totals_are_stated_per_candidate() -> None:
    for candidate in ("XMage", "Forge"):
        results = _results(candidate.upper())
        assert len(results["rows"]) == DENOMINATOR
        assert sum(results["counts"].values()) == DENOMINATOR
        assert f"| {candidate} |" in TEXT
    assert "**107**" in TEXT


def test_packet_states_the_observed_counts_not_the_historical_ones() -> None:
    for candidate in ("XMage", "Forge"):
        counts = _results(candidate.upper())["counts"]
        # The observed row appears with its real values.
        assert (
            f"{counts['PASS']} | {counts['FAIL']} | {counts['UNKNOWN']} | {counts['BLOCKED']}"
            in TEXT
        ), (
            candidate,
            counts,
        )
    # The historical figures appear only as superseded context.
    assert "`30 PASS`" in TEXT and "`79 PASS`" in TEXT


def test_comparison_counts_are_stated() -> None:
    document = json.loads((OUT / "CURRENT_BOUNDARY_COMPARISON.json").read_text(encoding="utf-8"))
    dispositions = document["dispositions"]
    assert dispositions.get("SAME_SEMANTICS", 0) == 0, (
        "SAME_SEMANTICS is non-zero; the packet's zero claim must be revisited"
    )
    assert document["denominator"] == DENOMINATOR
    assert "| `SAME_SEMANTICS` | 0 |" in TEXT
    assert "| `NON_COMPARABLE` (evidence gap) | 107 |" in TEXT


def _packet_gate_row(gate: str) -> list[str]:
    """The two candidate verdicts the packet states for a gate, in column order."""
    for line in TEXT.splitlines():
        if not line.startswith(f"| {gate} "):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        # cells[0] is the gate and its name; cells[1] and cells[2] are XMage, Forge.
        return [cell.strip("*") for cell in cells[1:3]]
    raise AssertionError(f"the packet has no row for {gate}")


def test_every_af_verdict_in_the_packet_matches_the_artifact() -> None:
    """Each column must carry ITS candidate's verdict.

    An earlier version matched only the first column, so every Forge verdict was
    a false pass: AF01 is FAIL for XMage and PASS for Forge, and a first-column
    match would have credited Forge with XMage's result.
    """
    for column, candidate in enumerate(("XMage", "Forge")):
        matrix = _matrix(candidate.upper())
        for gate, verdict in matrix.items():
            stated = _packet_gate_row(gate)
            assert stated[column] == verdict, (
                f"{candidate} {gate}: packet states {stated[column]!r}, artifact says {verdict!r}"
            )


def test_the_two_candidate_columns_actually_differ_somewhere() -> None:
    """Guards the previous defect: a test that only ever read one column."""
    differing = [
        gate
        for gate in ("AF00", "AF01", "AF02", "AF03", "AF04", "AF11")
        if _packet_gate_row(gate)[0] != _packet_gate_row(gate)[1]
    ]
    assert differing, "no gate differs between candidates; the columns are not being read"


def test_receipt_counts_are_stated() -> None:
    receipts = _receipts()
    assert len(receipts) == 4
    for path, receipt in receipts:
        assert receipt["returncode"] == 0
        assert receipt["failed"] == 0 and receipt["errors"] == 0
        assert receipt["runner"]["dirty"] is False
        assert len(receipt["runner"]["input_digests"]) > 0
        # The packet's executing column must be the receipt's own value, not a
        # hand-written figure that can drift. It once said c2d9bafe while the
        # receipts said 4291377e, misidentifying the code that ran the suites.
        # The packet may abbreviate, so require the row to CARRY the receipt's
        # own value. It once named c2d9bafe for the XMage suites while the
        # receipts recorded 4291377e, misidentifying the code that ran them.
        row = next(
            (line for line in TEXT.splitlines() if line.startswith(f"| `{Path(str(path)).name}`")),
            None,
        )
        assert row is not None, f"the packet has no row for {path.name}"
        # The packet may abbreviate, so its cell must be a PREFIX of what the
        # receipt recorded. It once named c2d9bafe for the XMage suites while the
        # receipts recorded 4291377e, which is not a prefix of anything the run
        # executed.
        cells = [cell.strip().strip("*") for cell in row.strip().strip("|").split("|")]
        stated = cells[5].replace("Lab ", "").strip().strip("`").strip()
        assert stated, f"{path.name}: the packet row has no executing-commit cell"
        assert receipt["executed_commit"].startswith(stated), (
            f"the packet states {stated!r} as the executing commit for {path.name}, "
            f"which is not a prefix of the recorded {receipt['executed_commit'][:12]}"
        )
        assert str(receipt["tests"]) in row and str(receipt["passed"]) in row, path.name


def test_packet_names_no_winner() -> None:
    for forbidden in (
        "selected provider",
        "chosen provider",
        "recommended provider",
        "better engine",
        "wins over",
    ):
        assert forbidden not in TEXT.lower(), forbidden


def test_packet_never_claims_a_selection_or_a_freeze() -> None:
    assert "PRODUCTION_PROVIDER = NOT SELECTED" in TEXT
    assert "ARCHITECTURE_FREEZE = NOT CLAIMED" in TEXT
    assert "PROVIDER_SELECTION_READY = NO" in TEXT
    assert "ARCHITECTURE_FREEZE_READY_FOR_COORDINATOR = NO" in TEXT
    # The affirmative forms must never appear as claims.
    assert "PRODUCTION_PROVIDER = SELECTED" not in TEXT
    assert "ARCHITECTURE_FREEZE = CLAIMED" not in TEXT
    assert "ARCHITECTURE_FREEZE_READY_FOR_COORDINATOR = YES" not in TEXT


def test_packet_binds_the_four_forge_identities_separately() -> None:
    for commit in (
        "ef958ee91ac6c9ce0152189f2654bf6e05abf273",
        "e15f37d6b2b5c0ad682948f86f037e07b6aaded5",
        "4753bb7c72ea60d653121e0bab989077b4009f9c",
        "a37a865a53280dd8ad6fad3384d69611e8c5a42f",
    ):
        assert commit in TEXT, commit
    assert "none is collapsed into a" in TEXT.lower()


def test_packet_records_the_two_decision_critical_defects() -> None:
    assert "accepted" in TEXT.lower() and "Hill Giant" in TEXT
    assert "ENGINE_CANDIDATE_DEFECT" in TEXT
    assert "byte-identical" in TEXT
    assert "UNCONTROLLED_ENGINE_RNG" in TEXT
    assert "accepted" in TEXT.lower()
    assert "require both refusals" in TEXT.lower() or "require both" in TEXT.lower()


def test_packet_states_the_pb_classifications() -> None:
    for marker in (
        "PB-03 starting-state classification",
        "PB-05 build provenance",
        "PB-06 per-scenario hidden channels",
        "PB-07 effective 29-card corpus",
        "PB-08 clean-process replay twin",
        "PB-09 Forge candidate identity",
    ):
        assert marker in TEXT, marker
    assert "RESOLVED" in TEXT
    assert "OPEN — RESERVED" in TEXT or "OPEN - RESERVED" in TEXT


def test_seed_position_is_reported_per_candidate() -> None:
    """A blanket "no seed was sent" was false for Forge.

    XMage reports `seed_supported: false` and genuinely sends nothing. Forge
    reports `seed_supported: true`, the driver sends the seed, and the observed
    state carries `rng_binding.root_seed` with the Rules call count. Forge's gap
    is the missing create-response echo, which is a narrower and different gap.
    """
    af01 = {
        candidate: json.loads((OUT / f"AF01_{candidate}.json").read_text(encoding="utf-8"))
        for candidate in ("XMAGE", "FORGE")
    }
    reported = {
        candidate: document["capabilities_provider_reported"]["seed_supported"]
        for candidate, document in af01.items()
    }
    assert reported["XMAGE"] is False
    assert reported["FORGE"] is True, "the packet's Forge seed claim depends on this"

    # Forge's observed state must actually carry a bound root seed.
    hidden = json.loads((OUT / "HIDDEN_INFO_FORGE.json").read_text(encoding="utf-8"))
    state = json.dumps(hidden)
    assert "explicit_seed" in state
    assert "root_seed" in state
    assert "424242" in state

    # The packet must not make the blanket claim for both.
    assert "Rules RNG is uncontrolled on both candidates" not in TEXT
    assert "the two candidates are in different states" in TEXT
    assert "Forge — seed sent and state-bound" in TEXT
    assert "XMage — fully uncontrolled" in TEXT
    assert "393" in TEXT
