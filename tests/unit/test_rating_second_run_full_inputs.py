"""Tests of the wave-2 input generator for the second rating run of H (Refs #1404).

Synthetic mini data for every rule (pool of 12 cards, wave 1 of 4, chunks of at most 3) plus one
reproduction check: regenerating the committed wave-2 inputs from the repository gives the same bytes.
"""

from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "analysis" / "rating_second_run_full_inputs.py"
COMMITTED = REPO / "data" / "research" / "chulane_rubric_v2_20261118" / "second_run_full_20261122"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rating_second_run_full_inputs", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["rating_second_run_full_inputs"] = module
    spec.loader.exec_module(module)
    return module


g = _load()


# --------------------------------------------------------------------------- pure helpers


def test_remaining_ids_is_the_pool_minus_wave1_and_checks_the_sizes() -> None:
    assert g.remaining_ids(["d", "a", "c", "b"], ["c"], 4) == ["a", "b", "d"]
    with pytest.raises(ValueError, match="expected 5"):
        g.remaining_ids(["a", "b", "c", "d"], ["a"], 5)
    with pytest.raises(ValueError, match="not in the pool"):
        g.remaining_ids(["a", "b"], ["z"], 2)


def test_top_set_takes_the_rank_share_and_draws_the_tie_group_with_the_seed() -> None:
    # 10 cards, 20 % -> 2; one card above the cut (90), cut value 50 shared by three cards
    h = {"a": 90, "b": 50, "c": 50, "d": 50, "e": 10, "f": 10, "g": 10, "h": 10, "i": 10, "j": 10}
    top = g.top_set(h, 20, random.Random(7))
    assert len(top) == 2 and "a" in top and len(top & {"b", "c", "d"}) == 1
    # same seed, same draw
    assert g.top_set(h, 20, random.Random(7)) == top


def test_wave2_stratum_puts_anchor_cards_first_then_lands_top_rest() -> None:
    assert g.wave2_stratum(True, True, True) == "anchor_land"
    assert g.wave2_stratum(True, False, True) == "anchor_spell"
    assert g.wave2_stratum(False, True, True) == "land"
    assert g.wave2_stratum(False, False, True) == "top20"
    assert g.wave2_stratum(False, False, False) == "rest"


def test_chunk_count_keeps_every_chunk_at_most_max_size() -> None:
    assert g.n_chunks_for(622, 100) == 7
    assert g.n_chunks_for(600, 100) == 6
    assert g.n_chunks_for(1, 100) == 1
    with pytest.raises(ValueError):
        g.n_chunks_for(0, 100)


def test_deal_balances_sizes_and_strata_and_is_deterministic() -> None:
    members = {
        "anchor_spell": [f"a{i}" for i in range(4)],
        "rest": [f"r{i:02d}" for i in range(17)],
    }
    order = ("anchor_spell", "rest")
    chunks = g.deal(members, order, 3, random.Random(1))
    sizes = sorted(len(c) for c in chunks)
    assert sizes == [7, 7, 7]  # 21 cards over 3 chunks
    anchors_per_chunk = sorted(sum(1 for _, s in c if s == "anchor_spell") for c in chunks)
    assert anchors_per_chunk == [1, 1, 2]
    all_ids = sorted(o for c in chunks for o, _ in c)
    assert all_ids == sorted(members["anchor_spell"] + members["rest"])
    assert g.deal(members, order, 3, random.Random(1)) == chunks
    with pytest.raises(ValueError, match="without a deal position"):
        g.deal({"other": ["x"]}, order, 2, random.Random(1))


def test_name_hits_match_whole_names_only() -> None:
    text = "This is optional. Opt is a card; so is Sol Ring, but not Sol Ringer."
    assert g.name_hits(["Opt", "Sol Ring", "Ponder"], text) == ["Opt", "Sol Ring"]
    assert g.name_hits(["Opt"], "optional only") == []
    assert g.name_hits(["Ring"], "Sol Ringer") == []


def test_leave_out_matches_any_listed_name() -> None:
    lo = g.LeaveOut(["A", "B"])
    assert lo == "A" and lo == "B" and lo != "C"  # anchor_block compares name == lo (reflected)
    assert bool(lo) and not bool(g.LeaveOut([]))


