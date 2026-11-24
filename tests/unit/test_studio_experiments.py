"""B2 (#1658): TableSpec, pilot fingerprint, experiment plan file, seed register, index.

New file because three new modules (``table_spec``, ``pilot_fingerprint``, ``experiments``)
have no test home yet. Fake boundary (no engine): the paired series runs with ``play_override``
(synthetic exposures, the variant wins every game); card preflight is a no-op. Real-engine
behaviour is NOT_RUN here.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from commander_lab.studio import (
    deck_series,
    experiments,
    launch,
    paired_comparison,
    paired_series,
    pilot_fingerprint,
)
from commander_lab.studio.__main__ import main as cli_main
from commander_lab.studio.paired_series import SCHEMA_PAIRED_JOB
from commander_lab.studio.store import DataClass, StudioStore
from commander_lab.studio.table_spec import TableSpec
from commander_lab.studio.web import create_app

REPO = Path(__file__).resolve().parents[2]
HEADERS = {"X-Studio": "1"}

# -- pilot fingerprint -----------------------------------------------------------------------

# The expected file set, built here independently of the module's constants (M1).
_PILOT_FILES = sorted(
    {
        *(
            p.relative_to(REPO).as_posix()
            for p in (REPO / "src/commander_lab/agents").rglob("*.py")
            if "__pycache__" not in p.parts
        ),
        *(
            p.relative_to(REPO).as_posix()
            for p in (REPO / "src/commander_lab/engine/rules/full_game_pilot").rglob("*.py")
            if "__pycache__" not in p.parts
        ),
        *(
            p.relative_to(REPO).as_posix()
            for p in (REPO / "src/commander_lab/engine/rules").glob("full_game_pilot_*.py")
        ),
        "src/commander_lab/models/pilots.py",
        "data/cards/pilot_card_knowledge.json",
        "data/cards/structural_role_profiles.json",
        "data/meta/spellbook_combos.json",
        "data/deck_guides/guides/chulane.json",
    }
)
_NOT_PILOT = (
    "src/commander_lab/studio/web.py",
    "src/commander_lab/engine/rules/full_game.py",
    "data/deck_guides/guides/notes.txt",
    "data/decks/precons/2011_counterpunch.json",
    "src/commander_lab/agents/__pycache__/pilots.cpython-313.pyc",
)


@pytest.fixture(scope="module")
def pilot_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("pilot_root")
    for rel in (*_PILOT_FILES, *_NOT_PILOT, "data/deck_guides/guides/precon_x.json"):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"line one\nline two {rel}\n".encode())
    return root


def _fp(root: Path, style: float | None = None) -> str:
    return pilot_fingerprint.pilot_fingerprint(
        policy_version="p1", strength="near_optimal_heuristic", style=style, root=root
    )


def test_the_real_repository_has_every_expected_pilot_file() -> None:
    assert set(_PILOT_FILES) <= {
        p.relative_to(REPO).as_posix() for p in pilot_fingerprint.pilot_files(REPO)
    }


@pytest.mark.parametrize("rel", _PILOT_FILES)
def test_every_pilot_file_changes_the_fingerprint(pilot_root: Path, rel: str) -> None:
    before = _fp(pilot_root)
    path = pilot_root / rel
    original = path.read_bytes()
    try:
        path.write_bytes(original + b"changed\n")
        assert _fp(pilot_root) != before
    finally:
        path.write_bytes(original)
    assert _fp(pilot_root) == before


@pytest.mark.parametrize("rel", _NOT_PILOT)
def test_a_file_outside_the_pilot_leaves_the_fingerprint(pilot_root: Path, rel: str) -> None:
    before = _fp(pilot_root)
    path = pilot_root / rel
    original = path.read_bytes()
    try:
        path.write_bytes(original + b"changed\n")
        assert _fp(pilot_root) == before
    finally:
        path.write_bytes(original)


def test_a_missing_pilot_file_is_an_error_not_left_out(pilot_root: Path) -> None:
    path = pilot_root / "src/commander_lab/models/pilots.py"
    original = path.read_bytes()
    path.unlink()
    try:
        with pytest.raises(FileNotFoundError, match=r"models/pilots\.py"):
            _fp(pilot_root)
    finally:
        path.write_bytes(original)


def test_line_endings_policy_strength_and_style(pilot_root: Path) -> None:
    before = _fp(pilot_root)
    path = pilot_root / _PILOT_FILES[0]
    original = path.read_bytes()
    try:
        path.write_bytes(original.replace(b"\n", b"\r\n"))
        assert _fp(pilot_root) == before  # CRLF and LF hash the same
    finally:
        path.write_bytes(original)
    assert _fp(pilot_root, 0.5) != before != _fp(pilot_root, 0.7)
    assert before != pilot_fingerprint.pilot_fingerprint(
        policy_version="p2", strength="near_optimal_heuristic", root=pilot_root
    )


# -- TableSpec -------------------------------------------------------------------------------


def _precons() -> list[str]:
    return [deck_id for deck_id, *_rest in launch._precons()[:3]]


def test_table_spec_checks_seats_opponents_and_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    opp = _precons()
    spec = TableSpec(seats=4, opponents=opp)
    assert spec.tested_seats() == [0, 1, 2, 3]
    assert TableSpec(seats=4, opponents=opp, seat_policy="fixed").tested_seats() == [0]
    five = [*opp, "precon/2011/other"]
    assert TableSpec(seats=5, opponents=five).tested_seats() == [0, 1, 2, 3, 4]  # shipped lock: six
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 4)  # the old lock, set back in memory
    with pytest.raises(ValidationError, match="locked"):
        TableSpec(seats=5, opponents=five)
    monkeypatch.undo()
    with pytest.raises(ValidationError, match="braucht 3 Gegner"):
        TableSpec(seats=4, opponents=opp[:2])
    with pytest.raises(ValidationError, match="doppelt"):
        TableSpec(seats=3, opponents=[opp[0], opp[0]])
    with pytest.raises(ValidationError):
        TableSpec.model_validate({"seats": 4, "opponents": opp, "seed_step": 4})
    rotation_spec = TableSpec(seats=4, opponent_mode="rotation", opponent_tables=[opp])
    draw_spec = TableSpec(seats=4, opponent_mode="draw", draw_pool=opp, draw_seed=7)
    for modelled in (rotation_spec, draw_spec):
        with pytest.raises(ValueError, match="noch nicht umgesetzt"):
            modelled.ensure_runnable()
    # fixed refuses conflicting fields of other modes
    with pytest.raises(ValidationError, match="erlaubt keine Angaben"):
        TableSpec(seats=4, opponents=opp, opponent_tables=[opp])
    with pytest.raises(ValidationError, match="erlaubt keine Angaben"):
        TableSpec(seats=4, opponents=opp, draw_pool=opp)
    with pytest.raises(ValidationError, match="erlaubt keine Angaben"):
        TableSpec(seats=4, opponents=opp, draw_seed=1)
    # rotation validations
    with pytest.raises(ValidationError, match="erlaubt keine Angaben"):
        TableSpec(seats=4, opponent_mode="rotation", opponents=opp, opponent_tables=[opp])
    with pytest.raises(ValidationError, match="erlaubt keine Angaben"):
        TableSpec(seats=4, opponent_mode="rotation", opponent_tables=[opp], draw_pool=opp)
    with pytest.raises(ValidationError, match="erlaubt keine Angaben"):
        TableSpec(seats=4, opponent_mode="rotation", opponent_tables=[opp], draw_seed=1)
    with pytest.raises(ValidationError, match="mindestens einen Tisch"):
        TableSpec(seats=4, opponent_mode="rotation", opponent_tables=[])
    with pytest.raises(ValidationError, match="braucht 3 Gegner"):
        TableSpec(seats=4, opponent_mode="rotation", opponent_tables=[opp[:2]])
    with pytest.raises(ValidationError, match="leere Gegner-Kennung"):
        TableSpec(seats=4, opponent_mode="rotation", opponent_tables=[[opp[0], " ", opp[2]]])
    with pytest.raises(ValidationError, match="nicht doppelt"):
        TableSpec(seats=4, opponent_mode="rotation", opponent_tables=[[opp[0], opp[0], opp[2]]])
    # draw validations
    with pytest.raises(ValidationError, match="erlaubt keine Angaben"):
        TableSpec(seats=4, opponent_mode="draw", opponents=opp, draw_pool=opp, draw_seed=1)
    with pytest.raises(ValidationError, match="erlaubt keine Angaben"):
        TableSpec(seats=4, opponent_mode="draw", opponent_tables=[opp], draw_pool=opp, draw_seed=1)
    with pytest.raises(ValidationError, match="nicht-leeren draw_pool"):
        TableSpec(seats=4, opponent_mode="draw", draw_pool=[], draw_seed=1)
    with pytest.raises(ValidationError, match="mindestens 3 Gegner"):
        TableSpec(seats=4, opponent_mode="draw", draw_pool=opp[:2], draw_seed=1)
    with pytest.raises(ValidationError, match="leere Gegner-Kennung"):
        TableSpec(seats=4, opponent_mode="draw", draw_pool=[opp[0], "", opp[2]], draw_seed=1)
    with pytest.raises(ValidationError, match="nicht doppelt"):
        TableSpec(seats=4, opponent_mode="draw", draw_pool=[opp[0], opp[0], opp[2]], draw_seed=1)
    with pytest.raises(ValidationError, match="ganzzahligen draw_seed"):
        TableSpec(seats=4, opponent_mode="draw", draw_pool=opp)
    with pytest.raises(ValidationError, match="Wahrheitswert"):
        TableSpec(seats=4, opponent_mode="draw", draw_pool=opp, draw_seed=True)


# -- experiments over web and CLI (fake engine) ----------------------------------------------


def _seed(store: StudioStore) -> None:
    src = store.register_source(
        data_class=DataClass.NORMALIZED_SOURCE, title="b2_test_source", sha256="1" * 64
    )
    for card_id, name, ci in (
        ("c_chulane", "Chulane, Teller of Tales", "WUG"),
        ("c_forest", "Forest", "G"),
        ("c_island", "Island", "U"),
        ("c_plains", "Plains", "W"),
        ("c_sol_ring", "Sol Ring", "C"),
    ):
        store.connection.execute(
            "INSERT OR IGNORE INTO card(card_id, oracle_name, color_identity, source_id) "
            "VALUES (?, ?, ?, ?)",
            (card_id, name, ci, src),
        )
    for deck_id in ("chulane-b2", "other-b2"):
        store.connection.execute(
            "INSERT OR IGNORE INTO deck(deck_id, name, created_at) VALUES (?, ?, ?)",
            (deck_id, deck_id, "2026-11-20T00:00:00Z"),
        )
    store.connection.commit()


def _cards(forests: int) -> list[dict[str, object]]:
    return [
        {"card_id": "c_chulane", "quantity": 1, "zone": "commander"},
        {"card_id": "c_sol_ring", "quantity": 1, "zone": "main"},
        {"card_id": "c_plains", "quantity": 20, "zone": "main"},
        {"card_id": "c_forest", "quantity": forests, "zone": "main"},
        {"card_id": "c_island", "quantity": 78 - forests, "zone": "main"},
    ]


def _player(base_id: str, variant_id: str) -> paired_comparison.PairPlayer:
    def play(arm: str, seed: int, seat: int) -> paired_comparison.PlayedGame:
        deck_id = base_id if arm == "base" else variant_id
        winners = [seat] if arm == "variant" else [(seat + 1) % 4]
        return {
            "exposure": {
                "game_id": f"b2-{deck_id}-{arm}-{seed}-{seat}",
                "seed": seed,
                "engine_commit": "5bd29ab6f318",
                "pilot": "GenericCommanderPilot 1.0.0",
                "decision_policy": "xmage-full-game-policy-1.0.0",
                "winner_seats": winners,
                # every seat row, as a game header has them: the table the games show (#1661)
                "seats": [
                    {
                        "seat": s,
                        "deck_id": deck_id if s == seat else f"opp-{s}",
                        "win_credit": 1.0 if s in winners else 0.0,
                        "first_hand": [],
                        "seen_by_turn_3": [],
                    }
                    for s in range(4)
                ],
            },
            "failure_class": None,
        }

    return play


@pytest.fixture
def lab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    store = StudioStore.open(tmp_path)
    try:
        _seed(store)
    finally:
        store.close()
    monkeypatch.setattr(paired_series, "_preflight_snapshot_cards", lambda *a, **k: None)
    manager = paired_series.paired_series_manager
    original = manager.start_series

    def start(*args: object, **kwargs: object) -> paired_series.PairedSeriesJob:
        base = str(kwargs["base_revision_id"]).split("@", 1)[0]
        kwargs["play_override"] = _player(f"{base}--base", f"{base}--variant")
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(manager, "start_series", start)
    client = TestClient(create_app(tmp_path))
    revs = {}
    for name, deck_id, forests, parent in (
        ("base", "chulane-b2", 40, None),
        ("variant", "chulane-b2", 38, "base"),
        ("variant2", "chulane-b2", 36, "base"),
        ("other", "other-b2", 45, None),
    ):
        res = client.post(
            f"/api/decks/{deck_id}/revisions",
            headers=HEADERS,
            json={
                "cards": _cards(forests),
                "note": name,
                "branch": "main" if parent is None else name,
                **({"parent_revision_id": revs[parent]} if parent else {}),
            },
        )
        assert res.status_code == 200, res.text
        revs[name] = res.json()["revision_id"]
    return {"client": client, "folder": tmp_path, "revs": revs}


def _plan(revs: dict[str, str], **over: object) -> dict[str, object]:
    plan: dict[str, object] = {
        "schema": "studio-experiment-plan-1",
        "question": "38 statt 40 Wälder",
        "question_kind": "axis",
        "deck_id": "chulane-b2",
        "base": {"revision_id": revs["base"]},
        "variants": [{"revision_id": revs["variant"]}],
        "table": {"seats": 4, "opponents": _precons()},
        "purpose": "exploration",
        "budget_pairs": 4,
        "look_every_pairs": 2,
        "first_seed": 100,
    }
    plan.update(over)
    return plan


def _wait(folder: Path, series_id: str) -> dict[str, object]:
    path = folder / "games" / f"{series_id}.paired.json"
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("status") in {"completed", "failed", "cancelled"}:
                assert raw["status"] == "completed", raw.get("error")
                return raw
        time.sleep(0.05)
    pytest.fail(f"series {series_id} did not finish")


def _start(lab: dict[str, object], plan: dict[str, object]) -> dict[str, object]:
    client = lab["client"]
    assert isinstance(client, TestClient)
    res = client.post("/api/experiments", headers=HEADERS, json={"plan": plan})
    assert res.status_code == 200, res.text
    started = res.json()
    _wait(Path(str(lab["folder"])), started["series_id"])
    return started


def _history(lab: dict[str, object]) -> dict[str, object]:
    client = lab["client"]
    assert isinstance(client, TestClient)
    res = client.get("/api/decks/chulane-b2/series", headers=HEADERS)
    assert res.status_code == 200
    return res.json()


def _index_rows(folder: Path) -> list[dict[str, object]]:
    store = StudioStore.open(folder)
    try:
        return [dict(r) for r in store.connection.execute("SELECT * FROM experiment")]
    finally:
        store.close()


def test_one_plan_file_gives_the_same_series_over_web_and_cli(
    lab: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    revs = lab["revs"]
    assert isinstance(revs, dict)
    folder = Path(str(lab["folder"]))
    plan = _plan(revs)
    web = _start(lab, plan)
    plan_file = folder / "plan.json"
    plan_file.write_text(json.dumps(plan), encoding="utf-8")
    capsys.readouterr()
    assert cli_main(["--data", str(folder), "experiment", "--plan", str(plan_file)]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert cli["status"] == "completed"
    for key in ("plan_sha", "table_hash", "seeds", "tested_seats", "arms"):
        assert web[key] == cli[key], key
    assert web["experiment_id"] != cli["experiment_id"]
    assert web["seeds"] == {
        "first": 100,
        "last": 100,
        "count": 1,
        "rule": "consecutive",
        "starting_seat_rule": "seed % seats",
    }
    record = deck_series.plan_record(folder, web["experiment_id"])
    assert record is not None and record["plan_sha"] == web["plan_sha"]
    assert record["data_class"] == "SIMULATED_RESULT"
    series = json.loads((folder / "games" / f"{web['series_id']}.paired.json").read_text())
    assert series["experiment"]["plan_sha"] == web["plan_sha"]
    assert series["seed_plan"]["first_seed"] == 100


def test_unknown_opponents_are_errors_and_studio_states_may_sit(
    lab: dict[str, object],
) -> None:
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    folder = Path(str(lab["folder"]))
    opp = _precons()
    for opponents, code in (
        ([opp[0], opp[1], "precon/does-not-exist"], 422),
        ([opp[0], opp[1], "other-b2@ffffffffffffffff"], 404),
    ):
        res = client.post(
            "/api/experiments",
            headers=HEADERS,
            json={"plan": _plan(revs, table={"seats": 4, "opponents": opponents})},
        )
        assert res.status_code == code, res.text
    assert _index_rows(folder) == []
    assert not (folder / "games" / "experiments").exists()
    # E15 Q6: any Studio deck state can take an opponent seat, another state of the same deck too
    started = _start(
        lab, _plan(revs, table={"seats": 4, "opponents": [revs["other"], revs["variant2"], opp[0]]})
    )
    deck_dir = folder / "games" / "paired_decks" / started["series_id"]
    snaps = sorted(p.name for p in deck_dir.glob("opponent-*.json"))
    assert len(snaps) == 2
    record = deck_series.plan_record(folder, started["experiment_id"])
    assert record is not None
    resolved = record["resolved"]
    assert isinstance(resolved, dict)
    assert len(resolved["table"]["opponent_hashes"]) == 3
    assert all(isinstance(h, str) and len(h) == 64 for h in resolved["table"]["opponent_hashes"])


def test_seed_register_refuses_confirmation_on_exploration_seeds(lab: dict[str, object]) -> None:
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    _start(lab, _plan(revs, budget_pairs=12, first_seed=100))  # exploration: seeds 100..102
    for first in (98, 100, 102):  # 98..100 still touches 100
        res = client.post(
            "/api/experiments",
            headers=HEADERS,
            json={"plan": _plan(revs, purpose="confirmation", budget_pairs=12, first_seed=first)},
        )
        assert res.status_code == 422 and "Erkundung" in res.json()["detail"], first
    confirmed = _start(lab, _plan(revs, purpose="confirmation", budget_pairs=12, first_seed=103))
    assert confirmed["seeds"]["first"] == 103


def test_plan_sha_mismatch_never_counts_and_adopt_is_then_untested(
    lab: dict[str, object],
) -> None:
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    folder = Path(str(lab["folder"]))
    started = _start(lab, _plan(revs))
    entry = next(s for s in _history(lab)["series"] if s["series_id"] == started["series_id"])
    assert entry["counts_as_result"] is True and entry["difference_pp"] == 100.0
    plan_path = folder / "games" / "experiments" / started["experiment_id"] / "plan.json"
    record = json.loads(plan_path.read_text(encoding="utf-8"))
    record["plan"]["question"] = "nachträglich geändert"
    plan_path.write_text(json.dumps(record), encoding="utf-8")
    entry = next(s for s in _history(lab)["series"] if s["series_id"] == started["series_id"])
    assert entry["status"] == "plan_mismatch"
    assert entry["counts_as_result"] is False and entry["difference_pp"] is None
    res = client.post(
        f"/api/experiments/{started['experiment_id']}/decision",
        headers=HEADERS,
        json={"decision": "adopted", "note": "ohne gültigen Test"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["tested"] is False
    entry = next(s for s in _history(lab)["series"] if s["series_id"] == started["series_id"])
    assert entry["experiment"]["decision_text"] == "übernommen (ungetestet)"


def test_adopt_sets_main_and_writes_the_decision_reject_keeps_it(lab: dict[str, object]) -> None:
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    folder = Path(str(lab["folder"]))
    first = _start(lab, _plan(revs))
    second = _start(lab, _plan(revs, variants=[{"revision_id": revs["variant2"]}], first_seed=200))

    def main_branch() -> str:
        store = StudioStore.open(folder)
        try:
            row = store.connection.execute(
                "SELECT revision_id FROM deck_branch WHERE deck_id = 'chulane-b2' AND branch = 'main'"
            ).fetchone()
            return str(row[0])
        finally:
            store.close()

    assert main_branch() == revs["base"]
    res = client.post(
        f"/api/experiments/{second['experiment_id']}/decision",
        headers=HEADERS,
        json={"decision": "rejected", "note": "zu wenig Grün"},
    )
    assert res.status_code == 200 and main_branch() == revs["base"]
    res = client.post(
        f"/api/experiments/{first['experiment_id']}/decision",
        headers=HEADERS,
        json={"decision": "adopted", "note": "Owner-Entscheid"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["tested"] is True
    assert main_branch() == revs["variant"]
    rows = {r["experiment_id"]: r for r in _index_rows(folder)}
    assert rows[first["experiment_id"]]["decision"] == "adopted"
    assert rows[first["experiment_id"]]["decision_tested"] == 1
    assert rows[second["experiment_id"]]["decision"] == "rejected"
    decision = json.loads(
        (folder / "games/experiments" / first["experiment_id"] / "decision.json").read_text()
    )
    assert decision["decision"] == "adopted" and decision["revision_id"] == revs["variant"]
    again = client.post(
        f"/api/experiments/{first['experiment_id']}/decision",
        headers=HEADERS,
        json={"decision": "rejected"},
    )
    assert again.status_code == 409
    assert (
        client.post(
            "/api/experiments/exp-1-1-unknown/decision",
            headers=HEADERS,
            json={"decision": "adopted"},
        ).status_code
        == 404
    )
    texts = {
        s["experiment"]["experiment_id"]: s["experiment"]["decision_text"]
        for s in _history(lab)["series"]
        if s["experiment"]
    }
    assert texts == {first["experiment_id"]: "übernommen", second["experiment_id"]: "verworfen"}


def _legacy_series(folder: Path, series_id: str, base: str, variant: str, created: str) -> None:
    path = folder / "games" / f"{series_id}.paired.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": SCHEMA_PAIRED_JOB,
                "series_id": series_id,
                "status": "completed",
                "base_ref": base,
                "variant_ref": variant,
                "budget_pairs": 4,
                "created_at": created,
                "seed_plan": {"purpose": "exploration", "first_seed": 500, "seeds_planned": 1},
                "result": {"pairs_completed": 4, "pairs_played": 4, "difference_pp": 25.0},
            }
        ),
        encoding="utf-8",
    )


def test_rebuilt_index_gives_the_same_history(lab: dict[str, object]) -> None:
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    folder = Path(str(lab["folder"]))
    first = _start(lab, _plan(revs))
    _start(lab, _plan(revs, variants=[{"revision_id": revs["variant2"]}], first_seed=300))
    client.post(
        f"/api/experiments/{first['experiment_id']}/decision",
        headers=HEADERS,
        json={"decision": "adopted", "note": "x"},
    )
    _legacy_series(folder, "paired-1-1-legacy01", revs["base"], revs["variant"], "2026-01-01")
    _legacy_series(folder, "paired-1-2-legacy02", revs["other"], revs["base"] + "x", "2026-01-02")
    before = _history(lab)
    assert len(before["series"]) == 3  # two experiments, one legacy series of this deck
    store = StudioStore.open(folder)
    try:
        with store.connection:
            store.connection.execute("DELETE FROM experiment_arm")
            store.connection.execute("DELETE FROM experiment")
    finally:
        store.close()
    res = client.post("/api/experiments/rebuild-index", headers=HEADERS)
    assert res.status_code == 200
    assert res.json() == {"experiments": 2, "legacy": 2, "skipped": 0}
    # the scan counts say how the legacy part was read (scanned before, indexed now)
    scan_keys = {
        "scan_files_read",
        "scan_files_total",
        "legacy_series_shown",
        "legacy_series_found",
    }

    def without_scan(payload: dict[str, object]) -> dict[str, object]:
        return {k: v for k, v in payload.items() if k not in scan_keys}

    rebuilt = _history(lab)
    assert without_scan(rebuilt) == without_scan(before)
    assert (before["legacy_series_shown"], rebuilt["legacy_series_shown"]) == (1, 0)
    # delete and rebuild once more: the answer is identical, scan counts included
    assert client.post("/api/experiments/rebuild-index", headers=HEADERS).status_code == 200
    assert _history(lab) == rebuilt
    # a series of another deck's state never appears at this deck
    other = client.get("/api/decks/other-b2/series", headers=HEADERS).json()
    assert {s["series_id"] for s in other["series"]} == {"paired-1-2-legacy02"}
    assert other["by_revision"].keys() == {revs["other"]}


def test_index_delivers_more_than_the_old_scan_limit(lab: dict[str, object]) -> None:
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    folder = Path(str(lab["folder"]))
    total = 2001
    for i in range(total):
        _legacy_series(
            folder, f"paired-2-{i:05d}-many", revs["base"], revs["variant"], f"2026-02-{i:05d}"
        )
    scanned = _history(lab)
    assert scanned["truncated"] or scanned["scan_truncated"]  # the old bounded scan
    assert client.post("/api/experiments/rebuild-index", headers=HEADERS).status_code == 200
    indexed = _history(lab)
    assert len(indexed["series"]) == indexed["series_total"] == total
    assert indexed["truncated"] is False and indexed["scan_truncated"] == 0
    assert len(indexed["by_revision"][revs["base"]]) == total


def test_experiment_routes_declare_their_cache_writes(
    lab: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the cache check on, an undeclared write group raises (``CacheCheckError``)."""
    from commander_lab.studio import cache

    monkeypatch.setattr(cache, "CHECK", True)
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    proven = cache.counters().get("* window_proven", 0)
    started = _start(lab, _plan(revs, first_seed=700))
    assert (
        client.post(
            f"/api/experiments/{started['experiment_id']}/decision",
            headers=HEADERS,
            json={"decision": "adopted"},
        ).status_code
        == 200
    )
    assert client.post("/api/experiments/rebuild-index", headers=HEADERS).status_code == 200
    counters = cache.counters()
    assert counters.get("* window_proven", 0) == proven + 3  # start, decision, rebuild
    assert "* window_undeclared" not in counters
    assert "* window_unproven" not in counters
    # plan files gone: the rebuild reads first and refuses instead of dropping the index
    shutil.rmtree(Path(str(lab["folder"])) / "games" / "experiments")
    refused = client.post("/api/experiments/rebuild-index", headers=HEADERS)
    assert refused.status_code == 409 and "Plan-Datei" in refused.json()["detail"]
    assert len(_index_rows(Path(str(lab["folder"])))) == 1


