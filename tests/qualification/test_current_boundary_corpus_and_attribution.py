"""Two P2 findings on the readiness packet and the corpus evidence.

1. Corpus completion was derived from the DECLARED name count, so appending 29
   names would have advertised a complete runtime corpus with no probe behind it.
   It also counted `len(deck_identity)`, which is a per-seat deck count and says
   nothing about cards. Completion must derive from behaviourally executed cards.

2. Block attribution was candidate-blind. The shared reason cited the XMage
   bridge's `starting_state_injection_supported=false` for every candidate, while
   `AF01_FORGE.json` reports `starting_state_injection_supported: true` and
   `scenario_injection_supported: true`. Forge's 44 blocked rows are therefore a
   Lab EXECUTION-PATH gap, not a Forge capability gap, and a blanket "these are
   candidate gaps" statement would misdirect remediation away from the work that
   would actually unblock them.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts/run_current_boundary_qualification.py"
PACKET = REPO / "docs/pre_freeze_completion_20260927/PROVIDER_READINESS_PACKET_20260928.md"
OUT = REPO / "qualification/final-current-boundary-20260927"

SOURCE = RUNNER.read_text(encoding="utf-8")
PACKET_TEXT = PACKET.read_text(encoding="utf-8")


def test_corpus_completion_is_not_derived_from_the_name_count() -> None:
    assert '"complete": not (set(frozen_corpus) - covered_corpus)' in SOURCE
    assert '"missing_identities": sorted(set(frozen_corpus) - covered_corpus)' in SOURCE
    # Only identities the frozen contract requires may count toward completion.
    assert "behaviourally_executed_cards & set(frozen_corpus)" in SOURCE


def test_corpus_does_not_count_decks_as_cards() -> None:
    """deck_identity is one entry per seat, not one per card."""
    assert '"imported_at_runtime": len(hidden_game.deck_identity)' not in SOURCE
    assert '"decks_imported_at_runtime": len(hidden_game.deck_identity)' in SOURCE
    assert '"behaviorally_executed_count": len(covered_corpus)' in SOURCE
    assert '"behaviorally_executed_count": len(covered_corpus)' in SOURCE


def test_executed_cards_come_from_a_passing_probe_not_a_list() -> None:
    assert 'card_result.outcome == "PASS"' in SOURCE
    assert 'card_result.evidence or {}).get("executed_cards")' in SOURCE
    # It must read the row RESULT. by_id holds materialization records, which
    # carry no outcome, so reading it there raises KeyError at runtime.
    assert 'row.fixture_id == "CARD_02"' in SOURCE


def test_block_attribution_reads_the_candidate_capability() -> None:
    assert 'identity.get("starting_state_injection_supported")' in SOURCE
    assert "LAB EXECUTION-PATH" in SOURCE
    assert "this is a LAB EXECUTION-PATH " in SOURCE
    assert "gap rather than a candidate capability gap" in SOURCE


def test_runner_carries_the_declared_capabilities_into_the_identity() -> None:
    assert 'identity["starting_state_injection_supported"] = declared.get(' in SOURCE
    assert '"capabilities_provider_reported"' in SOURCE


def test_no_single_candidate_is_named_as_the_reason_for_all() -> None:
    """The retired reason hard-cited XMage for every candidate."""
    for line in SOURCE.splitlines():
        if "starting_state_injection_supported=false" in line:
            assert line.strip().startswith("#"), line.strip()[:90]


def test_packet_attributes_per_candidate() -> None:
    assert "attribution is per candidate" in PACKET_TEXT.lower()
    assert "Forge needs the Lab to exercise" in PACKET_TEXT
    assert "a **Lab execution-path gap**" in PACKET_TEXT


def test_packet_does_not_exclude_further_harness_work() -> None:
    assert "None of these is blocked on further harness work" not in PACKET_TEXT
    assert "Closing Forge's rows is Lab work" in PACKET_TEXT


def test_packet_explains_the_corpus_derivation() -> None:
    assert "behaviourally executed" in PACKET_TEXT
    assert "per-seat deck count" in PACKET_TEXT
    assert "appending 29 names" in PACKET_TEXT


def test_artifact_corpus_uses_the_derived_fields_when_present() -> None:
    import json

    for candidate in ("XMAGE", "FORGE"):
        path = OUT / f"ACTUAL_CARD_{candidate}.json"
        if not path.is_file():
            continue
        corpus = json.loads(path.read_text(encoding="utf-8"))["required_29_card_corpus"]
        if "behaviorally_executed_cards" not in corpus:
            # Stale artifact from before this change; the next run rewrites it.
            # Assert only that it is not yet claiming the new derivation.
            assert "imported_at_runtime" in corpus, candidate
            continue
        assert "behaviorally_executed_cards" in corpus, candidate
        assert "decks_imported_at_runtime" in corpus, candidate
        assert corpus["complete"] is (corpus["behaviorally_executed_count"] >= 29), candidate
