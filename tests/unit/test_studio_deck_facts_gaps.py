"""Data gaps: EDHREC lookup by card name, the audit note and thin cohorts (#1404)."""

from __future__ import annotations

from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, deck_facts

from .test_studio_builder import _fill
from .test_studio_deck_facts import _row


def _observe(store: StudioStore, name: str, card_id: str | None, value: float | None) -> None:
    source = store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0]
    store.connection.execute(
        "INSERT INTO observation(card_id, card_name, metric, cohort, value, numerator, "
        "denominator, data_class, source_id) VALUES (?, ?, 'inclusion_pct', 'edhrec:test', ?, "
        "1, 10, 'ORIGINAL_SOURCE', ?)",
        (card_id, name, value, source),
    )
    store.connection.commit()


def test_edhrec_lookup_finds_front_face_names_without_card_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import universe

    store = StudioStore.open(tmp_path / "studio")
    monkeypatch.setattr(
        universe,
        "_card_name_index",
        lambda _store: (
            {
                "Brazen Borrower // Petty Theft": frozenset(
                    {"brazen borrower // petty theft", "brazen borrower"}
                )
            },
            {
                "brazen borrower // petty theft": "Brazen Borrower // Petty Theft",
                "brazen borrower": "Brazen Borrower // Petty Theft",
            },
        ),
    )
    _fill(store, tmp_path)
    _observe(store, "Brazen Borrower", None, 12.5)
    _observe(store, "Linked Card", "card:project:0002", 9.0)
    _observe(store, "Empty Value", None, None)
    store.bind_unbound("Test Commander")
    lookup = deck_facts.edhrec_lookup(store, ["Test Commander"])
    assert lookup is not None
    assert lookup("x", "Brazen Borrower // Petty Theft")  # front face of a two-name card
    assert lookup("x", "brazen borrower")  # case-insensitive
    assert lookup("card:project:0002", "Other Spelling")  # linked by card id as before
    assert not lookup("y", "Empty Value")  # a NULL value is no observation
    assert not lookup("y", "Fleetfoot Panther")
    assert deck_facts.edhrec_lookup(store, ["Other Commander"]) is None
    store.close()


def test_edhrec_lookup_never_credits_a_card_through_a_shared_front_face(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import universe

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    _observe(store, "Fire", None, 8.0)  # the single-faced card Fire
    _observe(store, "Shared Front", None, 7.0)  # front face of two different cards
    _observe(store, "Solo Front", None, 6.0)  # front face of exactly one card
    store.bind_unbound("Test Commander")
    # "fire" names the card Fire; "shared front" names two cards (absent from `unique`).
    by_oracle = {
        "Fire": frozenset({"fire"}),
        "Fire // Ice": frozenset({"fire // ice"}),
        "Solo Front // Back": frozenset({"solo front // back", "solo front"}),
    }
    unique = {"fire": "Fire", "fire // ice": "Fire // Ice", "solo front": "Solo Front // Back"}
    monkeypatch.setattr(universe, "_card_name_index", lambda _store: (by_oracle, unique))
    lookup = deck_facts.edhrec_lookup(store, ["Test Commander"])
    assert lookup is not None
    assert lookup("x", "Fire")
    assert not lookup("x", "Fire // Ice")  # the observation belongs to Fire, not to Fire // Ice
    assert lookup("x", "Solo Front // Back")  # a front face owned by one card credits that card
    assert not lookup("x", "Shared Front // Other")  # a shared front face credits no card
    store.close()


def _gap_rows() -> list[dict[str, object]]:
    return [
        _row("cmd", "Chief", zone="commander"),
        _row("a", "Tuned Zero"),
        _row("b", "All Thin"),
        _row("c", "Fine Card"),
        _row("d", "No Deck Card"),
        _row("f", "Forest", type_line="Basic Land — Forest", is_basic_land=1),
    ]


def test_thin_in_cohort_names_n_of_n_and_keeps_zero_apart_from_unknown() -> None:
    hits = {
        "Tuned Zero": {"all": 200, "tuned": 0},
        "All Thin": {"all": 5, "tuned": 50},
        "Fine Card": {"all": 100, "tuned": 100},
    }
    gaps = deck_facts.data_gaps(
        _gap_rows(),
        roles={x: ["r"] for x in "abcdf"},
        in_source_decks=lambda name: name in hits,
        has_edhrec=lambda card_id, name: True,
        cohort_hits=hits,
        cohort_sizes={"all": 1500, "tuned": 1064},
    )
    by_card = {item["name"]: item for item in gaps["gaps"]}
    assert set(by_card) == {"Tuned Zero", "All Thin", "No Deck Card"}
    assert by_card["Tuned Zero"]["reasons"] == []  # a note, not a missing datum
    assert by_card["Tuned Zero"]["thin"] == [{"cohort": "tuned", "n": 0, "of": 1064}]
    assert by_card["All Thin"]["thin"] == [{"cohort": "all", "n": 5, "of": 1500}]
    # No source deck at all stays unknown and gets no cohort count.
    assert by_card["No Deck Card"]["reasons"] == ["no_source_deck"]
    assert "thin" not in by_card["No Deck Card"]
    assert gaps["by_reason"]["thin_in_cohort"] == {"count": 2, "of": 3}
    assert gaps["by_reason"]["no_source_deck"] == {"count": 1, "of": 4}
    # A thin count is a note about the sample, not a missing datum.
    assert gaps["cards_with_gaps"] == 1
    assert gaps["cards_with_thin"] == 2


def test_thin_in_cohort_is_off_without_cohort_data() -> None:
    gaps = deck_facts.data_gaps(
        _gap_rows(),
        roles={x: ["r"] for x in "abcdf"},
        in_source_decks=lambda name: True,
        has_edhrec=lambda card_id, name: True,
    )
    assert "thin_in_cohort" not in gaps["by_reason"]
    assert gaps["gaps"] == []


def test_edhrec_reason_text_names_audit_source_and_date_only_when_given() -> None:
    plain = deck_facts.data_gaps(
        _gap_rows(), roles={}, in_source_decks=None, has_edhrec=lambda c, n: False
    )
    assert "Mindestquote" not in plain["reason_labels"]["no_edhrec"]
    audited = deck_facts.data_gaps(
        _gap_rows(),
        roles={},
        in_source_decks=None,
        has_edhrec=lambda c, n: False,
        edhrec_note=deck_facts.EDHREC_THRESHOLD_NOTE,
    )
    text = audited["reason_labels"]["no_edhrec"]
    assert "Mindestquote" in text and "2026-11-12" in text
    assert "%" not in text  # no number the audit text does not carry for the card
