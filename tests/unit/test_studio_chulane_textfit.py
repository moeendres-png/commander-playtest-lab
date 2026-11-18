"""Tests for Phase B2 (E1): deterministic Chulane-Textfit rules and Tierliste integration."""

from __future__ import annotations

from pathlib import Path

from commander_lab.studio import chulane_textfit, strength, strength_view
from commander_lab.studio.web import STATIC


def test_chulane_textfit_confusion_matrix_and_negative_controls() -> None:
    drake = chulane_textfit.evaluate_chulane_textfit(
        type_line="Creature — Drake",
        oracle_text="Flying\nWhen Shrieking Drake enters, return a creature you control to its owner's hand.",
        mana_value=1,
        produced_mana="",
    )
    assert drake["version"] == chulane_textfit.CHULANE_TEXTFIT_RULES_VERSION
    assert drake["weight_in_index"] == 0
    assert drake["is_creature_spell"] is True
    assert drake["self_bounce_or_blink"] is True
    assert drake["own_etb_trigger"] is True
    assert drake["foreign_trigger"] is False
    assert drake["cheap_mana_dork"] is False
    assert drake["matched_count"] == 3
    assert {m["rule_id"] for m in drake["matches"]} == {
        "is_creature_spell",
        "self_bounce_or_blink",
        "own_etb_trigger",
    }

    birds = chulane_textfit.evaluate_chulane_textfit(
        type_line="Creature — Bird",
        oracle_text="Flying\n{T}: Add one mana of any color.",
        mana_value=1,
        produced_mana="WUBRG",
    )
    assert birds["is_creature_spell"] is True
    assert birds["cheap_mana_dork"] is True
    assert birds["own_etb_trigger"] is False
    assert birds["matched_count"] == 2

    soul = chulane_textfit.evaluate_chulane_textfit(
        type_line="Creature — Elemental",
        oracle_text="Trample\nWhenever another nontoken creature enters, you may draw a card.",
        mana_value=6,
        produced_mana="",
    )
    assert soul["is_creature_spell"] is True
    assert soul["own_etb_trigger"] is False
    assert soul["foreign_trigger"] is True
    assert soul["foreign_phrase"] is not None

    azusa = chulane_textfit.evaluate_chulane_textfit(
        type_line="Legendary Creature — Human Monk",
        oracle_text="You may play two additional lands on each of your turns.",
        mana_value=3,
        produced_mana="",
    )
    assert azusa["is_creature_spell"] is True
    assert azusa["landfall_or_extra_land"] is True

    ephemerate = chulane_textfit.evaluate_chulane_textfit(
        type_line="Instant",
        oracle_text="Exile target creature you control, then return it to the battlefield under its owner's control.\nRebound",
        mana_value=1,
        produced_mana="",
    )
    assert ephemerate["is_creature_spell"] is False
    assert ephemerate["self_bounce_or_blink"] is True

    # Negative controls: opponent-only bounce & non-creature mana rock
    opp_bounce = chulane_textfit.evaluate_chulane_textfit(
        type_line="Instant",
        oracle_text="Return target creature an opponent controls to its owner's hand.",
        mana_value=1,
        produced_mana="",
    )
    assert opp_bounce["self_bounce_or_blink"] is False
    assert opp_bounce["matched_count"] == 0

    sol_ring = chulane_textfit.evaluate_chulane_textfit(
        type_line="Artifact",
        oracle_text="{T}: Add {C}{C}.",
        mana_value=1,
        produced_mana="C",
    )
    assert sol_ring["is_creature_spell"] is False
    assert sol_ring["cheap_mana_dork"] is False
    assert sol_ring["matched_count"] == 0


def test_pool_strength_exposes_chulane_textfit_only_for_chulane_with_zero_weight(
    tmp_path: Path,
) -> None:
    from tests.unit.studio_synth import add_card, make_store

    store = make_store(tmp_path)
    try:
        c_id = add_card(
            store,
            "Chulane, Teller of Tales",
            type_line="Legendary Creature — Human Druid",
            identity="WUG",
        )
        d_id = add_card(
            store,
            "Shrieking Drake",
            type_line="Creature — Drake",
            identity="U",
        )
        add_card(
            store,
            "Cmd A",
            type_line="Legendary Creature — Warrior",
            identity="W",
        )
        store.connection.execute(
            "UPDATE card SET oracle_text = ?, mana_value = ? WHERE card_id = ?",
            ("Whenever you cast a creature spell, draw a card.", 5.0, c_id),
        )
        store.connection.execute(
            "UPDATE card SET oracle_text = ?, mana_value = ? WHERE card_id = ?",
            (
                "Flying\nWhen Shrieking Drake enters, return a creature you control to its owner's hand.",
                1.0,
                d_id,
            ),
        )
        store.connection.commit()

        res_chulane = strength_view.compute(
            store, "Chulane, Teller of Tales", strength.StrengthSettings()
        )
        assert (
            res_chulane["chulane_textfit_version"] == chulane_textfit.CHULANE_TEXTFIT_RULES_VERSION
        )
        by_name = {c["name"]: c for c in res_chulane["cards"]}
        drake_tf = by_name["Shrieking Drake"]["chulane_textfit"]
        assert drake_tf is not None
        assert drake_tf["weight_in_index"] == 0
        assert drake_tf["self_bounce_or_blink"] is True
        assert drake_tf["matched_count"] == 3

        res_other = strength_view.compute(store, "Cmd A", strength.StrengthSettings())
        assert res_other["chulane_textfit_version"] is None
        assert all(c["chulane_textfit"] is None for c in res_other["cards"])
    finally:
        store.close()


def test_tierliste_js_renders_chulane_textfit_column_and_drawer() -> None:
    js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    for token in (
        "chulane_textfit_version",
        "Textfit (Chulane)",
        "textfitOf",
        "textfitCell",
        "Fremd-ETB-Trigger",
    ):
        assert token in js
