"""Pilot audit sampling, blinding and scoring (#1524); synthetic fixtures only."""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path

import pytest

from commander_lab.studio import pilot_audit_sample as pas

KINDS = ("priority", "target", "attack")


def _decision(seq: int, seat: int, kind: str, *, secret: str = "") -> dict[str, object]:
    return {
        "kind": "decision",
        "seq": seq,
        "decision_class": kind,
        "seat": seat,
        "prompt": f"Choose ({kind})",
        "minimum_selections": 1,
        "legal_options": [
            {"option_id": "o1", "label": "Pass", "option_type": "pass", "xmage_key": "KEY-ONE"},
            {"option_id": "o2", "label": f"Cast Spell {seq}", "option_type": "spell"},
        ],
        "pilot_state": {
            "turn_number": 1 + seq % 7,
            "actor_id": f"p{seat}",
            "players": [
                {
                    "player_id": f"p{seat}",
                    "is_actor": True,
                    "life": 40,
                    "hand": [{"name": "Island", "xmage_key": "KEY-TWO"}],
                    "deck_name": "SECRET-DECK-NAME",
                },
                {"player_id": "px", "life": 38, "hand": [{"name": "Hidden"}]},
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
) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    gid = f"game-{idx:03d}"
    lines: list[dict[str, object]] = [
        {
            "kind": "header",
            "schema": "studio-pilot-audit-1",
            "game_id": gid,
            "header": {
                "data_class": data_class,
                "pilot_fingerprint": fingerprint,
                "seats": [
                    {"seat": idx % 2, "deck_id": "chulane"},
                    {"seat": (idx + 1) % 2, "deck_id": "other"},
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


def _make_pool(folder: Path, games: int = 26) -> None:
    for i in range(games):
        _write_game(folder, i)


def _sample(tmp_path: Path, name: str = "out", seed: int = 7) -> Path:
    audit = tmp_path / "audit"
    if not audit.exists():
        _make_pool(audit)
    out = tmp_path / name
    rc = pas.main(
        [
            *("sample", "--audit-dir", str(audit), "--out-dir", str(out)),
            *("--seed", str(seed), "--tested-deck-id", "chulane"),
        ]
    )
    assert rc == 0
    return out


def test_deterministic(tmp_path: Path) -> None:
    a = _sample(tmp_path, "o1")
    b = _sample(tmp_path, "o2")
    for name in ("annotation_sheet_A.csv", "annotation_sheet_B.csv", "sample_key.json"):
        assert (a / name).read_bytes() == (b / name).read_bytes()
    c = _sample(tmp_path, "o3", seed=8)
    assert (a / "annotation_sheet_A.csv").read_bytes() != (
        c / "annotation_sheet_A.csv"
    ).read_bytes()


def test_refusals(tmp_path: Path) -> None:
    few = tmp_path / "few"
    for i in range(10):
        _write_game(few, i)
    cand, _ = pas.load_candidates(few, tested_deck_id="chulane")
    with pytest.raises(pas.AuditSampleError, match="games"):
        pas.build_sample(cand, seed=1)

    mixed = tmp_path / "mixed"
    _make_pool(mixed, 25)
    _write_game(mixed, 99, fingerprint="fp-2")
    with pytest.raises(pas.AuditSampleError, match="fingerprint"):
        pas.load_candidates(mixed)

    played = tmp_path / "played"
    _write_game(played, 0, data_class="PLAYED")
    with pytest.raises(pas.AuditSampleError, match="data_class"):
        pas.load_candidates(played)

    thin = tmp_path / "thin"
    for i in range(24):
        _write_game(thin, i, per_seat=2)
    cand, _ = pas.load_candidates(thin, tested_deck_id="chulane")
    with pytest.raises(pas.AuditSampleError, match="rateable"):
        pas.build_sample(cand, seed=1)
    assert (
        pas.main(
            ["sample", "--audit-dir", str(thin), "--out-dir", str(tmp_path / "x"), "--seed", "1"]
        )
        == 3
    )


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
    mana = _decision(1, 0, "mana_payment")
    assert not pas.is_rateable(mana)
    assert pas.is_rateable(_decision(1, 0, "priority"))


def test_blinding_and_halves(tmp_path: Path) -> None:
    out = _sample(tmp_path)
    for annotator in ("A", "B"):
        text = (out / f"annotation_sheet_{annotator}.csv").read_text(encoding="utf-8")
        for forbidden in (
            "game-0",
            "KEY-ONE",
            "KEY-TWO",
            "xmage",
            "SECRET-DECK",
            "seed",
            "chulane",
        ):
            assert forbidden not in text
        with (out / f"annotation_sheet_{annotator}.csv").open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 240
        assert set(rows[0]) == set(pas.SHEET_COLUMNS)
        assert all(r["verdict"] == "" and r["severity"] == "" for r in rows)
        assert "Opponent 1" in rows[0]["state_summary"]
    key = json.loads((out / "sample_key.json").read_text(encoding="utf-8"))
    assert key["tested_seat_items"] == 120
    assert key["calibration_size"] == 40
    assert key["seed"] == 7 and key["label"] == "SIMULATED_RESULT" and key["weight"] == 0
    assert len({i["game_id"] for i in key["items"]}) >= 24
    assert all(len(i["source_sha256"]) == 64 for i in key["items"])
    assert "calibration" not in (out / "annotation_sheet_A.csv").read_text(encoding="utf-8")


def test_output_inside_git_refused(tmp_path: Path) -> None:
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    cand, meta = pas.load_candidates(_pool(tmp_path), tested_deck_id="chulane")
    with pytest.raises(pas.AuditSampleError, match="git"):
        pas.write_sample(cand, meta, tmp_path / "repo" / "out", seed=1)


def _pool(tmp_path: Path) -> Path:
    audit = tmp_path / "audit"
    if not audit.exists():
        _make_pool(audit)
    return audit


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


def _key(tmp_path: Path) -> dict[str, object]:
    return json.loads((_sample(tmp_path) / "sample_key.json").read_text(encoding="utf-8"))


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

    bad = _annotations(key, 15, 2, 5)
    assert pas.score(key, bad, bad, _cal_owner(key, bad))["result"] == "FAIL"
    dec = _annotations(key, 10, 3, 2)
    assert pas.score(key, dec, dec, _cal_owner(key, dec))["result"] == "FAIL"
    seat = _annotations(key, 10, 0, 6)
    assert pas.score(key, seat, seat, _cal_owner(key, seat))["result"] == "FAIL"

    # No owner calibration sheet: never PASS.
    assert pas.score(key, good, good, None)["result"] == "UNKNOWN"
    # Missing annotation: UNKNOWN.
    partial = dict(good)
    partial.pop("I001")
    assert pas.score(key, partial, good, _cal_owner(key, good))["result"] == "UNKNOWN"


def test_disputed_without_owner_is_unknown(tmp_path: Path) -> None:
    key = _key(tmp_path)
    a = _annotations(key, 0, 0, 0)
    b = dict(a)
    disputed = next(
        i["item_id"]
        for i in key["items"]
        if not i["calibration"]  # type: ignore[attr-defined]
    )
    b[disputed] = pas.Annotation("clear_error", "minor")
    owner = _cal_owner(key, a)
    res = pas.score(key, a, b, owner)
    assert res["result"] == "UNKNOWN"
    assert res["disputed_for_owner"] == [disputed]
    owner[disputed] = pas.Annotation("ok", "none")
    assert pas.score(key, a, b, owner)["result"] == "PASS"
    owner[disputed] = pas.Annotation("clear_error", "minor")
    assert pas.score(key, a, b, owner)["result"] == "PASS"  # 1 error: bound within limits


def test_score_cli_and_invalid_rows(tmp_path: Path) -> None:
    out = _sample(tmp_path)
    key = json.loads((out / "sample_key.json").read_text(encoding="utf-8"))
    sheets = {}
    for annotator in ("A", "B"):
        src = out / f"annotation_sheet_{annotator}.csv"
        with src.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        for r in rows:
            r["verdict"], r["severity"] = "ok", "none"
        rows[0]["verdict"] = "bogus"
        sheets[annotator] = src
        with src.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(pas.SHEET_COLUMNS))
            w.writeheader()
            w.writerows(rows)
    rc = pas.main(
        [
            "score",
            "--key",
            str(out / "sample_key.json"),
            "--sheet-a",
            str(sheets["A"]),
            "--sheet-b",
            str(sheets["B"]),
            "--out-json",
            str(tmp_path / "r.json"),
        ]
    )
    assert rc == 2
    result = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert result["result"] == "UNKNOWN" and result["problems"]
    assert key["items"]
