"""Pilot audit sampling, blinding and scoring (#1524); synthetic fixtures only."""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path

import pytest

from commander_lab.studio import pilot_audit_sample as pas

KINDS = ("priority", "target", "declare_attacker")
PLAN_QUOTAS = {"priority": 60, "target": 40, "declare_attacker": 20}
RECORDED = "2999-01-01T00:00:00Z"


def _decision(seq: int, seat: int, kind: str) -> dict[str, object]:
    return {
        "kind": "decision",
        "seq": seq,
        "decision_class": kind,
        "seat": seat,
        "prompt": f"Full Game Seat {seat + 1}: choose ({kind}); Full Game Seat {2 - seat} waits",
        "minimum_selections": 1,
        "legal_options": [
            {"option_id": "o1", "label": "Pass", "option_type": "pass", "xmage_key": "KEY-ONE"},
            {"option_id": "o2", "label": f"Cast Spell {seq}", "option_type": "spell"},
        ],
        "pilot_state": {
            "turn_number": 1 + seq % 7,
            "actor_id": f"p{seat}",
            "active_player_id": "opp-token",
            "priority_player_id": f"p{seat}",
            "phase": "combat",
            "step": "declare_attackers",
            "players": [
                {
                    "player_id": f"p{seat}",
                    "is_actor": True,
                    "life": 40,
                    "poison_counters": 2,
                    "hand_count": 1,
                    "library_count": 80,
                    "graveyard_count": 0,
                    "exile_count": 0,
                    "private_state_visible": True,
                    "hand": [{"object_id": "h1", "name": "Island", "xmage_key": "KEY-TWO"}],
                    "mana_pool": {"white": 0, "blue": 2, "black": 0},
                    "battlefield": [
                        {
                            "name": "Bear",
                            "tapped": True,
                            "face_down": False,
                            "power": 2,
                            "toughness": 2,
                            "damage": 1,
                            "counters": [{"type": "+1/+1", "count": 2}],
                        },
                        {"name": "SECRET-MORPH-NAME", "face_down": True, "tapped": False},
                    ],
                    "granted_library": [{"name": "HIDDEN-LIB"}],
                    "deck_name": "SECRET-DECK-NAME",
                },
                {
                    "player_id": "opp-token",
                    "is_actor": False,
                    "life": 38,
                    "hand_count": 6,
                    "library_count": 70,
                    "graveyard_count": 1,
                    "private_state_visible": False,
                    "graveyard": [{"name": "Shock"}],
                    "battlefield": [],
                },
            ],
            "stack": [
                {"name": "Lightning Bolt", "controller_id": "opp-token"},
                {"face_down": True, "name": None, "controller_id": "opp-token"},
            ],
        },
        "response": {"selected_option_ids": ["o2" if seq % 3 else "o1"]},
    }


def _write_game(
    folder: Path,
    idx: int,
    *,
    fingerprint: str = "fp-1",
    data_class: str = "SIMULATED_RESULT",
    per_seat: int = 8,
    rotate: bool = True,
    recorded_at: str = RECORDED,
) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    gid = f"game-{idx:03d}"
    tested = idx % 2 if rotate else 0
    lines: list[dict[str, object]] = [
        {
            "kind": "header",
            "schema": "studio-pilot-audit-1",
            "game_id": gid,
            "recorded_at": recorded_at,
            "header": {
                "data_class": data_class,
                "pilot_fingerprint": fingerprint,
                "seats": [
                    {"seat": tested, "deck_id": "chulane"},
                    {"seat": 1 - tested, "deck_id": "other"},
                ],
            },
        }
    ]
    seq = 0
    for seat in (0, 1):
        for n in range(per_seat):
            seq += 1
            lines.append(_decision(seq, seat, KINDS[n % 3]))
    lines.append(
        {
            "kind": "decision",
            "seq": 999,
            "decision_class": "priority",
            "seat": 0,
            "minimum_selections": 1,
            "legal_options": [{"option_id": "x", "label": "Pass", "option_type": "pass"}],
            "response": {"selected_option_ids": ["x"]},
        }
    )
    path = folder / f"{gid}.audit.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for line in lines:
            handle.write(json.dumps(line) + "\n")
    return path