def _main_branch(folder: Path) -> str:
    store = StudioStore.open(folder)
    try:
        row = store.connection.execute(
            "SELECT revision_id FROM deck_branch WHERE deck_id = 'chulane-b2' AND branch = 'main'"
        ).fetchone()
        return str(row[0])
    finally:
        store.close()


def test_adopt_refuses_a_moved_base_and_can_be_undone(lab: dict[str, object]) -> None:
    """Review #1685 P2-1: adopting never overwrites a ``main`` that moved since the plan; the
    previous ``main`` is stored, and undo restores it only while ``main`` is the variant."""
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    folder = Path(str(lab["folder"]))
    first = _start(lab, _plan(revs))
    second = _start(lab, _plan(revs, variants=[{"revision_id": revs["variant2"]}], first_seed=200))

    def post(experiment: dict[str, object], action: str, **body: object) -> object:
        return client.post(
            f"/api/experiments/{experiment['experiment_id']}/{action}", headers=HEADERS, json=body
        )

    adopted = post(first, "decision", decision="adopted")
    assert adopted.status_code == 200 and adopted.json()["previous_revision_id"] == revs["base"]  # type: ignore[attr-defined]
    assert _main_branch(folder) == revs["variant"]
    # the second experiment was planned on the old base: no silent overwrite
    stale = post(second, "decision", decision="adopted")
    assert stale.status_code == 409 and "nicht mehr auf der Basis" in stale.json()["detail"]  # type: ignore[attr-defined]
    assert _main_branch(folder) == revs["variant"]
    undone = post(first, "undo")
    assert undone.status_code == 200 and undone.json()["restored_revision_id"] == revs["base"]  # type: ignore[attr-defined]
    assert _main_branch(folder) == revs["base"]
    rows = {r["experiment_id"]: r for r in _index_rows(folder)}
    assert rows[first["experiment_id"]]["decision"] == "open"
    decision = json.loads(
        (folder / "games/experiments" / first["experiment_id"] / "decision.json").read_text()
    )
    assert decision["decision"] == "undone" and decision["undone"]["decision"] == "adopted"
    assert post(first, "undo").status_code == 409  # nothing to undo any more
    # now the second may be adopted; after main moves away, its undo is refused
    assert post(second, "decision", decision="adopted").status_code == 200  # type: ignore[attr-defined]
    store = StudioStore.open(folder)
    try:
        with store.connection:
            store.connection.execute(
                "UPDATE deck_branch SET revision_id = ? WHERE deck_id = 'chulane-b2' "
                "AND branch = 'main'",
                (revs["variant"],),
            )
    finally:
        store.close()
    refused = post(second, "undo")
    assert refused.status_code == 409  # type: ignore[attr-defined]
    assert _main_branch(folder) == revs["variant"]
    # the rebuilt index keeps the stored previous main of an adoption
    assert client.post("/api/experiments/rebuild-index", headers=HEADERS).status_code == 200
    rows = {r["experiment_id"]: r for r in _index_rows(folder)}
    assert rows[second["experiment_id"]]["decision_previous_revision_id"] == revs["base"]


