"""Combo shells (#1366): spellbook variants deduplicated onto the combo (shell)
they belong to. The fixtures mirror the shape of the Commander Spellbook bulk
export (``variants.json``): a variant carries the combo it belongs to in ``of``,
its cards in ``uses``, generic slots in ``requires`` and its colour identity in
``identity``."""

from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import sys
from pathlib import Path

import pytest

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


def test_with_commander_survives_when_a_non_commander_variant_comes_first() -> None:
    # P2-1: a shell may have one variant without the commander processed first (even
    # with the same or smaller card_count) and a later variant that uses the commander
    # (or flags mustBeCommander). Order and card_count differences must never drop it.
    index = _index(
        _variant("1-2", 7, ["Alpha", "Beta"], commander=False),
        _variant("1-3-cmd", 7, ["Alpha", "Gamma", "Delta"], commander=True),
        _variant("1-4", 8, ["Alpha", "Beta"], commander=False),
        _variant("1-5", 8, ["Alpha", "Gamma"], commander=True),
    )
    counts = spellbook_shells.count_shells(["1-2", "1-3-cmd", "1-4", "1-5"], index, POOL)
    assert counts.shells == 2
    assert counts.with_commander == 2


def test_bool_combo_id_and_missing_or_blank_identity_fail_closed() -> None:
    # P3-3: True is an instance of int in Python and must not pass _combo_ids; missing,
    # None, empty/whitespace, or non-string identity must fail closed instead of looking
    # colourless ("C" is the only empty-colour-set marker).
    records: list[dict[str, object]] = [
        {
            "id": "bool-id",
            "of": [{"id": True}],
            "identity": "C",
            "uses": [{"card": {"name": "Alpha"}}, {"card": {"name": "Beta"}}],
            "requires": [],
        },
        {
            "id": "missing-id-text",
            "of": [{"id": 10}],
            "uses": [{"card": {"name": "Alpha"}}, {"card": {"name": "Beta"}}],
            "requires": [],
        },
        {
            "id": "none-id-text",
            "of": [{"id": 11}],
            "identity": None,
            "uses": [{"card": {"name": "Alpha"}}, {"card": {"name": "Beta"}}],
            "requires": [],
        },
        {
            "id": "blank-id-text",
            "of": [{"id": 12}],
            "identity": "   ",
            "uses": [{"card": {"name": "Alpha"}}, {"card": {"name": "Beta"}}],
            "requires": [],
        },
        {
            "id": "list-id-text",
            "of": [{"id": 13}],
            "identity": ["W", "U"],
            "uses": [{"card": {"name": "Alpha"}}, {"card": {"name": "Beta"}}],
            "requires": [],
        },
    ]
    index = spellbook_shells.build_variant_index(records, [])
    assert "bool-id" not in index
    counts = spellbook_shells.count_shells(
        ["bool-id", "missing-id-text", "none-id-text", "blank-id-text", "list-id-text"],
        index,
        POOL,
    )
    assert counts.shells == 0
    assert counts.shell_ids == ()


def test_build_script_writes_commander_scoped_csv_and_validates_identity(
    tmp_path: Path, monkeypatch: object
) -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "build_spellbook_shells.py"
    spec = importlib.util.spec_from_file_location("build_spellbook_shells", script_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod._parse_identity("C") == frozenset()
    assert mod._parse_identity("w, u, g") == frozenset({"W", "U", "G"})
    with pytest.raises(ValueError, match="identity"):
        mod._parse_identity("WXYZ")

    bulk = tmp_path / "variants.json.gz"
    bulk.write_bytes(
        gzip.compress(
            json.dumps(
                {
                    "version": "test",
                    "timestamp": "2026-11-15T00:00:00Z",
                    "variants": [_variant("1-2", 7, ["Alpha", "Beta"], identity="WU")],
                    "aliases": [],
                }
            ).encode("utf-8")
        )
    )
    links = tmp_path / "links.csv"
    with links.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["card_name", "fetch_status", "variant_ids"])
        writer.writeheader()
        writer.writerow({"card_name": "Alpha", "fetch_status": "AVAILABLE", "variant_ids": "1-2"})
    pool = tmp_path / "pool.json"
    pool.write_text(
        json.dumps({"cards": [{"card_name": "Alpha"}, {"card_name": "Beta"}]}), encoding="utf-8"
    )
    out = tmp_path / "shells.csv"

    mp = monkeypatch  # type: ignore[assignment]
    mp.setattr(  # type: ignore[attr-defined]
        sys,
        "argv",
        [
            "build_spellbook_shells.py",
            "--bulk",
            str(bulk),
            "--links",
            str(links),
            "--pool",
            str(pool),
            "--output",
            str(out),
            "--commander",
            "Custom Commander",
            "--identity",
            "WU",
        ],
    )
    assert mod.main() == 0
    with out.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [
        {
            "commander_name": "Custom Commander",
            "card_name": "Alpha",
            "fetch_status": "AVAILABLE",
            "shell_count": "1",
            "shell_count_2card": "1",
            "shell_count_3plus": "0",
            "shell_count_commander": "0",
            "shell_ids": "7",
        }
    ]