def _make_pool(folder: Path, games: int = 26, **kwargs: object) -> None:
    for i in range(games):
        _write_game(folder, i, **kwargs)  # type: ignore[arg-type]


def _plan(seed: int = 7, **kwargs: object) -> dict[str, object]:
    return pas.make_plan(
        seed=seed,
        tested_deck_id="chulane",
        strata=PLAN_QUOTAS,
        created_at="2026-12-01T00:00:00Z",
        **kwargs,  # type: ignore[arg-type]
    )


def _pool(tmp_path: Path) -> Path:
    audit = tmp_path / "audit"
    if not audit.exists():
        _make_pool(audit)
    return audit


def _sample(tmp_path: Path, name: str = "out", seed: int = 7) -> Path:
    audit = _pool(tmp_path)
    plan_path = tmp_path / f"plan_{seed}.json"
    plan_path.write_text(json.dumps(_plan(seed)), encoding="utf-8")
    out = tmp_path / name
    argv = ["sample", "--audit-dir", str(audit), "--out-dir", str(out), "--plan", str(plan_path)]
    assert pas.main(argv) == 0
    return out


def _key(tmp_path: Path) -> dict[str, object]:
    return json.loads((_sample(tmp_path) / "sample_key.json").read_text(encoding="utf-8"))


def test_deterministic(tmp_path: Path) -> None:
    a = _sample(tmp_path, "o1")
    b = _sample(tmp_path, "o2")
    for name in pas_files():
        assert (a / name).read_bytes() == (b / name).read_bytes()
    c = _sample(tmp_path, "o3", seed=8)
    assert (a / "annotation_sheet_A.csv").read_bytes() != (
        c / "annotation_sheet_A.csv"
    ).read_bytes()


def pas_files() -> tuple[str, ...]:
    return (
        "annotation_sheet_A.csv",
        "annotation_sheet_B.csv",
        "owner_calibration_sheet.csv",
        "sample_key.json",
    )


def test_plan_floors_cannot_be_lowered() -> None:
    for kwargs in ({"min_games": 1}, {"calibration": 0}, {"size": 100}, {"size": 241}):
        with pytest.raises(pas.AuditSampleError):
            _plan(**kwargs)
    with pytest.raises(pas.AuditSampleError, match="sum"):
        pas.make_plan(seed=1, tested_deck_id="chulane", strata={"priority": 5})
    # the CLI has no way to override the floors on `sample`
    with pytest.raises(SystemExit):
        pas.main(
            ["sample", "--audit-dir", "x", "--out-dir", "y", "--plan", "z", "--min-games", "1"]
        )


def test_plan_cli_written_once(tmp_path: Path) -> None:
    out = tmp_path / "plan.json"
    argv = ["plan", "--out", str(out), "--seed", "3", "--tested-deck-id", "chulane"]
    assert pas.main(argv) == 0
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert plan["strata_per_half"] and plan["created_at"] and plan["seed"] == 3
    assert pas.main(argv) == 3


