"""Strength index follow-up to #1275: truthful reasons, tiers on the shown index, configurable
other commanders, oracle_id fallback parity. Synthetic data only."""

from __future__ import annotations

import copy
import json
import math
from collections.abc import Mapping
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from scripts import import_card_understanding as importer

from commander_lab.studio import (
    StudioStore,
    card_understanding,
    number_contract,
    strength,
    strength_view,
    understanding_field,
    universe,
)
from commander_lab.studio.strength import Observation, PoolContext, StrengthSettings
from commander_lab.studio.web import create_app
from tests.unit.studio_synth import add_card, add_deck, add_signal, make_store

CMD = "Cmd A"
INCLUSION = "edhrec_commander_inclusion"
CARDS = [f"Card {index:02d}" for index in range(6)]


def _store(folder: Path | None = None) -> StudioStore:
    store = make_store(folder)
    add_card(store, CMD, type_line="Legendary Creature — Test")
    add_card(store, "Other Cmd", type_line="Legendary Creature — Test")
    add_card(store, "Forest", type_line="Basic Land — Forest", basic=True)
    for name in CARDS:
        add_card(store, name)
    for index, name in enumerate(CARDS[:5]):  # one source only: 5 of 6 cards listed
        add_signal(store, CMD, INCLUSION, name, 90 - 10 * index, 100)
    add_signal(store, "Other Cmd", INCLUSION, "Card 00", 1, 10)  # makes "Other Cmd" known
    return store


def _cards(result: strength_view.StrengthResult) -> dict[str, strength_view.StrengthCard]:
    return {card["name"]: card for card in result["cards"]}


def test_a_filter_card_leaves_the_deck_universe_out_of_its_denominator() -> None:
    """Main's denominator (every weighted component the source can exist for, here 10.5: 3 + 2 +
    4 + 1 + 0.5) minus the deck universe (4) for a filter card: 3 of 6.5 for a card with only the
    commander inclusion; the control card, which is no filter card, has the same signal and the
    universe too: 7 of 10.5."""
    settings = StrengthSettings(min_coverage=0.0, min_components=1)
    obs = {
        "x": {"commander_inclusion": Observation(0.9, 90, 100)},
        "y": {
            "commander_inclusion": Observation(0.5, 50, 100),
            "deck_universe": Observation(0.5, 50, 100),
        },
        "z": {
            "commander_inclusion": Observation(0.1, 10, 100),
            "deck_universe": Observation(0.1, 10, 100),
        },
        "w": {"commander_inclusion": Observation(0.3, 30, 100)},  # control: not a filter card
    }
    collected = {strength.COMMANDER_INCLUSION, strength.DECK_UNIVERSE}
    scored = strength.score_pool(
        settings, obs, collected, context=PoolContext(filter_cards=frozenset({"x"}))
    )
    assert scored["x"]["coverage"] == pytest.approx(3 / 6.5, abs=1e-4)
    assert scored["w"]["coverage"] == pytest.approx(3 / 10.5, abs=1e-4)
    assert scored["y"]["coverage"] == pytest.approx(7 / 10.5, abs=1e-4)


def test_no_positive_weight_and_no_source_have_their_own_reasons() -> None:
    zero = StrengthSettings(weights={name: 0.0 for name in strength.COMPONENTS})
    obs = {"a": {"commander_inclusion": Observation(0.9, 90, 100)}}
    only = strength.score_pool(zero, obs, {"commander_inclusion"})["a"]
    assert only["index"] is None and only["tier"] == "U"
    assert only["reason"] == "NO_POSITIVE_WEIGHT"  # not ENOUGH_DATA, not TOO_LITTLE_DATA
    nothing = strength.score_pool(StrengthSettings(), {"a": {}}, set())["a"]
    assert nothing["reason"] == "NO_SOURCE_FOR_COMMANDER" and nothing["tier"] == "U"