def test_tam_wubrg_qualifies_five_colour_planeswalker_shells_rejected_for_chulane(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert spellbook_shells.TAM_NAME == "Tam, the Possibility"
    assert frozenset({"W", "U", "B", "R", "G"}) == spellbook_shells.TAM_IDENTITY

    tam_pool = {
        spellbook_shells.TAM_NAME,
        "Chandra, Hope's Beacon",
        "Deepglow Skate",
        "The Chain Veil",
    }
    variants = [
        _variant(
            "pw-wubrg",
            501,
            [spellbook_shells.TAM_NAME, "Chandra, Hope's Beacon", "Deepglow Skate"],
            identity="WUBRG",
        ),
        _variant(
            "pw-br",
            502,
            ["Chandra, Hope's Beacon", "The Chain Veil"],
            identity="BR",
        ),
    ]
    index = spellbook_shells.build_variant_index(variants, [])

    # Default Chulane (WUG) rejects both 5-colour and BR Planeswalker shells.
    chulane_counts = spellbook_shells.count_shells(["pw-wubrg", "pw-br"], index, tam_pool)
    assert chulane_counts.shells == 0
    chulane_snap = spellbook_shells.build_template_snapshot(variants, tam_pool)
    assert chulane_snap["pool_shells"] == []

    # TAM (WUBRG) qualifies both shells and recognises Tam as the commander.
    tam_counts = spellbook_shells.count_shells(
        ["pw-wubrg", "pw-br"],
        index,
        tam_pool,
        identity=spellbook_shells.TAM_IDENTITY,
        commander=spellbook_shells.TAM_NAME,
    )
    assert tam_counts.shells == 2
    assert tam_counts.two_card == 1
    assert tam_counts.three_plus == 1
    assert tam_counts.with_commander == 1
    assert tam_counts.shell_ids == (501, 502)

    tam_snap = spellbook_shells.build_template_snapshot(
        variants,
        tam_pool,
        identity=spellbook_shells.TAM_IDENTITY,
        commander=spellbook_shells.TAM_NAME,
    )
    assert tam_snap["commander"] == spellbook_shells.TAM_NAME
    assert tam_snap["identity"] == "BGRUW"
    pool_shells = tam_snap["pool_shells"]
    assert isinstance(pool_shells, list) and len(pool_shells) == 2

    # CLI build_spellbook_shells.py accepts --identity WUBRG for TAM.
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "build_spellbook_shells.py"
    spec = importlib.util.spec_from_file_location("build_spellbook_shells_tam", script_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    bulk = tmp_path / "variants.json.gz"
    bulk.write_bytes(
        gzip.compress(
            json.dumps(
                {
                    "version": "test-tam",
                    "timestamp": "2026-11-19T00:00:00Z",
                    "variants": variants,
                    "aliases": [],
                }
            ).encode("utf-8")
        )
    )
    links = tmp_path / "links.csv"
    with links.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["card_name", "fetch_status", "variant_ids"])
        writer.writeheader()
        writer.writerow(
            {
                "card_name": "Chandra, Hope's Beacon",
                "fetch_status": "AVAILABLE",
                "variant_ids": "pw-wubrg;pw-br",
            }
        )
    pool_file = tmp_path / "pool.json"
    pool_file.write_text(
        json.dumps({"cards": [{"card_name": name} for name in sorted(tam_pool)]}),
        encoding="utf-8",
    )
    out = tmp_path / "tam_shells.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_spellbook_shells.py",
            "--bulk",
            str(bulk),
            "--links",
            str(links),
            "--pool",
            str(pool_file),
            "--output",
            str(out),
            "--commander",
            spellbook_shells.TAM_NAME,
            "--identity",
            "WUBRG",
        ],
    )
    assert mod.main() == 0
    with out.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [
        {
            "commander_name": spellbook_shells.TAM_NAME,
            "card_name": "Chandra, Hope's Beacon",
            "fetch_status": "AVAILABLE",
            "shell_count": "2",
            "shell_count_2card": "1",
            "shell_count_3plus": "1",
            "shell_count_commander": "1",
            "shell_ids": "501;502",
        }
    ]