def test_refusals(tmp_path: Path) -> None:
    plan = _plan()
    few = tmp_path / "few"
    _make_pool(few, 10)
    cand, _ = pas.load_candidates(few, plan)
    with pytest.raises(pas.AuditSampleError, match="games"):
        pas.build_sample(cand, plan)

    mixed = tmp_path / "mixed"
    _make_pool(mixed, 25)
    _write_game(mixed, 99, fingerprint="fp-2")
    with pytest.raises(pas.AuditSampleError, match="fingerprint"):
        pas.load_candidates(mixed, plan)

    played = tmp_path / "played"
    _write_game(played, 0, data_class="PLAYED")
    with pytest.raises(pas.AuditSampleError, match="data_class"):
        pas.load_candidates(played, plan)

    norot = tmp_path / "norot"
    _make_pool(norot, 24, rotate=False)
    with pytest.raises(pas.AuditSampleError, match="rotation"):
        pas.load_candidates(norot, plan)

    early = tmp_path / "early"
    _make_pool(early, 24, recorded_at="2020-01-01T00:00:00Z")
    with pytest.raises(pas.AuditSampleError, match="before the plan"):
        pas.load_candidates(early, plan)

    thin = tmp_path / "thin"
    _make_pool(thin, 24, per_seat=2)
    cand, _ = pas.load_candidates(thin, plan)
    with pytest.raises(pas.AuditSampleError, match="rateable"):
        pas.build_sample(cand, plan)


def test_probe_four_games_cannot_pass(tmp_path: Path) -> None:
    small = tmp_path / "small"
    _make_pool(small, 4, per_seat=40)
    cand, meta = pas.load_candidates(small, _plan())
    with pytest.raises(pas.AuditSampleError, match="games"):
        pas.write_sample(cand, meta, tmp_path / "o", _plan())
    # A forged key (floors lowered) can never PASS.
    key = _key(tmp_path)
    ok = {i["item_id"]: pas.Annotation("ok", "none") for i in key["items"]}  # type: ignore[attr-defined]
    cal = {i["item_id"]: ok[i["item_id"]] for i in key["items"] if i["calibration"]}  # type: ignore[attr-defined]
    assert pas.score(key, ok, ok, cal)["result"] == "PASS"
    forged = json.loads(json.dumps(key))
    forged["plan"]["min_games"] = 1
    assert pas.score(forged, ok, ok, cal)["result"] == "UNKNOWN"
    forged = json.loads(json.dumps(key))
    for item in forged["items"]:
        item["calibration"] = False
    assert pas.score(forged, ok, ok, {})["result"] == "UNKNOWN"
    forged = json.loads(json.dumps(key))
    forged["items"] = [i for i in forged["items"] if i["game_id"] in {"game-000", "game-001"}]
    assert pas.score(forged, ok, ok, cal)["result"] == "UNKNOWN"
    for field, value in (("label", "OTHER"), ("tier_list", True), ("seed", None)):
        forged = json.loads(json.dumps(key))
        forged[field] = value
        assert pas.score(forged, ok, ok, cal)["result"] == "UNKNOWN"


def test_rateable_rule() -> None:
    forced = _decision(1, 0, "priority")
    forced["legal_options"] = [{"option_id": "x", "label": "Pass", "option_type": "pass"}]
    assert not pas.is_rateable(forced)
    dup = _decision(1, 0, "priority")
    dup["legal_options"] = [
        {"option_id": "a", "label": "Pass", "option_type": "pass"},
        {"option_id": "b", "label": "pass", "option_type": "pass"},
    ]
    dup["response"] = {"selected_option_ids": ["a"]}
    assert not pas.is_rateable(dup)
    assert not pas.is_rateable(_decision(1, 0, "mana_payment"))
    assert pas.is_rateable(_decision(1, 0, "priority"))