def test_the_tier_follows_the_index_as_shown() -> None:
    settings = StrengthSettings(
        weights={name: 0.0 for name in strength.COMPONENTS} | {"synergy": 1.0},
        tier_cuts={"S": 90.0, "A": 66.7, "B": 40.0, "C": 10.0},
        min_coverage=0.0,
        min_components=1,
    )
    values = zip("abcd", (1, 2, 3, 4), strict=True)
    obs = {key: {"synergy": Observation(value)} for key, value in values}
    result = strength.score_pool(settings, obs, {"synergy"})
    assert result["c"]["index"] == 66.7  # raw 66.666...: shown as 66.7
    assert result["c"]["tier"] == "A"  # the shown value meets the cut 66.7: never "66.7 but B"


def test_other_commanders_are_ranked_by_default_and_not_when_switched_off() -> None:
    store = _store()
    default = _cards(strength_view.compute(store, CMD, StrengthSettings()))
    assert default["Other Cmd"]["tier"] != "N"  # ranked like any card by default
    assert StrengthSettings().rank_other_commanders is True
    cards = _cards(strength_view.compute(store, CMD, StrengthSettings(rank_other_commanders=False)))
    assert cards["Other Cmd"]["tier"] == "N"
    assert cards["Other Cmd"]["reason"] == strength.NOT_RANKED_OTHER_COMMANDER
    assert cards[CMD]["tier"] == "N" and cards["Forest"]["tier"] == "N"
    # They take no part in the percentile population: Card 00 is the top of the five listed.
    top = next(c for c in cards["Card 00"]["components"] if c["component"] == "commander_inclusion")
    assert top["percentile"] == 1.0
    on = _cards(strength_view.compute(store, CMD, StrengthSettings(rank_commander_and_basics=True)))
    assert on["Other Cmd"]["tier"] != "N"


def test_the_deck_universe_filter_card_has_the_universe_out_of_its_denominator() -> None:
    store = _store()
    for index in range(40):
        add_deck(store, f"d{index}", ["Card 00", "Card 01"])
    universe.save_profile(store, "mit", {"min_universe": 5, "must_contain": ["Card 00"]})
    # 40 local decks are a counted corpus: keep the EDHREC weights (E2.a off) so that the control
    # card still has its commander inclusion in the denominator, as this test measures
    result = strength_view.compute(
        store, CMD, StrengthSettings(universe_profile="mit", edhrec_with_corpus=True)
    )
    cards = _cards(result)
    status = {c["component"]: c["status"] for c in cards["Card 00"]["components"]}
    assert status["deck_universe"] == strength.FILTER_CARD
    # the filter card has the universe weight (4) out of its denominator: 3 of 6.5; the control
    # card of the same pool has the commander inclusion and the universe present: 7 of 10.5
    assert cards["Card 00"]["coverage"] == pytest.approx(3 / 6.5, abs=1e-4)
    assert cards["Card 01"]["coverage"] == pytest.approx(7 / 10.5, abs=1e-4)
    with pytest.raises(KeyError):
        strength_view.compute(store, CMD, StrengthSettings(universe_profile="nope"))


def test_the_minimum_number_of_signals_never_exceeds_the_weighted_components() -> None:
    settings = StrengthSettings(
        weights={name: 0.0 for name in strength.COMPONENTS} | {"commander_inclusion": 1.0},
        min_coverage=0.0,
        min_components=3,
    )
    obs = {"a": {"commander_inclusion": Observation(0.9, 90, 100)}}
    scored = strength.score_pool(settings, obs, {strength.COMMANDER_INCLUSION})
    assert scored["a"]["tier"] != "U" and scored["a"]["reason"] == "ENOUGH_DATA"


