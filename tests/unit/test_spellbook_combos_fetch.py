"""Unit tests for the Spellbook fetch script's variant selection (issue #1378)."""

from __future__ import annotations

from scripts.spellbook_combos_fetch import _select_variants, _Variant

_COMMANDER = "Chulane, Teller of Tales"
_CORPUS_KEYS = {"card alpha", "card beta"}


def _variant(variant_id: str, produces: tuple[str, ...]) -> _Variant:
    return _Variant(
        variant_id=variant_id,
        identity="WUG",
        status="OK",
        spoiler=False,
        commander_legal=True,
        names=("Card Alpha", "Card Beta"),
        foreign_commander=False,
        produces=produces,
        edhrec_decks=None,
    )


def test_produceless_variant_does_not_consume_its_card_set() -> None:
    facts = [_variant("0001", ()), _variant("0002", ("Infinite mana",))]
    generated, counts = _select_variants(
        facts,
        corpus_keys=set(_CORPUS_KEYS),
        preserved_sets=set(),
        commander=_COMMANDER,
        note="test note",
    )
    assert [entry["combo_id"] for entry in generated] == ["chulane-sb-0002"]
    assert counts["no_produces"] == 1
    assert counts["same_cardset_merged"] == 0
    assert counts["kept"] == 1


def test_duplicate_of_a_kept_variant_still_merges() -> None:
    facts = [_variant("0001", ("Infinite mana",)), _variant("0002", ("Infinite mana",))]
    generated, counts = _select_variants(
        facts,
        corpus_keys=set(_CORPUS_KEYS),
        preserved_sets=set(),
        commander=_COMMANDER,
        note="test note",
    )
    assert [entry["combo_id"] for entry in generated] == ["chulane-sb-0001"]
    assert counts["same_cardset_merged"] == 1
    assert counts["kept"] == 1