def test_blinding_state_and_halves(tmp_path: Path) -> None:
    out = _sample(tmp_path)
    for annotator in ("A", "B"):
        path = out / f"annotation_sheet_{annotator}.csv"
        text = path.read_text(encoding="utf-8")
        for forbidden in (
            "game-0",
            "KEY-ONE",
            "KEY-TWO",
            "xmage",
            "SECRET",
            "HIDDEN-LIB",
            "seed",
            "chulane",
            "Full Game Seat",
            "opp-token",
        ):
            assert forbidden not in text
        with path.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 240
        assert set(rows[0]) == set(pas.SHEET_COLUMNS)
        assert all(r["verdict"] == "" and r["severity"] == "" for r in rows)
        state = rows[0]["state_summary"]
        assert "Opponent 1 [" in state and "hand 6 cards" in state
        assert "face-down permanent" in state and "tapped, 2/2, damage 1, 2x +1/+1" in state
        assert "Lightning Bolt (Opponent 1)" in state and "face-down spell" in state
        assert "poison 2" in state and "library 70" in state and "graveyard (1): Shock" in state
        assert "mana pool 2 blue" in state
        assert "You" in rows[0]["prompt"] and "Opponent 1" in rows[0]["prompt"]
    key = json.loads((out / "sample_key.json").read_text(encoding="utf-8"))
    assert key["tested_seat_items"] == 120 and key["calibration_size"] == 40
    assert key["seed"] == 7 and key["label"] == "SIMULATED_RESULT" and key["weight"] == 0
    assert key["games_sampled"] >= 24
    assert all(len(i["source_sha256"]) == 64 for i in key["items"])
    assert "calibration" not in (out / "annotation_sheet_A.csv").read_text(encoding="utf-8")
    with (out / "owner_calibration_sheet.csv").open(encoding="utf-8") as fh:
        owner_rows = list(csv.DictReader(fh))
    cal_ids = {i["item_id"] for i in key["items"] if i["calibration"]}
    assert {r["item_id"] for r in owner_rows} == cal_ids
    assert all(r["verdict"] == "" for r in owner_rows)


def test_strata_fallback_reported(tmp_path: Path) -> None:
    plan = _plan()
    audit = _pool(tmp_path)
    cand, _ = pas.load_candidates(audit, plan)
    thin = [c for c in cand if c.kind != "declare_attacker" or c.seq % 4 == 0]
    _, _, report = pas.build_sample(thin, plan)
    tested = report["tested_seat"]
    assert isinstance(tested, dict) and tested["shortfall_redistributed"] > 0
    assert sum(tested["drawn"].values()) == 120


def test_output_inside_git_refused(tmp_path: Path) -> None:
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    plan = _plan()
    cand, meta = pas.load_candidates(_pool(tmp_path), plan)
    with pytest.raises(pas.AuditSampleError, match="git"):
        pas.write_sample(cand, meta, tmp_path / "repo" / "out", plan)


def test_wilson_known_values() -> None:
    assert pas.wilson_upper(14, 240) == pytest.approx(0.0955, abs=1e-3)
    assert pas.wilson_upper(14, 240) <= 0.10 < pas.wilson_upper(15, 240)
    assert pas.wilson_upper(2, 240) <= 0.03 < pas.wilson_upper(3, 240)
    assert pas.wilson_upper(5, 120) <= 0.10 < pas.wilson_upper(6, 120)
    assert pas.wilson_upper(0, 240) == pytest.approx(0.0158, abs=1e-3)


def _annotations(
    key: dict[str, object], clear: int, deciding: int, tested_clear: int
) -> dict[str, pas.Annotation]:
    items = key["items"]
    assert isinstance(items, list)
    tested = [i["item_id"] for i in items if i["tested_seat"]]
    other = [i["item_id"] for i in items if not i["tested_seat"]]
    errors = tested[:tested_clear] + other[: clear - tested_clear]
    out = {i["item_id"]: pas.Annotation("ok", "none") for i in items}
    for n, iid in enumerate(errors):
        out[iid] = pas.Annotation("clear_error", "game_deciding" if n < deciding else "minor")
    return out


def _cal_owner(
    key: dict[str, object], final: dict[str, pas.Annotation]
) -> dict[str, pas.Annotation]:
    items = key["items"]
    assert isinstance(items, list)
    return {i["item_id"]: final[i["item_id"]] for i in items if i["calibration"]}