def test_a_deck_row_with_an_oracle_id_counts_for_the_card_under_any_spelling() -> None:
    from commander_lab.studio import builder, universe_view

    store = make_store()
    add_card(store, CMD, type_line="Legendary Creature — Test")
    fire_id = add_card(store, "Fire // Ice")
    vault_id = add_card(store, "Lim-Dûl's Vault")
    db = store.connection
    db.execute("UPDATE card SET oracle_id = 'o-fire' WHERE oracle_name = 'Fire // Ice'")
    db.execute("UPDATE card SET oracle_id = 'o-vault' WHERE oracle_name = 'Lim-Dûl''s Vault'")
    add_deck(store, "d1", ["Fire", "Lim-Dul's Vault"])
    add_deck(store, "d2", ["Fire // Ice"])
    db.execute(
        "UPDATE corpus_deck_card SET oracle_id = 'o-vault' WHERE card_name = 'Lim-Dul''s Vault'"
    )
    pool = builder.pool_cards(store, [CMD], with_signals=False)
    cards = {str(c["name"]): c for c in pool["cards"]}  # type: ignore[attr-defined]
    assert cards["Fire // Ice"]["decks"]["all"] == 2  # front face "Fire" + the full name
    assert cards["Lim-Dûl's Vault"]["decks"]["all"] == 1  # accent spelling, found by its id
    assert cards["Lim-Dûl's Vault"]["decks_known"] is True

    universe.save_profile(store, "alle", {"min_universe": 1})
    spread = {
        c["name"]: c
        for c in universe_view.pool_spread(store, "alle", commander_names=[CMD])["cards"]
    }
    assert spread["Lim-Dûl's Vault"]["matched"] is True
    assert spread["Lim-Dûl's Vault"]["matched_name"] == "Lim-Dul's Vault"
    assert spread["Lim-Dûl's Vault"]["hits"] == 1

    co_fire = universe_view.card_cooccurrence(store, "alle", fire_id, commander_names=[CMD])
    co_vault = universe_view.card_cooccurrence(store, "alle", vault_id, commander_names=[CMD])
    assert co_vault["matched"] is True and co_vault["decks_with_card"] == 1
    assert any(
        p["card_name"] == "Lim-Dûl's Vault" and p["decks_together"] == 1 for p in co_fire["pairs"]
    )
    assert any(
        p["card_name"] == "Fire // Ice" and p["decks_together"] == 1 for p in co_vault["pairs"]
    )

    computed = _cards(strength_view.compute(store, CMD, StrengthSettings(universe_profile="alle")))
    vault_comp = next(
        c for c in computed["Lim-Dûl's Vault"]["components"] if c["component"] == "deck_universe"
    )
    assert vault_comp["status"] == strength.PRESENT
    assert vault_comp["numerator"] == 1 and vault_comp["denominator"] == 2


def test_other_commander_names_matches_case_insensitively() -> None:
    store = _store()
    others = strength_view._other_commander_names(store, "other cmd")
    assert "other cmd" not in others
    assert "cmd a" in others


def test_filter_card_removing_sole_weighted_signal_gets_too_little_data() -> None:
    settings = StrengthSettings(
        weights={name: 0.0 for name in strength.COMPONENTS} | {"deck_universe": 1.0},
        min_coverage=0.0,
        min_components=1,
        require_commander_signal=False,
    )
    obs = {"x": {}, "y": {"deck_universe": Observation(0.5, 5, 10)}}
    scored = strength.score_pool(
        settings,
        obs,
        {strength.DECK_UNIVERSE},
        context=PoolContext(filter_cards=frozenset({"x"})),
    )
    assert scored["x"]["tier"] == "U"
    assert scored["x"]["reason"] == "TOO_LITTLE_DATA"


def test_bracket_labels_follow_the_bracket_column_of_the_imported_files() -> None:
    import csv
    from pathlib import Path

    folder = Path(__file__).resolve().parents[2] / "data" / "research" / "deckbuilder_1655"
    seen: dict[str, str] = {}
    for variant in strength.BRACKETS:
        path = folder / f"commander_bracket_signals_{variant}_1.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            row = next(csv.DictReader(handle))
        assert row["variant"] == variant
        seen[variant] = row["bracket"]
    assert seen == {"core": "2", "upgraded": "3", "optimized": "4", "cedh": "5"}
    choices = strength_view.presets()["panel"]["choices"]["bracket"]  # type: ignore[index,call-overload]
    served = {choice["value"]: choice["label"] for choice in choices}
    for variant, number in seen.items():
        assert f"Bracket {number})" in served[variant], (variant, served[variant])