def test_removed_anchor_rows_counts_rows_per_criterion_over_both_tables() -> None:
    anchors = {
        "spell": {
            "H": [{"card": "A", "value": 50}, {"card": "B", "value": 40}],
            "E": [{"card": "A", "value": 60}],
        },
        "land": {"H": [{"card": "L", "value": 30}]},
    }
    assert g.removed_anchor_rows(anchors, {"A", "L"}) == {
        "E": 1,
        "F": 0,
        "T": 0,
        "R": 0,
        "K": 0,
        "D": 0,
        "H": 2,
    }


def test_retest_pick_draws_per_wave1_stratum_and_never_a_flagged_card() -> None:
    cards = [
        {"oracle_id": "f1", "stratum": "flagged"},
        {"oracle_id": "t1", "stratum": "top20"},
        {"oracle_id": "t2", "stratum": "top20"},
        {"oracle_id": "r1", "stratum": "rest"},
        {"oracle_id": "r2", "stratum": "rest_fill"},
        {"oracle_id": "l1", "stratum": "land"},
    ]
    picked = g.retest_pick(cards, (("top20", 1), ("rest", 2), ("land", 1)), random.Random(3))
    ids = {o for o, _ in picked}
    assert len(picked) == 4 and "f1" not in ids and {"r1", "r2", "l1"} <= ids
    with pytest.raises(ValueError, match="2 cards, 3 wanted"):
        g.retest_pick(cards, (("top20", 3),), random.Random(3))


def test_instructions_name_the_count_per_chunk_and_the_path() -> None:
    text = g.instructions("<RATER_DIR>/", {1: 89, 2: 88, 3: 50}, 3)
    assert "| 1 | 89 |\n| 2 | 88 |\n| 3 | 50 |" in text
    assert "`<RATER_DIR>/rr2_input_N.jsonl`" in text and "<RATER_DIR>//" not in text
    assert "Your number **N** (1 to 3)" in text
    assert "It must print `C True`" in text
    assert "rr_input" not in text.replace("rr2_input", "")
    with pytest.raises(ValueError):
        g.instructions("/x", {1: 5, 3: 5}, 3)


# --------------------------------------------------------------------------- synthetic end to end

FAKE_RENDER = """
class _BA:
    @staticmethod
    def anchor_block(anchors, leave_out=None, heading="Spells"):
        rows = [f"#### {heading}"]
        for crit, items in sorted(anchors.items()):
            for r in items:
                if leave_out and r["card"] == leave_out:
                    continue
                rows.append(f"| {crit} | {r['value']} | {r['card']} |")
        return "\\n".join(rows) + "\\n"


BA = _BA()


def system_prompt(guide, anchors, leave_out=None):
    return guide + BA.anchor_block(anchors["spell"], leave_out, "Spells") + BA.anchor_block(
        anchors["land"], leave_out, "Lands (judge a land as a land)"
    )


def card_block(f, pat):
    return f"CARD: {f['name']}\\noracle_id: {f['oracle_id']}\\nland: {f['is_land_front']}"
"""