def test_score_pass_fail_unknown(tmp_path: Path) -> None:
    key = _key(tmp_path)
    good = _annotations(key, 14, 2, 5)
    res = pas.score(key, good, good, _cal_owner(key, good))
    assert res["result"] == "PASS"
    assert res["kappa_verdict_AB"] == 1.0
    assert res["kappa_calibration_A_owner"] == 1.0 and res["kappa_calibration_B_owner"] == 1.0

    bad = _annotations(key, 15, 2, 5)
    assert pas.score(key, bad, bad, _cal_owner(key, bad))["result"] == "FAIL"
    dec = _annotations(key, 10, 3, 2)
    assert pas.score(key, dec, dec, _cal_owner(key, dec))["result"] == "FAIL"
    seat = _annotations(key, 10, 0, 6)
    assert pas.score(key, seat, seat, _cal_owner(key, seat))["result"] == "FAIL"

    assert pas.score(key, good, good, None)["result"] == "UNKNOWN"
    partial = dict(good)
    partial.pop("I001")
    assert pas.score(key, partial, good, _cal_owner(key, good))["result"] == "UNKNOWN"


def test_disputed_without_owner_is_unknown(tmp_path: Path) -> None:
    key = _key(tmp_path)
    a = _annotations(key, 0, 0, 0)
    b = dict(a)
    disputed = next(i["item_id"] for i in key["items"] if not i["calibration"])  # type: ignore[attr-defined]
    b[disputed] = pas.Annotation("clear_error", "minor")
    owner = _cal_owner(key, a)
    res = pas.score(key, a, b, owner)
    assert res["result"] == "UNKNOWN"
    assert res["disputed_for_owner"] == [disputed]
    owner[disputed] = pas.Annotation("ok", "none")
    assert pas.score(key, a, b, owner)["result"] == "PASS"


def _fill(src: Path, dst: Path, verdict: str = "ok", severity: str = "none") -> None:
    with src.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["verdict"], r["severity"] = verdict, severity
    with dst.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(pas.SHEET_COLUMNS))
        w.writeheader()
        w.writerows(rows)


def test_score_cli_owner_template_and_duplicates(tmp_path: Path) -> None:
    out = _sample(tmp_path)
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    _fill(out / "annotation_sheet_A.csv", a)
    _fill(out / "annotation_sheet_B.csv", b)
    # B disputes the first item; duplicate row in A for another item.
    rows = list(csv.DictReader(b.open(encoding="utf-8")))
    rows[0]["verdict"], rows[0]["severity"] = "clear_error", "minor"
    with b.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(pas.SHEET_COLUMNS))
        w.writeheader()
        w.writerows(rows)
    base = [
        "score",
        "--key",
        str(out / "sample_key.json"),
        "--sheet-a",
        str(a),
        "--sheet-b",
        str(b),
    ]
    tpl, res = tmp_path / "owner_template.csv", tmp_path / "r.json"
    assert pas.main([*base, "--owner-template", str(tpl), "--out-json", str(res)]) == 2
    template = list(csv.DictReader(tpl.open(encoding="utf-8")))
    key = json.loads((out / "sample_key.json").read_text(encoding="utf-8"))
    needed = {i["item_id"] for i in key["items"] if i["calibration"]} | {"I001"}
    assert {r["item_id"] for r in template} == needed
    assert all(r["verdict"] == "" for r in template)
    # Owner answers everything asked: now PASS.
    owner = tmp_path / "owner.csv"
    _fill(tpl, owner)
    assert pas.main([*base, "--sheet-owner", str(owner)]) == 0
    # Duplicate row for an item makes the sheet invalid -> UNKNOWN.
    with a.open("a", encoding="utf-8", newline="") as fh:
        csv.DictWriter(fh, fieldnames=list(pas.SHEET_COLUMNS)).writerow(
            {**rows[5], "verdict": "ok", "severity": "none"}
        )
    assert pas.main([*base, "--sheet-owner", str(owner), "--out-json", str(res)]) == 2
    result = json.loads(res.read_text(encoding="utf-8"))
    assert any("duplicate" in p for p in result["problems"])
