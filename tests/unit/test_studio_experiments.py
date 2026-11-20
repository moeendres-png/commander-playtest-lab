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


def test_table_spec_checks_seats_opponents_and_modes() -> None:
    opp = _precons()
    spec = TableSpec(seats=4, opponents=opp)
    assert spec.tested_seats() == [0, 1, 2, 3]
    assert TableSpec(seats=4, opponents=opp, seat_policy="fixed").tested_seats() == [0]
    with pytest.raises(ValidationError, match="locked"):
        TableSpec(seats=5, opponents=[*opp, "kaervek/current"])
    with pytest.raises(ValidationError, match="braucht 3 Gegner"):
        TableSpec(seats=4, opponents=opp[:2])
    with pytest.raises(ValidationError, match="doppelt"):
        TableSpec(seats=3, opponents=[opp[0], opp[0]])
    with pytest.raises(ValidationError):
        TableSpec.model_validate({"seats": 4, "opponents": opp, "seed_step": 4})
    for mode in ("rotation", "draw"):
        modelled = TableSpec(seats=4, opponents=opp, opponent_mode=mode)
        with pytest.raises(ValueError, match="noch nicht umgesetzt"):
            modelled.ensure_runnable()


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
                "seats": [
                    {
                        "seat": seat,
                        "deck_id": deck_id,
                        "win_credit": 1.0 if seat in winners else 0.0,
                        "first_hand": [],
                        "seen_by_turn_3": [],
                    }
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
    assert _history(lab) == before
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
