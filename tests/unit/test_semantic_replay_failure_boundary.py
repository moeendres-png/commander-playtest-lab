"""Replay failure privacy and post-context shutdown qualification boundaries.

Only the transport is synthetic. Recording, native-offer policy, source/schema
locks, fingerprints, comparison, replay verification and publication are real.
These tests do not assert real-JVM or complete-game qualification credit.
"""

from __future__ import annotations

import copy
import json
import runpy
import traceback
from pathlib import Path
from typing import Any

import pytest

from commander_lab.engine.rules.failure_privacy import diagnostics_digest
from commander_lab.engine.rules.full_game import (
    FULL_GAME_SHUTDOWN_ALREADY_EXITED,
    FULL_GAME_SHUTDOWN_FORCED_KILL,
    FULL_GAME_SHUTDOWN_GRACEFUL,
    FULL_GAME_SHUTDOWN_UNACKED_EXIT,
    FullGameProtocolError,
    XmageFullGameRunner,
)
from commander_lab.semantic_replay import consumer, gate, recorder
from commander_lab.semantic_replay.divergence import DivergenceClass, ReplayDivergence

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_VALUES = ("privateHandCanary7e4b", "PRIVATE_HAND_CANARY_7E4B")
MISSING = object()
BAD_SHUTDOWNS = (
    FULL_GAME_SHUTDOWN_FORCED_KILL,
    FULL_GAME_SHUTDOWN_UNACKED_EXIT,
    FULL_GAME_SHUTDOWN_ALREADY_EXITED,
    None,
    MISSING,
    "PRIVATE_SHUTDOWN_CANARY_7E4B",
)


@pytest.fixture(scope="module")
def setup() -> tuple[Any, Any, Any]:
    # Reuse the repository-native, JVM-free fixture constructor; no duplicate
    # deck/scenario/pilot contract or manually stubbed source-lock verifier.
    build_setup = runpy.run_path(str(ROOT / "scripts/run_external_full_game_conformance.py"))[
        "build_setup"
    ]
    return build_setup(4)


def install_transport(
    monkeypatch: pytest.MonkeyPatch,
    setup: tuple[Any, Any, Any],
    *,
    stage: str = "",
    private: str = PRIVATE_VALUES[0],
    disposition: Any = FULL_GAME_SHUTDOWN_GRACEFUL,
    fail_only_consumer: bool = False,
) -> list[Any]:
    scenario = setup[0]
    instances: list[Any] = []

    class Transport:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.imports = 0
            self.submitted = False
            self.stage = stage if not fail_only_consumer or len(instances) == 2 else ""
            instances.append(self)

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *args: Any) -> None:
            if disposition is not MISSING:
                self.shutdown_disposition = disposition

        def status(self) -> dict[str, Any]:
            # For interleaved drain the actor is a loser; for survivor drain
            # the actor is the configured survivor. Both use an offered pass.
            actor = 1 if self.stage == "interleaved-drain" else 0
            state: dict[str, Any] = {
                "seat": actor,
                "turn_number": 1,
                "phase": "precombat_main",
                "players": [
                    {
                        "seat": i,
                        "player_id": f"p{i}",
                        "is_actor": i == actor,
                        "life": 40,
                        "battlefield": [],
                        "graveyard": [],
                        "command": [],
                        "hand_count": 0,
                        "library_count": 99,
                    }
                    for i in range(4)
                ],
            }
            state["players"][actor]["hand"] = []
            return {
                "decision": {
                    "actor_id": f"p{actor}",
                    "seat": actor,
                    "decision_id": "d1",
                    "decision_class": "priority",
                    "decision_offset": 1,
                    "context": {},
                    "minimum_selections": 1,
                    "maximum_selections": 1,
                    "pilot_state": state,
                    "legal_options": [
                        {
                            "label": "Pass priority",
                            "metadata": {},
                            "option_id": "p",
                            "option_type": "pass_priority",
                        }
                    ],
                },
                "turn_number": 1,
                "rules_seed_binding": {
                    "rules_seed": scenario.seed,
                    "rules_random_calls": 0,
                    "rules_seed_matches": True,
                    "rules_seed_explicit": True,
                },
            }

        def failure(self) -> dict[str, Any]:
            result = self.status()
            result["failure"] = {
                "code": "ENGINE_FAILURE",
                "message": private,
                "nested": {"private_hand": [private]},
            }
            return result

        def request(self, kind: str, payload: Any = None) -> dict[str, Any]:
            if self.stage == "transport" and kind == "start_full_game":
                # Even another boundary's alleged public_message is untrusted.
                exc = FullGameProtocolError(private)
                exc.public_message = private
                raise exc
            if kind == "get_provider_version":
                return {
                    "engine": "xmage",
                    "engine_commit": scenario.xmage_commit,
                    "engine_version": "1.4.61",
                }
            if kind == "import_deck":
                self.imports += 1
                return {
                    "deck_handle": {
                        "handle_id": f"h{self.imports}",
                        "deck_hash": payload["deck"]["deck_hash"],
                    }
                }
            if kind == "create_full_game":
                return {"player_count": 4, "seed": scenario.seed}
            if kind == "start_full_game":
                if self.stage == "start":
                    return self.failure()
                result = self.status()
                if self.stage == "poll":
                    result.pop("decision")
                return result
            if kind == "get_full_game_decision":
                return self.failure()
            if kind == "submit_full_game_decision":
                self.submitted = True
                if self.stage in {"submit", "interleaved-drain", "survivor-drain"}:
                    return self.failure()
                result = self.status()
                result.pop("decision")
                if self.stage != "midgame":
                    result["terminal"] = True
                return result
            if kind == "get_concede_offer":
                return {"concede_available": True}
            if kind == "submit_concede":
                return self.status()
            if kind == "get_full_game_result":
                return {
                    "outcomes": [
                        {"seat": i, "left": False, "life": 40, "won": i == 0, "lost": i != 0}
                        for i in range(4)
                    ]
                }
            return {}

    monkeypatch.setattr(recorder, "_RawFullGameClient", Transport)
    monkeypatch.setattr(consumer, "_RawFullGameClient", Transport)
    return instances


