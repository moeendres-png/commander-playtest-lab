from __future__ import annotations

import pytest

from commander_lab.whole_deck.oracle_fact_verification import (
    ORACLE_TEXT_LEGITIMATELY_EMPTY,
    OracleFactVerificationError,
    validate_verified_empty_fact,
)


def _verification() -> dict[str, object]:
    return {
        "oracle_name": "Verified Vanilla",
        "mana_cost": "{1}{U}",
        "mana_value": 2,
        "type_line": "Creature — Fish",
        "color_identity": "U",
        "oracle_rules_text": "",
        "oracle_text_classification": ORACLE_TEXT_LEGITIMATELY_EMPTY,
        "canonical_source_id": "inventory row | Scryfall https://scryfall.com/card/example",
        "canonical_verification_status": "verified_from_canonical_source_2026-08-07",
    }


def _current_fact() -> dict[str, object]:
    return {
        "oracle_name": "Verified Vanilla",
        "mana_cost": "{1}{U}",
        "mana_value": 2.0,
        "type_line": "Creature — Fish",
        "color_identity": ["U"],
        "oracle_text": None,
    }


def test_verified_empty_fact_accepts_matching_current_fact() -> None:
    validate_verified_empty_fact("Verified Vanilla", _verification(), _current_fact())


def test_verified_empty_fact_fails_closed_if_rules_text_appears() -> None:
    current = _current_fact()
    current["oracle_text"] = "Flying"

    with pytest.raises(OracleFactVerificationError, match="current_rules_text_is_now_nonempty"):
        validate_verified_empty_fact("Verified Vanilla", _verification(), current)


def test_verified_empty_fact_fails_closed_on_identity_fact_drift() -> None:
    current = _current_fact()
    current["mana_value"] = 3.0

    with pytest.raises(OracleFactVerificationError, match="mana_value"):
        validate_verified_empty_fact("Verified Vanilla", _verification(), current)


def test_verified_empty_fact_requires_verified_scryfall_backed_provenance() -> None:
    verification = _verification()
    verification["canonical_source_id"] = "unverified local note"

    with pytest.raises(
        OracleFactVerificationError, match="verification_source_not_scryfall_backed"
    ):
        validate_verified_empty_fact("Verified Vanilla", verification, _current_fact())