def test_a_series_with_a_foreign_or_missing_plan_sha_never_counts(lab: dict[str, object]) -> None:
    """Review #1685 P2-3: the result side of the binding (the series names the plan SHA)."""
    revs = lab["revs"]
    assert isinstance(revs, dict)
    folder = Path(str(lab["folder"]))
    started = _start(lab, _plan(revs))
    path = folder / "games" / f"{started['series_id']}.paired.json"
    original = json.loads(path.read_text(encoding="utf-8"))
    for experiment in ({**original["experiment"], "plan_sha": "0" * 64}, None):
        path.write_text(json.dumps({**original, "experiment": experiment}), encoding="utf-8")
        entry = next(s for s in _history(lab)["series"] if s["series_id"] == started["series_id"])
        assert entry["status"] == "plan_mismatch" and entry["counts_as_result"] is False
    path.write_text(json.dumps(original), encoding="utf-8")
    entry = next(s for s in _history(lab)["series"] if s["series_id"] == started["series_id"])
    assert entry["counts_as_result"] is True


def test_a_style_other_than_the_series_style_is_refused(lab: dict[str, object]) -> None:
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    table = {"seats": 4, "opponents": _precons(), "pilot": {"style": 0.7}}
    res = client.post("/api/experiments", headers=HEADERS, json={"plan": _plan(revs, table=table)})
    assert res.status_code == 422 and "Stil" in res.json()["detail"]
    assert _index_rows(Path(str(lab["folder"]))) == []