def record(setup: tuple[Any, Any, Any], path: Path, *, drain: bool = False) -> Any:
    scenario, decks, pilots = setup
    return recorder.record_tape(
        scenario=scenario,
        decks=decks,
        pilots=pilots,
        command=("synthetic-transport",),
        output_path=path,
        max_decisions=0 if drain else 1,
        concede_to_finish=drain,
    )


def assert_private_absent(exc: ReplayDivergence, private: str) -> None:
    assert private not in exc.detail
    assert private not in str(exc)
    assert private not in repr(exc.args)
    assert private not in "".join(traceback.format_exception(exc))


@pytest.mark.parametrize("private", [*PRIVATE_VALUES, "私密手牌7e4b\n/card/path"])
@pytest.mark.parametrize("prefix", ["engine failed at start: ", "step 7: ", "schema invalid: "])
def test_untrusted_divergence_details_are_safe_at_every_public_sink(
    private: str, prefix: str
) -> None:
    raw = prefix + json.dumps({"message": private, "code": "ENGINE_FAILURE"}, ensure_ascii=False)
    exc = ReplayDivergence(DivergenceClass.EARLY_TERMINATION, raw)
    assert_private_absent(exc, private)
    assert "EARLY_TERMINATION" in str(exc)
    assert "ENGINE_FAILURE" in exc.detail
    assert diagnostics_digest((raw,)) in exc.detail
    if prefix.startswith("step"):
        assert exc.detail.startswith("step 7:")


@pytest.mark.parametrize("private", PRIVATE_VALUES)
@pytest.mark.parametrize(
    "stage",
    ["start", "poll", "submit", "midgame", "interleaved-drain", "survivor-drain", "transport"],
)
def test_recorder_failure_stages_never_publish_private_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    setup: tuple[Any, Any, Any],
    stage: str,
    private: str,
) -> None:
    instances = install_transport(monkeypatch, setup, stage=stage, private=private)
    path = tmp_path / "record.json"
    with pytest.raises(ReplayDivergence) as caught:
        record(setup, path, drain="drain" in stage)
    assert caught.value.divergence == DivergenceClass.EARLY_TERMINATION
    assert_private_absent(caught.value, private)
    assert not path.exists()
    assert len(instances) == 1
    if "drain" in stage:
        assert instances[0].submitted is True  # reach the actual drain branch


@pytest.mark.parametrize("stage", ["start", "poll", "submit", "transport"])
@pytest.mark.parametrize("private", PRIVATE_VALUES)
def test_consumer_failures_redact_text_and_chained_tracebacks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    setup: tuple[Any, Any, Any],
    stage: str,
    private: str,
) -> None:
    install_transport(monkeypatch, setup)
    path = tmp_path / "record.json"
    record(setup, path)
    install_transport(monkeypatch, setup, stage=stage, private=private)
    with pytest.raises(ReplayDivergence) as caught:
        consumer.replay_tape(path, command=("synthetic-transport",))
    assert caught.value.divergence == DivergenceClass.EARLY_TERMINATION
    assert_private_absent(caught.value, private)


