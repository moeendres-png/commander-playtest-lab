"""Combo shells (#1366): spellbook variants deduplicated onto the combo (shell)
they belong to. The fixtures mirror the shape of the Commander Spellbook bulk
export (``variants.json``): a variant carries the combo it belongs to in ``of``,
its cards in ``uses``, generic slots in ``requires`` and its colour identity in
``identity``."""

from __future__ import annotations

from commander_lab.studio import spellbook_shells

POOL = {"Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Commander Card"}


def _variant(
    variant_id: str,
    shell: int,
    cards: list[str],
    *,
    identity: str = "GWU",
    commander: bool = False,
    templates: int = 0,
    also_of: tuple[int, ...] = (),
) -> dict[str, object]:
    return {
        "id": variant_id,
        "of": [{"id": shell}, *({"id": other} for other in also_of)],
        "identity": identity,
        "uses": [
            {"card": {"name": name}, "mustBeCommander": bool(commander and index == 0)}
            for index, name in enumerate(cards)
        ],
        "requires": [
            {"template": {"id": 100 + index}, "mustBeCommander": False}
            for index in range(templates)
        ],
    }


def _index(*records: dict[str, object]) -> dict[str, spellbook_shells.VariantFacts]:
    return spellbook_shells.build_variant_index(records, [])


def test_variants_of_one_shell_count_once() -> None:
    # Three functionally identical variants of one combo (the Pitiless Plunderer
    # pattern: 19 printed variants, one shell) count as one shell, not three.
    index = _index(
        _variant("1-2-3", 42, ["Alpha", "Beta", "Gamma"]),
        _variant("1-2-4", 42, ["Alpha", "Beta", "Delta"]),
        _variant("1-2-5", 42, ["Alpha", "Beta", "Epsilon"]),
    )
    counts = spellbook_shells.count_shells(["1-2-3", "1-2-4", "1-2-5"], index, POOL)
    assert counts.shells == 1
    assert counts.shell_ids == (42,)


def test_two_shells_count_two() -> None:
    index = _index(
        _variant("1-2", 7, ["Alpha", "Beta"]),
        _variant("1-3-4", 9, ["Alpha", "Gamma", "Delta"]),
    )
    counts = spellbook_shells.count_shells(["1-2", "1-3-4"], index, POOL)
    assert counts.shells == 2
    assert counts.two_card == 1
    assert counts.three_plus == 1


def test_shell_outside_the_commander_identity_counts_zero() -> None:
    # The identity test runs per variant: a black variant of the shell does not
    # qualify for Chulane (WUG) even though the shell also has a WUG variant the
    # card is not part of.
    index = _index(_variant("1-2-3", 42, ["Alpha", "Beta", "Gamma"], identity="BGU"))
    counts = spellbook_shells.count_shells(["1-2-3"], index, POOL)
    assert counts.shells == 0


def test_shell_with_a_partner_outside_the_pool_counts_zero() -> None:
    index = _index(_variant("1-2-9", 42, ["Alpha", "Beta", "Outsider"]))
    counts = spellbook_shells.count_shells(["1-2-9"], index, POOL)
    assert counts.shells == 0


def test_template_slots_count_towards_the_card_count() -> None:
    # Two named cards plus one generic template slot are a three-card combo.
    index = _index(_variant("1-2--7", 42, ["Alpha", "Beta"], templates=1))
    counts = spellbook_shells.count_shells(["1-2--7"], index, POOL)
    assert counts.shells == 1
    assert counts.two_card == 0
    assert counts.three_plus == 1


def test_commander_shells_are_counted_apart() -> None:
    index = _index(
        _variant("1-2", 7, ["Alpha", "Beta"], commander=True),
        _variant("1-3-4", 9, ["Alpha", "Gamma", "Delta"]),
    )
    counts = spellbook_shells.count_shells(["1-2", "1-3-4"], index, POOL)
    assert counts.with_commander == 1


