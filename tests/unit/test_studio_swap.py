"""Unit tests for the Studio deck builder: swap helper (``swap.py``, ``POST /api/swap``),
decklist parser (Proposal 7 / D5), role coverage median (Proposal 4 / D2) and German deck
validation (D7). The swap tests use their own synthetic store (``_swap_store``)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, builder, labels, swap, universe
from commander_lab.studio.web import STATIC, create_app
from tests.unit.studio_synth import SOURCE, add_card, add_deck, make_store

COMMANDER = "Cmd A"
# card name -> the decks (indexes 0..9) that list it
PLAYS: dict[str, set[int]] = {
    "Rem Common": set(range(8)),
    "Rem Mid": set(range(5)),
    "Rem Mid Two": set(range(5, 10)),
    "Rem Rare": {9},
    "Shatter": {0, 1, 2},
    "Hate Only": set(range(7)),
    "Draw": set(range(9)),
    "Rem Reserved": set(range(6)),
    "Rem Taken": {0, 1},
    "Rem Candidate": {0},
    "Beast A": set(range(6)),
    "Beast B": {0, 1},
    "Plain Beast": {0},
    "Outside Rem": set(range(4)),  # a card the collection does not hold
}
ROLES = {
    "Cmd A": ["removal"],
    "Rem Common": ["removal"],
    "Rem Mid": ["removal"],
    "Rem Mid Two": ["removal"],
    "Rem Rare": ["removal"],
    "Rem Unknown": ["removal"],
    "Rem Reserved": ["removal"],
    "Rem Taken": ["removal"],
    "Rem Candidate": ["removal"],
    "Shatter": ["removal", "hate"],
    "Hate Only": ["hate"],
    "Draw": ["card_draw"],
    "Wasteland Basic": ["removal"],
}


def _oid(name: str) -> str:
    return "oid-" + name.casefold().replace(" ", "-")


def _swap_store(folder: Path, *, decks: int = 10) -> tuple[StudioStore, dict[str, str]]:
    """A store with a commander, a pool of named cards (roles above), ``decks`` source decks
    (the first four are also in the cohort ``bracket:3``) and one card the collection lacks
    (``Outside Rem``, known only from public card data)."""
    store = make_store(folder)
    ids: dict[str, str] = {}
    cards = [
        (COMMANDER, "Legendary Creature"),
        ("Wasteland Basic", "Basic Land"),
        ("Plain Beast", "Creature"),
        ("Beast A", "Creature"),
        ("Beast B", "Creature"),
        ("Rem Unknown", "Instant"),
        *(
            (name, "Instant")
            for name in PLAYS
            if name not in {"Outside Rem"} and "Beast" not in name
        ),
    ]
    for name, type_line in dict.fromkeys(cards):
        ids[name] = add_card(
            store, name, type_line=type_line, identity="G", basic=name == "Wasteland Basic"
        )
    db = store.connection
    for name, card_id in ids.items():
        db.execute(
            "UPDATE card SET oracle_id = ?, mana_value = ? WHERE card_id = ?",
            (_oid(name), 2.0 if name == "Shatter" else 1.0, card_id),
        )
        for role in ROLES.get(name, []):
            db.execute("INSERT INTO card_role VALUES (?, ?, ?)", (_oid(name), role, SOURCE))
    # no free copy of this one (it sits in another deck)
    db.execute(
        "UPDATE inventory SET available_lower_bound = 0, reserved = 1 WHERE card_id = ?",
        (ids["Rem Reserved"],),
    )
    db.execute(
        "INSERT INTO scryfall_card(oracle_id, scryfall_id, name, front_name, layout, mana_cost, "
        "mana_value, type_line, oracle_text, color_identity, commander_legality, keywords, "
        "produced_mana, source_id) VALUES (?, 'sid', 'Outside Rem', 'Outside Rem', 'normal', "
        "'{G}', 3, 'Instant', '', 'G', 'legal', '[]', '', ?)",
        (_oid("Outside Rem"), SOURCE),
    )
    db.execute("INSERT INTO card_role VALUES (?, 'removal', ?)", (_oid("Outside Rem"), SOURCE))
    for index in range(decks):
        names = [name for name, members in PLAYS.items() if index in members]
        add_deck(store, f"d{index}", names, commanders=(COMMANDER,),
                 cohorts=["bracket:3"] if index < 4 else [])  # fmt: skip
    db.commit()
    return store, ids


def _swap(store: StudioStore, ids: dict[str, str], card: str, mode: str, **extra: object):
    deck = extra.pop("deck", ["Cmd A", "Shatter", "Rem Taken", "Draw", "Wasteland Basic"])
    return swap.swap_candidates(
        store,
        commander=COMMANDER,
        deck_card_ids=[ids[name] for name in deck],  # type: ignore[union-attr]
        card_id=ids[card],
        mode=mode,
        **extra,  # type: ignore[arg-type]
    )


def _names(result: dict[str, object]) -> list[str]:
    items = result["items"]
    assert isinstance(items, list)
    return [str(item["name"]) for item in items]


def test_replace_orders_by_decks_then_name_and_puts_unknown_last(tmp_path: Path) -> None:
    store, ids = _swap_store(tmp_path / "studio")
    result = _swap(store, ids, "Shatter", "replace")
    items = {str(i["name"]): i for i in result["items"]}  # type: ignore[attr-defined]
    # 'Shatter' has the roles removal and hate; the card in the deck, the commander, the basic
    # land, the card without a free copy and the card with another role are not listed.
    assert _names(result) == [
        "Rem Common",  # 8 of 10
        "Hate Only",  # 7 of 10 (shares 'hate')
        "Rem Mid",  # 5 of 10, tie with 'Rem Mid Two': by name
        "Rem Mid Two",
        "Rem Candidate",  # 1 of 10
        "Rem Rare",  # 1 of 10
        "Rem Unknown",  # not named by any deck: unknown, last
    ]
    assert result["roles_of_card"] == ["hate", "removal"]
    assert result["group"] == {"name": "all", "kind": "cohort", "decks": 10, "small": True}
    assert items["Rem Common"]["decks"] == 8 and items["Rem Common"]["of"] == 10
    assert items["Rem Common"]["share"] == 0.8
    assert items["Rem Common"]["shared_roles"] == ["removal"]
    assert items["Hate Only"]["shared_roles"] == ["hate"]
    assert items["Rem Common"]["mv_delta"] == -1.0
    unknown = items["Rem Unknown"]
    assert unknown["decks"] is None and unknown["share"] is None
    assert unknown["unknown_reason"] == "not_in_decks"
    assert result["unknown_count"] == 1
    assert result["fallback"] is None
    assert result["small_group"] is True and all(i["small_group"] for i in items.values())
    for hidden in ("Cmd A", "Wasteland Basic", "Rem Taken", "Draw", "Rem Reserved", "Shatter"):
        assert hidden not in items


def test_cut_lists_only_deck_cards_with_a_shared_role_rarest_first(tmp_path: Path) -> None:
    store, ids = _swap_store(tmp_path / "studio")
    deck = ["Cmd A", "Shatter", "Rem Common", "Rem Rare", "Rem Unknown", "Draw", "Wasteland Basic"]
    result = _swap(store, ids, "Rem Candidate", "cut", deck=deck)
    assert _names(result) == ["Rem Rare", "Shatter", "Rem Common", "Rem Unknown"]
    by_name = {str(i["name"]): i for i in result["items"]}  # type: ignore[attr-defined]
    assert [by_name[n]["decks"] for n in ("Rem Rare", "Shatter", "Rem Common")] == [1, 3, 8]
    assert by_name["Rem Unknown"]["decks"] is None and by_name["Rem Unknown"]["share"] is None
    assert result["unknown_count"] == 1
    assert all(item["in_deck"] for item in by_name.values())
    # the commander, the basic land and a card without a shared role are never cut candidates
    assert not {"Cmd A", "Wasteland Basic", "Draw", "Rem Candidate"} & set(by_name)


def test_unknown_is_last_and_never_zero_in_both_modes(tmp_path: Path) -> None:
    store, ids = _swap_store(tmp_path / "studio")
    for mode, deck in (("replace", ["Cmd A"]), ("cut", ["Cmd A", "Rem Unknown", "Rem Rare"])):
        result = _swap(
            store, ids, "Shatter" if mode == "replace" else "Rem Candidate", mode, deck=deck
        )
        decks = [item["decks"] for item in result["items"]]  # type: ignore[attr-defined]
        assert decks[-1] is None
        assert None not in decks[: decks.index(None)]
        assert 0 not in [d for d in decks if d is None]


def test_a_counted_zero_is_a_zero_and_unknown_is_not(tmp_path: Path) -> None:
    store, ids = _swap_store(tmp_path / "studio")
    result = _swap(store, ids, "Shatter", "replace", cohort="bracket:3")
    by_name = {str(i["name"]): i for i in result["items"]}  # type: ignore[attr-defined]
    assert result["group"]["decks"] == 4  # type: ignore[index]
    assert by_name["Rem Mid Two"]["decks"] == 0 and by_name["Rem Mid Two"]["share"] == 0.0
    assert by_name["Rem Unknown"]["decks"] is None
    assert _names(result)[-1] == "Rem Unknown"


def test_marks_and_labels_change_neither_order_nor_inclusion(tmp_path: Path) -> None:
    store, ids = _swap_store(tmp_path / "studio")
    before = {
        mode: _names(_swap(store, ids, card, mode))
        for mode, card in (("replace", "Shatter"), ("cut", "Rem Candidate"))
    }
    builder.set_mark(store, ids["Rem Rare"], favorite=True, excluded=False, note="mein Liebling")
    builder.set_mark(store, ids["Rem Common"], favorite=False, excluded=True, note="")
    builder.set_mark(store, ids["Shatter"], favorite=False, excluded=True, note="")
    labels.set_card_labels(store, ids["Rem Mid"], ["Tempo"])
    after = {
        mode: _names(_swap(store, ids, card, mode))
        for mode, card in (("replace", "Shatter"), ("cut", "Rem Candidate"))
    }
    assert after == before
    items = {str(i["name"]): i for i in _swap(store, ids, "Shatter", "replace")["items"]}  # type: ignore[attr-defined]
    # an existing display field, nothing more
    assert items["Rem Rare"]["favorite"] is True and items["Rem Common"]["excluded"] is True


def test_include_unowned_adds_reserved_and_outside_cards_last_among_equals(tmp_path: Path) -> None:
    store, ids = _swap_store(tmp_path / "studio")
    default = _swap(store, ids, "Shatter", "replace")
    assert "Rem Reserved" not in _names(default) and "Outside Rem" not in _names(default)
    assert default["include_unowned"] is False
    more = _swap(store, ids, "Shatter", "replace", include_unowned=True)
    by_name = {str(i["name"]): i for i in more["items"]}  # type: ignore[attr-defined]
    assert set(_names(default)) < set(_names(more))
    assert by_name["Rem Reserved"]["available"] == 0 and by_name["Rem Reserved"]["in_collection"]
    assert by_name["Rem Reserved"]["decks"] == 6
    outside = by_name["Outside Rem"]
    assert outside["card_id"] is None and outside["in_collection"] is False
    assert outside["available"] == 0 and outside["decks"] == 4 and outside["of"] == 10
    assert _names(more)[:3] == ["Rem Common", "Hate Only", "Rem Reserved"]
    # the extra cards fit the same order rule: decks descending, ties by name, unknown last
    known = [i["decks"] for i in more["items"] if i["decks"] is not None]  # type: ignore[attr-defined]
    assert known == sorted(known, reverse=True)
    assert _names(more)[-1] == "Rem Unknown"
    # a cut list names deck cards only: the switch changes nothing there
    cut_default = _swap(store, ids, "Rem Candidate", "cut")
    cut_more = _swap(store, ids, "Rem Candidate", "cut", include_unowned=True)
    assert _names(cut_default) == _names(cut_more)


def test_a_card_without_roles_falls_back_to_its_type_group_and_says_so(tmp_path: Path) -> None:
    store, ids = _swap_store(tmp_path / "studio")
    result = _swap(store, ids, "Plain Beast", "replace")
    assert result["roles_of_card"] == []
    assert result["fallback"] == {"kind": "type_group", "type_group": "Creature"}
    assert "keine Rollen erfasst" in str(result["basis"])
    assert _names(result) == ["Beast A", "Beast B"]  # only creatures, never the removal cards
    assert all(item["shared_roles"] == [] for item in result["items"])  # type: ignore[attr-defined]
    assert [item["decks"] for item in result["items"]] == [6, 2]  # type: ignore[attr-defined]


def test_denominators_and_counts_equal_the_pool_for_the_same_group(tmp_path: Path) -> None:
    store, ids = _swap_store(tmp_path / "studio")
    pool = builder.pool_cards(store, [COMMANDER], with_signals=False)
    by_id = {str(c["card_id"]): c for c in pool["cards"]}  # type: ignore[attr-defined]
    for cohort in ("all", "bracket:3"):
        result = _swap(store, ids, "Shatter", "replace", cohort=cohort, include_unowned=True)
        assert result["group"]["decks"] == pool["cohorts"][cohort]  # type: ignore[index]
        for item in result["items"]:  # type: ignore[attr-defined]
            assert item["of"] == pool["cohorts"][cohort]  # type: ignore[index]
            if item["card_id"] is None:
                continue
            card = by_id[item["card_id"]]
            if card["decks_known"]:
                assert item["decks"] == card["decks"][cohort]
            else:
                assert item["decks"] is None


def test_a_universe_profile_is_counted_like_the_pool_shows_it(tmp_path: Path) -> None:
    store, ids = _swap_store(tmp_path / "studio")
    universe.save_profile(store, "vier", {"cohorts": ["bracket:3"]})
    pool = builder.pool_cards(store, [COMMANDER], profile="vier", with_signals=False)
    by_id = {str(c["card_id"]): c for c in pool["cards"]}  # type: ignore[attr-defined]
    result = _swap(store, ids, "Shatter", "replace", universe="vier", include_unowned=True)
    assert result["group"] == {"name": "vier", "kind": "universe", "decks": 4, "small": True}
    assert result["group"]["decks"] == pool["universe"]["denominator"]  # type: ignore[index]
    for item in result["items"]:  # type: ignore[attr-defined]
        if item["card_id"] is None:
            assert item["decks"] == 4  # 'Outside Rem' is in decks 0..3
            continue
        shown = by_id[item["card_id"]]["universe"]
        assert item["decks"] == shown["hits"] and item["of"] == shown["denominator"]
    # four of four decks each, ties by name; the rest follow with fewer decks, unknown last
    assert _names(result)[:4] == ["Hate Only", "Outside Rem", "Rem Common", "Rem Mid"]
    assert _names(result)[-1] == "Rem Unknown"


def test_small_group_flag_follows_the_thirty_deck_line(tmp_path: Path) -> None:
    store, ids = _swap_store(tmp_path / "studio", decks=30)
    result = _swap(store, ids, "Shatter", "replace")
    assert result["group"]["decks"] == 30  # type: ignore[index]
    assert result["small_group"] is False and result["group"]["small"] is False  # type: ignore[index]
    assert not any(item["small_group"] for item in result["items"])  # type: ignore[attr-defined]
    assert "unsicher" not in str(result["basis"])
    small = _swap(store, ids, "Shatter", "replace", cohort="bracket:3")
    assert small["small_group"] is True and "unsicher" in str(small["basis"])


def test_limit_keeps_total_and_unknown_count_of_the_whole_list(tmp_path: Path) -> None:
    store, ids = _swap_store(tmp_path / "studio")
    result = _swap(store, ids, "Shatter", "replace", limit=2)
    assert _names(result) == ["Rem Common", "Hate Only"]
    assert result["total"] == 7 and result["unknown_count"] == 1


def test_an_empty_group_makes_everything_unknown_not_zero(tmp_path: Path) -> None:
    store, ids = _swap_store(tmp_path / "studio")
    # a group name no deck of this commander carries is not a group of this commander
    with pytest.raises(ValueError, match="Unbekannte Vergleichsgruppe"):
        _swap(store, ids, "Shatter", "replace", cohort="empty")
    other = make_store(tmp_path / "other")
    add_card(other, COMMANDER, type_line="Legendary Creature", identity="G")
    victim = add_card(other, "Lonely Card", type_line="Instant", identity="G")
    other.connection.execute("UPDATE card SET oracle_id = 'o1' WHERE card_id = ?", (victim,))
    other.connection.execute("INSERT INTO card_role VALUES ('o1', 'removal', ?)", (SOURCE,))
    peer = add_card(other, "Peer Card", type_line="Instant", identity="G")
    other.connection.execute("UPDATE card SET oracle_id = 'o2' WHERE card_id = ?", (peer,))
    other.connection.execute("INSERT INTO card_role VALUES ('o2', 'removal', ?)", (SOURCE,))
    result = swap.swap_candidates(
        other, commander=COMMANDER, deck_card_ids=[], card_id=victim, mode="replace"
    )
    assert result["group"]["decks"] == 0  # type: ignore[index]
    assert [(i["name"], i["decks"], i["share"]) for i in result["items"]] == [  # type: ignore[attr-defined]
        ("Peer Card", None, None)
    ]
    assert result["unknown_count"] == 1
    assert "keine Quelldecks" in str(result["basis"])


def _client(tmp_path: Path) -> tuple[TestClient, dict[str, str]]:
    folder = tmp_path / "studio"
    store, ids = _swap_store(folder)
    store.close()
    return TestClient(create_app(folder), headers={"X-Studio": "1"}), ids


def _post(client: TestClient, ids: dict[str, str], **fields: object):
    body: dict[str, object] = {
        "commander": COMMANDER,
        "deck_card_ids": [ids["Cmd A"], ids["Shatter"]],
        "card_id": ids["Shatter"],
        "mode": "replace",
        "cohort": "all",
    }
    body.update(fields)
    return client.post("/api/swap", json=body)


def test_route_answers_and_matches_the_pool_route(tmp_path: Path) -> None:
    client, ids = _client(tmp_path)
    answer = _post(client, ids)
    assert answer.status_code == 200
    data = answer.json()
    assert [i["name"] for i in data["items"]][:2] == ["Rem Common", "Hate Only"]
    pool = client.get("/api/pool", params={"commander": COMMANDER}).json()
    assert data["group"]["decks"] == pool["cohorts"]["all"] == 10
    by_id = {c["card_id"]: c for c in pool["cards"]}
    for item in data["items"]:
        assert item["decks"] == by_id[item["card_id"]]["decks"].get("all", None)
    with_more = _post(client, ids, include_unowned=True).json()
    assert "Outside Rem" in [i["name"] for i in with_more["items"]]
    cut = _post(client, ids, mode="cut", card_id=ids["Rem Candidate"]).json()
    assert [i["name"] for i in cut["items"]] == ["Shatter"]


@pytest.mark.parametrize(
    ("fields", "status"),
    [
        ({"mode": "swap"}, 422),
        ({"cohort": "gibt-es-nicht"}, 422),
        ({"limit": 0}, 422),
        ({"limit": 301}, 422),
        ({"exclude_marked": True}, 422),
        ({"card_id": ""}, 422),
        ({"deck_card_ids": ["card:nope"]}, 422),
        ({"deck_card_ids": ["x"] * 301}, 422),
        ({"commander": []}, 422),
        ({"commander": ["a", "b", "c"]}, 422),
        ({"card_id": "card:nope"}, 404),
        ({"commander": "Nobody"}, 404),
        ({"universe": "keins"}, 404),
    ],
)
def test_route_validation(tmp_path: Path, fields: dict[str, object], status: int) -> None:
    client, ids = _client(tmp_path)
    assert _post(client, ids, **fields).status_code == status


def test_route_refuses_the_commander_and_a_basic_land_as_the_card(tmp_path: Path) -> None:
    client, ids = _client(tmp_path)
    assert _post(client, ids, card_id=ids["Cmd A"]).status_code == 422
    assert _post(client, ids, card_id=ids["Wasteland Basic"]).status_code == 422


def test_no_price_purchase_or_verdict_wording_in_answers_or_page_code(tmp_path: Path) -> None:
    client, ids = _client(tmp_path)
    texts = [
        json.dumps(_post(client, ids, include_unowned=True).json(), ensure_ascii=False),
        json.dumps(_post(client, ids, mode="cut").json(), ensure_ascii=False),
        json.dumps(_post(client, ids, card_id=ids["Plain Beast"]).json(), ensure_ascii=False),
        (STATIC / "swap.js").read_text(encoding="utf-8"),
    ]
    for text in texts:
        low = text.casefold()
        for word in ("besser", "kaufen", "zukauf", "preis", "price", "euro", "usd", "€"):
            assert word not in low, word
    assert "innerHTML" not in texts[-1]


def _seed_swap_store(tmp_path: Path) -> StudioStore:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    source_id = str(store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0])
    with store.connection as db:
        # Add 4 cards across 2 roles ('removal' and 'card_draw') + 1 card with unknown frequency:
        # Removal cards:
        # - 'rem-high': Swords to Plowshares (in d1, d2, d3 -> 3/3, available in pool)
        # - 'rem-mid': Path to Exile (in d1, d2 -> 2/3, available in pool)
        # - 'rem-low': Shattered Acolyte (in d1 -> 1/3, in deck)
        # - 'rem-unk': Obscure Purge (not in corpus_deck_card -> decks_known is False, available in pool)
        # Card draw card:
        # - 'draw-high': Harmonize (in d1, d2, d3 -> 3/3, role 'card_draw' only)
        cards = [
            ("rem-high", "Swords to Plowshares", "oid-rem-high", "removal"),
            ("rem-mid", "Path to Exile", "oid-rem-mid", "removal"),
            ("rem-low", "Shattered Acolyte", "oid-rem-low", "removal"),
            ("rem-unk", "Obscure Purge", "oid-rem-unk", "removal"),
            ("draw-high", "Harmonize", "oid-draw-high", "card_draw"),
        ]
        for cid, name, oid, role in cards:
            db.execute(
                "INSERT INTO card (card_id, oracle_id, oracle_name, color_identity, mana_cost, "
                "mana_value, type_line, oracle_text, is_basic_land, commander_legal, "
                "legality_verified_at, identity_evidence, source_id) "
                "VALUES (?, ?, ?, 'G', '{1}{G}', 2, 'Instant', '', 0, 1, '2026-11-15', 'scryfall', ?)",
                (cid, oid, name, source_id),
            )
            db.execute(
                "INSERT INTO inventory VALUES (?, 1, 1, 0, 1, 1, 1, '2026-11-15', ?)",
                (cid, source_id),
            )
            db.execute(
                "INSERT INTO card_role VALUES (?, ?, ?)",
                (oid, role, source_id),
            )

        for did in ("d1", "d2", "d3"):
            db.execute(
                "INSERT INTO corpus_deck_card VALUES (?, 'Swords to Plowshares', 'oid-rem-high', 1, 'main', 'exact')",
                (did,),
            )
            db.execute(
                "INSERT INTO corpus_deck_card VALUES (?, 'Harmonize', 'oid-draw-high', 1, 'main', 'exact')",
                (did,),
            )
        for did in ("d1", "d2"):
            db.execute(
                "INSERT INTO corpus_deck_card VALUES (?, 'Path to Exile', 'oid-rem-mid', 1, 'main', 'exact')",
                (did,),
            )
        db.execute(
            "INSERT INTO corpus_deck_card VALUES ('d1', 'Shattered Acolyte', 'oid-rem-low', 1, 'main', 'exact')"
        )
    return store


def test_swap_and_decklist_parse_routes_and_german_validation(tmp_path: Path) -> None:
    store = _seed_swap_store(tmp_path)
    # Verify role_coverage_median in cohort_shapes (Proposal 4 / D2)
    shapes = {row["cohort"]: row for row in builder.cohort_shapes(store, ["Test Commander"])}
    assert "role_coverage_median" in shapes["all"]
    assert shapes["all"]["role_coverage_median"] is not None

    # Verify German validation message (D7)
    pool_payload = builder.pool_cards(store, ["Test Commander"])
    cmd_id = str(pool_payload["commander_ids"][0])

    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})

    created = client.post(
        "/api/decks", json={"name": "Chulane Test", "commander_card_ids": [cmd_id]}
    ).json()
    rev = client.get(f"/api/revisions/{created['revision_id']}").json()
    size_issues = [i for i in rev["issues"] if i["code"] == "deck_size"]
    assert size_issues and "ein Commander-Deck hat 100" in size_issues[0]["message"]

    resp = client.post(
        "/api/swap",
        json={
            "commander": "Test Commander",
            "deck_card_ids": [cmd_id, "rem-low", "rem-mid"],
            "card_id": "rem-low",
            "mode": "replace",
            "cohort": "all",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["name"] == "Swords to Plowshares"

    parse_resp = client.post(
        "/api/decklist-parse",
        json={
            "commander": "Test Commander",
            "text": "// Maindeck\n1x Swords to Plowshares (2X2) 31\n4 Forest\n1 Black Lotus\n",
        },
    )
    assert parse_resp.status_code == 200
    parsed = parse_resp.json()
    in_names = {row["name"]: row["quantity"] for row in parsed["in_collection"]}
    assert in_names == {"Swords to Plowshares": 1, "Forest": 4}
    missing_names = [row["name"] for row in parsed["not_in_collection"]]
    assert missing_names == ["Black Lotus"]
    raw_text = str(parsed).casefold()
    for forbidden in ("kaufen", "zukauf", "preis", "eur", "usd", "$", "€"):
        assert forbidden not in raw_text