def test_the_two_ranking_switches_are_independent() -> None:
    store = _store()
    both = StrengthSettings(rank_commander_and_basics=True, rank_other_commanders=False)
    cards = _cards(strength_view.compute(store, CMD, both))
    # the commander card and basics are ranked, the other commander card still is not
    assert cards["Other Cmd"]["tier"] == "N"
    assert cards["Other Cmd"]["reason"] == strength.NOT_RANKED_OTHER_COMMANDER
    assert cards["Forest"]["tier"] != "N"


# ---------- rubric v2 data set (Kartenverständnis): helpers of the field and loader tests ----------

SCORES = {"E": 60, "F": 70, "T": 40, "R": 50, "K": 20, "D": 80, "H": 65}


def _row(oracle_id: str, card: str = "Card", **changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "oracle_id": oracle_id,
        "card": card,
        "scores": dict(SCORES),
        "confidence": "high",
        "reason": "According to the card text it does one small thing.",
        "notes": {"H": "small"},
        "rule_claims": [],
        "version": "v2.1",
        "rater_tier": "large",
        "rubric": "chulane-rubric-v2.1",
    }
    return row | changes


def _dataset(rows: list[dict[str, object]]) -> dict[str, card_understanding.UnderstandingRow]:
    return card_understanding.parse_lines([json.dumps(row) for row in rows])


def _with_oracle_ids(store: StudioStore, names: list[str]) -> None:
    for name in names:
        store.connection.execute(
            "UPDATE card SET oracle_id = ? WHERE oracle_name = ?", (f"o-{name}", name)
        )


def _scored_answer() -> tuple[StudioStore, strength_view.StrengthResult]:
    store = _store()
    _with_oracle_ids(store, CARDS)
    return store, strength_view.compute(store, CMD, StrengthSettings())


# ---------- rubric v2 field "Kartenverständnis (Modellurteil)" (Q1-b3, #1678, E5) ----------


