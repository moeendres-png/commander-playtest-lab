"""Tests of the card-block generator v2 for the rating v3 of H (plan Bewertung v3, I1; Refs #1404).

One test (or more) per correction G1-G12 on the cards the plan names, plus: the committed outputs
reproduce byte for byte (two builds give the same bytes), every SHA-256 of the manifest holds,
the card order and oracle ids are unchanged, all corrections off render the committed v2 blocks,
and the unchanged A2 script recounts the defects of the G table on facts_v2. Only repository data
is read; no rating is read or produced.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
V2 = REPO / "data" / "research" / "chulane_rubric_v2_20261118"
V3 = REPO / "data" / "research" / "chulane_rubric_v3_20261123"
A2_REPORT = REPO / "docs" / "analysis-reports" / "rating_v3_phaseA2_kartenblock_defekte_20261123.md"
COMMANDER_PREFIX = "Commander (the deck's commander, for rule checks): "


def _load(name: str) -> ModuleType:
    if str(V3) not in sys.path:
        sys.path.insert(0, str(V3))
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, V3 / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


rp = _load("render_prompt_v2")
ef = _load("extract_facts_v2")
rc = _load("a2_recount_v2")


def _jl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


@pytest.fixture(scope="module")
def full() -> Any:
    return rp.build(REPO)


@pytest.fixture(scope="module")
def by_name(full: Any) -> dict[str, tuple[dict[str, Any], dict[str, Any] | None, str]]:
    pats = {p["oracle_id"]: p for p in full.patterns}
    return {
        f["name"]: (f, pats.get(f["oracle_id"]), full.blocks[f["oracle_id"]]) for f in full.facts
    }


@pytest.fixture(scope="module")
def v2_facts() -> dict[str, dict[str, Any]]:
    return {f["name"]: f for f in _jl(V2 / "data" / "facts.jsonl")}


@pytest.fixture(scope="module")
def manifest() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((V3 / "facts_v2_manifest.json").read_text("utf-8"))
    return data


def _block(by_name: dict[str, Any], name: str) -> str:
    block: str = by_name[name][2]
    return block


# --------------------------------------------------------------------------- reproduction


def test_two_builds_give_the_same_bytes_and_match_the_committed_outputs(
    full: Any, tmp_path: Path
) -> None:
    files = rp.write_all(REPO, tmp_path)
    again = rp.build(REPO)
    assert ef.dumps_jsonl(again.facts).encode("utf-8") == files["facts_v2.jsonl"]
    assert ef.dumps_jsonl(full.facts).encode("utf-8") == files["facts_v2.jsonl"]
    for name in ("facts_v2.jsonl", "patterns_v2.jsonl", "facts_v2_manifest.json"):
        assert (V3 / name).read_bytes() == files[name], f"{name} is not the generator output"


def test_every_sha256_of_the_manifest_holds(manifest: dict[str, Any]) -> None:
    assert len(manifest["inputs_sha256"]) == len(rp.INPUTS) == 16
    for rel, digest in manifest["inputs_sha256"].items():
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == digest, rel
    assert set(manifest["outputs_sha256"]) == {"facts_v2.jsonl", "patterns_v2.jsonl"}
    for name, digest in manifest["outputs_sha256"].items():
        assert hashlib.sha256((V3 / name).read_bytes()).hexdigest() == digest, name


def test_v2_files_stay_unchanged() -> None:
    v2_manifest = json.loads((V2 / "data" / "facts_manifest.json").read_text("utf-8"))
    for name in ("facts.jsonl", "pool_benchmarks.json"):
        digest = hashlib.sha256((V2 / "data" / name).read_bytes()).hexdigest()
        assert digest == v2_manifest["outputs_sha256"][name], name


def test_card_order_oracle_ids_and_block_heads_are_unchanged(full: Any) -> None:
    v2 = _jl(V2 / "data" / "facts.jsonl")
    assert [f["oracle_id"] for f in full.facts] == [f["oracle_id"] for f in v2]
    assert [p["oracle_id"] for p in full.patterns] == [f["oracle_id"] for f in v2]
    assert len(full.blocks) == 922
    for f in full.facts:
        head = full.blocks[f["oracle_id"]].split("\n")[:2]
        assert head == [f"CARD: {f['name']}", f"oracle_id: {f['oracle_id']}"]


def test_all_corrections_off_render_the_committed_v2_blocks(manifest: dict[str, Any]) -> None:
    off = rp.build(REPO, ef.CORRECTIONS)
    committed = rp.committed_v2_blocks(REPO)
    assert len(committed) == 922
    assert [o for o in committed if off.blocks[o] != committed[o]] == []
    assert manifest["drift_check_all_corrections_off"]["cards_equal"] == 922


def test_manifest_lists_the_corrections_that_changed_each_card(
    manifest: dict[str, Any], full: Any
) -> None:
    rows = manifest["changed_by_card"]
    assert [r["oracle_id"] for r in rows] == [f["oracle_id"] for f in full.facts]
    assert all("G12" in r["changed_by"] for r in rows)
    by = {r["name"]: set(r["changed_by"]) for r in rows}
    assert {"G1"} <= by["Krosan Verge"] and {"G2", "G3"} - by["Wilt-Leaf Liege"] == {"G3"}
    assert {"G7", "G4"} <= by["Grizzled Outcasts // Krallenhorde Wantons"]
    counts = manifest["counts"]["cards_changed_per_correction"]
    assert counts["G2"] == 17 and counts["G8"] == 4 and counts["G12"] == 922
    assert manifest["counts"]["cards_changed_without_single_attribution"] == 0


def test_rater_visible_records_carry_no_usage_or_rating_key(full: Any) -> None:
    def keys(obj: Any) -> set[str]:
        if isinstance(obj, dict):
            return set(obj) | {k for v in obj.values() for k in keys(v)}
        if isinstance(obj, list):
            return {k for v in obj for k in keys(v)}
        return set()

    found = keys(full.facts) | keys(full.patterns)
    assert "oracle_id" in found
    assert {k for k in found if ef.LEAK_KEYS.search(k)} == set()


# --------------------------------------------------------------------------- G1 fetch lands

G1_LANDS = {
    "Escape Tunnel": ["G", "U", "W"],
    "Mountain Valley": ["G"],
    "Fabled Passage": ["G", "U", "W"],
    "Terramorphic Expanse": ["G", "U", "W"],
    "Myriad Landscape": ["G", "U", "W"],
    "Riveteers Overlook": ["G"],
    "Cabaretti Courtyard": ["G", "W"],
    "Vibrant Cityscape": ["G", "U", "W"],
    "Grixis Panorama": ["U"],
    "Rocky Tar Pit": [],
    "Demolition Field": ["G", "U", "W"],
    "Maestros Theater": ["U"],
    "Evolving Wilds": ["G", "U", "W"],
    "Krosan Verge": ["G", "W"],
    "Jund Panorama": ["G"],
}


def test_g1_the_15_fetch_lands_fetch_with_their_colours(by_name: dict[str, Any]) -> None:
    assert len(G1_LANDS) == 15
    for name, colours in G1_LANDS.items():
        f, _, block = by_name[name]
        assert f["land"]["fetches_land"] is True, name
        assert f["land"]["fetchable_wug_colours"] == colours, name
        assert "fetches a land: yes" in block and "(fetchable: " in block, name
    assert by_name["Evolving Wilds"][0]["land"]["fetched_land_enters"] == "tapped"
    assert by_name["Mountain Valley"][0]["land"]["fetched_land_enters"] == "untapped"
    assert "makes G/W of the deck's colours (fetchable: G/W)" in _block(by_name, "Krosan Verge")


def test_g1_non_fetch_lands_keep_their_land_facts(
    by_name: dict[str, Any], v2_facts: dict[str, Any]
) -> None:
    others = [
        n
        for n, (f, _, _) in by_name.items()
        if f["is_land_front"] and f.get("land") and n not in G1_LANDS
    ]
    assert len(others) == 50
    for n in others:
        new, old = by_name[n][0]["land"], v2_facts[n]["land"]
        for key in ("enters_tapped", "wug_colours_produced", "produces_any_colour", "fetches_land"):
            assert new[key] == old[key], (n, key)
        assert new["fetchable_wug_colours"] == []


# --------------------------------------------------------------------------- G2 hybrid


def test_g2_hybrid_symbols_are_counted_apart_without_contradiction(
    by_name: dict[str, Any],
) -> None:
    hybrid = [n for n, (f, _, _) in by_name.items() if f["pips_front"]["hybrid_symbols"]]
    assert len(hybrid) == 17
    for n in hybrid:
        f, _, block = by_name[n]
        assert "(cost has no coloured symbol)" not in block, n
        assert "hybrid symbols counted as their better option" in block, n
        assert len(f["castability"]["hybrid_counted_as"]) == f["pips_front"]["hybrid_symbols"]
        assert f["castability"]["hybrid_or_phyrexian_left_out"] is False
        assert f["castability"]["p_colours_given_lands"] < 1.0, n
    cost = _block(by_name, "Wilt-Leaf Liege").split("\n")[2]
    assert cost.endswith(
        "Cost symbols (front face): G/W x3 (hybrid: each pays with either part), generic 1"
    )


def test_g2_castability_of_every_other_spell_is_carried_from_v2(
    by_name: dict[str, Any], v2_facts: dict[str, Any], manifest: dict[str, Any]
) -> None:
    from commander_lab.studio import castability

    src = ef.load_sources(REPO)
    spells = [
        n for n, (f, _, _) in by_name.items() if f.get("castability") and not f["hybrid_pips_front"]
    ]
    assert len(spells) == 840  # 857 spells with castability minus 17 hybrid
    differ = []
    for n in spells:
        old = v2_facts[n]["castability"]
        new = by_name[n][0]["castability"]
        assert new["values_from"] == ef.CARRIED
        extra = ("cost_reduction_in_text", "values_from")
        assert {k: v for k, v in new.items() if k not in extra} == old, n
        need, _ = castability.requirement(by_name[n][0]["mana_cost"] or "")
        res = castability.colour_probability(src.land_groups, src.nonland + 1, need, old["turn"])
        got = (res["p_on_curve"], res["p_colours_given_lands"])
        want = (old["p_on_curve"], old["p_colours_given_lands"])
        if len(need) <= 1:
            assert got == want, n
        elif got != want:
            assert got[0] <= want[0] and got[1] < want[1], n  # #1751: no longer overstated
            differ.append(n)
    note = manifest["castability_method"]
    assert len(differ) == note["carried_values_today_module_differs"] == 41
    assert note["carried_values_differ_cards"] == sorted(differ)


# --------------------------------------------------------------------------- G3 castability notes


def test_g3_x_and_cost_reduction_notes(by_name: dict[str, Any]) -> None:
    x_cards = [n for n, (f, _, _) in by_name.items() if (f.get("castability") or {}).get("x_cost")]
    assert len(x_cards) == 14
    for n in x_cards:
        assert "(X counted as 0)" in _block(by_name, n), n
    reduced = [
        n
        for n, (f, _, _) in by_name.items()
        if (f.get("castability") or {}).get("cost_reduction_in_text")
    ]
    assert len(reduced) == 23
    for n in ("Treasure Cruise", "Dig Through Time", "Gate Colossus", "Merrow Skyswimmer"):
        assert n in reduced
        assert "cost reduction or alternative cost in the text not modelled" in _block(by_name, n)
    assert "not modelled" not in _block(by_name, "Wilt-Leaf Liege")
    assert "(X counted as 0)" not in _block(by_name, "Wilt-Leaf Liege")


# --------------------------------------------------------------------------- G4 rulings


def test_g4_every_ruling_in_full_sorted_and_article_pointers_left_out(
    by_name: dict[str, Any], v2_facts: dict[str, Any], manifest: dict[str, Any]
) -> None:
    with_rulings = [n for n, f in v2_facts.items() if f["rulings"]]
    assert len(with_rulings) == 518
    for n in with_rulings:
        f, _, block = by_name[n]
        kept = [r for r in v2_facts[n]["rulings"] if not ef.ARTICLE_POINTER.match(r["comment"])]
        assert len(f["rulings"]) == len(kept), n
        keys = [(r["published_at"], r["comment"]) for r in f["rulings"]]
        assert keys == sorted(keys), n
        for r in kept:
            assert f"  - {r['published_at']}: " + r["comment"].replace("\n", " ") in block, n
        assert not any(ln.startswith("  - 2") and ln.endswith("…") for ln in block.splitlines()), n
    assert "For more information" not in _block(
        by_name, "Grizzled Outcasts // Krallenhorde Wantons"
    )
    stats = manifest["prompt_token_stats"]
    assert stats["v2prime_blocks"]["sum"] > stats["v2_blocks"]["sum"]
    assert stats["v2_blocks"]["median"] == 426.5  # the v2 estimate (prompt_token_stats.json)


# --------------------------------------------------------------------------- G5 pattern hits


def test_g5_no_role_label_evidence_and_no_etb_own_on_noncreatures(
    full: Any, by_name: dict[str, Any]
) -> None:
    facts = {f["oracle_id"]: f for f in full.facts}
    assert len(full.patterns) == 922
    for p in full.patterns:
        assert not any(str(h[0]["line"]).startswith("roles by text") for h in p["hits"].values())
        if "etb_own" in p["hits"]:
            assert facts[p["oracle_id"]]["is_creature_front"], p["name"]
    _, sanctuary, block = by_name["Selesnya Sanctuary"]
    assert "etb_own_noncreature" in sanctuary["hidden_hits"] and "etb_own" not in block
    _, veil, block = by_name["Veil of Summer"]
    assert "noncreature_draw_or_ramp" in veil["hidden_hits"]
    assert "noncreature_draw_or_ramp" not in block


# --------------------------------------------------------------------------- G6 / G10 glossary

PREPARE = [
    "Biblioplex Tomekeeper",
    "Skycoach Waypoint",
    "Studious First-Year // Rampant Growth",
    "Prudent Fateseer // Peer Review",
    "Dirgur Focusmage // Braingeyser",
    "Infinite Coursework",
    "Tam, Observant Sequencer // Deep Sight",
    "Emergency Phytomedic // Seed Suture",
    "Spellbook Seeker // Careful Study",
]
PLANESWALKERS = {
    "Tezzeret, Betrayer of Flesh": "4",
    "Gideon Jura": "6",
    "Narset, Parter of Veils": "5",
    "Elspeth, Knight-Errant": "4",
}


def test_g6_mechanics_glossary_lines_on_the_a2_cards(by_name: dict[str, Any]) -> None:
    gl = {e["id"]: e for e in ef.load_sources(REPO).glossary}
    expected = {n: ["prepare"] for n in PREPARE}
    expected["Ransom Note"] = ["goad", "cloak"]
    expected["Brazen Borrower // Petty Theft"] = ["adventure"]
    expected["Exploration Broodship"] = ["station"]
    for n in PLANESWALKERS:
        expected[n] = ["loyalty_abilities"]
    assert len(expected) == 9 + 1 + 1 + 1 + 4
    for n, terms in expected.items():
        block = _block(by_name, n)
        assert "Mechanics (rules summary, quoted from public card data):" in block, n
        for t in terms:
            assert t in by_name[n][0]["glossary_terms"], (n, t)
            assert gl[t]["text"] in block, (n, t)
    for n in ("Hexhaven Battalion", "Campus Crier"):
        assert gl["empower"]["text"] in _block(by_name, n)


def test_g6_flip_and_g10_copy_rule_have_no_repository_source_and_are_omitted(
    by_name: dict[str, Any],
) -> None:
    data = json.loads((V3 / "mechanics_glossary.json").read_text("utf-8"))
    omitted = " ".join(e["term"] for e in data["ohne_beleg_weggelassen"])
    assert "Flip" in omitted and "Kopie" in omitted
    assert "Mechanics (rules summary" not in _block(
        by_name, "Faithful Squire // Kaiso, Memory of Loyalty"
    )


def test_glossary_texts_are_verbatim_quotes_of_their_cited_source() -> None:
    data = json.loads((V3 / "mechanics_glossary.json").read_text("utf-8"))
    pck = json.loads((REPO / "data/cards/pilot_card_knowledge.json").read_text("utf-8"))["cards"]
    rulings = [
        (f["name"], r["published_at"], r["comment"])
        for f in _jl(V2 / "data" / "facts.jsonl")
        for r in f["rulings"]
    ]
    names = {}
    for i in (1, 2, 3):
        for row in _jl(REPO / f"data/research/deckbuilder_1655/mtgjson_printings_1655_{i}.jsonl"):
            names.setdefault(row["oracle_id"], row["name"])
    r1655 = [
        (names.get(r["oracle_id"]), r["published_at"], r["comment"])
        for r in _jl(REPO / "data/research/deckbuilder_1655/card_rulings_1655.jsonl")
    ]
    entries = data["entries"]
    assert len(entries) == 16
    for e in entries:
        s = e["source"]
        if s["file"] == "pck":
            source = pck[s["card"]]["oracle_text"]
        elif s["file"] == "facts_v2":
            source = " ".join(c for n, d, c in rulings if n == s["card"] and d == s["date"])
        else:
            source = " ".join(c for n, d, c in r1655 if n == s["card"] and d == s["date"])
        parts = e["text"].split(" [...] ") if e["excerpt"] else [e["text"]]
        for part in parts:
            assert part in source, e["id"]


def test_g10_token_entries_on_the_five_a2_cards(by_name: dict[str, Any]) -> None:
    gl = {e["id"]: e["text"] for e in ef.load_sources(REPO).glossary}
    expected = {
        "Killer Service": ["token_food"],
        "An Offer You Can't Refuse": ["token_treasure"],
        "Graf Mole": ["token_clue"],
        "Sophia, Dogged Detective": ["token_food"],
        "Academy Manufactor": ["token_clue", "token_food", "token_treasure"],
    }
    for n, terms in expected.items():
        for t in terms:
            assert t in by_name[n][0]["glossary_terms"], (n, t)
            assert gl[t] in _block(by_name, n), (n, t)
    assert gl["token_treasure"] not in _block(by_name, "Wilt-Leaf Liege")


# --------------------------------------------------------------------------- G7 / G8 faces


def test_g7_back_face_power_toughness_keywords_and_mana_per_face(
    by_name: dict[str, Any],
) -> None:
    backs = {
        "Faithful Squire // Kaiso, Memory of Loyalty": "3/4",
        "Brigid, Clachan's Heart // Brigid, Doun's Mind": "3/2",
        "Thraben Sentry // Thraben Militia": "5/4",
        "Grizzled Outcasts // Krallenhorde Wantons": "7/7",
    }
    report = A2_REPORT.read_text(encoding="utf-8")
    for n, pt in backs.items():
        assert by_name[n][0]["faces"][1]["power_toughness"] == pt, n
        assert re.search(rf"^Face 2: .*\| Power/toughness: {pt}:$", _block(by_name, n), re.M), n
        assert f"({pt})" in report, n
    assert "Keywords: Flying (face 2)" in _block(
        by_name, "Faithful Squire // Kaiso, Memory of Loyalty"
    )
    assert "Transform, Trample (face 2)" in _block(by_name, "Thraben Sentry // Thraben Militia")
    assert "Enchant (face 2)" in _block(by_name, "Soul Seizer // Ghastly Haunting")
    assert "Produces mana: G (face 2)" in _block(
        by_name, "Brigid, Clachan's Heart // Brigid, Doun's Mind"
    )
    assert "UNBEKANNT" not in "".join(b for _, _, b in by_name.values())


def test_g8_loyalty_of_the_four_planeswalkers(by_name: dict[str, Any]) -> None:
    xmage = json.loads((REPO / "data/cards/xmage_card_facts.json").read_text("utf-8"))["cards"]
    for n, loyalty in PLANESWALKERS.items():
        assert by_name[n][0]["loyalty"] == loyalty == str(int(xmage[n]["loyalty"]))
        assert f"\nLoyalty: {loyalty} (starting loyalty)\n" in _block(by_name, n)
    pws = [n for n, (f, _, _) in by_name.items() if "Planeswalker" in f["type_line"]]
    assert sorted(pws) == sorted(PLANESWALKERS)


# --------------------------------------------------------------------------- G9 references


def test_g9_referenced_cards_carry_their_oracle_text(by_name: dict[str, Any]) -> None:
    pck = json.loads((REPO / "data/cards/pilot_card_knowledge.json").read_text("utf-8"))["cards"]
    expected = {
        "Angel's Herald": ["Empyrial Archangel"],
        "Arachnus Spinner": ["Arachnus Web"],
        "Scepter of Empires": ["Crown of Empires", "Throne of Empires"],
    }
    for n, refs in expected.items():
        f, _, block = by_name[n]
        assert [r["name"] for r in f["referenced_cards"]] == refs, n
        for r in refs:
            assert f"Referenced card: {r} — " in block
            text = pck[r]["oracle_text"].replace("\n", "\n  ")
            assert text in block, (n, r)
    with_refs = [n for n, (f, _, _) in by_name.items() if f.get("referenced_cards")]
    assert sorted(with_refs) == sorted(expected)
    assert "Referenced card: none fixed" in _block(by_name, "Sorcerous Spyglass")
    assert "Referenced card" not in _block(by_name, "Hexhaven Battalion")  # token named Cadet


# --------------------------------------------------------------------------- G11 / G12


def test_g11_body_benchmark_note_on_the_17_a2_cards(by_name: dict[str, Any]) -> None:
    noted = [n for n, (_, _, b) in by_name.items() if "[printed P/T; this card enters with" in b]
    assert len(noted) == 17
    for n in ("Primordial Hydra", "Hydroid Krasis", "Enclave Elite", "Burdened Stoneback"):
        assert n in noted
    assert "[printed P/T" not in _block(by_name, "Wilt-Leaf Liege")


def test_g12_commander_line_in_every_block_quotes_the_guide(full: Any) -> None:
    guide = (V2 / "GUIDE_v2.md").read_text(encoding="utf-8")
    line = rp.commander_line(guide)
    assert line.startswith("Chulane, Teller of Tales {2}{G}{W}{U}, Legendary Creature")
    pck = json.loads((REPO / "data/cards/pilot_card_knowledge.json").read_text("utf-8"))["cards"]
    oracle = pck["Chulane, Teller of Tales"]["oracle_text"].replace("Vigilance\n", "Vigilance. ")
    assert line.endswith(oracle.replace("\n", " "))
    blocks = list(full.blocks.values())
    assert len(blocks) == 922
    assert all(b.split("\n")[-1] == f"{COMMANDER_PREFIX}{line}" for b in blocks)


# --------------------------------------------------------------------------- A2 recount


def test_a2_recount_on_facts_v2_leaves_nothing_open_in_the_target_classes(
    full: Any, manifest: dict[str, Any]
) -> None:
    result = rc.recount(REPO, full.facts, full.patterns, full.blocks)
    assert result == manifest["a2_recount"]
    keys = result["keys"]
    before = {
        "f_land_colours_none_but_fetches": 15,
        "f_land_fetch_flag_wrong": 6,
        "f_land_untapped_but_fetched_land_tapped": 10,
        "f_hybrid_pips_double_counted": 17,
        "f_castability_x_at_zero_not_said": 14,
        "f_castability_ignores_alt_cost_or_self_reduction": 23,
        "g_ruling_text_truncated_240": 239,
        "g_rulings_cut_more_than_4": 118,
        "f_pattern_etb_own_on_noncreature": 40,
        "f_pattern_evidence_is_role_label_not_text": 104,
        "a_back_face_pt_missing": 4,
        "d_planeswalker_loyalty_missing": 4,
        "c_named_reference_undefined": 4,
        "f_body_benchmark_ignores_etb_counters": 17,
    }
    for key, n in before.items():
        assert keys[key]["detector_before"] == n, key
    target = [k for k, v in keys.items() if v["correction"] in result["target_classes"]]
    assert len(target) == 19
    assert {k: keys[k]["unresolved_cards"] for k in target if keys[k]["unresolved_after"]} == {}
    assert result["unresolved_in_target_classes"] == 0
    for key in ("f_land_fetch_flag_wrong", "f_pattern_etb_own_on_noncreature",
                "f_pattern_evidence_is_role_label_not_text", "g_ruling_empty_article_pointer",
                "f_castability_hybrid_phyrexian_left_out_not_said"):  # fmt: skip
        assert keys[key]["detector_after"] == 0, key
    assert result["rerender_diff_after"] == 0
    assert result["chulane_text_in_blocks"] == {"before": 0, "after": 922}
    assert keys["c_copy_effect"]["unresolved_after"] == 9  # no source in the repository