def test_resume_after_a_pilot_change_says_so_instead_of_mixing() -> None:
    """Review #1685 P2-2: stored games of another pilot (or without a fingerprint) stop the
    resume with an honest German reason; the same pilot goes on."""
    current = "fp:" + "a" * 64

    def played(fingerprint: str | None) -> paired_comparison.PlayedGame:
        return {
            "exposure": {
                "game_id": "g",
                "seed": 1,
                "engine_commit": "c",
                "pilot": "GenericCommanderPilot 1.0.0",
                "pilot_fingerprint": fingerprint,
                "decision_policy": "p",
                "winner_seats": [0],
                "seats": [],
            },
            "failure_class": None,
        }

    same = {("base", 1, 0): played("a" * 64), ("variant", 1, 0): played("a" * 64)}
    assert paired_series.pilot_change_message(same, current) is None
    for other in (None, "b" * 64):
        message = paired_series.pilot_change_message(
            {**same, ("base", 2, 0): played(other)}, current
        )
        assert message is not None
        assert message.startswith("nicht fortsetzbar: 1 gespeicherte Partien")


def test_resume_without_a_test_player_stops_on_a_pilot_change(
    lab: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Delta review #1685: the mixing guard runs on the real resume path (no play_override)."""
    revs = lab["revs"]
    assert isinstance(revs, dict)
    folder = Path(str(lab["folder"]))
    started = _start(lab, _plan(revs))  # its stored games carry no fingerprint (fake player)
    path = folder / "games" / f"{started['series_id']}.paired.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**raw, "status": "running"}), encoding="utf-8")  # a hard stop
    monkeypatch.setattr(
        paired_series,
        "series_engine",
        lambda *a, **k: launch.SeriesEngine(
            command=("fake-java",), jvm_flags=(), games_per_jvm=1, serial_gc=False, appcds=False
        ),
    )
    monkeypatch.setattr(paired_series, "command_bridge_jar_sha256", lambda *a, **k: None)
    with pytest.raises(
        ValueError, match=r"nicht fortsetzbar: \d+ gespeicherte Partien.*neu starten"
    ):
        paired_series.PairedSeriesManager().resume_series(folder, started["series_id"])


def test_adopt_and_undo_write_only_what_they_read(
    lab: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Delta review #1685: ``main`` moves between the check and the write (a second adoption,
    another window): the conditional write refuses with 409 and changes nothing."""
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    folder = Path(str(lab["folder"]))
    first = _start(lab, _plan(revs))

    def move_main(to: str) -> None:
        store = StudioStore.open(folder)
        try:
            with store.connection:
                store.connection.execute(
                    "UPDATE deck_branch SET revision_id = ? WHERE deck_id = 'chulane-b2' "
                    "AND branch = 'main'",
                    (to,),
                )
        finally:
            store.close()

    real_read = experiments._main_revision
    move_main(revs["variant2"])  # someone else moved main; the stale read still sees the base
    monkeypatch.setattr(experiments, "_main_revision", lambda *_a: revs["base"])
    res = client.post(
        f"/api/experiments/{first['experiment_id']}/decision",
        headers=HEADERS,
        json={"decision": "adopted"},
    )
    assert res.status_code == 409
    assert _main_branch(folder) == revs["variant2"]
    assert _index_rows(folder)[0]["decision"] == "open"
    monkeypatch.setattr(experiments, "_main_revision", real_read)
    move_main(revs["base"])
    assert (
        client.post(
            f"/api/experiments/{first['experiment_id']}/decision",
            headers=HEADERS,
            json={"decision": "adopted"},
        ).status_code
        == 200
    )
    move_main(revs["variant2"])  # moved after the adoption; the stale read sees the variant
    monkeypatch.setattr(experiments, "_main_revision", lambda *_a: revs["variant"])
    res = client.post(f"/api/experiments/{first['experiment_id']}/undo", headers=HEADERS)
    assert res.status_code == 409
    assert _main_branch(folder) == revs["variant2"]
    assert _index_rows(folder)[0]["decision"] == "adopted"


# -- B2b (#1658): experiment detail, read-only routes, no overwrite, old store ---------------


def _detail(lab: dict[str, object], experiment_id: str) -> dict[str, object]:
    client = lab["client"]
    assert isinstance(client, TestClient)
    res = client.get(f"/api/experiments/{experiment_id}", headers=HEADERS)
    assert res.status_code == 200, res.text
    body = res.json()
    assert isinstance(body, dict)
    return body


def test_experiment_detail_shows_the_plan_and_the_maturity_of_the_series_route(
    lab: dict[str, object],
) -> None:
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    first = _start(lab, _plan(revs, budget_pairs=8))
    second = _start(lab, _plan(revs, variants=[{"revision_id": revs["variant2"]}], first_seed=200))
    history = _history(lab)
    for started in (first, second):
        detail = _detail(lab, started["experiment_id"])
        assert detail["data_class"] == "SIMULATED_RESULT"
        assert detail["plan_state"] == "intact" and detail["legacy"] is False
        plan = detail["plan"]
        assert isinstance(plan, dict)
        assert plan["purpose"] == "exploration" and plan["stop_rule"] == "obf_looks"
        assert plan["look_every_pairs"] == 2 and plan["question_kind"] == "axis"
        assert [a["role"] for a in detail["arms"]] == ["base", "variant"]
        assert [a["revision_id"] for a in detail["arms"]] == [
            a["revision_id"] for a in started["arms"]
        ]
        assert all(isinstance(a["deck_hash"], str) for a in detail["arms"])
        assert detail["seeds"]["first"] == started["seeds"]["first"]
        assert detail["seeds"]["count"] == started["seeds"]["count"]
        assert detail["table_hash"] == started["table_hash"]
        sid = started["series_id"]
        # the same entry and the same maturity as the deck's series route, nothing recomputed
        entry = next(s for s in history["series"] if s["series_id"] == sid)
        assert detail["result"] == entry
        assert detail["reifegrad"] == history["reifegrad"]["befunde"][sid]
        assert detail["reifegrad"]["n"] == entry["pairs_completed"]
        assert detail["reifegrad"]["N"] == entry["pairs_planned"]
    assert _detail(lab, first["experiment_id"])["result"]["pairs_planned"] == 8
    # adopting the first moves main: the second is a finding about another state, not current
    assert (
        client.post(
            f"/api/experiments/{first['experiment_id']}/decision",
            headers=HEADERS,
            json={"decision": "adopted"},
        ).status_code
        == 200
    )
    adopted = _detail(lab, first["experiment_id"])
    stale = _detail(lab, second["experiment_id"])
    assert adopted["current_main_revision_id"] == revs["variant"]
    assert adopted["reifegrad"]["stand"]["bezug"] == "aktuell"
    assert stale["reifegrad"]["stand"]["bezug"] != "aktuell"
    assert stale["experiment"]["decision"] == "open"
    assert client.get("/api/experiments/exp-1-1-unknown", headers=HEADERS).status_code == 404
    for bad in ("nothing", "exp-" + "a" * 100, "exp-a.b", "paired-a.b", "paired-%20x"):
        assert client.get(f"/api/experiments/{bad}", headers=HEADERS).status_code == 422, bad
    assert client.get("/api/experiments/exp-../x", headers=HEADERS).status_code in (404, 422)
    assert client.get("/api/experiments/..%2Fplan", headers=HEADERS).status_code in (404, 422)


def test_unknown_stays_unknown_in_the_detail_of_a_legacy_series(lab: dict[str, object]) -> None:
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    folder = Path(str(lab["folder"]))
    path = folder / "games" / "paired-3-1-running01.paired.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": SCHEMA_PAIRED_JOB,
                "series_id": "paired-3-1-running01",
                "status": "running",
                "base_ref": revs["base"],
                "variant_ref": revs["variant"],
                "budget_pairs": 4,
                "created_at": "2026-03-01",
            }
        ),
        encoding="utf-8",
    )
    assert client.post("/api/experiments/rebuild-index", headers=HEADERS).status_code == 200
    detail = _detail(lab, "paired-3-1-running01")
    assert detail["legacy"] is True and detail["experiment"] is None
    assert detail["plan"] is None and detail["plan_state"] == "legacy"
    assert detail["seeds"] == {"first": None, "last": None, "count": None, "rule": None}
    assert detail["arms"][0]["deck_hash"] is None  # not stored for a legacy row: unknown
    result = detail["result"]
    assert result["counts_as_result"] is False
    assert result["pairs_completed"] is None
    assert result["difference_pp"] is None
    assert detail["reifegrad"]["n"] is None


def _tree(folder: Path) -> dict[str, tuple[int, int]]:
    return {
        p.relative_to(folder).as_posix(): (p.stat().st_mtime_ns, p.stat().st_size)
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def test_read_routes_write_neither_the_store_nor_a_file(lab: dict[str, object]) -> None:
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    folder = Path(str(lab["folder"]))
    started = _start(lab, _plan(revs))
    _legacy_series(folder, "paired-4-1-legacy04", revs["base"], revs["variant"], "2026-04-01")
    StudioStore.open(folder).close()  # the opening migration runs before the snapshot
    before = _tree(folder)
    db = folder / "studio.sqlite3"
    assert db.is_file()
    db_bytes = db.read_bytes()
    for url in (
        f"/api/experiments/{started['experiment_id']}",
        "/api/experiments/paired-4-1-legacy04",  # not indexed yet: 404, and nothing indexed
        "/api/decks/chulane-b2/series",
    ):
        assert client.get(url, headers=HEADERS).status_code in (200, 404)
    assert _tree(folder) == before
    assert db.read_bytes() == db_bytes
    assert {r["experiment_id"] for r in _index_rows(folder)} == {started["experiment_id"]}


def test_a_colliding_experiment_id_overwrites_nothing(
    lab: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two starts of the same plan in the same second from two processes get the same id;
    the second never touches the plan, run, decision files or index rows of the first."""
    import itertools

    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    folder = Path(str(lab["folder"]))
    monkeypatch.setattr(experiments.time, "time", lambda: 1_800_000_000.0)
    monkeypatch.setattr(experiments, "_SEQ", itertools.count(1))
    first = _start(lab, _plan(revs))
    adopt = client.post(
        f"/api/experiments/{first['experiment_id']}/decision",
        headers=HEADERS,
        json={"decision": "rejected", "note": "erstes"},
    )
    assert adopt.status_code == 200
    own = folder / "games" / "experiments" / first["experiment_id"]
    files = {p.name: p.read_bytes() for p in own.iterdir()}
    assert set(files) == {"plan.json", "run.json", "decision.json"}
    rows = _index_rows(folder)
    monkeypatch.setattr(experiments, "_SEQ", itertools.count(1))  # the other process
    res = client.post("/api/experiments", headers=HEADERS, json={"plan": _plan(revs)})
    assert res.status_code == 409 and "existiert schon" in res.json()["detail"]
    assert {p.name: p.read_bytes() for p in own.iterdir()} == files
    assert _index_rows(folder) == rows
    # the files alone (index rows gone, a rebuild not yet run) are not overwritten either
    store = StudioStore.open(folder)
    try:
        with store.connection:
            store.connection.execute("DELETE FROM experiment_arm")
            store.connection.execute("DELETE FROM experiment")
    finally:
        store.close()
    monkeypatch.setattr(experiments, "_SEQ", itertools.count(1))
    res = client.post("/api/experiments", headers=HEADERS, json={"plan": _plan(revs)})
    assert res.status_code == 409
    assert {p.name: p.read_bytes() for p in own.iterdir()} == files
    assert _index_rows(folder) == []
    # and the index row alone (folder gone) is not overwritten or removed
    assert client.post("/api/experiments/rebuild-index", headers=HEADERS).status_code == 200
    rows = _index_rows(folder)
    assert [r["experiment_id"] for r in rows] == [first["experiment_id"]]
    shutil.rmtree(own)
    monkeypatch.setattr(experiments, "_SEQ", itertools.count(1))
    res = client.post("/api/experiments", headers=HEADERS, json={"plan": _plan(revs)})
    assert res.status_code == 409
    assert _index_rows(folder) == rows
    assert not own.exists()


def test_reject_keeps_every_piece_of_evidence(lab: dict[str, object]) -> None:
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    folder = Path(str(lab["folder"]))
    started = _start(lab, _plan(revs))
    before = _detail(lab, started["experiment_id"])
    res = client.post(
        f"/api/experiments/{started['experiment_id']}/decision",
        headers=HEADERS,
        json={"decision": "rejected", "note": "nein"},
    )
    assert res.status_code == 200
    own = folder / "games" / "experiments" / started["experiment_id"]
    assert {p.name for p in own.iterdir()} == {"plan.json", "run.json", "decision.json"}
    assert (folder / "games" / f"{started['series_id']}.paired.json").is_file()
    after = _detail(lab, started["experiment_id"])
    assert after["arms"] == before["arms"]

    def numbers(detail: dict[str, object]) -> dict[str, object]:
        result = detail["result"]
        assert isinstance(result, dict)
        return {k: v for k, v in result.items() if k != "experiment"}  # decision text differs

    assert numbers(after) == numbers(before)
    assert after["result"]["counts_as_result"] is True
    assert after["experiment"]["decision"] == "rejected"
    assert after["experiment"]["decision_note"] == "nein"
    store = StudioStore.open(folder)
    try:
        assert store.connection.execute(
            "SELECT 1 FROM deck_revision WHERE revision_id = ?", (revs["variant"],)
        ).fetchone()
    finally:
        store.close()
    assert _main_branch(folder) == revs["base"]


def test_a_schema_21_store_from_before_the_index_stays_readable(
    lab: dict[str, object],
) -> None:
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    folder = Path(str(lab["folder"]))
    _legacy_series(folder, "paired-5-1-legacy05", revs["base"], revs["variant"], "2026-05-01")
    store = StudioStore.open(folder)
    try:
        with store.connection:  # a store as written by a client before B2: no index tables
            store.connection.execute("DROP TABLE experiment_arm")
            store.connection.execute("DROP TABLE experiment")
    finally:
        store.close()
    history = _history(lab)  # opening adds the tables again, the legacy scan still finds it
    assert [s["series_id"] for s in history["series"]] == ["paired-5-1-legacy05"]
    store = StudioStore.open(folder)
    try:
        version = store.connection.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        assert version is not None and int(version[0]) == 21
        assert store.connection.execute("SELECT COUNT(*) FROM experiment").fetchone()[0] == 0
    finally:
        store.close()
    assert client.get("/api/experiments/paired-5-1-legacy05", headers=HEADERS).status_code == 404
    assert client.post("/api/experiments/rebuild-index", headers=HEADERS).status_code == 200
    assert _detail(lab, "paired-5-1-legacy05")["legacy"] is True


def test_detail_maturity_depends_on_the_other_series_of_the_deck(lab: dict[str, object]) -> None:
    """Review #1725 P2-2: Holm family and the used-seed register depend on the deck's other
    series; the detail takes the finding from that whole computation, not from this series
    alone."""
    revs = lab["revs"]
    assert isinstance(revs, dict)
    folder = Path(str(lab["folder"]))
    one = _start(lab, _plan(revs, purpose="confirmation", first_seed=200))
    two = _start(
        lab,
        _plan(
            revs,
            purpose="confirmation",
            first_seed=300,
            variants=[{"revision_id": revs["variant2"]}],
        ),
    )
    # a legacy series (scanned, not indexed) that played seed 300: confirmation two is not fresh
    path = folder / "games" / "paired-6-1-legacy06.paired.json"
    path.write_text(
        json.dumps(
            {
                "schema": SCHEMA_PAIRED_JOB,
                "series_id": "paired-6-1-legacy06",
                "status": "completed",
                "base_ref": revs["base"],
                "variant_ref": revs["variant"],
                "budget_pairs": 4,
                "created_at": "2026-06-01",
                "result": {
                    "pairs_completed": 4,
                    "pairs_played": 4,
                    "difference_pp": 25.0,
                    "seeds": [300],
                },
            }
        ),
        encoding="utf-8",
    )
    history = _history(lab)
    assert len(history["series"]) == 3
    befunde = history["reifegrad"]["befunde"]
    for started in (one, two):
        detail = _detail(lab, started["experiment_id"])
        assert detail["reifegrad"] == befunde[started["series_id"]]
    # the other series matter: a Holm family of two, and the legacy seed makes two not fresh

    def fresh(sid: str) -> object:
        return next(
            c["erfuellt"]
            for c in befunde[sid]["bedingungen"]
            if str(c["name"]).startswith("frische Seeds")
        )

    assert any("Holm-Familie: 2" in h for h in befunde[one["series_id"]]["hinweise"])
    assert (fresh(one["series_id"]), fresh(two["series_id"])) == (True, False)


def test_plan_state_mismatch_and_missing_show_no_plan(lab: dict[str, object]) -> None:
    """Review #1725 P2-1: a changed or deleted plan file is never shown as intact."""
    revs = lab["revs"]
    assert isinstance(revs, dict)
    folder = Path(str(lab["folder"]))
    started = _start(lab, _plan(revs))
    plan_path = folder / "games" / "experiments" / started["experiment_id"] / "plan.json"
    record = json.loads(plan_path.read_text(encoding="utf-8"))
    record["plan"]["budget_pairs"] = 400
    plan_path.write_text(json.dumps(record), encoding="utf-8")
    changed = _detail(lab, started["experiment_id"])
    assert changed["plan_state"] == "mismatch"
    assert changed["plan"] is None and changed["table"] is None
    assert changed["result"]["status"] == "plan_mismatch"
    # a plan changed and its own SHA recomputed is consistent in itself, but not the
    # plan the index names
    record["plan_sha"] = deck_series.plan_sha(record["plan"], record["resolved"])
    plan_path.write_text(json.dumps(record), encoding="utf-8")
    resealed = _detail(lab, started["experiment_id"])
    assert resealed["plan_state"] == "mismatch" and resealed["plan"] is None
    plan_path.unlink()
    missing = _detail(lab, started["experiment_id"])
    assert missing["plan_state"] == "missing"
    assert missing["plan"] is None and missing["table"] is None


def test_detail_says_why_a_maturity_is_unknown(lab: dict[str, object]) -> None:
    """Review #1725 P3 (c): no finding stays None with a stated reason."""
    revs = lab["revs"]
    assert isinstance(revs, dict)
    folder = Path(str(lab["folder"]))
    store = StudioStore.open(folder)
    try:
        with store.connection:
            for exp_id, deck_id in (("exp-9-1-nofinding", "chulane-b2"), ("exp-9-2-nodeck", "")):
                store.connection.execute(
                    "INSERT INTO experiment(experiment_id, deck_id, question, purpose, "
                    "base_revision_id, created_at) VALUES (?, ?, 'q', 'exploration', "
                    "'gone@1', '2026-07-01')",
                    (exp_id, deck_id),
                )
                store.connection.execute(
                    "INSERT INTO experiment_arm(experiment_id, role, revision_id) "
                    "VALUES (?, 'base', 'gone@1')",
                    (exp_id,),
                )
    finally:
        store.close()
    no_finding = _detail(lab, "exp-9-1-nofinding")
    assert no_finding["reifegrad"] is None
    assert no_finding["reifegrad_hinweis"] == "kein Befund im Deck-Verlauf (unbekannt)"
    no_deck = _detail(lab, "exp-9-2-nodeck")
    assert no_deck["reifegrad"] is None
    assert no_deck["reifegrad_hinweis"] == "Deck unbekannt: kein Reifegrad (unbekannt)"


def test_start_errors_are_named_not_mistaken_for_a_collision(
    lab: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review #1725 P3 (b), (a): a blocked experiments folder and an index conflict from a
    concurrent rebuild are clear 409s; the conflict leaves no orphaned row of this call."""
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    folder = Path(str(lab["folder"]))
    blocker = folder / "games" / "experiments"
    blocker.parent.mkdir(parents=True, exist_ok=True)
    blocker.write_text("kein Ordner", encoding="utf-8")
    res = client.post("/api/experiments", headers=HEADERS, json={"plan": _plan(revs)})
    assert res.status_code == 409
    assert "kann nicht angelegt werden" in res.json()["detail"]
    assert "existiert schon" not in res.json()["detail"]
    assert str(folder) not in res.json()["detail"]  # no local path, no OS error text
    assert "Errno" not in res.json()["detail"]
    blocker.unlink()
    original = experiments._insert

    def rebuild_first(store: StudioStore, row: object, arms: object) -> None:
        monkeypatch.setattr(experiments, "_insert", original)
        experiments.rebuild_index(store, folder)  # the concurrent rebuild indexes the plan
        original(store, row, arms)  # type: ignore[arg-type]

    monkeypatch.setattr(experiments, "_insert", rebuild_first)
    res = client.post("/api/experiments", headers=HEADERS, json={"plan": _plan(revs)})
    assert res.status_code == 409 and "Index-Konflikt" in res.json()["detail"]
    assert _index_rows(folder) == []
    assert not any((folder / "games" / "experiments").iterdir())
    # a conflicting row of someone else (same id, other plan SHA) stays untouched
    foreign_sha = "f" * 64

    def foreign_first(store: StudioStore, row: dict[str, object], arms: object) -> None:
        monkeypatch.setattr(experiments, "_insert", original)
        original(store, {**row, "plan_sha": foreign_sha}, arms)  # type: ignore[arg-type]
        store.connection.commit()
        original(store, row, arms)  # type: ignore[arg-type]

    monkeypatch.setattr(experiments, "_insert", foreign_first)
    res = client.post("/api/experiments", headers=HEADERS, json={"plan": _plan(revs)})
    assert res.status_code == 409 and "Index-Konflikt" in res.json()["detail"]
    rows = _index_rows(folder)
    assert [r["plan_sha"] for r in rows] == [foreign_sha]
    store = StudioStore.open(folder)
    try:
        arms_left = store.connection.execute("SELECT COUNT(*) FROM experiment_arm").fetchone()[0]
    finally:
        store.close()
    assert arms_left == 2


def test_a_failed_start_leaves_no_index_row_and_no_folder(lab: dict[str, object]) -> None:
    """Review #1725 P3 (M11): a start whose series does not start removes its own row."""
    revs = lab["revs"]
    assert isinstance(revs, dict)
    folder = Path(str(lab["folder"]))
    plan = experiments.ExperimentPlan.model_validate(_plan(revs))

    def refuse(settings: dict[str, object]) -> paired_series.PairedSeriesJob:
        raise RuntimeError("Serie startet nicht")

    store = StudioStore.open(folder)
    try:
        with pytest.raises(RuntimeError, match="Serie startet nicht"):
            experiments.start_experiment(store, folder, plan, start_series=refuse)
    finally:
        store.close()
    assert _index_rows(folder) == []
    exp_folder = folder / "games" / "experiments"
    assert not exp_folder.exists() or not any(exp_folder.iterdir())


def test_a_series_named_by_two_experiments_is_credited_to_neither(
    lab: dict[str, object],
) -> None:
    """Review #1725 P2-1: run.json of A names B's series; the detail of A shows A's own entry
    (plan mismatch, not counted) and no maturity, never B's result."""
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    folder = Path(str(lab["folder"]))
    a = _start(lab, _plan(revs))
    b = _start(lab, _plan(revs, variants=[{"revision_id": revs["variant2"]}], first_seed=200))
    run = folder / "games" / "experiments" / a["experiment_id"] / "run.json"
    run.write_text(
        json.dumps({"experiment_id": a["experiment_id"], "series_id": b["series_id"]}),
        encoding="utf-8",
    )
    assert client.post("/api/experiments/rebuild-index", headers=HEADERS).status_code == 200
    detail_a = _detail(lab, a["experiment_id"])
    assert detail_a["result"]["experiment"]["experiment_id"] == a["experiment_id"]
    assert detail_a["result"]["counts_as_result"] is False
    assert detail_a["result"]["status"] == "plan_mismatch"
    assert detail_a["result"]["pairs_completed"] is None
    assert detail_a["reifegrad"] is None
    assert "mehrfach verknüpft" in str(detail_a["reifegrad_hinweis"])
    detail_b = _detail(lab, b["experiment_id"])
    assert detail_b["result"]["experiment"]["experiment_id"] == b["experiment_id"]
    assert detail_b["reifegrad"] is None  # the same series id: not credited to B either


def test_rebuild_holds_the_write_lock_while_it_reads_the_files(lab: dict[str, object]) -> None:
    """Review #1725 P2-2: a failed start in another process cleans up while a rebuild reads
    the files; the rebuild must not write the removed row back (a row without a plan file
    would refuse every later rebuild)."""
    import threading

    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    folder = Path(str(lab["folder"]))
    started = _start(lab, _plan(revs))
    own = folder / "games" / "experiments" / started["experiment_id"]
    read_done = threading.Event()
    original = experiments._legacy_row
    games = folder / "games"
    _legacy_series(games.parent, "paired-7-1-legacy07", revs["base"], revs["variant"], "2026")
    errors: list[BaseException] = []

    def slow_legacy(store: StudioStore, raw: object) -> object:
        read_done.set()  # the plan files are read; the other process cleans up now
        time.sleep(0.5)
        return original(store, raw)  # type: ignore[arg-type]

    def rebuild() -> None:
        store = StudioStore.open(folder)
        try:
            experiments._legacy_row = slow_legacy  # type: ignore[assignment]
            experiments.rebuild_index(store, folder)
        except BaseException as error:
            errors.append(error)
        finally:
            experiments._legacy_row = original
            store.close()

    other = StudioStore.open(folder)  # the failing start of the other process
    try:
        worker = threading.Thread(target=rebuild)
        worker.start()
        assert read_done.wait(10)
        with other.connection:
            other.connection.execute(
                "DELETE FROM experiment_arm WHERE experiment_id = ?", (started["experiment_id"],)
            )
            other.connection.execute(
                "DELETE FROM experiment WHERE experiment_id = ?", (started["experiment_id"],)
            )
        shutil.rmtree(own)
        worker.join(15)
    finally:
        other.close()
    assert not errors, errors
    assert started["experiment_id"] not in {r["experiment_id"] for r in _index_rows(folder)}
    assert client.post("/api/experiments/rebuild-index", headers=HEADERS).status_code == 200


# -- B2-Rest (#1658): 422 variant validations and Owner 5a withdraw_experiment ---------------


def test_experiment_plan_and_resolve_plan_validate_all_variants(lab: dict[str, object]) -> None:
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    # Duplicate revision_ids in variants -> 422
    dup = _plan(
        revs,
        variants=[{"revision_id": revs["variant"]}, {"revision_id": revs["variant"]}],
    )
    res_dup = client.post("/api/experiments", headers=HEADERS, json={"plan": dup})
    assert res_dup.status_code == 422
    assert "doppelt" in res_dup.text
    # Variant equal to base -> 422
    same = _plan(revs, variants=[{"revision_id": revs["base"]}])
    res_same = client.post("/api/experiments", headers=HEADERS, json={"plan": same})
    assert res_same.status_code == 422
    assert "zwei verschiedene Stände" in res_same.text
    # Second variant unknown -> 404 (checked before len(variants) != 1)
    unknown_second = _plan(
        revs,
        variants=[{"revision_id": revs["variant"]}, {"revision_id": "rev-does-not-exist"}],
    )
    res_unk = client.post("/api/experiments", headers=HEADERS, json={"plan": unknown_second})
    assert res_unk.status_code == 404
    # Second variant belongs to foreign deck -> 422
    foreign_second = _plan(
        revs,
        variants=[{"revision_id": revs["variant"]}, {"revision_id": revs["other"]}],
    )
    res_foreign = client.post("/api/experiments", headers=HEADERS, json={"plan": foreign_second})
    assert res_foreign.status_code == 422
    assert "kein Stand des Decks" in res_foreign.text
    # Two valid distinct variants of the same deck -> 422 (multi-variant not runnable yet)
    two_valid = _plan(
        revs,
        variants=[{"revision_id": revs["variant"]}, {"revision_id": revs["variant2"]}],
    )
    res_multi = client.post("/api/experiments", headers=HEADERS, json={"plan": two_valid})
    assert res_multi.status_code == 422
    assert "mehrere Varianten" in res_multi.text


def _make_unplayed_experiment(
    lab: dict[str, object],
    *,
    purpose: str = "exploration",
    first_seed: int = 500,
    variant_key: str = "variant",
    opponents: list[str] | None = None,
) -> dict[str, object]:
    """Create an indexed experiment with an intact plan.json and a pending (0 games) .paired.json."""
    revs = lab["revs"]
    assert isinstance(revs, dict)
    folder = Path(str(lab["folder"]))
    plan_dict = _plan(
        revs,
        purpose=purpose,
        first_seed=first_seed,
        variants=[{"revision_id": revs[variant_key]}],
    )
    if opponents is not None:
        plan_dict["table"]["opponents"] = opponents
    plan = experiments.ExperimentPlan.model_validate(plan_dict)

    def cancelled_unplayed_starter(settings: dict[str, object]) -> paired_series.PairedSeriesJob:
        series_id = f"paired-unplayed-{first_seed}-{variant_key}"
        series_path = folder / "games" / f"{series_id}.paired.json"
        series_path.parent.mkdir(parents=True, exist_ok=True)
        series_path.write_text(
            json.dumps(
                {
                    "schema": SCHEMA_PAIRED_JOB,
                    "series_id": series_id,
                    "status": "cancelled",
                    "base_ref": settings["base_revision_id"],
                    "variant_ref": settings["variant_revision_id"],
                    "budget_pairs": settings["budget_pairs"],
                    "pairs_attempted": 0,
                    "games_played": 0,
                    "result": None,
                    "created_at": "2026-11-24T00:00:00Z",
                    "experiment": settings["experiment"],
                }
            ),
            encoding="utf-8",
        )

        class _StubJob:
            def __init__(self, sid: str) -> None:
                self.series_id = sid
                self.bridge_jar_sha256 = None

        return _StubJob(series_id)  # type: ignore[return-value]

    store = StudioStore.open(folder)
    try:
        return experiments.start_experiment(
            store, folder, plan, start_series=cancelled_unplayed_starter
        )
    finally:
        store.close()


def test_store_adds_experiment_status_column_without_schema_bump(tmp_path: Path) -> None:
    """An existing schema-21 store without experiment.status gets the column on open."""
    from commander_lab.studio.store import SCHEMA_VERSION

    assert SCHEMA_VERSION == 21
    store = StudioStore.open(tmp_path)
    try:
        # Simulate a pre-Owner-5a schema-21 table without ``status``
        with store.connection:
            store.connection.execute("DROP TABLE experiment_arm")
            store.connection.execute("DROP TABLE experiment")
            store.connection.execute(
                "CREATE TABLE experiment ("
                "experiment_id TEXT PRIMARY KEY, deck_id TEXT NOT NULL, question TEXT NOT NULL, "
                "question_kind TEXT, purpose TEXT NOT NULL, base_revision_id TEXT NOT NULL, "
                "plan_sha TEXT, table_hash TEXT, first_seed INTEGER, last_seed INTEGER, "
                "series_id TEXT, engine_pin TEXT, bridge_jar_sha256 TEXT, bridge_state TEXT, "
                "pilot_fingerprint TEXT, decision TEXT NOT NULL DEFAULT 'open' "
                "CHECK (decision IN ('open', 'adopted', 'rejected')), "
                "decision_at TEXT, decision_note TEXT, decision_tested INTEGER, "
                "decision_previous_revision_id TEXT, created_at TEXT NOT NULL)"
            )
            store.connection.execute(
                "INSERT INTO experiment(experiment_id, deck_id, question, purpose, "
                "base_revision_id, created_at) VALUES ('exp-old-1', 'd', 'q', 'exploration', "
                "'r1', '2026-11-20T00:00:00Z')"
            )
    finally:
        store.close()

    reopened = StudioStore.open(tmp_path)
    try:
        cols = {
            str(r["name"]) for r in reopened.connection.execute("PRAGMA table_info(experiment)")
        }
        assert "status" in cols
        row = reopened.connection.execute(
            "SELECT status FROM experiment WHERE experiment_id = 'exp-old-1'"
        ).fetchone()
        assert row is not None and row["status"] == "active"
        ver = reopened.connection.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        assert ver is not None and int(ver["value"]) == 21
    finally:
        reopened.close()


def test_withdraw_unplayed_exploration_releases_seeds_and_survives_rebuild(
    lab: dict[str, object],
) -> None:
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    folder = Path(str(lab["folder"]))

    created = _make_unplayed_experiment(lab, purpose="exploration", first_seed=600)
    exp_id = str(created["experiment_id"])

    # Before withdrawal: withdrawable is True, and confirmation on same seeds is blocked
    detail = _detail(lab, exp_id)
    assert detail["status"] == "active"
    assert detail["status_text"] == "aktiv"
    assert detail["withdrawable"] is True
    assert detail["withdraw_blocked_reasons"] == []
    assert detail["experiment"]["status"] == "active"
    assert detail["experiment"]["withdrawable"] is True

    overlap = client.post(
        "/api/experiments",
        headers=HEADERS,
        json={"plan": _plan(revs, purpose="confirmation", first_seed=600)},
    )
    assert overlap.status_code == 422 and "überschneidet" in overlap.json()["detail"]

    # Withdraw via POST /api/experiments/{id}/withdraw
    res = client.post(
        f"/api/experiments/{exp_id}/withdraw",
        headers=HEADERS,
        json={"note": "falscher Gegner-Tisch"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "withdrawn"
    assert body["experiment_id"] == exp_id
    assert body["note"] == "falscher Gegner-Tisch"

    withdraw_file = folder / "games" / "experiments" / exp_id / "withdraw.json"
    assert withdraw_file.is_file()
    w_data = json.loads(withdraw_file.read_text(encoding="utf-8"))
    assert w_data["schema"] == experiments.SCHEMA_WITHDRAW
    assert w_data["plan_sha"] == created["plan_sha"]

    # Still visible in detail and deck series list, no longer withdrawable, cannot decide
    after = _detail(lab, exp_id)
    assert after["status"] == "withdrawn"
    assert after["status_text"] == "zurückgezogen"
    assert after["withdrawable"] is False
    assert after["withdraw_blocked_reasons"]
    history = _history(lab)
    listed = [s for s in history["series"] if s["series_id"] == created["series_id"]]
    assert len(listed) == 1
    assert listed[0]["experiment"]["status"] == "withdrawn"

    # Second withdraw -> 409; decide on withdrawn -> 409
    assert client.post(f"/api/experiments/{exp_id}/withdraw", headers=HEADERS).status_code == 409
    assert (
        client.post(
            f"/api/experiments/{exp_id}/decision",
            headers=HEADERS,
            json={"decision": "rejected"},
        ).status_code
        == 409
    )

    # Rebuild index restores status='withdrawn' from withdraw.json
    assert client.post("/api/experiments/rebuild-index", headers=HEADERS).status_code == 200
    rebuilt = _detail(lab, exp_id)
    assert rebuilt["status"] == "withdrawn"
    assert rebuilt["withdrawable"] is False

    # Seeds are now released: confirmation on seed 600 succeeds!
    conf = _start(lab, _plan(revs, purpose="confirmation", first_seed=600))
    assert conf["experiment_id"]

    # Unknown -> 404, invalid ID -> 422
    assert (
        client.post("/api/experiments/exp-1-1-unknown/withdraw", headers=HEADERS).status_code == 404
    )
    assert client.post("/api/experiments/not-valid/withdraw", headers=HEADERS).status_code == 422


def test_withdraw_refuses_played_running_corrupt_decided_legacy_and_family_activity(
    lab: dict[str, object],
) -> None:
    import os

    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    folder = Path(str(lab["folder"]))

    # 1. Played experiment (has result) -> refused
    played = _start(lab, _plan(revs, first_seed=700))
    assert _detail(lab, played["experiment_id"])["withdrawable"] is False
    assert (
        client.post(
            f"/api/experiments/{played['experiment_id']}/withdraw", headers=HEADERS
        ).status_code
        == 409
    )

    # 2. Legacy series -> refused (422 for non-exp id in validate_experiment_id, detail says False)
    _legacy_series(folder, "paired-9-1-leg9", revs["base"], revs["variant"], "2026-01-01")
    assert client.post("/api/experiments/rebuild-index", headers=HEADERS).status_code == 200
    assert _detail(lab, "paired-9-1-leg9")["withdrawable"] is False

    # 3. Decided unplayed experiment -> refused
    dec = _make_unplayed_experiment(lab, purpose="exploration", first_seed=710)
    assert (
        client.post(
            f"/api/experiments/{dec['experiment_id']}/decision",
            headers=HEADERS,
            json={"decision": "rejected"},
        ).status_code
        == 200
    )
    assert _detail(lab, str(dec["experiment_id"]))["withdrawable"] is False
    assert (
        client.post(
            f"/api/experiments/{dec['experiment_id']}/withdraw", headers=HEADERS
        ).status_code
        == 409
    )

    # 4. Active running.lock -> refused
    locked = _make_unplayed_experiment(lab, purpose="exploration", first_seed=720)
    lock_path = folder / "games" / "paired_decks" / str(locked["series_id"]) / "running.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    assert _detail(lab, str(locked["experiment_id"]))["withdrawable"] is False
    assert (
        client.post(
            f"/api/experiments/{locked['experiment_id']}/withdraw", headers=HEADERS
        ).status_code
        == 409
    )

    # 5. Non-empty progress.jsonl -> refused
    prog = _make_unplayed_experiment(lab, purpose="exploration", first_seed=730)
    prog_path = folder / "games" / "paired_decks" / str(prog["series_id"]) / "progress.jsonl"
    prog_path.parent.mkdir(parents=True, exist_ok=True)
    prog_path.write_text('{"arm":"base"}\n', encoding="utf-8")
    assert _detail(lab, str(prog["experiment_id"]))["withdrawable"] is False
    assert (
        client.post(
            f"/api/experiments/{prog['experiment_id']}/withdraw", headers=HEADERS
        ).status_code
        == 409
    )

    # 6. Non-empty journal.jsonl -> refused
    jrn = _make_unplayed_experiment(lab, purpose="exploration", first_seed=740)
    jrn_path = folder / "games" / "series" / str(jrn["series_id"]) / "journal.jsonl"
    jrn_path.parent.mkdir(parents=True, exist_ok=True)
    jrn_path.write_text('{"game_id":"g1"}\n', encoding="utf-8")
    assert _detail(lab, str(jrn["experiment_id"]))["withdrawable"] is False
    assert (
        client.post(
            f"/api/experiments/{jrn['experiment_id']}/withdraw", headers=HEADERS
        ).status_code
        == 409
    )

    # 7. Corrupt .paired.json -> refused (fail-closed)
    corrupt = _make_unplayed_experiment(lab, purpose="exploration", first_seed=750)
    (folder / "games" / f"{corrupt['series_id']}.paired.json").write_text(
        "{not valid json", encoding="utf-8"
    )
    assert _detail(lab, str(corrupt["experiment_id"]))["withdrawable"] is False
    assert (
        client.post(
            f"/api/experiments/{corrupt['experiment_id']}/withdraw", headers=HEADERS
        ).status_code
        == 409
    )

    # 8. Tampered plan.json (_plan_state != "intact") -> refused
    tampered = _make_unplayed_experiment(lab, purpose="exploration", first_seed=760)
    plan_file = folder / "games" / "experiments" / str(tampered["experiment_id"]) / "plan.json"
    plan_file.write_text('{"schema": "broken"}', encoding="utf-8")
    assert _detail(lab, str(tampered["experiment_id"]))["withdrawable"] is False
    assert (
        client.post(
            f"/api/experiments/{tampered['experiment_id']}/withdraw", headers=HEADERS
        ).status_code
        == 409
    )

    # 9. Confirmation without table_hash -> refused (fail-closed)
    no_th = _make_unplayed_experiment(lab, purpose="confirmation", first_seed=800)
    store = StudioStore.open(folder)
    try:
        with store.connection:
            store.connection.execute(
                "UPDATE experiment SET table_hash = NULL WHERE experiment_id = ?",
                (no_th["experiment_id"],),
            )
    finally:
        store.close()
    assert _detail(lab, str(no_th["experiment_id"]))["withdrawable"] is False
    res_no_th = client.post(f"/api/experiments/{no_th['experiment_id']}/withdraw", headers=HEADERS)
    assert res_no_th.status_code == 409 and "table_hash" in res_no_th.json()["detail"]

    # 10. Confirmation Holm family check: sibling has looks_used > 0 -> refused!
    conf_a = _make_unplayed_experiment(
        lab, purpose="confirmation", first_seed=810, variant_key="variant"
    )
    conf_b = _make_unplayed_experiment(
        lab, purpose="confirmation", first_seed=820, variant_key="variant2"
    )
    # Both unplayed: conf_a is withdrawable right now
    assert _detail(lab, str(conf_a["experiment_id"]))["withdrawable"] is True
    # Now sibling conf_b gets a look (looks_used = 1 in its .paired.json result)
    sib_path = folder / "games" / f"{conf_b['series_id']}.paired.json"
    sib_raw = json.loads(sib_path.read_text(encoding="utf-8"))
    sib_raw["result"] = {"looks_used": 1, "pairs_completed": 2}
    sib_path.write_text(json.dumps(sib_raw), encoding="utf-8")
    detail_a = _detail(lab, str(conf_a["experiment_id"]))
    assert detail_a["withdrawable"] is False
    assert any("Holm-Familienmitglied" in r for r in detail_a["withdraw_blocked_reasons"])
    res_fam = client.post(f"/api/experiments/{conf_a['experiment_id']}/withdraw", headers=HEADERS)
    assert res_fam.status_code == 409 and "Holm-Familienmitglied" in res_fam.json()["detail"]


def test_withdraw_blocks_resume_pending_live_job_malformed_looks_and_start_race(
    lab: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """PR #1788 review regressions (P1-1, P1-2, P2-1, P3-1)."""
    revs = lab["revs"]
    assert isinstance(revs, dict)
    client = lab["client"]
    assert isinstance(client, TestClient)
    folder = Path(str(lab["folder"]))

    # P1-1: withdrawn plan cannot be resumed (_is_disk_resumable == False, resume_series raises)
    w_exp = _make_unplayed_experiment(lab, purpose="exploration", first_seed=900)
    w_sid = str(w_exp["series_id"])
    w_path = folder / "games" / f"{w_sid}.paired.json"
    # Populate fields _is_disk_resumable requires so only withdraw.json makes it False
    deck_dir = folder / "games" / "paired_decks" / w_sid
    deck_dir.mkdir(parents=True, exist_ok=True)
    (deck_dir / "base-a.json").write_text("{}", encoding="utf-8")
    (deck_dir / "variant-b.json").write_text("{}", encoding="utf-8")
    raw = json.loads(w_path.read_text(encoding="utf-8"))
    raw.update(
        {
            "opponent_deck_ids": ["opp1", "opp2", "opp3"],
            "seed_plan": {"first_seed": 900, "seeds_planned": 4},
            "tested_seats": [0, 1, 2, 3],
            "threshold_pp": 5.0,
        }
    )
    w_path.write_text(json.dumps(raw), encoding="utf-8")
    assert paired_series.PairedSeriesManager._is_disk_resumable(raw, folder) is True

    assert (
        client.post(
            f"/api/experiments/{w_exp['experiment_id']}/withdraw", headers=HEADERS
        ).status_code
        == 200
    )
    assert paired_series.PairedSeriesManager._is_disk_resumable(raw, folder) is False
    with pytest.raises(ValueError, match="zurückgezogen"):
        paired_series.paired_series_manager.resume_series(folder, w_sid)
    # Corrupt withdraw.json still blocks fail-closed
    (folder / "games" / "experiments" / str(w_exp["experiment_id"]) / "withdraw.json").write_text(
        "{corrupt", encoding="utf-8"
    )
    assert paired_series.PairedSeriesManager._is_disk_resumable(raw, folder) is False
    # Malformed experiment payload blocks fail-closed
    assert (
        paired_series.PairedSeriesManager._is_disk_resumable({**raw, "experiment": "bad"}, folder)
        is False
    )

    # P1-2a: status == "pending" in .paired.json blocks withdrawal
    pend = _make_unplayed_experiment(lab, purpose="exploration", first_seed=910)
    pend_path = folder / "games" / f"{pend['series_id']}.paired.json"
    pend_raw = json.loads(pend_path.read_text(encoding="utf-8"))
    pend_raw["status"] = "pending"
    pend_path.write_text(json.dumps(pend_raw), encoding="utf-8")
    assert _detail(lab, str(pend["experiment_id"]))["withdrawable"] is False
    assert (
        client.post(
            f"/api/experiments/{pend['experiment_id']}/withdraw", headers=HEADERS
        ).status_code
        == 409
    )

    # P1-2b: live in-process job in paired_series_manager blocks withdrawal
    live_exp = _make_unplayed_experiment(lab, purpose="exploration", first_seed=920)
    live_sid = str(live_exp["series_id"])

    class _LiveStub:
        status = "pending"

    monkeypatch.setattr(
        paired_series.paired_series_manager,
        "get_job",
        lambda sid: _LiveStub() if sid == live_sid else None,
    )
    assert _detail(lab, str(live_exp["experiment_id"]))["withdrawable"] is False
    assert (
        client.post(
            f"/api/experiments/{live_exp['experiment_id']}/withdraw", headers=HEADERS
        ).status_code
        == 409
    )
    monkeypatch.undo()

    # P1-2c: race window in start_experiment (withdrawn before post-start UPDATE) cancels job
    cancelled_jobs: list[str] = []

    class _CancelJob:
        def __init__(self, sid: str) -> None:
            self.series_id = sid
            self.bridge_jar_sha256 = None

        def cancel(self) -> None:
            cancelled_jobs.append(self.series_id)

    plan_race = experiments.ExperimentPlan.model_validate(_plan(revs, first_seed=930))

    def racing_starter(settings: dict[str, object]) -> paired_series.PairedSeriesJob:
        exp_meta = settings["experiment"]
        assert isinstance(exp_meta, dict)
        eid = str(exp_meta["experiment_id"])
        # Another request withdraws the freshly inserted row before start_series returns
        other_store = StudioStore.open(folder)
        try:
            experiments.withdraw_experiment(other_store, folder, eid, note="race")
        finally:
            other_store.close()
        return _CancelJob("paired-race-930")  # type: ignore[return-value]

    store = StudioStore.open(folder)
    try:
        with pytest.raises(experiments.WithdrawRefused, match="während des Starts"):
            experiments.start_experiment(store, folder, plan_race, start_series=racing_starter)
    finally:
        store.close()
    assert cancelled_jobs == ["paired-race-930"]

    # P2-1: malformed looks_used in .paired.json (string or bool) blocks withdrawal fail-closed
    for bad_looks, seed in (("corrupt", 940), (True, 950)):
        mal = _make_unplayed_experiment(lab, purpose="exploration", first_seed=seed)
        mal_path = folder / "games" / f"{mal['series_id']}.paired.json"
        mal_raw = json.loads(mal_path.read_text(encoding="utf-8"))
        mal_raw["looks_used"] = bad_looks
        mal_path.write_text(json.dumps(mal_raw), encoding="utf-8")
        assert _detail(lab, str(mal["experiment_id"]))["withdrawable"] is False
        assert (
            client.post(
                f"/api/experiments/{mal['experiment_id']}/withdraw", headers=HEADERS
            ).status_code
            == 409
        )

    # P3-1: rebuild_index requires withdraw.json status == "withdrawn"
    bad_w = _make_unplayed_experiment(lab, purpose="exploration", first_seed=960)
    bad_w_file = folder / "games" / "experiments" / str(bad_w["experiment_id"]) / "withdraw.json"
    bad_w_file.write_text(
        json.dumps(
            {
                "schema": experiments.SCHEMA_WITHDRAW,
                "experiment_id": bad_w["experiment_id"],
                "plan_sha": bad_w["plan_sha"],
                "status": "active",
            }
        ),
        encoding="utf-8",
    )
    assert client.post("/api/experiments/rebuild-index", headers=HEADERS).status_code == 200
    assert _detail(lab, str(bad_w["experiment_id"]))["status"] == "active"