def _field(
    store: StudioStore,
    answer: Mapping[str, object],
    data: dict[str, card_understanding.UnderstandingRow],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    monkeypatch.setattr(card_understanding, "DATASET_COMMANDER", CMD)
    return understanding_field.with_understanding(store, answer, dataset=data)


def test_the_field_only_adds_one_key_and_leaves_the_answer_as_it_was(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, answer = _scored_answer()
    before = copy.deepcopy(answer)
    data = _dataset([_row("o-Card 00", scores=SCORES | {"H": 90}), _row("o-Card 03")])
    after = _field(store, answer, data, monkeypatch)
    assert answer == before  # the given (possibly remembered) answer is not modified
    assert set(after) - set(before) == {understanding_field.FIELD}
    assert {key: value for key, value in after.items() if key != "kartenverstaendnis"} == before
    field = after["kartenverstaendnis"]
    assert isinstance(field, dict)
    assert field["verfuegbar"] is True and field["grund"] is None
    assert field["name"] == "Kartenverständnis (Modellurteil)" and field["kriterium"] == "H"
    assert field["n_bewertet"] == 2 and field["n_gesamt"] == len(before["cards"])
    assert field["herkunft"] == {
        "version": "v2.1",
        "rubric": "chulane-rubric-v2.1",
        "commander": CMD,
        "rows": 2,
        "matched": 2,
        "rater_tiers": {"large": 2},
    }


def test_every_figure_is_a_valid_judgement_and_an_unrated_card_has_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, answer = _scored_answer()
    data = _dataset(
        [
            _row("o-Card 00", scores=SCORES | {"H": 90}, confidence="low", raters=3),
            _row("o-Card 03", scores=SCORES | {"H": 0}),
        ]
    )
    field = _field(store, answer, data, monkeypatch)["kartenverstaendnis"]
    assert isinstance(field, dict)
    figures = field["zahlen"]
    ids = {card["name"]: card["card_id"] for card in answer["cards"]}
    by_id = {figure["id"]: figure for figure in figures}
    assert set(by_id) == {
        f"kartenverstaendnis:{ids['Card 00']}",
        f"kartenverstaendnis:{ids['Card 03']}",
    }
    for figure in figures:
        assert number_contract.check(figure) == []
        assert figure["klasse"] == number_contract.URTEIL == "URTEIL"
        assert figure["einheit"] == "Punkte" and figure["n"] is None and figure["N"] is None
        assert "data_class" not in figure  # never a simulated result
        assert figure["kohorte"] == f"{CMD} · Bracket 3 (Annahme der Rater)"
        assert "nicht gegen Spielergebnisse validiert" in figure["hinweise"]
    high = by_id[f"kartenverstaendnis:{ids['Card 00']}"]
    assert high["wert"] == 90.0 and high["bezeichnung"] == "H Gesamtwert (0 bis 100)"
    assert (
        high["quelle"] == "Rubrik v2.1 (chulane-rubric-v2.1), Modell-Rater Stufe large, 3 Bewerter"
    )
    assert high["hinweise"][0] == "Rater-Vertrauen low (Selbstauskunft)"
    zero = by_id[f"kartenverstaendnis:{ids['Card 03']}"]
    assert zero["wert"] == 0.0 and "1 Bewerter" in zero["quelle"]  # a real 0 stays a real 0
    # a card the data set does not list has no figure at all: "unbekannt", never 0
    assert f"kartenverstaendnis:{ids['Card 01']}" not in by_id


def test_another_commander_gets_no_field(monkeypatch: pytest.MonkeyPatch) -> None:
    store, answer = _scored_answer()
    data = _dataset([_row(f"o-{name}") for name in CARDS])
    monkeypatch.setattr(card_understanding, "DATASET_COMMANDER", "Someone Else")
    after = understanding_field.with_understanding(store, answer, dataset=data)
    assert "kartenverstaendnis" not in after and after == answer
    # positive case: the data set's commander matches regardless of case and spaces
    renamed = answer | {"commander": f" {CMD.lower()}"}
    monkeypatch.setattr(card_understanding, "DATASET_COMMANDER", CMD.upper())
    found = understanding_field.with_understanding(store, renamed, dataset=data)  # type: ignore[arg-type]
    assert found["kartenverstaendnis"]["n_bewertet"] == len(CARDS)  # type: ignore[index]


def test_the_field_is_only_offered_for_the_bracket_the_raters_judged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, answer = _scored_answer()
    data = _dataset([_row(f"o-{name}") for name in CARDS])
    assert answer["settings"]["bracket"] == "upgraded"
    for bracket in ("cedh", "core", "optimized", "none", None):
        changed = answer | {"settings": {**answer["settings"], "bracket": bracket}}
        field = _field(store, changed, data, monkeypatch)["kartenverstaendnis"]  # type: ignore[arg-type]
        assert isinstance(field, dict)
        assert field["verfuegbar"] is False and "Bracket 3" in field["grund"]
        assert field["zahlen"] == [] and field["n_bewertet"] == 0 and field["herkunft"] is None
    no_settings = {k: v for k, v in answer.items() if k != "settings"}
    field = _field(store, no_settings, data, monkeypatch)["kartenverstaendnis"]
    assert field["verfuegbar"] is False  # type: ignore[index]


def test_a_broken_data_file_makes_the_field_unavailable_not_wrong(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, answer = _scored_answer()
    path = tmp_path / "bad.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(card_understanding, "DATASET_PATH", path)
    monkeypatch.setattr(card_understanding, "DATASET_COMMANDER", CMD)
    field = understanding_field.with_understanding(store, answer)["kartenverstaendnis"]
    assert isinstance(field, dict)
    assert field["verfuegbar"] is False and "nicht lesbar" in field["grund"]
    assert field["zahlen"] == []


def _judgement_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: Path, settings: object = None
) -> tuple[dict[str, object], dict[str, object]]:
    """The answer of ``/api/strength`` with the data file ``path``, and the index answer."""
    folder = tmp_path / "studio"
    store = _store(folder)
    _with_oracle_ids(store, CARDS)
    store.connection.commit()
    expected = strength_view.compute(store, CMD, StrengthSettings())
    store.close()
    monkeypatch.setattr(card_understanding, "DATASET_PATH", path)
    monkeypatch.setattr(card_understanding, "DATASET_COMMANDER", CMD)
    body: dict[str, object] = {"commander": CMD}
    if settings is not None:
        body["settings"] = settings
    with TestClient(create_app(folder)) as client:
        response = client.post("/api/strength", json=body, headers={"X-Studio": "1"})
    assert response.status_code == 200
    return response.json(), json.loads(json.dumps(expected))


def test_the_strength_route_sends_the_judgement_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "cu.jsonl"
    path.write_text(
        "\n".join(json.dumps(_row(f"o-{name}", name)) for name in CARDS[:4]) + "\n",
        encoding="utf-8",
    )
    body, expected = _judgement_route(tmp_path, monkeypatch, path)
    field = body["kartenverstaendnis"]
    assert isinstance(field, dict)
    assert field["verfuegbar"] is True and field["n_bewertet"] == 4
    assert all(number_contract.check(figure) == [] for figure in field["zahlen"])
    assert body["tier_counts"] == expected["tier_counts"]
    # the overall rating v1 fell (Q1-b3, E15 Q1): no field of it is sent any more
    assert not [key for key in body if key.startswith("overall")]
    assert all(not key.startswith("overall") for card in body["cards"] for key in card)
    assert body["cards"] == expected["cards"]


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (b"\xff\xfe not utf-8\n", "nicht lesbar"),
        (
            json.dumps(_row("o-Card 00", scores=SCORES | {"H": 10**400})).encode() + b"\n",
            "nicht lesbar",
        ),
        (json.dumps(_row("o-Card 00", version="v2")).encode() + b"\n", "nicht lesbar"),
        (
            json.dumps(_row("o-Card 00", rubric="chulane-rubric-v1")).encode() + b"\n",
            "nicht lesbar",
        ),
        (b"[" * 100000 + b"\n", "nicht lesbar"),
        (None, "Datensatz nicht gefunden"),
    ],
)
def test_a_defective_data_file_never_breaks_the_strength_judgement_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: bytes | None, reason: str
) -> None:
    path = tmp_path / "cu.jsonl"
    if content is not None:
        path.write_bytes(content)
    body, expected = _judgement_route(tmp_path, monkeypatch, path)
    field = body["kartenverstaendnis"]
    assert isinstance(field, dict)
    assert field["verfuegbar"] is False and reason in field["grund"]
    assert field["zahlen"] == []
    assert body["tier_counts"] == expected["tier_counts"]


