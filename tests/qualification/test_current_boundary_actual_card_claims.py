"""The actual-card artifact must not assert what the run did not observe.

`ACTUAL_CARD_*.json` carried a prose claim: "the engine itself rejected an illegal
colour identity and unknown card names during this run, proving the import is
engine-validated". The bound-source run showed the opposite for Forge: the executed
bridge ACCEPTED a colour-identity violation and a non-Commander commander. A prose
claim that contradicts the run's own evidence is a false credit in exactly the class
this workstream exists to remove, and it was sitting in a decision-relevant artifact.

The corpus completeness figure was also a pointer to prose rather than a number, so
the 29-card shortfall could not be read off the artifact.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts/run_current_boundary_qualification.py"
OUT = REPO / "qualification/final-current-boundary-20260927"


def test_the_refusal_statement_is_conditional_not_unconditional() -> None:
    """A statement may say the engine refused, but only when it did.

    The defect was an UNCONDITIONAL prose claim that the engine rejected an
    illegal colour identity, which the Forge run contradicted. Saying it
    conditionally, on the observed verdict, is the fix; saying it at all is not.
    """
    source = RUNNER.read_text(encoding="utf-8")
    start = source.index("af03_evidence = {")
    end = source.index("# ----", start)
    block = source[start:end]
    assert '"statement"' in block
    # The statement is selected by the observed verdict, not asserted outright.
    assert 'if af03.verdict == "PASS"' in block
    assert "else" in block
    assert "did NOT refuse" in block
    # The retirement comment must still record what the old claim said.
    assert "the engine itself rejected" in source


def test_no_unconditional_prose_claim_remains() -> None:
    """The old string may only survive inside a comment recording its removal."""
    source = RUNNER.read_text(encoding="utf-8")
    for line in source.splitlines():
        if "proving the import is" in line or "the engine itself rejected" in line:
            assert line.strip().startswith("#"), line.strip()[:90]


def test_engine_validated_is_a_derived_mapping() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert '"engine_validated": af03_evidence,' in source
    assert "af03_evidence = {" in source
    # It must carry the probe verdicts, not a sentence.
    for key in ('"verdict"', '"probes_passed"', '"probes_failed"', '"probes_unknown"'):
        assert key in source, key


def test_corpus_shortfall_is_a_number_not_a_prose_pointer() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "see ACTUAL_CARD_DENOMINATOR note in FINAL_HANDOFF" not in source
    assert "def frozen_actual_card_corpus() -> tuple[str, ...]:" in source
    assert "ACTUAL_CARD_DOMAIN_MANIFEST" in source
    assert "regression_corpus_29" in source
    assert '"required_count": len(frozen_corpus),' in source
    # Completion is measured against the frozen identities. An earlier version
    # compared the declared NAME count, so appending 29 names would have
    # advertised a complete runtime corpus with no probe behind it.
    assert '"complete": not (set(frozen_corpus) - covered_corpus)' in source
    assert '"missing_identities": sorted(set(frozen_corpus) - covered_corpus)' in source
    assert "behaviourally_executed_cards & set(frozen_corpus)" in source
    assert '"behaviorally_executed_count": len(covered_corpus)' in source


def test_card_list_is_declared_once() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "ACTUAL_CARD_NAMES: tuple[str, ...] = (" in source
    # The list must not also be inlined at the artifact site, or the corpus count
    # would be restated rather than derived.
    assert '"cards": list(ACTUAL_CARD_NAMES)' in source
    # Declared exactly once, so the two sites cannot drift apart.
    assert source.count("ACTUAL_CARD_NAMES: tuple[str, ...] = (") == 1


def test_artifact_reports_observed_refusals_when_present() -> None:
    for candidate in ("XMAGE", "FORGE"):
        path = OUT / f"ACTUAL_CARD_{candidate}.json"
        if not path.is_file():
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        evidence = document["engine_validated"]
        if isinstance(evidence, str):
            continue  # stale artifact from before this change; the runner rewrites it
        assert "verdict" in evidence, candidate
        if evidence["verdict"] != "PASS":
            assert evidence["probes_failed"] or evidence["probes_unknown"], candidate
            assert "did NOT refuse" in evidence["statement"], candidate


def test_corpus_artifact_states_the_shortfall() -> None:
    for candidate in ("XMAGE", "FORGE"):
        path = OUT / f"ACTUAL_CARD_{candidate}.json"
        if not path.is_file():
            continue
        corpus = json.loads(path.read_text(encoding="utf-8"))["required_29_card_corpus"]
        if isinstance(corpus, str):
            continue
        assert corpus["required_count"] == 29, candidate
        if "behaviorally_executed_count" in corpus:
            assert corpus["complete"] is (corpus["behaviorally_executed_count"] >= 29), candidate
