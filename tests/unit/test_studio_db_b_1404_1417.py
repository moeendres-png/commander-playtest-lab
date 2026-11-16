"""Self-contained unit tests for PR DB-B (#1404 op. 5/7/10, #1413, #1417, B-1, B-2, B-7, decks.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import (
    StudioStore,
    builder,
    combos,
    decks,
    packages,
    similar_decks,
    strength_view,
    swap,
)
from commander_lab.studio.decks import RevisionCard
from commander_lab.studio.store import now_utc
from commander_lab.studio.strength import StrengthSettings
from commander_lab.studio.web import create_app

COMMANDER = "Chulane, Teller of Tales"
REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "commander_lab" / "studio" / "static"


def _ensure_source(store: StudioStore, source_id: str, data_class: str, title: str) -> None:
    store.connection.execute(
        "INSERT OR IGNORE INTO source (source_id, data_class, title, sha256, imported_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (source_id, data_class, title, "0" * 64, now_utc()),
    )


def _add_card(
    store: StudioStore,
    card_id: str,
    name: str,
    *,
    identity: str = "G,U,W",
    mana_cost: str = "{1}{G}",
    mana_value: float = 2.0,
    type_line: str = "Creature — Elf Druid",
    oracle_text: str = "Tap: Add {G}.",
    legal: int = 1,
    owned: int = 1,
    available: int = 1,
    roles: tuple[str, ...] = (),
    is_basic: int = 0,
    oracle_id: str | None = None,
    front_name: str | None = None,
    keywords: str = "[]",
    power: str | None = None,
    toughness: str | None = None,
) -> None:
    oid = oracle_id or f"oid-{card_id}"
    src_id = "src-card-fixture"
    with store.connection:
        _ensure_source(store, src_id, "ORIGINAL_SOURCE", "Test Card Fixture")
        store.connection.execute(
            "INSERT OR REPLACE INTO card "
            "(card_id, oracle_id, oracle_name, color_identity, mana_cost, mana_value, "
            "type_line, oracle_text, is_basic_land, commander_legal, source_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                card_id,
                oid,
                name,
                identity,
                mana_cost,
                mana_value,
                type_line,
                oracle_text,
                is_basic,
                legal,
                src_id,
            ),
        )
        store.connection.execute(
            "INSERT OR REPLACE INTO inventory "
            "(card_id, observed, owned_lower_bound, reserved, available_lower_bound, "
            "quantity_exact, source_id) "
            "VALUES (?, 1, ?, 0, ?, ?, ?)",
            (card_id, owned, available, owned, src_id),
        )
        for role in roles:
            store.connection.execute(
                "INSERT OR IGNORE INTO card_role (oracle_id, role, source_id) VALUES (?, ?, ?)",
                (oid, role, src_id),
            )
        store.connection.execute(
            "INSERT OR REPLACE INTO scryfall_card "
            "(oracle_id, scryfall_id, name, front_name, layout, mana_cost, mana_value, "
            "type_line, oracle_text, color_identity, commander_legality, keywords, "
            "produced_mana, power, toughness, source_id) "
            "VALUES (?, ?, ?, ?, 'normal', ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, ?)",
            (
                oid,
                f"scry-{card_id}",
                name,
                front_name or name.split(" // ")[0],
                mana_cost,
                mana_value,
                type_line,
                oracle_text,
                identity,
                "legal" if legal else "not_legal",
                keywords,
                power,
                toughness,
                src_id,
            ),
        )


def _add_corpus_deck(
    store: StudioStore,
    deck_id: str,
    commander: str,
    cohorts: tuple[str, ...],
    cards: list[str],
    *,
    platform: str = "edhrec",
    play_group: str = "community",
) -> None:
    src_id = "src-corpus"
    cohort_primary = cohorts[0] if cohorts else "all"
    with store.connection:
        _ensure_source(store, src_id, "ORIGINAL_SOURCE", "Test Corpus")
        store.connection.execute(
            "INSERT INTO corpus_deck "
            "(deck_id, cohort, url, platform, play_group, tags, fingerprint, "
            "legality_audit, source_id) "
            "VALUES (?, ?, ?, ?, ?, '[]', ?, 'LEGAL', ?)",
            (
                deck_id,
                cohort_primary,
                f"https://example.invalid/{deck_id}",
                platform,
                play_group,
                f"fp-{deck_id}",
                src_id,
            ),
        )
        store.connection.execute(
            "INSERT OR IGNORE INTO commander_binding (kind, key, commander_name, basis) "
            "VALUES ('corpus_deck', ?, ?, 'test')",
            (deck_id, commander),
        )
        for coh in cohorts:
            store.connection.execute(
                "INSERT OR IGNORE INTO corpus_cohort (cohort, deck_id) VALUES (?, ?)",
                (coh, deck_id),
            )
        for card_name in cards:
            store.connection.execute(
                "INSERT INTO corpus_deck_card "
                "(deck_id, card_name, quantity, section, normalization_status) "
                "VALUES (?, ?, 1, 'main', 'OK')",
                (deck_id, card_name),
            )


def _build_fixture_store(tmp_path: Path) -> StudioStore:
    store = StudioStore.open(tmp_path)
    _add_card(
        store,
        "cmd-1",
        COMMANDER,
        identity="G,U,W",
        mana_cost="{2}{G}{W}{U}",
        mana_value=5.0,
        type_line="Legendary Creature — Human Druid",
        oracle_text="Vigilance. Whenever you cast a creature spell, draw a card.",
        keywords='["Vigilance"]',
        power="2",
        toughness="4",
    )
    _add_card(
        store,
        "c-dork1",
        "Llanowar Elves",
        identity="G",
        mana_cost="{G}",
        mana_value=1.0,
        type_line="Creature — Elf Druid",
        oracle_text="{T}: Add {G}.",
        roles=("ramp", "mana_dork"),
        power="1",
        toughness="1",
    )
    _add_card(
        store,
        "c-dork2",
        "Birds of Paradise",
        identity="G",
        mana_cost="{G}",
        mana_value=1.0,
        type_line="Creature — Bird",
        oracle_text="Flying. {T}: Add one mana of any color.",
        roles=("ramp", "mana_dork"),
        keywords='["Flying"]',
        power="0",
        toughness="1",
    )
    _add_card(
        store,
        "c-dork3",
        "Elvish Mystic",
        identity="G",
        mana_cost="{G}",
        mana_value=1.0,
        type_line="Creature — Elf Druid",
        oracle_text="{T}: Add {G}.",
        roles=("ramp", "mana_dork"),
        power="1",
        toughness="1",
    )
    _add_card(
        store,
        "c-bounce",
        "Shrieking Drake",
        identity="U",
        mana_cost="{U}",
        mana_value=1.0,
        type_line="Creature — Drake",
        oracle_text="Flying. When Shrieking Drake enters, return a creature you control to its owner's hand.",
        roles=("bounce", "flicker"),
        keywords='["Flying"]',
        power="1",
        toughness="1",
    )
    _add_card(
        store,
        "c-alarm",
        "Intruder Alarm",
        identity="U",
        mana_cost="{2}{U}",
        mana_value=3.0,
        type_line="Enchantment",
        oracle_text="Whenever a creature enters, untap all creatures.",
        roles=("untapper",),
    )
    _add_card(
        store,
        "c-draw",
        "Rhystic Study",
        identity="U",
        mana_cost="{2}{U}",
        mana_value=3.0,
        type_line="Enchantment",
        oracle_text="Whenever an opponent casts a spell, you may draw a card unless that player pays {1}.",
        roles=("card_draw",),
    )
    _add_card(
        store,
        "c-unseen",
        "Obscure Elk",
        identity="G",
        mana_cost="{2}{G}",
        mana_value=3.0,
        type_line="Creature — Elk",
        oracle_text="Trample.",
        roles=("ramp",),
        keywords='["Trample"]',
    )
    # Card outside Chulane's color identity (Black) — in collection but NEVER in pool!
    _add_card(
        store,
        "c-black",
        "Demonic Tutor",
        identity="B",
        mana_cost="{1}{B}",
        mana_value=2.0,
        type_line="Sorcery",
        oracle_text="Search your library for a card, put that card into your hand, then shuffle.",
        roles=("tutor",),
    )
    _add_card(
        store,
        "c-forest",
        "Forest",
        identity="G",
        mana_cost="",
        mana_value=0.0,
        type_line="Basic Land — Forest",
        oracle_text="({T}: Add {G}.)",
        is_basic=1,
        owned=20,
        available=20,
    )

    # 8 decks total: 4 in bracket:4, 2 in bracket:5, 2 in bracket:3 -> tuned = 6 (B4+B5)
    for i in range(4):
        cards = ["Birds of Paradise", "Shrieking Drake", "Intruder Alarm", "Rhystic Study"]
        if i == 0:
            cards.append("Llanowar Elves")
        if i < 3:
            cards.append("Elvish Mystic")
        _add_corpus_deck(store, f"d-b4-{i}", COMMANDER, ("bracket:4",), cards)

    for i in range(2):
        _add_corpus_deck(
            store,
            f"d-b5-{i}",
            COMMANDER,
            ("bracket:5",),
            ["Birds of Paradise", "Shrieking Drake", "Intruder Alarm", "Elvish Mystic"],
        )

    for i in range(2):
        _add_corpus_deck(
            store,
            f"d-b3-{i}",
            COMMANDER,
            ("bracket:3",),
            ["Llanowar Elves", "Rhystic Study"],
        )

    # Foreign commander deck must remain strictly isolated
    _add_corpus_deck(
        store,
        "d-other",
        "Other Commander",
        ("bracket:4",),
        ["Obscure Elk", "Birds of Paradise"],
    )

    # Global shares + commander signals for swap lift & strength tests
    with store.connection:
        _ensure_source(store, "src-sig", "OBSERVED_COHORT", "Signals")
        for name, val, num, den in [
            ("Llanowar Elves", 0.08, 800, 10000),
            ("Elvish Mystic", 0.10, 1000, 10000),
            ("Birds of Paradise", 0.50, 5000, 10000),
            # Note: Obscure Elk has NO global signal -> lift is unknown (None), sorts last!
        ]:
            store.connection.execute(
                "INSERT INTO card_signal "
                "(commander_name, card_name, signal, value, numerator, denominator, source_id) "
                "VALUES ('', ?, 'edhrec_global_inclusion', ?, ?, ?, 'src-sig')",
                (name, val, num, den),
            )
        for name, val, num, den in [
            ("Birds of Paradise", 0.80, 800, 1000),
            ("Shrieking Drake", 0.70, 700, 1000),
            ("Elvish Mystic", 0.40, 400, 1000),
            ("Llanowar Elves", 0.25, 250, 1000),
            ("Intruder Alarm", 0.60, 600, 1000),
        ]:
            store.connection.execute(
                "INSERT INTO card_signal "
                "(commander_name, card_name, signal, value, numerator, denominator, source_id) "
                "VALUES (?, ?, 'edhrec_commander_inclusion', ?, ?, ?, 'src-sig')",
                (COMMANDER, name, val, num, den),
            )
    return store


def _sample_deck_entries() -> list[RevisionCard]:
    return [
        RevisionCard("cmd-1", 1, "commander"),
        RevisionCard("c-dork1", 1, "main"),
        RevisionCard("c-bounce", 1, "main"),
        RevisionCard("c-unseen", 1, "main"),
        RevisionCard("c-forest", 10, "main"),
    ]


def test_offline_scryfall_query_evaluator_and_fail_closed() -> None:
    cards = [
        {
            "name": "Shrieking Drake",
            "front_name": "Shrieking Drake",
            "type_line": "Creature — Drake",
            "oracle_text": "Flying. Return a creature.",
            "keywords": frozenset({"flying"}),
            "mana_value": 1.0,
            "mana_cost": "{U}",
            "identity": frozenset({"U"}),
            "mana_colors": frozenset({"U"}),
            "commander_legal": True,
            "power": "1",
            "toughness": "1",
        },
        {
            "name": "Sol Ring",
            "front_name": "Sol Ring",
            "type_line": "Artifact",
            "oracle_text": "{T}: Add {C}{C}.",
            "keywords": frozenset(),
            "mana_value": 1.0,
            "mana_cost": "{1}",
            "identity": frozenset(),
            "mana_colors": frozenset(),
            "commander_legal": True,
            "power": None,
            "toughness": None,
        },
    ]
    st, reason, hits = combos.evaluate_scryfall_query(
        "t:creature kw:flying mv<=2 (mana={U} OR id=u) is:permanent legal:commander",
        cards,
    )
    assert st == "OK"
    assert reason is None
    assert [c["name"] for c in hits] == ["Shrieking Drake"]

    # Missing, empty, or unsupported queries MUST fail closed to UNKNOWN (never 0)
    for bad in (None, "", "   ", "otag:ramp", "t:/drake/", "-m<{0}", "unknownfield:1"):
        bad_st, bad_reason, bad_hits = combos.evaluate_scryfall_query(bad, cards)
        assert bad_st == "UNKNOWN", bad
        assert bad_reason
        assert bad_hits == []


def test_deck_combos_template_slots_and_pool_shells_fail_closed(tmp_path: Path) -> None:
    store = _build_fixture_store(tmp_path)
    try:
        tpl_path = tmp_path / "templates.json"
        tpl_path.write_text(
            json.dumps(
                {
                    "commander": COMMANDER,
                    "pool_shells": [
                        {
                            "shell_id": 101,
                            "variant_id": "v101",
                            "uses": ["Shrieking Drake", "Intruder Alarm"],
                            "with_commander": True,
                            "produces": ["Infinite ETB"],
                        }
                    ],
                    "template_shells": [
                        {
                            "shell_id": 202,
                            "variant_id": "v202",
                            "uses": ["Shrieking Drake"],
                            "missing_from_pool": [],
                            "with_commander": True,
                            "produces": ["Infinite creature casts"],
                            "requires": [
                                {
                                    "template_id": "t-ok",
                                    "name": "Creature tapping for mana",
                                    "scryfall_query": 't:creature o:"Add {G}"',
                                    "quantity": 1,
                                },
                                {
                                    "template_id": "t-unk-otag",
                                    "name": "Supported fallback unknown",
                                    "scryfall_query": "otag:mana-dork t:creature",
                                    "quantity": 1,
                                },
                                {
                                    "template_id": "t-none",
                                    "name": "Missing query slot",
                                    "scryfall_query": None,
                                    "quantity": 1,
                                },
                                {
                                    "template_id": "t-zone",
                                    "name": "Zone and commander condition not evaluated",
                                    "scryfall_query": "t:creature",
                                    "quantity": 1,
                                    "must_be_commander": True,
                                    "zone_locations": ["B"],
                                },
                                {
                                    "template_id": "t-tutor",
                                    "name": "Sorcery outside commander identity",
                                    "scryfall_query": "t:sorcery",
                                    "quantity": 1,
                                },
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        rows = decks.list_rows(store, _sample_deck_entries())
        result = combos.deck_combos(store, rows, [COMMANDER], template_snapshot_path=tpl_path)
        assert result["template_status"] == "OK"
        assert len(result["pool_shells"]) == 1  # type: ignore[arg-type]
        assert result["pool_shells"][0]["missing_from_deck"] == ["Intruder Alarm"]  # type: ignore[index]

        slots = result["template_slots"][0]["slots"]  # type: ignore[index]
        by_id = {s["template_id"]: s for s in slots}

        assert by_id["t-ok"]["status"] == "OK"
        assert by_id["t-ok"]["fulfilled_in_deck"] is True
        assert by_id["t-ok"]["deck"]["hits"] >= 1
        assert by_id["t-ok"]["pool"]["hits"] >= 2

        # The evaluator ignores zone/commander conditions: only partly checked
        assert by_id["t-zone"]["partially_checked"] is True
        assert by_id["t-ok"]["partially_checked"] is False
        assert isinstance(by_id["t-ok"]["matches_in_pool_total"], int)

        # Unsupported or missing query MUST stay UNKNOWN with None hits (never 0!)
        for unk_id in ("t-unk-otag", "t-none"):
            assert by_id[unk_id]["status"] == "UNKNOWN"
            assert by_id[unk_id]["fulfilled_in_deck"] is False
            assert by_id[unk_id]["deck"]["hits"] is None
            assert by_id[unk_id]["pool"]["hits"] is None
            assert by_id[unk_id]["collection"]["hits"] is None
            assert by_id[unk_id]["matches_in_pool_total"] is None  # never 0 when unknown

        # Demonic Tutor is black -> counted in collection (1), NOT in Chulane pool (0)
        assert by_id["t-tutor"]["status"] == "OK"
        assert by_id["t-tutor"]["pool"]["hits"] == 0
        assert by_id["t-tutor"]["collection"]["hits"] == 1

        # Commander mismatch refuses foreign snapshot
        foreign = combos.deck_combos(
            store, rows, ["Other Commander"], template_snapshot_path=tpl_path
        )
        assert foreign["template_status"] == "NOT_COLLECTED"
        assert foreign["pool_shells"] == []
    finally:
        store.close()


def test_decks_bom_detection_and_baseline_path_hardening(tmp_path: Path) -> None:
    assert decks._detect_format(["\ufeffName,Quantity", "Sol Ring,1"]) == "csv"
    assert decks._detect_format(["\ufeff1x Llanowar Elves [Ramp]"]) == "archidekt"

    safe_dir = tmp_path / "decks"
    safe_dir.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("1 Black Lotus\n", encoding="utf-8")
    link = safe_dir / "escape.txt"
    link.symlink_to(outside)

    for bad_id in ("repo:../secret", "repo:foo/bar", "repo:foo\x00bar", "repo:escape"):
        with pytest.raises(KeyError):
            decks.resolve_repo_baseline_cards(
                StudioStore.in_memory(),
                bad_id,
                commander_names=[COMMANDER],
                decks_dir=safe_dir,
            )


def test_tuned_cohort_in_builder_and_similar_decks_and_cooccurrence(tmp_path: Path) -> None:
    store = _build_fixture_store(tmp_path)
    try:
        sizes = builder.cohort_sizes(store, [COMMANDER])
        assert sizes["bracket:4"] == 4
        assert sizes["bracket:5"] == 2
        assert sizes["tuned"] == 6  # combined derived B4+B5 without foreign commander

        # _canonical_name exact casefold tie-break
        owners = {"fire": ["Fire // Ice", "fire", "Fire"]}
        assert similar_decks._canonical_name(owners, "fire") == "Fire"

        # Similar decks tuned cohort only inspects the 6 B4/B5 decks
        sim = similar_decks.find_similar_decks(
            store,
            [COMMANDER],
            deck_card_ids=["c-bounce", "c-dork1"],
            cohort="tuned",
        )
        assert sim["decks_considered"] == 6

        # Cooccurrence computes lift & partner markers cleanly within SQL budget
        co = builder.card_cooccurrence(store, "c-bounce", [COMMANDER], cohort="tuned", limit=10)
        assert co["card_decks"] == 6
        cards = {item["name"]: item for item in co["cards"]}
        assert cards["Birds of Paradise"]["both_hits"] == 6
        assert cards["Birds of Paradise"]["partner_decks"] == 6
        assert cards["Birds of Paradise"]["cohort_decks"] == 6
        assert cards["Birds of Paradise"]["lift"] == pytest.approx(1.0)
        assert "combo_partner" in cards["Birds of Paradise"]
    finally:
        store.close()


def test_swap_lift_sorting_and_unknown_last(tmp_path: Path) -> None:
    store = _build_fixture_store(tmp_path)
    try:
        res = swap.swap_candidates(
            store,
            commander=COMMANDER,
            deck_card_ids=["c-dork1"],
            card_id="c-dork1",
            mode="replace",
            cohort="tuned",
            sort_by="lift",
        )
        assert res["sort_by"] == "lift"
        names = [c["name"] for c in res["candidates"]]  # type: ignore[index]
        # Elvish Mystic: cohort share 5/6 (0.8333) / global 0.10 -> lift 8.33
        # Birds of Paradise: cohort share 6/6 (1.0) / global 0.50 -> lift 2.00
        # Obscure Elk: missing global inclusion -> lift None -> MUST be strictly last!
        assert names == ["Elvish Mystic", "Birds of Paradise", "Obscure Elk"]
        last = res["candidates"][-1]  # type: ignore[index]
        assert last["lift"] is None
        assert res["unknown_count"] == 1

        with pytest.raises(ValueError):
            swap.swap_candidates(
                store,
                commander=COMMANDER,
                deck_card_ids=["c-dork1"],
                card_id="c-dork1",
                mode="replace",
                sort_by="invalid",
            )
    finally:
        store.close()


def test_strength_view_role_ranks_and_score_invariance(tmp_path: Path) -> None:
    store = _build_fixture_store(tmp_path)
    try:
        res = strength_view.compute(store, COMMANDER, StrengthSettings())
        by_name = {c["name"]: c for c in res["cards"]}
        # Birds of Paradise has higher commander inclusion than Elvish Mystic and Llanowar Elves
        birds = by_name["Birds of Paradise"]
        mystic = by_name["Elvish Mystic"]
        elves = by_name["Llanowar Elves"]
        assert birds["tier"] not in ("U", "N")
        assert birds["role_ranks"]["ramp"]["rank"] < mystic["role_ranks"]["ramp"]["rank"]
        assert mystic["role_ranks"]["ramp"]["rank"] < elves["role_ranks"]["ramp"]["rank"]
        # Unscored cards (U/N) receive no role ranks and never consume rank slots
        assert by_name[COMMANDER]["tier"] == "N"
        assert by_name[COMMANDER]["role_ranks"] == {}
        assert by_name["Obscure Elk"]["tier"] == "U"
        assert by_name["Obscure Elk"]["role_ranks"] == {}
        assert (
            birds["role_ranks"]["ramp"]["total"]
            == mystic["role_ranks"]["ramp"]["total"]
            == elves["role_ranks"]["ramp"]["total"]
            == 3
        )
    finally:
        store.close()


def test_packages_build_plan_upgrade_path_and_mark_invariance(tmp_path: Path) -> None:
    store = _build_fixture_store(tmp_path)
    try:
        tpl_path = tmp_path / "tpl.json"
        tpl_path.write_text(
            json.dumps(
                {
                    "commander": COMMANDER,
                    "pool_shells": [
                        {
                            "shell_id": 77,
                            "variant_id": "v77",
                            "uses": ["Shrieking Drake", "Intruder Alarm"],
                            "produces": ["Infinite mana"],
                        }
                    ],
                    "template_shells": [],
                }
            ),
            encoding="utf-8",
        )
        cards = _sample_deck_entries()
        plan_before = packages.build_plan(store, [COMMANDER], cards, cohort="tuned")
        pkgs_before = packages.deck_packages(
            store, [COMMANDER], cards, cohort="tuned", template_snapshot_path=tpl_path
        )
        upg_before = packages.upgrade_path(store, [COMMANDER], cards, cohort="tuned")

        assert len(plan_before["steps"]) == 6  # type: ignore[arg-type]
        assert plan_before["cohort_decks"] == 6
        assert plan_before["small_sample"] is True  # 6 < 30 flagged
        assert plan_before["pool_total"] > 0
        assert all(
            "pool_tagged" in row and "pool_total" in row
            for row in plan_before["role_coverage"]  # type: ignore[attr-defined]
        )

        # Synergy & shell packages
        assert len(pkgs_before["shell_packages"]) == 1  # type: ignore[arg-type]
        assert pkgs_before["small_sample"] is True

        # Upgrade path keeps unknown Obscure Elk separated (never 0) and suggests Birds/Mystic over Elves
        unk_names = [u["name"] for u in upg_before["unknown_corpus_cards"]]  # type: ignore[index]
        assert unk_names == ["Obscure Elk"]
        cuts = {s["cut"]["name"]: s for s in upg_before["swap_suggestions"]}  # type: ignore[index]
        assert "Llanowar Elves" in cuts
        alt_names = [a["name"] for a in cuts["Llanowar Elves"]["alternatives"]]
        assert "Birds of Paradise" in alt_names

        # Mark invariance: favorites, exclusions, and notes MUST NOT change any output!
        with store.connection:
            for cid, fav, excl, note in [
                ("c-dork2", 0, 1, "skip me"),
                ("c-dork1", 1, 0, "pet card"),
                ("c-unseen", 1, 0, "love elk"),
            ]:
                store.connection.execute(
                    "INSERT OR REPLACE INTO card_mark "
                    "(card_id, favorite, excluded, note, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (cid, fav, excl, note, now_utc()),
                )

        assert packages.build_plan(store, [COMMANDER], cards, cohort="tuned") == plan_before
        assert (
            packages.deck_packages(
                store, [COMMANDER], cards, cohort="tuned", template_snapshot_path=tpl_path
            )
            == pkgs_before
        )
        assert packages.upgrade_path(store, [COMMANDER], cards, cohort="tuned") == upg_before
    finally:
        store.close()


def test_web_routes_packages_build_plan_upgrade_path_and_swap_lift(tmp_path: Path) -> None:
    folder = tmp_path / "web"
    folder.mkdir()
    store = _build_fixture_store(folder)
    store.close()

    with TestClient(create_app(folder)) as client:
        payload_cards = [
            {"card_id": c.card_id, "quantity": c.quantity, "zone": c.zone}
            for c in _sample_deck_entries()
        ]
        hdr = {"x-studio": "1"}
        r_plan = client.post(
            "/api/build-plan",
            headers=hdr,
            json={"commander": COMMANDER, "cards": payload_cards, "cohort": "tuned"},
        )
        assert r_plan.status_code == 200, r_plan.text
        assert len(r_plan.json()["steps"]) == 6

        r_pkg = client.post(
            "/api/packages",
            headers=hdr,
            json={"commander": COMMANDER, "cards": payload_cards, "cohort": "tuned"},
        )
        assert r_pkg.status_code == 200, r_pkg.text
        assert r_pkg.json()["schema"] == packages.PACKAGES_SCHEMA

        r_upg = client.post(
            "/api/upgrade-path",
            headers=hdr,
            json={"commander": COMMANDER, "cards": payload_cards, "cohort": "tuned"},
        )
        assert r_upg.status_code == 200, r_upg.text
        assert r_upg.json()["schema"] == packages.UPGRADE_PATH_SCHEMA

        r_swap = client.post(
            "/api/swap",
            headers=hdr,
            json={
                "commander": COMMANDER,
                "deck_card_ids": ["c-dork1"],
                "card_id": "c-dork1",
                "mode": "replace",
                "cohort": "tuned",
                "sort_by": "lift",
            },
        )
        assert r_swap.status_code == 200, r_swap.text
        assert r_swap.json()["sort_by"] == "lift"


def test_studio_static_csp_and_db_b_ui_markers() -> None:
    pkg_js = (STATIC_DIR / "packages.js").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    tier_js = (STATIC_DIR / "tierliste.js").read_text(encoding="utf-8")
    decks_html = (STATIC_DIR / "decks.html").read_text(encoding="utf-8")
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    # CSP: no innerHTML / eval DOM sinks in new & touched JS modules
    assert ".innerHTML" not in pkg_js
    assert ".outerHTML" not in pkg_js
    assert "eval(" not in pkg_js
    assert ".innerHTML" not in app_js
    assert ".outerHTML" not in app_js

    # UI markers for PR DB-B
    assert '<script src="packages.js"></script>' in index_html
    assert 'value="tuned"' in decks_html
    assert '["plan", "Bauplan"]' in app_js
    assert '["packages", "Pakete & Upgrade"]' in app_js
    assert "showStrengthBreakdown" in app_js
    assert "Sort: Lift" in app_js
    assert '["tuned", "B4+5 (Tuned)"]' in app_js
    assert "decks.html?commander=" in app_js
    assert "combos-template-slots" in app_js
    assert "Erfüllung unbekannt" in app_js
    assert "role_ranks" in tier_js