def test_a_changed_data_file_invalidates_the_remembered_judgement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "studio"
    store = _store(folder)
    _with_oracle_ids(store, CARDS)
    store.connection.commit()
    store.close()
    path = tmp_path / "cu.jsonl"
    monkeypatch.setattr(card_understanding, "DATASET_PATH", path)
    monkeypatch.setattr(card_understanding, "DATASET_COMMANDER", CMD)
    head = {"X-Studio": "1"}
    with TestClient(create_app(folder)) as client:
        counts = []
        for rows in (CARDS[:2], CARDS[:3]):
            path.write_text(
                "\n".join(json.dumps(_row(f"o-{name}", name)) for name in rows) + "\n",
                encoding="utf-8",
            )
            body = client.post("/api/strength", json={"commander": CMD}, headers=head).json()
            counts.append(body["kartenverstaendnis"]["n_bewertet"])
    assert counts == [2, 3]


def test_the_strength_route_withholds_the_judgement_for_another_bracket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "cu.jsonl"
    path.write_text(json.dumps(_row("o-Card 00", "Card 00")) + "\n", encoding="utf-8")
    body, _ = _judgement_route(tmp_path, monkeypatch, path, settings={"bracket": "cedh"})
    field = body["kartenverstaendnis"]
    assert isinstance(field, dict)
    assert field["verfuegbar"] is False and field["zahlen"] == []


