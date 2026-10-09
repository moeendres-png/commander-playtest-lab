"""C1: the full-game replay gate, decided by semantic replay tapes.

Two tapes are recorded in fresh processes and compared step by step
(`compare_tapes`); the first tape is then consumed by a third fresh process
(`replay_tape`), which re-derives every legal set, selection, event digest and
the terminal outcome from the live engine. The conformance runner's twin
transcript hash is kept on the gate as a diagnostic only.
"""

from __future__ import annotations

import json
from pathlib import Path

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import (
    XMAGE_FULL_GAME_COMMAND_ENV,
    FullGameConformanceError,
    FullGamePilotBinding,
    FullGameReplayGate,
    FullGameSemanticTapeEvidence,
    XmageFullGameRunner,
)
from commander_lab.models import RulesDeckInput

from . import comparator, consumer, recorder
from .divergence import REPLAY_DIVERGENCE_DETAIL_LIMIT, ReplayDivergence


def _bounded_detail(detail: str) -> str:
    if len(detail) <= REPLAY_DIVERGENCE_DETAIL_LIMIT:
        return detail
    return detail[: REPLAY_DIVERGENCE_DETAIL_LIMIT - 3] + "..."


def run_semantic_tape_replay(
    runner: XmageFullGameRunner,
    *,
    scenario: FutureXmageScenario,
    decks: tuple[RulesDeckInput, ...],
    pilots: tuple[FullGamePilotBinding, ...],
    tape_dir: str | Path,
) -> FullGameSemanticTapeEvidence:
    """Record two tapes, compare them, and consume the first in a fresh process.

    A recording failure propagates (fail closed). A comparison or consumer
    divergence is recorded in the evidence, and the gate built from it fails.
    """
    command = runner.command
    if command is None:
        raise FullGameConformanceError(
            f"{XMAGE_FULL_GAME_COMMAND_ENV} is required for the semantic tape replay"
        )
    directory = Path(tape_dir)
    directory.mkdir(parents=True, exist_ok=True)
    paths = (directory / "first.tape.json", directory / "second.tape.json")
    tapes = tuple(
        recorder.record_tape(
            scenario=scenario,
            decks=decks,
            pilots=pilots,
            command=command,
            output_path=path,
            cwd=runner.cwd,
        )
        for path in paths
    )
    comparison = comparator.compare_tapes(
        json.loads(paths[0].read_text(encoding="utf-8")),
        json.loads(paths[1].read_text(encoding="utf-8")),
    )
    replay_pass, steps_verified = True, len(tapes[0].steps)
    divergence_class: str | None = None
    divergence_detail: str | None = None
    try:
        verdict = consumer.replay_tape(paths[0], command=command, cwd=runner.cwd)
        steps_verified = int(verdict["steps_verified"])
    except ReplayDivergence as exc:
        replay_pass, steps_verified, divergence_class = False, 0, exc.divergence.value
        divergence_detail = _bounded_detail(exc.detail)
    return FullGameSemanticTapeEvidence(
        tape_schema_version=tapes[0].schema_version,
        first_tape_id=tapes[0].tape_id,
        second_tape_id=tapes[1].tape_id,
        recorded_steps=len(tapes[0].steps),
        tape_comparison_match=comparison.match,
        compared_steps=comparison.compared_steps,
        first_divergence_kind=(
            comparison.divergence.kind.value if comparison.divergence is not None else None
        ),
        fresh_process_replay_pass=replay_pass,
        replay_steps_verified=steps_verified,
        replay_divergence_class=divergence_class,
        replay_divergence_detail=divergence_detail,
    )


def run_replay_gate(
    runner: XmageFullGameRunner,
    *,
    scenario: FutureXmageScenario,
    decks: tuple[RulesDeckInput, ...],
    pilots: tuple[FullGamePilotBinding, ...],
    tape_dir: str | Path,
) -> FullGameReplayGate:
    first = runner.run(scenario=scenario, decks=decks, pilots=pilots)
    second = runner.run(scenario=scenario, decks=decks, pilots=pilots)
    tape = run_semantic_tape_replay(
        runner, scenario=scenario, decks=decks, pilots=pilots, tape_dir=tape_dir
    )
    return XmageFullGameRunner.replay_gate(scenario=scenario, first=first, second=second, tape=tape)


__all__ = ["run_replay_gate", "run_semantic_tape_replay"]
