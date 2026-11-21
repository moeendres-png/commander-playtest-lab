"""Seat-count contract of the real-deck gate (4/5/6 seats); no engine, no Java.

Runners, batches and tapes are fakes: these tests prove the driver's seat plan, its fail-closed
seat checks and its report, never native card behaviour.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from scripts import run_real_deck_gate as gate

from commander_lab.engine.rules.full_game_pilot.common import XMAGE_FULL_GAME_COMMAND_ENV
from tests.unit.test_full_game_semantic_tape_gate import _tape
from tests.unit.test_xmage_full_game import _result

LEGACY_SINGLE_KEYS = frozenset(
    {
        "gate",
        "evidence_class",
        "engine_version",
        "xmage_commit",
        "player_count",
        "seed",
        "scenario_id",
        "candidate_id",
        "opponent_deck_ids",
        "decision_count",
        "terminal",
        "winner_seats",
        "observed_decision_classes",
        "semantic_transcript_sha256",
        "raw_result_sha256",
        "consumed_gameplay_evidence",
        "holdout_consumed",
        "fallback_used",
        "hidden_information_actor_scoped",
        "rules_authority",
        "decision_authority",
        "claim_basis",
    }
)
LEGACY_REPLAY_KEYS = frozenset(
    {
        "gate",
        "seed",
        "semantic_replay_match",
        "usability_gate_passed",
        "natural_terminal_runs_verified",
        "semantic_replay_scope",
        "full_natural_terminal_replay_validated",
        "semantic_tape",
        "twin_transcript_hash_match",
        "raw_result_match",
        "bit_exact_replay_validated",
        "runs",
    }
)
LEGACY_BATCH_KEYS = frozenset(
    {
        "gate",
        "usability_gate_passed",
        "evidence_scope",
        "total_cases",
        "completed_cases",
        "failed_cases",
        "resumed_cases",
        "records",
    }
)
REFERENCE_SEAT_IDS = ["rogshai/seat-1", "kaervek/seat-2", "rogshai/seat-3", "kaervek/seat-4"]
# Pinned on purpose: a new precon or a changed catalog that shifts the pod must be seen.
SEEDED_EXTRA_STEMS = ("2022_heads_i_win__tails_you_lose", "2023_call_for_backup")


def _seat_result(
    scen: Any,
    /,
    *,
    outcome_seats: list[int] | None = None,
    actor_seats: list[int] | None = None,
    **updates: Any,
) -> Any:
    n = scen.player_count
    base = _result(scen)
    payload = dict(base.result_payload)
    payload["outcomes"] = [
        {"seat": seat, "won": seat == 0}
        for seat in (range(n) if outcome_seats is None else outcome_seats)
    ]
    payload["transcript"] = [
        {"kind": "decision_accepted", "decision_class": "priority", "actor_seat": seat}
        for seat in (range(n) if actor_seats is None else actor_seats)
    ]
    return base.model_copy(update={"result_payload": payload, **updates})


def _install_runner(monkeypatch: pytest.MonkeyPatch, make_result: Any = _seat_result) -> list[Any]:
    constructed: list[Any] = []

    class FakeRunner:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            constructed.append(kwargs.get("command"))
            self.command = kwargs.get("command")

        def run(self, *, scenario: Any, **kwargs: Any) -> Any:
            return make_result(scenario)

    monkeypatch.setattr(gate, "XmageFullGameRunner", FakeRunner)
    monkeypatch.delenv(XMAGE_FULL_GAME_COMMAND_ENV, raising=False)
    return constructed


def _forbid_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("engine constructed although the configuration is invalid")

    monkeypatch.setattr(gate, "XmageFullGameRunner", forbidden)
    monkeypatch.setattr(gate, "XmageFullGameBatchRunner", forbidden)
    monkeypatch.setattr(gate, "run_semantic_tape_replay", forbidden)


def _single_args(tmp_path: Path, **extra: Any) -> argparse.Namespace:
    return argparse.Namespace(root=str(gate.ROOT), seed=7, out=tmp_path / "single.json", **extra)


def _fake_jar(tmp_path: Path) -> Path:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"synthetic jar bytes")
    return jar


# --- default 4 stays what it was --------------------------------------------------------


def test_default_four_seat_setup_is_unchanged() -> None:
    scenario, decks, pilots = gate.build_gate_setup(gate.ROOT, 123)
    assert gate.DEFAULT_PLAYER_COUNT == 4
    assert gate.SEAT_DECKS == ("rogshai", "kaervek", "rogshai", "kaervek")
    assert [deck.deck_id for deck in decks] == REFERENCE_SEAT_IDS
    assert [pilot.seat for pilot in pilots] == [1, 2, 3, 4]
    assert scenario.player_count == 4
    assert scenario.scenario_id == "real-deck-technical-gate-4p-123"
    assert scenario.opponent_deck_ids == tuple(REFERENCE_SEAT_IDS[1:])
    assert gate.build_gate_setup(gate.ROOT, 123, 4) == (scenario, decks, pilots)


def test_default_single_output_keeps_legacy_keys_and_adds_no_seat_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[int] = []
    constructed = _install_runner(monkeypatch)

    class Recording:
        def __init__(self) -> None:
            constructed.append("legacy-call")

        def run(self, *, scenario: Any, **kwargs: Any) -> Any:
            seen.append(scenario.player_count)
            return _result(scenario)

    monkeypatch.setattr(gate, "XmageFullGameRunner", Recording)
    assert gate.cmd_single(_single_args(tmp_path)) == 0
    payload = json.loads((tmp_path / "single.json").read_text())
    assert set(payload) == LEGACY_SINGLE_KEYS
    assert seen == [4]
    # the legacy path builds the runner exactly as before: no argument at all
    assert constructed == ["legacy-call"]


def test_default_replay_keeps_legacy_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_runner(monkeypatch, lambda scenario: _result(scenario))
    monkeypatch.setattr(gate, "run_semantic_tape_replay", lambda *a, **kw: _tape())
    assert gate.cmd_replay(argparse.Namespace(root=gate.ROOT, seed=7, out=tmp_path / "r.json")) == 0
    assert set(json.loads((tmp_path / "r.json").read_text())) == LEGACY_REPLAY_KEYS


def test_default_batch_prints_legacy_keys_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install_runner(monkeypatch)
    _install_batch(monkeypatch, lambda case: _result(case.scenario))
    args = argparse.Namespace(root=gate.ROOT, base_seed=5, count=2, out_dir=tmp_path)
    assert gate.cmd_batch(args) == 0
    summary = json.loads(capsys.readouterr().out)
    assert set(summary) == LEGACY_BATCH_KEYS
    assert [r["case_id"] for r in summary["records"]] == [
        "real-deck-technical-gate-4p-5",
        "real-deck-technical-gate-4p-6",
    ]


# --- 5 and 6 seats: plan without gaps, deterministic decks -------------------------------


@pytest.mark.parametrize("count", [5, 6])
def test_five_and_six_seat_plans_have_no_seat_gaps(count: int) -> None:
    scenario, decks, pilots = gate.build_gate_setup(gate.ROOT, 11, count)
    assert [pilot.seat for pilot in pilots] == list(range(1, count + 1))
    assert scenario.player_count == count
    assert scenario.scenario_id == f"real-deck-technical-gate-{count}p-11"
    assert len(decks) == count
    assert len(scenario.opponent_deck_ids) == count - 1
    assert [deck.deck_id for deck in decks[:4]] == REFERENCE_SEAT_IDS
    assert len({deck.deck_id for deck in decks}) == count
    assert [pilot.deck_id for pilot in pilots] == [deck.deck_id for deck in decks]
    for stem, deck in zip(SEEDED_EXTRA_STEMS, decks[4:], strict=False):
        assert deck.deck_id == f"precon-{stem}/seat-{decks.index(deck) + 1}"


def test_seeded_extra_decks_are_pinned_independent_of_game_seed() -> None:
    assert gate.select_extra_decks(gate.ROOT, 1) == SEEDED_EXTRA_STEMS[:1]
    assert gate.select_extra_decks(gate.ROOT, 2) == SEEDED_EXTRA_STEMS
    assert gate.select_extra_decks(gate.ROOT, 2) == gate.select_extra_decks(gate.ROOT, 2)
    first = gate.build_gate_setup(gate.ROOT, 1, 6)[1]
    other = gate.build_gate_setup(gate.ROOT, 9999, 6)[1]
    assert [d.deck_id for d in first] == [d.deck_id for d in other]
    assert [d.deck_hash for d in first] == [d.deck_hash for d in other]


def test_explicit_extra_decks_replace_the_seeded_choice() -> None:
    _, decks, _ = gate.build_gate_setup(gate.ROOT, 3, 5, ("2023_veloci_ramp_tor",))
    assert decks[4].deck_id == "precon-2023_veloci_ramp_tor/seat-5"
    assert decks[4].source_path is not None
    assert Path(decks[4].source_path).name == "2023_veloci_ramp_tor.json"


@pytest.mark.parametrize(
    ("count", "stems", "message"),
    [
        (5, ("2023_veloci_ramp_tor", "2023_blood_rites"), "exactly 1"),
        (6, ("2023_veloci_ramp_tor",), "exactly 2"),
        (4, ("2023_veloci_ramp_tor",), "exactly 0"),
        (6, ("2023_blood_rites", "2023_blood_rites"), "repeat"),
        (5, ("no_such_precon",), "unknown precon"),
        (5, ("../rogshai_current",), "invalid precon file stem"),
    ],
)
def test_bad_explicit_extra_decks_fail_closed(
    count: int, stems: tuple[str, ...], message: str
) -> None:
    with pytest.raises(gate.GateConfigError, match=message):
        gate.build_gate_setup(gate.ROOT, 3, count, stems)


@pytest.mark.parametrize("count", [3, 7, 0, -1, True, "5", 5.0])
def test_unsupported_player_count_is_a_configuration_error(count: Any) -> None:
    with pytest.raises(gate.GateConfigError, match="player count must be 4, 5 or 6"):
        gate.build_gate_setup(gate.ROOT, 3, count)


def _plan(count: int = 5) -> tuple[Any, Any, Any]:
    return gate.build_gate_setup(gate.ROOT, 3, count)


def test_valid_seat_plan_passes_the_validator() -> None:
    scenario, decks, pilots = _plan()
    gate.validate_seat_plan(scenario, decks, pilots, 5)


@pytest.mark.parametrize(
    ("seats", "message"),
    [
        ((1, 2, 3, 4, 6), "seat gap"),  # gap before the last seat
        ((0, 1, 2, 3, 4), "seat gap"),  # engine numbering used for pilot seats
        ((1, 2, 4, 3, 5), "seat gap"),  # order matters
        ((1, 2, 3, 4), "seat gap"),  # a seat is missing
    ],
)
def test_seat_gap_is_rejected_by_the_plan_validator(seats: tuple[int, ...], message: str) -> None:
    scenario, decks, pilots = _plan()
    gapped = tuple(
        pilot.model_copy(update={"seat": seat}) for pilot, seat in zip(pilots, seats, strict=False)
    )
    with pytest.raises(gate.GateConfigError, match=message):
        gate.validate_seat_plan(scenario, decks, gapped, 5)


def test_plan_validator_rejects_mismatched_player_count_and_decks() -> None:
    scenario, decks, pilots = _plan()
    with pytest.raises(gate.GateConfigError, match="scenario player_count"):
        gate.validate_seat_plan(scenario.model_copy(update={"player_count": 4}), decks, pilots, 5)
    with pytest.raises(gate.GateConfigError, match="decks for 5 seats"):
        gate.validate_seat_plan(scenario, decks[:4], pilots, 5)
    with pytest.raises(gate.GateConfigError, match="not unique"):
        gate.validate_seat_plan(scenario, (*decks[:4], decks[0]), pilots, 5)


# --- rejected before any engine call -----------------------------------------------------


@pytest.mark.parametrize("value", ["3", "7", "x", "0", "-4", "5.5"])
def test_cli_rejects_unsupported_player_count_with_exit_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    value: str,
) -> None:
    _forbid_engine(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        gate.main(["single", "--player-count", value, "--out", str(tmp_path / "o.json")])
    assert exc.value.code == 2
    assert "player count must be" in capsys.readouterr().err
    assert not (tmp_path / "o.json").exists()


def test_direct_call_with_bad_player_count_returns_2_before_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _forbid_engine(monkeypatch)
    assert gate.cmd_single(_single_args(tmp_path, player_count=7)) == 2
    assert not (tmp_path / "single.json").exists()


def test_six_seat_replay_stops_before_the_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _forbid_engine(monkeypatch)
    assert gate.tape_max_seats() == 5  # the tape model's own limit, read from the model
    args = argparse.Namespace(root=gate.ROOT, seed=7, out=tmp_path / "r.json", player_count=6)
    assert gate.cmd_replay(args) == 2
    assert "at most 5 seats" in capsys.readouterr().err
    assert not (tmp_path / "r.json").exists()


def test_missing_jar_stops_before_the_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _forbid_engine(monkeypatch)
    assert gate.cmd_single(_single_args(tmp_path, jar=tmp_path / "missing.jar")) == 2
    assert "--jar is not a file" in capsys.readouterr().err


def test_jar_must_match_the_environment_start_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    jar = _fake_jar(tmp_path)
    other = tmp_path / "other.jar"
    other.write_bytes(b"x")
    constructed = _install_runner(monkeypatch)
    monkeypatch.setenv(XMAGE_FULL_GAME_COMMAND_ENV, f"java -jar {other} full-game")
    assert gate.cmd_single(_single_args(tmp_path, jar=jar)) == 2
    assert "not the archive started by" in capsys.readouterr().err
    assert constructed == []
    # the same archive in a command with JVM options is accepted and kept as given
    monkeypatch.setenv(XMAGE_FULL_GAME_COMMAND_ENV, f"java -Xmx3g -jar {jar} full-game")
    assert gate.cmd_single(_single_args(tmp_path, jar=jar)) == 0
    assert constructed == [("java", "-Xmx3g", "-jar", str(jar), "full-game")]


# --- extended report: SIMULATED_RESULT, n/N, JAR hash, deck manifest ----------------------


@pytest.mark.parametrize("count", [4, 5, 6])
def test_single_report_carries_class_deck_manifest_counts_and_jar_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: int
) -> None:
    constructed = _install_runner(monkeypatch)
    jar = _fake_jar(tmp_path)
    assert gate.cmd_single(_single_args(tmp_path, player_count=count, jar=jar)) == 0
    payload = json.loads((tmp_path / "single.json").read_text())
    assert set(payload) > LEGACY_SINGLE_KEYS
    assert payload["player_count"] == count
    block = payload["seat_gate"]
    assert block["result_class"] == "SIMULATED_RESULT"
    assert block["qualification_evidence"] is False
    assert block["player_count"] == count
    assert block["jar"] == {
        "status": "HASHED",
        "path": str(jar),
        "sha256": hashlib.sha256(b"synthetic jar bytes").hexdigest(),
        "size_bytes": len(b"synthetic jar bytes"),
    }
    assert constructed == [("java", "-jar", str(jar.resolve()), "full-game")]
    assert [d["seat"] for d in block["decks"]] == list(range(1, count + 1))
    assert [d["deck_id"] for d in block["decks"][:4]] == REFERENCE_SEAT_IDS
    for entry, stem in zip(block["decks"][4:], SEEDED_EXTRA_STEMS, strict=False):
        assert entry["source_file"] == f"data/decks/precons/{stem}.json"
    assert block["extra_deck_selection"]["mode"] == ("seeded" if count > 4 else "none")
    assert block["all_checks_passed"] is True
    assert block["checks"] == {
        name: {"passed": 1, "failed": 0, "unknown": 0, "total": 1}
        for name in (
            "decision_seats_observed",
            "outcome_seats_contiguous",
            "scenario_player_count",
            "seat_plan_contiguous",
            "terminal",
            "winner_seats_in_range",
        )
    }


def test_explicit_extra_deck_is_named_in_the_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_runner(monkeypatch)
    args = _single_args(tmp_path, player_count=5, extra_decks=("2023_veloci_ramp_tor",))
    assert gate.cmd_single(args) == 0
    block = json.loads((tmp_path / "single.json").read_text())["seat_gate"]
    assert block["extra_deck_selection"] == {
        "mode": "explicit",
        "selection_seed": None,
        "stems": ["2023_veloci_ramp_tor"],
    }
    assert block["decks"][4]["source_file"] == "data/decks/precons/2023_veloci_ramp_tor.json"
    assert block["jar"] == {"status": "UNKNOWN", "path": None, "sha256": None, "size_bytes": None}


def test_missing_jar_hash_is_unknown_never_a_digest() -> None:
    identity = gate.jar_identity(None)
    assert identity["status"] == "UNKNOWN"
    assert identity["sha256"] is None
    assert identity["size_bytes"] is None


@pytest.mark.parametrize(
    "bad",
    [
        {"outcome_seats": [0, 1, 2, 4, 5]},  # seat gap in the engine outcomes
        {"outcome_seats": [0, 1, 2, 3]},  # too few outcomes
        {"actor_seats": [0, 1, 2, 3]},  # seat 4 never decided
        {"actor_seats": [0, 1, 2, 4, 5]},  # engine seat gap among the deciders
    ],
)
def test_five_seat_engine_gaps_fail_the_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: dict[str, list[int]]
) -> None:
    _install_runner(monkeypatch, lambda scenario: _seat_result(scenario, **bad))
    assert gate.cmd_single(_single_args(tmp_path, player_count=5)) == 1
    block = json.loads((tmp_path / "single.json").read_text())["seat_gate"]
    assert block["all_checks_passed"] is False
    failed = [name for name, c in block["checks"].items() if c["failed"]]
    assert failed, block["checks"]


def test_result_with_other_player_count_than_requested_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def make(scenario: Any) -> Any:
        return _seat_result(scenario, scenario=scenario.model_copy(update={"player_count": 4}))

    _install_runner(monkeypatch, make)
    assert gate.cmd_single(_single_args(tmp_path, player_count=5)) == 1
    checks = json.loads((tmp_path / "single.json").read_text())["seat_gate"]["checks"]
    assert checks["scenario_player_count"]["failed"] == 1


def test_unknown_is_counted_as_unknown_not_zero_and_not_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # no decision events at all: the observed seats are UNKNOWN, not 0 of N and not N of N
    _install_runner(monkeypatch, lambda scenario: _seat_result(scenario, actor_seats=[]))
    assert gate.cmd_single(_single_args(tmp_path, player_count=5)) == 1
    block = json.loads((tmp_path / "single.json").read_text())["seat_gate"]
    assert block["checks"]["decision_seats_observed"] == {
        "passed": 0,
        "failed": 0,
        "unknown": 1,
        "total": 1,
    }
    assert block["all_checks_passed"] is False
    unknown = gate.result_seat_checks(None, 5)
    assert set(unknown.values()) == {None}
    checks = gate._Checks()
    checks.add_all(unknown)
    assert checks.all_passed is False
    assert all(entry["unknown"] == 1 and entry["passed"] == 0 for entry in checks.render().values())
    assert gate._Checks().all_passed is False  # nothing checked is not a pass


# --- flag position -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv_builder",
    [
        lambda out: ["--player-count", "5", "single", "--out", out],
        lambda out: ["single", "--player-count", "5", "--out", out],
        lambda out: ["--player-count", "4", "single", "--player-count", "5", "--out", out],
    ],
)
def test_player_count_works_before_and_after_the_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv_builder: Any
) -> None:
    seen: list[int] = []

    def make(scenario: Any) -> Any:
        seen.append(scenario.player_count)
        return _seat_result(scenario)

    _install_runner(monkeypatch, make)
    assert gate.main(argv_builder(str(tmp_path / "o.json"))) == 0
    assert seen == [5]


def test_main_without_flags_runs_four_seats_without_seat_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[int] = []

    def make(scenario: Any) -> Any:
        seen.append(scenario.player_count)
        return _result(scenario)

    _install_runner(monkeypatch, make)
    assert gate.main(["single", "--out", str(tmp_path / "o.json")]) == 0
    assert seen == [4]
    assert "seat_gate" not in json.loads((tmp_path / "o.json").read_text())


# --- replay: tape manifest checks --------------------------------------------------------


def _tape_json(
    count: int,
    *,
    player_count: int | None = None,
    seats: list[int] | None = None,
    actors: list[int] | None = None,
    swap_decks: bool = False,
) -> dict[str, Any]:
    _, decks, _ = gate.build_gate_setup(gate.ROOT, 7, count)
    ids = [deck.deck_id for deck in decks]
    if swap_decks:
        ids[0], ids[1] = ids[1], ids[0]
    return {
        "game_manifest": {
            "player_count": count if player_count is None else player_count,
            "seat_principals": [
                {"seat": seat, "deck_id": deck_id}
                for seat, deck_id in zip(seats or range(1, count + 1), ids, strict=False)
            ],
            "decks": [{"deck_id": deck_id} for deck_id in ids],
        },
        "steps": [
            {"step_kind": "decision", "actor_principal": actor}
            for actor in (actors or range(1, count + 1))
        ],
    }


def _install_tapes(monkeypatch: pytest.MonkeyPatch, tapes: dict[str, Any]) -> None:
    def fake_replay(runner: Any, *, tape_dir: Any, **kwargs: Any) -> Any:
        for name, payload in tapes.items():
            (Path(tape_dir) / name).write_text(json.dumps(payload), encoding="utf-8")
        return _tape()

    monkeypatch.setattr(gate, "run_semantic_tape_replay", fake_replay)


def _replay_args(tmp_path: Path, **extra: Any) -> argparse.Namespace:
    return argparse.Namespace(root=gate.ROOT, seed=7, out=tmp_path / "replay.json", **extra)


def test_five_seat_replay_checks_both_tapes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_runner(monkeypatch)
    good = _tape_json(5)
    _install_tapes(monkeypatch, {"first.tape.json": good, "second.tape.json": good})
    assert gate.cmd_replay(_replay_args(tmp_path, player_count=5, jar=_fake_jar(tmp_path))) == 0
    payload = json.loads((tmp_path / "replay.json").read_text())
    block = payload["seat_gate"]
    assert block["result_class"] == "SIMULATED_RESULT"
    assert block["jar"]["sha256"] == hashlib.sha256(b"synthetic jar bytes").hexdigest()
    assert set(payload) == LEGACY_REPLAY_KEYS | {"seat_gate"}
    for name in (
        "tape_player_count",
        "tape_seats_contiguous",
        "tape_deck_order",
        "tape_actor_seats_in_range",
        "tape_decision_seats_observed",
    ):
        assert block["checks"][name] == {"passed": 2, "failed": 0, "unknown": 0, "total": 2}
    assert block["checks"]["terminal"]["total"] == 2  # both natural runs


@pytest.mark.parametrize(
    ("bad_tape", "failing"),
    [
        (_tape_json(5, player_count=4), "tape_player_count"),
        (_tape_json(5, seats=[1, 2, 3, 4, 6]), "tape_seats_contiguous"),
        (_tape_json(5, seats=[0, 1, 2, 3, 4]), "tape_seats_contiguous"),
        (_tape_json(5, swap_decks=True), "tape_deck_order"),
        (_tape_json(5, actors=[1, 2, 3, 4, 6]), "tape_actor_seats_in_range"),
        (_tape_json(5, actors=[1, 2, 3, 4, 4]), "tape_decision_seats_observed"),
    ],
)
def test_tape_with_gap_or_wrong_player_count_fails_the_replay_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad_tape: dict[str, Any], failing: str
) -> None:
    _install_runner(monkeypatch)
    _install_tapes(monkeypatch, {"first.tape.json": _tape_json(5), "second.tape.json": bad_tape})
    assert gate.cmd_replay(_replay_args(tmp_path, player_count=5)) == 1
    payload = json.loads((tmp_path / "replay.json").read_text())
    assert payload["semantic_replay_match"] is True  # the tape system itself said PASS
    assert payload["usability_gate_passed"] is False
    assert payload["seat_gate"]["checks"][failing]["failed"] == 1


def test_missing_tape_is_unknown_and_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_runner(monkeypatch)
    _install_tapes(monkeypatch, {"first.tape.json": _tape_json(5)})  # no second tape written
    assert gate.cmd_replay(_replay_args(tmp_path, player_count=5)) == 1
    checks = json.loads((tmp_path / "replay.json").read_text())["seat_gate"]["checks"]
    assert checks["tape_seats_contiguous"] == {
        "passed": 1,
        "failed": 0,
        "unknown": 1,
        "total": 2,
    }


# --- batch -------------------------------------------------------------------------------


def _install_batch(monkeypatch: pytest.MonkeyPatch, make_result: Any) -> None:
    class FakeBatch:
        def __init__(self, *a: Any, **kw: Any) -> None:
            pass

        def run(self, cases: Any, **kwargs: Any) -> Any:
            records = [
                SimpleNamespace(
                    case_id=c.case_id,
                    status="completed",
                    elapsed_seconds=0,
                    failure_class=None,
                    failure_message=None,
                    result=make_result(c),
                )
                for c in cases
            ]
            return SimpleNamespace(
                total_cases=len(records),
                completed_cases=len(records),
                failed_cases=0,
                resumed_cases=0,
                records=records,
            )

    monkeypatch.setattr(gate, "XmageFullGameBatchRunner", FakeBatch)


@pytest.mark.parametrize("count", [5, 6])
def test_batch_reports_n_of_n_per_check_and_seat_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    count: int,
) -> None:
    _install_runner(monkeypatch)
    _install_batch(monkeypatch, lambda case: _seat_result(case.scenario))
    args = argparse.Namespace(
        root=gate.ROOT, base_seed=40, count=3, out_dir=tmp_path, player_count=count
    )
    assert gate.cmd_batch(args) == 0
    summary = json.loads(capsys.readouterr().out)
    assert [r["case_id"] for r in summary["records"]] == [
        f"real-deck-technical-gate-{count}p-{seed}" for seed in (40, 41, 42)
    ]
    block = summary["seat_gate"]
    assert block["result_class"] == "SIMULATED_RESULT"
    assert block["player_count"] == count
    assert summary["usability_gate_passed"] is True
    for entry in block["checks"].values():
        assert entry == {"passed": 3, "failed": 0, "unknown": 0, "total": 3}


def test_batch_with_one_seat_gap_fails_and_missing_results_are_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install_runner(monkeypatch)
    _install_batch(
        monkeypatch,
        lambda case: _seat_result(
            case.scenario, outcome_seats=[0, 1, 2, 4, 5] if case.scenario.seed == 41 else None
        ),
    )
    args = argparse.Namespace(
        root=gate.ROOT, base_seed=40, count=2, out_dir=tmp_path, player_count=5
    )
    assert gate.cmd_batch(args) == 1
    summary = json.loads(capsys.readouterr().out)
    assert summary["usability_gate_passed"] is False
    assert summary["seat_gate"]["checks"]["outcome_seats_contiguous"] == {
        "passed": 1,
        "failed": 1,
        "unknown": 0,
        "total": 2,
    }
    # a case without a result stays unknown for every check
    assert set(gate.result_seat_checks(None, 5).values()) == {None}