# id, name, H, land; anchors: Anchor Land, Anchor Spell; flagged: Flag Card
CARDS = [
    ("c00", "Top Zero", 90, False),
    ("c01", "Top One", 80, False),
    ("c02", "Top Two", 70, False),
    ("c03", "Flag Card", 60, False),
    ("c04", "Rest Four", 40, False),
    ("c05", "Rest Five", 35, False),
    ("c06", "Rest Six", 30, False),
    ("c07", "Rest Seven", 10, False),
    ("c08", "Plain Land", 25, True),
    ("c09", "Other Land", 15, True),
    ("c10", "Anchor Land", 20, True),
    ("c11", "Anchor Spell", 50, False),
]
WAVE1 = [("c00", "top20"), ("c04", "rest"), ("c09", "land"), ("c03", "flagged")]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _fake_repo(root: Path, module: ModuleType) -> Path:
    rub = root / module.RUB
    (rub / "scripts").mkdir(parents=True)
    (rub / "scripts" / "render_prompt.py").write_text(FAKE_RENDER, encoding="utf-8")
    (rub / "scripts" / "build_anchors.py").write_text("# fake\n", encoding="utf-8")
    facts = [{"oracle_id": o, "name": n, "is_land_front": land} for o, n, _, land in CARDS]
    _write_jsonl(rub / "data" / "facts.jsonl", facts)
    _write_jsonl(rub / "data" / "patterns.jsonl", [])
    anchors = {
        "spell": {
            "H": [{"card": "Anchor Spell", "value": 50}, {"card": "Somewhere Else", "value": 30}]
        },
        "land": {"H": [{"card": "Anchor Land", "value": 20}]},
    }
    (rub / "anchors.json").write_text(json.dumps(anchors), encoding="utf-8")
    guide = "GUIDE TEXT\n"
    (rub / "GUIDE_v2.md").write_text(guide, encoding="utf-8")
    (rub / "output_schema.json").write_text("{}\n", encoding="utf-8")
    _write_jsonl(rub / "audit" / "audit_A_flagged.jsonl", [{"card": "Flag Card"}])
    _write_jsonl(
        root / module.PRIOR, [{"oracle_id": o, "scores": {"H": h}} for o, _, h, _ in CARDS]
    )
    w1 = root / module.WAVE1_DIR
    by_id = {f["oracle_id"]: f for f in facts}
    manifest = {
        "meta": {"pool": {"anchors_left_out_of_guide_tables": []}},
        "cards": [{"oracle_id": o, "stratum": s} for o, s in WAVE1],
    }
    w1.mkdir(parents=True)
    (w1 / "rr_sample_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    blocks = [
        {"seq": i + 1, "oracle_id": o, "card": by_id[o]["name"],
         "card_block": f"CARD: {by_id[o]['name']}\noracle_id: {o}\nland: {by_id[o]['is_land_front']}"}
        for i, (o, _) in enumerate(WAVE1)
    ]  # fmt: skip
    _write_jsonl(w1 / "rr_input_1.jsonl", blocks[:2])
    _write_jsonl(w1 / "rr_input_2.jsonl", blocks[2:3])
    _write_jsonl(w1 / "rr_input_3.jsonl", blocks[3:])
    rendered = guide + "#### Spells\n| H | 50 | Anchor Spell |\n| H | 30 | Somewhere Else |\n"
    rendered += "#### Lands (judge a land as a land)\n| H | 20 | Anchor Land |\n"
    (w1 / "rr_guide_v2_1_rendered.md").write_text(rendered, encoding="utf-8")
    return root