def test_schema_validation_does_not_echo_invalid_private_input(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, setup: tuple[Any, Any, Any]
) -> None:
    install_transport(monkeypatch, setup)
    path = tmp_path / "record.json"
    record(setup, path)
    payload = json.loads(path.read_text())
    payload["game_manifest"]["player_count"] = PRIVATE_VALUES[1]
    path.write_text(json.dumps(payload))
    with pytest.raises(ReplayDivergence) as caught:
        consumer.replay_tape(path, command=("synthetic-transport",))
    assert caught.value.divergence == DivergenceClass.MALFORMED_TAPE
    assert_private_absent(caught.value, PRIVATE_VALUES[1])


@pytest.mark.parametrize("disposition", BAD_SHUTDOWNS)
def test_recording_requires_graceful_shutdown_and_preserves_existing_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, setup: tuple[Any, Any, Any], disposition: Any
) -> None:
    path = tmp_path / "record.json"
    install_transport(monkeypatch, setup)
    record(setup, path)
    previous = path.read_bytes()
    install_transport(monkeypatch, setup, disposition=disposition)
    with pytest.raises(ReplayDivergence, match="REPLAY_SHUTDOWN_NOT_GRACEFUL"):
        record(setup, path)
    assert path.read_bytes() == previous
    assert not path.with_suffix(".json.tmp").exists()
    new_path = tmp_path / "new.json"
    with pytest.raises(ReplayDivergence, match="REPLAY_SHUTDOWN_NOT_GRACEFUL"):
        record(setup, new_path)
    assert not new_path.exists()


@pytest.mark.parametrize("disposition", BAD_SHUTDOWNS)
def test_replay_requires_graceful_shutdown_before_returning_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, setup: tuple[Any, Any, Any], disposition: Any
) -> None:
    path = tmp_path / "record.json"
    install_transport(monkeypatch, setup)
    record(setup, path)
    instances = install_transport(monkeypatch, setup, disposition=disposition)
    with pytest.raises(ReplayDivergence, match="REPLAY_SHUTDOWN_NOT_GRACEFUL"):
        consumer.replay_tape(path, command=("synthetic-transport",))
    assert instances[0].submitted is True  # semantic step succeeds first


def test_failed_shutdown_preserves_the_primary_replay_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, setup: tuple[Any, Any, Any]
) -> None:
    install_transport(monkeypatch, setup, stage="start", disposition=FULL_GAME_SHUTDOWN_FORCED_KILL)
    with pytest.raises(ReplayDivergence) as caught:
        record(setup, tmp_path / "record.json")
    assert "engine failed at start" in caught.value.detail
    assert "REPLAY_SHUTDOWN_NOT_GRACEFUL" not in caught.value.detail
    assert_private_absent(caught.value, PRIVATE_VALUES[0])


def test_graceful_record_then_replay_preserves_full_semantic_verification(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, setup: tuple[Any, Any, Any]
) -> None:
    instances = install_transport(monkeypatch, setup)
    path = tmp_path / "record.json"
    tape = record(setup, path)
    verdict = consumer.replay_tape(path, command=("synthetic-transport",))
    assert len(instances) == 2
    assert all(c.shutdown_disposition == FULL_GAME_SHUTDOWN_GRACEFUL for c in instances)
    assert verdict["pass"] is True
    assert verdict["tape_id"] == tape.tape_id
    assert verdict["steps_verified"] == len(tape.steps) == 1
    assert verdict["terminal"] == tape.terminal_checkpoint.model_dump(mode="json")
    assert tape.steps[0].selected_labels == ("Pass priority",)
    # An independently tampered recorded semantic event still fails closed.
    payload = copy.deepcopy(tape.model_dump(mode="json"))
    payload["steps"][0]["event_digest"] = "f" * 64
    path.write_text(json.dumps(payload))
    with pytest.raises(ReplayDivergence) as caught:
        consumer.replay_tape(path, command=("synthetic-transport",))
    assert caught.value.divergence == DivergenceClass.EVENT_DIGEST_MISMATCH
    assert caught.value.detail.startswith("step 1:")


@pytest.mark.parametrize("private", PRIVATE_VALUES)
def test_three_process_gate_failure_evidence_contains_no_private_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, setup: tuple[Any, Any, Any], private: str
) -> None:
    instances = install_transport(
        monkeypatch, setup, stage="submit", private=private, fail_only_consumer=True
    )
    scenario, decks, pilots = setup
    evidence = gate.run_semantic_tape_replay(
        XmageFullGameRunner(command=("synthetic-transport",)),
        scenario=scenario,
        decks=decks,
        pilots=pilots,
        tape_dir=tmp_path,
    )
    assert len(instances) == 3
    assert evidence.tape_comparison_match is True
    assert evidence.passed is False
    assert evidence.replay_divergence_class == "EARLY_TERMINATION"
    assert private not in evidence.model_dump_json()
    assert "diagnostics sha256:" in str(evidence.replay_divergence_detail)