def test_the_strength_route_sends_no_field_for_another_commander(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "studio"
    store = _store(folder)
    _with_oracle_ids(store, CARDS)
    store.connection.commit()
    store.close()
    path = tmp_path / "cu.jsonl"
    path.write_text(json.dumps(_row("o-Card 00", "Card 00")) + "\n", encoding="utf-8")
    monkeypatch.setattr(card_understanding, "DATASET_PATH", path)
    monkeypatch.setattr(card_understanding, "DATASET_COMMANDER", "Other Cmd")
    with TestClient(create_app(folder)) as client:
        body = client.post(
            "/api/strength", json={"commander": CMD}, headers={"X-Studio": "1"}
        ).json()
    assert "kartenverstaendnis" not in body and body["cards"]


# ---------- the data set loader ----------


def test_the_loader_accepts_a_valid_line_and_keeps_the_optional_fields() -> None:
    row = card_understanding.parse_row(
        _row("x", raters=2, rounded=True, score_sd=dict.fromkeys(card_understanding.CRITERIA, 2.5))
    )
    assert row["scores"]["H"] == 65 and row["raters"] == 2 and row["rounded"] is True
    assert card_understanding.parse_row(_row("y", score_sd=None))["score_sd"] is None
    with pytest.raises(card_understanding.DatasetNotFoundError):
        card_understanding.load(Path("does/not/exist.jsonl"))


@pytest.mark.parametrize(
    "change",
    [
        {"scores": {k: v for k, v in SCORES.items() if k != "K"}},
        {"scores": SCORES | {"X": 10}},
        {"scores": SCORES | {"H": 101}},
        {"scores": SCORES | {"H": -5}},
        {"scores": SCORES | {"H": True}},
        {"scores": SCORES | {"H": "70"}},
        {"scores": SCORES | {"H": math.inf}},
        {"scores": [1, 2]},
        {"confidence": "certain"},
        {"rater_tier": "medium"},
        {"rater_tier": None},
        {"model": "anything"},
        {"version": "v2"},
        {"rubric": "chulane-rubric-v1"},
        {"oracle_id": ""},
        {"reason": "  "},
        {"notes": {"Z": "unknown criterion"}},
        {"rule_claims": "none"},
        {"raters": 0},
        {"score_sd": {"H": 1.0}},
        {"rounded": "yes"},
    ],
)
def test_the_loader_rejects_a_broken_line(change: dict[str, object]) -> None:
    with pytest.raises(card_understanding.UnderstandingDataError):
        card_understanding.parse_row(_row("x") | change)


@pytest.mark.parametrize(
    "missing",
    [
        "oracle_id",
        "card",
        "scores",
        "confidence",
        "reason",
        "notes",
        "rule_claims",
        "version",
        "rater_tier",
        "rubric",
    ],
)
def test_the_loader_rejects_a_line_without_a_required_field(missing: str) -> None:
    row = _row("x")
    del row[missing]
    with pytest.raises(card_understanding.UnderstandingDataError, match="missing"):
        card_understanding.parse_row(row)


def test_the_loader_rejects_a_mixed_version_data_set() -> None:
    lines = [json.dumps(_row("a")), json.dumps(_row("b", version="v2", rubric="other"))]
    with pytest.raises(card_understanding.UnderstandingDataError, match="line 2"):
        card_understanding.parse_lines(lines)


def test_the_loader_fails_closed_and_names_the_lines() -> None:
    lines = [
        json.dumps(_row("a")),
        "",
        "{not json",
        json.dumps(_row("a")),
        json.dumps(_row("b", scores={})),
    ]
    with pytest.raises(card_understanding.UnderstandingDataError) as caught:
        card_understanding.parse_lines(lines)
    text = str(caught.value)
    assert (
        "3 broken" in text
        and "line 3" in text
        and "line 4" in text
        and "twice" in text
        and "line 5" in text
    )
    with pytest.raises(card_understanding.UnderstandingDataError):
        card_understanding.parse_row([])


def test_the_checked_in_data_set_is_valid_and_matches_its_constants() -> None:
    rows = card_understanding.load(card_understanding.DATASET_PATH)
    assert rows, "the data set is empty"
    for row in rows.values():
        assert row["version"] == card_understanding.DATASET_VERSION
        assert row["rubric"] == card_understanding.DATASET_RUBRIC
        assert all(row["scores"][axis] % 5 == 0 for axis in card_understanding.CRITERIA)


# ---------- the importer ----------


def _raw(oracle_id: str, rater: str, version: str = "v2.1", **changes: object) -> dict[str, object]:
    row = _row(oracle_id, "Card") | {"rater": rater, "batch": f"{rater}_b0", "version": version}
    row.pop("rater_tier")
    row.pop("rubric")
    row["uncertainty"] = ""
    row["pattern_check"] = []
    row["model"] = "ignored"
    return row | changes


def _import(
    rows: list[dict[str, object]], version: str, tmp_path: Path
) -> list[card_understanding.UnderstandingRow]:
    source = tmp_path / "in.jsonl"
    source.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    ratings, _skipped = importer.read_ratings([source], version, "large")
    lines, _used = importer.build(ratings, version)
    return lines


def test_the_importer_means_rounds_and_keeps_the_lowest_confidence(tmp_path: Path) -> None:
    rows = [
        _raw("a", "R1", scores=SCORES | {"H": 45, "E": 50}),
        _raw("a", "R2", scores=SCORES | {"H": 50, "E": 50}, confidence="low"),
        _raw("b", "R1"),
    ]
    lines = {line["oracle_id"]: line for line in _import(rows, "v2.1", tmp_path)}
    one, single = lines["a"], lines["b"]
    assert one["scores"]["H"] == 50 and one["scores"]["E"] == 50  # 47.5 rounds half up
    assert one["rounded"] is True and one["raters"] == 2 and one["confidence"] == "low"
    assert one["score_sd"]["H"] == pytest.approx(3.54, abs=0.01) and one["score_sd"]["E"] == 0
    assert (
        one["reason"] == rows[1]["reason"]
    )  # the rater whose H is closest to the mean (tie: name)
    assert single["raters"] == 1 and single["score_sd"] is None and single["rounded"] is False
    assert single["rater_tier"] == "large" and "model" not in single


def test_the_importer_reads_one_version_and_rounds_off_grid_scores(tmp_path: Path) -> None:
    rows = [
        _raw("a", "R1", version="v2", scores=SCORES | {"H": 5}),
        _raw("a", "R2", version="v2.1"),
        _raw("c", "R1", scores=SCORES | {"H": 44}, rater_tier="small"),
        _raw("d", "R1", version="v1"),
    ]
    lines = {line["oracle_id"]: line for line in _import(rows, "v2.1", tmp_path)}
    assert set(lines) == {"a", "c"}  # the other versions are not read
    assert lines["a"]["version"] == "v2.1" and lines["a"]["scores"]["H"] == 65
    assert lines["a"]["raters"] == 1 and lines["a"]["rubric"] == card_understanding.DATASET_RUBRIC
    assert lines["c"]["scores"]["H"] == 45 and lines["c"]["rounded"] is True
    assert lines["c"]["rater_tier"] == "small"
    source = tmp_path / "in.jsonl"
    out = tmp_path / "out.jsonl"
    assert importer.main([str(source), "--out", str(out), "--version", "v2"]) == 2
    assert not out.exists()
    assert card_understanding.parse_lines(importer.render(list(lines.values())).splitlines())


def test_the_importer_rejects_a_broken_input_line(tmp_path: Path) -> None:
    source = tmp_path / "in.jsonl"
    source.write_text(
        json.dumps(_raw("a", "R1", scores=SCORES | {"H": 130})) + "\n", encoding="utf-8"
    )
    with pytest.raises(card_understanding.UnderstandingDataError, match=r"in\.jsonl:1"):
        importer.read_ratings([source], "v2.1", "large")
    out = tmp_path / "out.jsonl"
    assert importer.main([str(source), "--out", str(out)]) == 2 and not out.exists()


def test_the_importer_output_is_deterministic_and_checkable(tmp_path: Path) -> None:
    source = tmp_path / "in.jsonl"
    source.write_text(
        "\n".join(json.dumps(_raw(o, "R1")) for o in ("b", "a")) + "\n", encoding="utf-8"
    )
    out = tmp_path / "out.jsonl"
    assert importer.main([str(source), "--out", str(out)]) == 0
    first = out.read_text(encoding="utf-8")
    assert importer.main([str(source), "--out", str(out), "--check"]) == 0
    out.write_text(first + "\n", encoding="utf-8")
    assert importer.main([str(source), "--out", str(out), "--check"]) == 1
    assert len(card_understanding.load(out)) == 2