@pytest.fixture
def mini(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(g, "POOL_SIZE", 12)
    monkeypatch.setattr(g, "WAVE1_SIZE", 4)
    monkeypatch.setattr(g, "MAX_CHUNK", 3)
    monkeypatch.setattr(g, "RETEST_PLAN", (("top20", 1), ("rest", 1), ("land", 1)))
    return _fake_repo(tmp_path / "repo", g)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def test_build_covers_the_remaining_cards_once_in_small_chunks(mini: Path, tmp_path: Path) -> None:
    meta = g.build(mini, tmp_path / "an", tmp_path / "blind" / "rater", None)
    # 12 - 4 = 8 remaining cards -> ceil(8 / 3) = 3 chunks (3, 3, 2) + retest chunk 4 (3 cards)
    assert meta["n_pool_wave2"] == 8 and meta["chunks_pool"] == 3 and meta["retest_chunk"] == 4
    assert meta["composition_wave2"] == {
        "anchor_land": 1,
        "anchor_spell": 1,
        "land": 1,
        "rest": 3,
        "top20": 2,
    }
    assert [meta["per_chunk"][k]["n"] for k in ("1", "2", "3", "4")] == [3, 3, 2, 3]
    manifest = json.loads((tmp_path / "an" / "rr2_manifest.json").read_text(encoding="utf-8"))
    pool = [c["oracle_id"] for c in manifest["cards"] if c["role"] == "pool"]
    assert sorted(pool) == ["c01", "c02", "c05", "c06", "c07", "c08", "c10", "c11"]
    retest = sorted(c["oracle_id"] for c in manifest["cards"] if c["role"] == "retest")
    assert retest == ["c00", "c04", "c09"]  # one per wave-1 primary stratum, never the flagged c03
    rater = tmp_path / "blind" / "rater"
    rows = _read_jsonl(rater / "rr2_input_1.jsonl")
    assert len(rows) == 3 and set(rows[0]) == {"seq", "oracle_id", "card", "card_block"}
    assert [r["seq"] for r in rows] == [1, 2, 3]


def test_each_chunk_guide_leaves_out_only_its_own_anchor_cards(mini: Path, tmp_path: Path) -> None:
    meta = g.build(mini, tmp_path / "an", tmp_path / "blind" / "rater", None)
    rater = tmp_path / "blind" / "rater"
    seen = 0
    for k in ("1", "2", "3"):
        names = {r["card"] for r in _read_jsonl(rater / f"rr2_input_{k}.jsonl")}
        guide = (rater / f"rr2_guide_{k}.md").read_text(encoding="utf-8")
        for anchor in ("Anchor Spell", "Anchor Land"):
            assert (f"| {anchor} |" in guide) == (anchor not in names)
        seen += len(meta["per_chunk"][k]["anchors_left_out"])
        assert "Somewhere Else" in guide
    assert seen == 2
    # the retest guide is byte-identical with the wave-1 guide
    w1_guide = mini / g.WAVE1_DIR / "rr_guide_v2_1_rendered.md"
    assert (rater / "rr2_guide_4.md").read_bytes() == w1_guide.read_bytes()


def test_inputs_carry_no_prior_score_and_runs_are_byte_identical(
    mini: Path, tmp_path: Path
) -> None:
    g.build(mini, tmp_path / "a", tmp_path / "ra" / "rater", "<RATER_DIR>")
    g.build(mini, tmp_path / "b", tmp_path / "rb" / "rater", "<RATER_DIR>")
    names = sorted(p.name for p in (tmp_path / "ra" / "rater").iterdir())
    assert len(names) == 10  # 4 inputs, 4 guides, schema, instructions
    for name in names:
        assert (tmp_path / "ra" / "rater" / name).read_bytes() == (
            tmp_path / "rb" / "rater" / name
        ).read_bytes()
    assert (tmp_path / "a" / "rr2_manifest.json").read_bytes() == (
        tmp_path / "b" / "rr2_manifest.json"
    ).read_bytes()
    for k in (1, 2, 3, 4):
        text = (tmp_path / "ra" / "rater" / f"rr2_input_{k}.jsonl").read_text(encoding="utf-8")
        assert '"scores"' not in text and '"H"' not in text and "stratum" not in text
    instr = (tmp_path / "ra" / "rater" / "rr2_rater_instructions.md").read_text(encoding="utf-8")
    assert "`<RATER_DIR>/rr2_guide_N.md`" in instr and "| 4 | 3 |" in instr


def test_a_live_rater_folder_inside_the_analyst_folder_is_refused(
    mini: Path, tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match="must not be the analyst folder"):
        g.build(mini, tmp_path / "an", tmp_path / "an" / "rater", None)
    with pytest.raises(ValueError, match="must not be the analyst folder"):
        g.build(mini, tmp_path / "same", tmp_path / "same", None)


def test_a_changed_wave1_card_block_stops_the_build(mini: Path, tmp_path: Path) -> None:
    path = mini / g.WAVE1_DIR / "rr_input_2.jsonl"
    row = _read_jsonl(path)[0]
    row["card_block"] += "\nextra"
    _write_jsonl(path, [row])
    with pytest.raises(ValueError, match="1 wave-1 card blocks no longer render identically"):
        g.build(mini, tmp_path / "an", tmp_path / "blind" / "rater", None)


def test_a_changed_wave1_guide_stops_the_build(mini: Path, tmp_path: Path) -> None:
    (mini / g.WAVE1_DIR / "rr_guide_v2_1_rendered.md").write_text("other\n", encoding="utf-8")
    with pytest.raises(ValueError, match="retest guide differs"):
        g.build(mini, tmp_path / "an", tmp_path / "blind" / "rater", None)


# --------------------------------------------------------------------------- committed inputs


def test_the_committed_wave2_inputs_regenerate_byte_for_byte(tmp_path: Path) -> None:
    out = tmp_path / "rec"
    g.build(REPO, out, out / "rater", "<RATER_DIR>")
    committed = sorted(p.name for p in (COMMITTED / "rater").iterdir())
    assert len(committed) == 18  # 8 inputs, 8 guides, schema, instructions
    assert committed == sorted(p.name for p in (out / "rater").iterdir())
    for name in committed:
        assert (out / "rater" / name).read_bytes() == (COMMITTED / "rater" / name).read_bytes(), (
            name
        )
    new = json.loads((out / "rr2_manifest.json").read_text(encoding="utf-8"))
    old = json.loads((COMMITTED / "rr2_manifest.json").read_text(encoding="utf-8"))
    # the commit id depends on the clone depth; everything else must match
    new["meta"].pop("source_commit_last_touching_sources")
    old["meta"].pop("source_commit_last_touching_sources")
    assert new == old
    assert new["meta"]["n_pool_wave2"] == 622 and new["meta"]["chunks_pool"] == 7
    assert all(new["meta"]["per_chunk"][str(k)]["n"] <= 100 for k in range(1, 9))