def test_a_renamed_variant_resolves_through_the_alias_table() -> None:
    record = _variant("10-20", 7, ["Alpha", "Beta"])
    aliases = [{"id": "9-20", "variant": {"id": "10-20"}}]
    index = spellbook_shells.build_variant_index([record], aliases)
    counts = spellbook_shells.count_shells(["9-20"], index, POOL)
    assert counts.shells == 1


def test_unknown_and_retired_variants_are_ignored() -> None:
    record = _variant("10-20", 7, ["Alpha", "Beta"])
    aliases = [{"id": "8-20", "variant": None}]  # retired without a successor
    index = spellbook_shells.build_variant_index([record], aliases)
    counts = spellbook_shells.count_shells(["8-20", "404-404"], index, POOL)
    assert counts.shells == 0
    assert counts.two_card == 0
    assert counts.three_plus == 0
    assert counts.with_commander == 0


def test_a_card_without_variants_has_counted_zeros() -> None:
    counts = spellbook_shells.count_shells([], _index(), POOL)
    assert counts.shells == 0
    assert counts.shell_ids == ()


def test_the_smallest_card_count_of_a_shell_wins() -> None:
    # The slots of a shell are fixed, so its qualifying variants agree on the
    # card count; if a snapshot disagrees anyway, the smallest count is the
    # documented, deterministic reading.
    index = _index(
        _variant("1-2", 7, ["Alpha", "Beta"]),
        _variant("1-2-3", 7, ["Alpha", "Beta", "Gamma"]),
    )
    counts = spellbook_shells.count_shells(["1-2", "1-2-3"], index, POOL)
    assert counts.shells == 1
    assert counts.two_card == 1
    assert counts.three_plus == 0


def test_a_colourless_variant_fits_every_commander() -> None:
    # The export writes the identity of a colourless variant as "C", which is
    # no colour: it must not fail the subset test against WUG.
    index = _index(_variant("1-2", 7, ["Alpha", "Beta"], identity="C"))
    counts = spellbook_shells.count_shells(["1-2"], index, POOL)
    assert counts.shells == 1


def test_variants_sharing_a_combo_through_of_are_one_shell() -> None:
    # A variant can belong to several combos (``of`` has more than one entry:
    # a specific recipe and the generic one it instantiates). Variants linked
    # by a shared combo are one shell, whichever entry of ``of`` is read first.
    index = _index(
        _variant("1-2-3", 7, ["Alpha", "Beta", "Gamma"], also_of=(99,)),
        _variant("1-2-4", 8, ["Alpha", "Beta", "Delta"], also_of=(99,)),
        _variant("1-2-5", 99, ["Alpha", "Beta", "Epsilon"]),
    )
    counts = spellbook_shells.count_shells(["1-2-3", "1-2-4", "1-2-5"], index, POOL)
    assert counts.shells == 1
    assert counts.shell_ids == (7,)


def test_the_shell_does_not_depend_on_the_order_of_of() -> None:
    first = _variant("1-2-3", 7, ["Alpha", "Beta", "Gamma"], also_of=(99,))
    second = _variant("1-2-4", 99, ["Alpha", "Beta", "Delta"], also_of=(7,))
    counts = spellbook_shells.count_shells(["1-2-3", "1-2-4"], _index(first, second), POOL)
    assert counts.shells == 1
    assert counts.shell_ids == (7,)


def test_a_variant_with_the_commander_card_involves_the_commander() -> None:
    # The commander sits in the command zone: a combo that uses her card needs
    # her, even though the export only flags ``mustBeCommander`` for cards that
    # are required to be the commander.
    index = _index(
        _variant("1-2", 7, ["Commander Card", "Beta"]),
        _variant("1-3-4", 9, ["Alpha", "Gamma", "Delta"]),
    )
    counts = spellbook_shells.count_shells(
        ["1-2", "1-3-4"], index, POOL, commander="Commander Card"
    )
    assert counts.shells == 2
    assert counts.with_commander == 1
