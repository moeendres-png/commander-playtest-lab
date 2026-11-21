"""Real-deck end-to-end usability gate for 4, 5 or 6 seats (technical only).

Runs actual verified Commander decks (2x RogShai + 2x Kaervek) through the
existing full-game runner under external deterministic pilots: single game,
same-seed replay, and an isolated batch. Result class is
REAL_CARD_TECHNICAL_USABILITY_GATE -- never matchup evidence.

Seat count (``--player-count 4|5|6``, default 4). The default is the historical 4-seat
gate and stays unchanged: same decks, same scenario ids, same output keys. Seats 5 and 6
take the four reference decks and add precons from ``data/decks/precons``. Which precons
is deterministic: the eligible precons (statically valid, one deck per commander) are
ranked by ``sha256("<EXTRA_DECK_SELECTION_SEED>:<file stem>")`` and the first ones are
taken, so the pod does not depend on the game seed or on directory order. ``--extra-decks
stem,stem`` names them explicitly instead (exactly player_count - 4 stems).

Opt-in report. When ``--player-count``, ``--extra-decks`` or ``--jar`` is given, the output
gains a ``seat_gate`` block: result class SIMULATED_RESULT (never qualification evidence),
the ordered seat decks with their file names, a ``pod`` label and ``table_a5`` (never true
here: seats 1-4 are reference decks, table A5 is five precons), n/N per check and the
SHA-256 of the ``--jar`` bridge archive. Every check is labelled "engine" (observed from the
engine result, the tape steps or the archive) or "plan" (copied from the gate's own plan or
the recorder input, so it only catches driver bugs); ``check_groups`` counts n/N per group and
``all_checks_passed`` needs both groups to pass. An unknown value is counted as unknown, never
as 0 or as a pass. More than four seats require ``--jar`` (exit 2 otherwise); the archive is
hashed again after the run and a changed or vanished file is a red ``jar_unchanged`` check.
The ``seat_gate.jar`` block names the effective start command (with COMMANDER_LAB_XMAGE_JVM_FLAGS
spliced in). A bridge command from the environment must be a plain java launcher with only JVM
options before one ``-jar`` and an absolute archive path equal to ``--jar``. The deck list is
labelled "plan" and carries the SHA-256 of each deck file. A winner list that does not match
the ``won`` outcomes, or that nobody wins, is not a pass. With 6 seats the report says that no
replay is claimed.
A seat gap (seats must be exactly 1..N, engine seats 0..N-1) or a player_count that differs
between plan, result and tape fails the gate. Without those flags no key is added.

The semantic replay tape model holds at most 5 seats; ``replay`` with 6 seats therefore
stops before any engine call (no replay claim for 6 seats). ``single`` and ``batch`` run 6.
The released-seat lock of the Studio (``launch.MAX_RELEASED_SEATS``) is not touched here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import (
    FullGamePilotBinding,
    XmageFullGameRunner,
    _with_jvm_flags,
)
from commander_lab.engine.rules.full_game_batch import (
    FullGameBatchCase,
    XmageFullGameBatchRunner,
)
from commander_lab.engine.rules.full_game_pilot.common import (
    XMAGE_FULL_GAME_COMMAND_ENV,
    XMAGE_JVM_FLAGS_ENV,
)
from commander_lab.engine.rules.full_game_series import FullGameSeriesResult
from commander_lab.engine.rules.project import load_project_rules_decks, load_rules_deck_snapshot
from commander_lab.models import (
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    RulesDeckInput,
)
from commander_lab.qualification.current_boundary.bridge_launcher import canonical_xmage_engine_pin
from commander_lab.semantic_replay.gate import run_semantic_tape_replay
from commander_lab.semantic_replay.tape import TapeGameManifest
from commander_lab.semantic_replay.tape_helpers import deck_content_digest

ROOT = Path(__file__).resolve().parents[1]
# G1: the live pin is read from config/rules_engines.json, never restated here.
XMAGE_COMMIT = canonical_xmage_engine_pin()
GATE_LABEL = "REAL_CARD_TECHNICAL_USABILITY_GATE"

# Seat plan: two verified decks, each fielded twice (only two distinct
# verified real decks exist; repeated copies are declared, not hidden).
SEAT_DECKS = ("rogshai", "kaervek", "rogshai", "kaervek")
BASE_SEED = 20260923

DEFAULT_PLAYER_COUNT = 4
MIN_PLAYER_COUNT = 4
MAX_PLAYER_COUNT = 6
# Seeds the ranking of extra precons for 5/6 seats (not the game seed): one fixed pod per
# seat count, so every game of a batch and every gate run fields the same decks.
EXTRA_DECK_SELECTION_SEED = BASE_SEED
PRECON_DIR = Path("data/decks/precons")
PRECON_FAMILY_PREFIX = "precon-"
RESULT_CLASS = "SIMULATED_RESULT"
# Table A5 of the 5/6-seat measurements (docs/analysis-reports/seats_5_6_part_b_report.md): five
# precons. The gate's first four seats are the reference decks, so its pods are never table A5;
# the report says so explicitly instead of leaving a reader to assume it.
TABLE_A5_PRECONS = frozenset(
    {
        "2023_eldrazi_unbound",
        "2026_lorehold_spirit",
        "2024_animated_army",
        "2022_token_triumph",
        "2023_veloci_ramp_tor",
    }
)
# "engine": observed from the engine result, the recorded tape steps or the archive that ran.
# "plan": copied from the gate's own plan or recorder input; compared with itself, so it can
# catch a driver bug but is no evidence about the engine.
CHECK_GROUPS = {
    "terminal": "engine",
    "outcome_seats_contiguous": "engine",
    "decision_seats_observed": "engine",
    "winner_seats_in_range": "engine",
    "tape_actor_seats_in_range": "engine",
    "tape_decision_seats_observed": "engine",
    "jar_unchanged": "engine",
    "seat_plan_contiguous": "plan",
    "scenario_player_count": "plan",
    "tape_player_count": "plan",
    "tape_seats_contiguous": "plan",
    "tape_deck_order": "plan",
}
JAR_MAIN_COMMAND = "full-game"
# Bound at import: the static check must not follow a replaced runner class.
_validate_deck_construction = XmageFullGameRunner._validate_deck_construction


class GateConfigError(ValueError):
    """Invalid gate configuration; reported as exit code 2 before any engine call."""


def _material_hash(deck_id: str, commanders: tuple[str, ...], mainboard: tuple[str, ...]) -> str:
    return deck_content_digest(deck_id=deck_id, commander_names=commanders, mainboard=mainboard)


def load_gate_decks(root: Path) -> dict[str, RulesDeckInput]:
    """Load canonical decks: rogshai via manifest loader, kaervek via adapter.

    Kaervek's snapshot file uses the same card-entry shape as rogshai
    (oracle_name/quantity/zone) but carries a scalar commander field, so it
    is adapted without altering any card content.
    """
    decks = load_project_rules_decks(root)
    rogshai = decks["rogshai/current"]
    kaervek_path = root / "data/decks/opponents/kaervek/current/deck.json"
    payload = json.loads(kaervek_path.read_text(encoding="utf-8"))
    commanders = (str(payload["commander"]),)
    mainboard: list[str] = []
    for entry in payload["cards"]:
        if entry.get("zone") != "main":
            continue
        mainboard.extend([str(entry["oracle_name"])] * int(entry.get("quantity", 1)))
    kaervek = RulesDeckInput(
        deck_id="kaervek/current",
        name=str(payload["name"]),
        commander_names=commanders,
        mainboard=tuple(mainboard),
        deck_hash=str(payload["deck_hash"]),
        source_path=str(kaervek_path),
    )
    return {"rogshai": rogshai, "kaervek": kaervek}


def _static_deck_check(deck: RulesDeckInput) -> bool:
    """Engine-free construction check (100 cards, color identity, hash) of a seat deck."""
    seat_deck = RulesDeckInput(
        deck_id=deck.deck_id,
        name=deck.name,
        commander_names=deck.commander_names,
        mainboard=deck.mainboard,
        sideboard=deck.sideboard,
        deck_hash=_material_hash(deck.deck_id, deck.commander_names, deck.mainboard),
        source_path=deck.source_path,
    )
    try:
        _validate_deck_construction(seat_deck)
    except Exception:  # any construction failure makes the deck ineligible
        return False
    return True


def _load_precon(root: Path, stem: str) -> RulesDeckInput:
    if not stem or Path(stem).name != stem or not all(c.isalnum() or c == "_" for c in stem):
        raise GateConfigError(f"invalid precon file stem: {stem!r}")
    path = root / PRECON_DIR / f"{stem}.json"
    if not path.is_file():
        raise GateConfigError(f"unknown precon deck: {stem!r} (no {PRECON_DIR}/{stem}.json)")
    return load_rules_deck_snapshot(path)


def _extra_deck_rank(stem: str) -> str:
    return hashlib.sha256(f"{EXTRA_DECK_SELECTION_SEED}:{stem}".encode()).hexdigest()


def select_extra_decks(
    root: Path, count: int, explicit: Sequence[str] | None = None
) -> tuple[str, ...]:
    """Precon file stems for the seats beyond the four reference decks (deterministic).

    ``explicit`` stems are validated and used as given (exactly ``count`` of them). Without
    them the eligible precons are ranked by sha256 of the fixed selection seed and the file
    stem; a precon is eligible when it passes the static deck check and neither its
    commander nor its file repeats one already seated.
    """
    if count < 0:
        raise GateConfigError("extra deck count must not be negative")
    if count == 0 and explicit is None:
        return ()
    reference_commanders = {tuple(deck.commander_names) for deck in load_gate_decks(root).values()}
    if explicit is not None:
        stems = tuple(explicit)
        if len(stems) != count:
            raise GateConfigError(
                f"--extra-decks must name exactly {count} deck(s) for this seat count, "
                f"got {len(stems)}"
            )
        if len(set(stems)) != len(stems):
            raise GateConfigError("--extra-decks must not repeat a deck")
        seated = set(reference_commanders)
        for stem in stems:
            deck = _load_precon(root, stem)
            if not _static_deck_check(deck):
                raise GateConfigError(f"precon {stem!r} fails the static deck check")
            if tuple(deck.commander_names) in seated:
                raise GateConfigError(f"precon {stem!r} repeats a seated commander")
            seated.add(tuple(deck.commander_names))
        return stems
    pool = sorted(
        (path.stem for path in (root / PRECON_DIR).glob("*.json")),
        key=lambda stem: (_extra_deck_rank(stem), stem),
    )
    chosen: list[str] = []
    seated_commanders = set(reference_commanders)
    for stem in pool:
        deck = _load_precon(root, stem)
        commanders = tuple(deck.commander_names)
        if commanders in seated_commanders or not _static_deck_check(deck):
            continue
        chosen.append(stem)
        seated_commanders.add(commanders)
        if len(chosen) == count:
            return tuple(chosen)
    raise GateConfigError(f"only {len(chosen)} eligible precon decks for {count} extra seats")


def seat_families(
    root: Path,
    player_count: int = DEFAULT_PLAYER_COUNT,
    extra_decks: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """Ordered deck family per seat: the four reference families, then ``precon-<stem>``."""
    _check_player_count(player_count)
    extras = select_extra_decks(root, player_count - MIN_PLAYER_COUNT, extra_decks)
    return (*SEAT_DECKS, *(f"{PRECON_FAMILY_PREFIX}{stem}" for stem in extras))


def _check_player_count(player_count: object) -> int:
    if type(player_count) is not int or not MIN_PLAYER_COUNT <= player_count <= MAX_PLAYER_COUNT:
        raise GateConfigError(
            f"player count must be {MIN_PLAYER_COUNT}, {MIN_PLAYER_COUNT + 1} or "
            f"{MAX_PLAYER_COUNT}, got {player_count!r}"
        )
    return player_count


def validate_seat_plan(
    scenario: FutureXmageScenario,
    decks: Sequence[RulesDeckInput],
    pilots: Sequence[FullGamePilotBinding],
    player_count: int,
) -> None:
    """Fail closed unless seats are exactly 1..N and every cardinality agrees with N."""
    seats = [pilot.seat for pilot in pilots]
    if seats != list(range(1, player_count + 1)):
        raise GateConfigError(f"seat gap: pilot seats {seats} are not 1..{player_count}")
    if len(decks) != player_count:
        raise GateConfigError(f"{len(decks)} decks for {player_count} seats")
    deck_ids = [deck.deck_id for deck in decks]
    for index, deck_id in enumerate(deck_ids, start=1):
        # every seat deck id ends in its own seat index; that is what keeps the ids unique
        if not deck_id.endswith(f"/seat-{index}"):
            raise GateConfigError(f"seat {index} deck id {deck_id!r} does not carry its seat index")
    if [pilot.deck_id for pilot in pilots] != deck_ids:
        raise GateConfigError("pilot deck ids do not follow the seat deck order")
    if scenario.player_count != player_count:
        raise GateConfigError(
            f"scenario player_count {scenario.player_count} differs from {player_count}"
        )
    if tuple(scenario.opponent_deck_ids) != tuple(deck_ids[1:]):
        raise GateConfigError("scenario opponents differ from the seat decks")


def _load_seat_family_decks(root: Path, families: Sequence[str]) -> dict[str, RulesDeckInput]:
    canonical = load_gate_decks(root)
    for family in families:
        if family not in canonical:
            canonical[family] = _load_precon(root, family.removeprefix(PRECON_FAMILY_PREFIX))
    return canonical


def build_gate_setup(
    root: Path,
    seed: int,
    player_count: int = DEFAULT_PLAYER_COUNT,
    extra_decks: Sequence[str] | None = None,
) -> tuple[FutureXmageScenario, tuple[RulesDeckInput, ...], tuple[FullGamePilotBinding, ...]]:
    """Build seat decks/pilots/scenario for one real-deck game (4 seats by default)."""
    families = seat_families(root, player_count, extra_decks)
    canonical = _load_seat_family_decks(root, families)
    decks: list[RulesDeckInput] = []
    pilots: list[FullGamePilotBinding] = []
    for index, family in enumerate(families, start=1):
        base = canonical[family]
        seat_deck_id = f"{family}/seat-{index}"
        seat_deck = RulesDeckInput(
            deck_id=seat_deck_id,
            name=base.name,
            commander_names=base.commander_names,
            mainboard=base.mainboard,
            sideboard=base.sideboard,
            deck_hash=_material_hash(seat_deck_id, base.commander_names, base.mainboard),
            source_path=base.source_path,
        )
        decks.append(seat_deck)
        pilots.append(
            FullGamePilotBinding(
                seat=index,
                deck_id=seat_deck_id,
                strategy="generic",
                commander_names=seat_deck.commander_names,
                config=PilotConfig(
                    pilot_name="auto",
                    strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
                    mode=PilotDecisionMode.DETERMINISTIC,
                ),
                pilot_identity="GenericCommanderPilot",
                pilot_version="1.0.0",
                decision_policy_version="xmage-full-game-policy-1.0.0",
            )
        )
    own = decks[0]
    assert own.deck_hash is not None
    scenario = FutureXmageScenario(
        candidate_id=own.deck_id,
        deck_hash=own.deck_hash,
        opponent_deck_ids=tuple(deck.deck_id for deck in decks[1:]),
        player_count=player_count,
        seat=1,
        scenario_id=_scenario_id(player_count, seed),
        seed=seed,
        xmage_commit=XMAGE_COMMIT,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )
    validate_seat_plan(scenario, decks, pilots, player_count)
    return scenario, tuple(decks), tuple(pilots)


def _scenario_id(player_count: int, seed: int) -> str:
    return f"real-deck-technical-gate-{player_count}p-{seed}"


def summarize_result(result, gate: str) -> dict:
    if isinstance(result, FullGameSeriesResult):
        # a Studio series result (Owner decision E9) is no gate evidence
        raise TypeError("the real-deck gate takes no Studio series result (FullGameSeriesResult)")
    return {
        "gate": gate,
        "evidence_class": result.evidence_class,
        "engine_version": result.engine_version,
        "xmage_commit": result.xmage_commit,
        "player_count": result.scenario.player_count,
        "seed": result.scenario.seed,
        "scenario_id": result.scenario.scenario_id,
        "candidate_id": result.scenario.candidate_id,
        "opponent_deck_ids": list(result.scenario.opponent_deck_ids),
        "decision_count": result.decision_count,
        "terminal": result.terminal,
        "winner_seats": list(result.winner_seats),
        "observed_decision_classes": sorted(
            {
                str(event.get("decision_class"))
                for event in result.result_payload.get("transcript", [])
                if isinstance(event, dict) and event.get("kind") == "decision_accepted"
            }
        ),
        "semantic_transcript_sha256": result.semantic_transcript_sha256,
        "raw_result_sha256": result.raw_result_sha256,
        "consumed_gameplay_evidence": result.consumed_gameplay_evidence,
        "holdout_consumed": result.holdout_consumed,
        "fallback_used": result.fallback_used,
        "hidden_information_actor_scoped": result.hidden_information_actor_scoped,
        "rules_authority": result.xmage_rules_authority,
        "decision_authority": result.commander_lab_pilot_decision_authority,
        # C3: which of the claims above were observed in this run.
        "claim_basis": result.claim_basis.model_dump(mode="json"),
    }


@dataclass(frozen=True)
class GateOptions:
    player_count: int
    extra_decks: tuple[str, ...] | None
    jar: Path | None
    # True once --player-count, --extra-decks or --jar was passed: only then the output
    # gains the ``seat_gate`` block and the extra fail-closed seat checks.
    extended: bool
    # The start command that runs ``jar`` (set by ``_prepare`` once it is validated).
    command: tuple[str, ...] | None = None


def _stem_list(value: str) -> tuple[str, ...]:
    stems = tuple(part.strip() for part in value.split(",") if part.strip())
    if not stems:
        raise argparse.ArgumentTypeError("--extra-decks needs at least one file stem")
    return stems


def _seat_count(value: str) -> int:
    try:
        count = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"player count must be an integer, got {value!r}"
        ) from None
    try:
        return _check_player_count(count)
    except GateConfigError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def resolve_options(args: argparse.Namespace) -> GateOptions:
    raw_count = getattr(args, "player_count", None)
    raw_extra = getattr(args, "extra_decks", None)
    raw_jar = getattr(args, "jar", None)
    if isinstance(raw_extra, str):
        raw_extra = _stem_list(raw_extra)
    count = _check_player_count(DEFAULT_PLAYER_COUNT if raw_count is None else raw_count)
    if count > DEFAULT_PLAYER_COUNT and raw_jar is None:
        raise GateConfigError(
            f"--jar is required for {count} seats: the report must name the archive that ran"
        )
    return GateOptions(
        player_count=count,
        extra_decks=None if raw_extra is None else tuple(raw_extra),
        jar=None if raw_jar is None else Path(raw_jar),
        extended=raw_count is not None or raw_extra is not None or raw_jar is not None,
    )


def tape_max_seats() -> int:
    """Seats the semantic replay tape model can hold (read from the model, not restated)."""
    for meta in TapeGameManifest.model_fields["player_count"].metadata:
        limit = getattr(meta, "le", None)
        if isinstance(limit, int):
            return limit
    raise GateConfigError("the tape model declares no player_count upper bound")


def jar_identity(jar: Path | None) -> dict[str, Any]:
    """SHA-256 of the bridge archive; without ``--jar`` the hash is UNKNOWN (never 0)."""
    if jar is None:
        return {"status": "UNKNOWN", "path": None, "sha256": None, "size_bytes": None}
    if not jar.is_file():
        raise GateConfigError(f"--jar is not a file: {jar}")
    digest = hashlib.sha256()
    size = 0
    with jar.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return {"status": "HASHED", "path": str(jar), "sha256": digest.hexdigest(), "size_bytes": size}


_JAVA_LAUNCHERS = ("java", "javaw", "java.exe")
_CLASSPATH_OPTIONS = ("-cp", "-classpath", "--class-path", "-p", "--module-path")


def bridge_command_for_jar(jar: Path) -> tuple[str, ...]:
    """The start command that runs exactly ``jar``.

    Without ``COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD`` it is ``java -jar <absolute jar>
    full-game``. A given environment command must be a plain java launcher: only options
    (``-X...``, ``-D...``, ``-javaagent:...``) before one ``-jar``, no classpath option, and an
    absolute archive path equal to ``--jar``. The bridge JVM starts in its own working
    directory, so a relative archive token would not name the file that was hashed.
    """
    raw = os.environ.get(XMAGE_FULL_GAME_COMMAND_ENV, "").strip()
    if not raw:
        return ("java", "-jar", str(jar.resolve()), JAR_MAIN_COMMAND)
    command = tuple(shlex.split(raw))
    reason = _launcher_problem(command, jar)
    if reason is not None:
        raise GateConfigError(f"{XMAGE_FULL_GAME_COMMAND_ENV} does not start --jar {jar}: {reason}")
    return command


def _launcher_problem(command: tuple[str, ...], jar: Path) -> str | None:
    if not command or os.path.basename(command[0]).lower() not in _JAVA_LAUNCHERS:
        return "it is not a plain java launcher"
    if command.count("-jar") != 1:
        return "it needs exactly one -jar"
    index = command.index("-jar")
    for token in command[1:index]:
        if not token.startswith("-") or token.split("=", 1)[0] in _CLASSPATH_OPTIONS:
            return f"only JVM options may precede -jar, found {token!r}"
    if index + 1 >= len(command):
        return "-jar names no archive"
    archive = Path(command[index + 1])
    if not archive.is_absolute():
        return "the -jar archive must be an absolute path (the bridge starts in its own directory)"
    if archive.resolve() != jar.resolve():
        return "the -jar archive is another file"
    return None


def _make_runner(options: GateOptions) -> XmageFullGameRunner:
    if options.jar is None or options.command is None:
        return XmageFullGameRunner()
    return XmageFullGameRunner(command=options.command)


class _Checks:
    """n/N per check. True is a pass, False a failure, None unknown (never counted as 0)."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, int]] = {}

    def add(self, name: str, state: bool | None) -> None:
        if name not in CHECK_GROUPS:
            raise KeyError(f"check {name!r} has no group")
        entry = self._data.setdefault(name, {"passed": 0, "failed": 0, "unknown": 0, "total": 0})
        entry["total"] += 1
        entry["unknown" if state is None else "passed" if state else "failed"] += 1

    def add_all(self, states: dict[str, bool | None]) -> None:
        for name, state in states.items():
            self.add(name, state)

    def render(self) -> dict[str, dict[str, Any]]:
        return {
            name: {**entry, "group": CHECK_GROUPS[name]}
            for name, entry in sorted(self._data.items())
        }

    def group_summary(self) -> dict[str, dict[str, int]]:
        """n/N per group, counted over every single check instance."""
        summary = {
            group: {"passed": 0, "failed": 0, "unknown": 0, "total": 0}
            for group in ("engine", "plan")
        }
        for name, entry in self._data.items():
            for key in ("passed", "failed", "unknown", "total"):
                summary[CHECK_GROUPS[name]][key] += entry[key]
        return summary

    def group_passed(self, group: str) -> bool:
        counts = self.group_summary()[group]
        return counts["total"] > 0 and counts["passed"] == counts["total"]

    @property
    def all_passed(self) -> bool:
        """Engine and plan checks all passed; a group without a check is not a pass."""
        return self.group_passed("engine") and self.group_passed("plan")


def result_seat_checks(result: Any, player_count: int) -> dict[str, bool | None]:
    """Seat checks of one finished game; ``result`` None (no result) leaves every one unknown."""
    names = (
        "terminal",
        "scenario_player_count",
        "outcome_seats_contiguous",
        "decision_seats_observed",
        "winner_seats_in_range",
    )
    if result is None:
        return dict.fromkeys(names)
    payload = result.result_payload if isinstance(result.result_payload, dict) else {}
    outcomes = payload.get("outcomes")
    outcome_state: bool | None = None
    if (
        isinstance(outcomes, list)
        and outcomes
        and all(isinstance(o, dict) and type(o.get("seat")) is int for o in outcomes)
    ):
        outcome_state = sorted(o["seat"] for o in outcomes) == list(range(player_count))
    transcript = payload.get("transcript")
    actors = {
        event["actor_seat"]
        for event in (transcript if isinstance(transcript, list) else [])
        if isinstance(event, dict)
        and event.get("kind") == "decision_accepted"
        and type(event.get("actor_seat")) is int
    }
    return {
        "terminal": result.terminal is True,
        "scenario_player_count": result.scenario.player_count == player_count,
        "outcome_seats_contiguous": outcome_state,
        "decision_seats_observed": (actors == set(range(player_count)) if actors else None),
        "winner_seats_in_range": _winner_state(result, outcomes, player_count),
    }


def _winner_state(result: Any, outcomes: Any, player_count: int) -> bool | None:
    """Winners must equal the seats whose outcome says ``won`` and lie in 1..N.

    Unknown (None) when an outcome has no boolean ``won`` or nobody won: an empty winner
    list is never a pass.
    """
    if not isinstance(outcomes, list) or not all(
        isinstance(o, dict) and type(o.get("seat")) is int and type(o.get("won")) is bool
        for o in outcomes
    ):
        return None
    won = {o["seat"] + 1 for o in outcomes if o["won"]}
    if not won:
        return None
    winners = {int(seat) for seat in result.winner_seats}
    return winners == won and all(1 <= seat <= player_count for seat in winners)


def read_tape(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def tape_seat_checks(
    tape: dict[str, Any] | None, player_count: int, decks: Sequence[RulesDeckInput]
) -> dict[str, bool | None]:
    """Seat checks of one recorded tape; a missing or unreadable tape leaves them unknown."""
    names = (
        "tape_player_count",
        "tape_seats_contiguous",
        "tape_deck_order",
        "tape_actor_seats_in_range",
        "tape_decision_seats_observed",
    )
    manifest = tape.get("game_manifest") if isinstance(tape, dict) else None
    if not isinstance(manifest, dict):
        return dict.fromkeys(names)
    principals = manifest.get("seat_principals")
    tape_decks = manifest.get("decks")
    steps = tape.get("steps") if isinstance(tape, dict) else None
    deck_ids = [deck.deck_id for deck in decks]
    seat_state: bool | None = None
    order_state: bool | None = None
    if isinstance(principals, list) and all(isinstance(p, dict) for p in principals):
        seat_state = [p.get("seat") for p in principals] == list(range(1, player_count + 1))
        if isinstance(tape_decks, list) and all(isinstance(d, dict) for d in tape_decks):
            order_state = [p.get("deck_id") for p in principals] == deck_ids and [
                d.get("deck_id") for d in tape_decks
            ] == deck_ids
    range_state: bool | None = None
    observed_state: bool | None = None
    if isinstance(steps, list) and steps and all(isinstance(x, dict) for x in steps):
        actors = [x.get("actor_principal") for x in steps]
        range_state = all(type(a) is int and 1 <= a <= player_count for a in actors)
        decision_actors = {
            x.get("actor_principal") for x in steps if x.get("step_kind", "decision") == "decision"
        }
        observed_state = decision_actors == set(range(1, player_count + 1))
    return {
        "tape_player_count": manifest.get("player_count") == player_count
        if type(manifest.get("player_count")) is int
        else None,
        "tape_seats_contiguous": seat_state,
        "tape_deck_order": order_state,
        "tape_actor_seats_in_range": range_state,
        "tape_decision_seats_observed": observed_state,
    }


def _relative_source(root: Path, source_path: str | None) -> str | None:
    if source_path is None:
        return None
    try:
        return Path(source_path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return Path(source_path).name


def seat_gate_block(
    root: Path,
    options: GateOptions,
    decks: Sequence[RulesDeckInput],
    checks: _Checks,
    jar: dict[str, Any],
) -> dict[str, Any]:
    """The opt-in ``seat_gate`` report: class, ordered seat decks, n/N per check, JAR hash."""
    explicit = options.extra_decks is not None
    extras = [d for d in decks[MIN_PLAYER_COUNT:]]
    return {
        "result_class": RESULT_CLASS,
        "qualification_evidence": False,
        "player_count": options.player_count,
        "seat_numbering": f"pilot seats 1..{options.player_count}; engine seats 0..{options.player_count - 1}",
        "decks": [
            {
                "seat": index,
                "deck_id": deck.deck_id,
                "deck_name": deck.name,
                "source_file": _relative_source(root, deck.source_path),
                "source_file_sha256": _file_sha256(deck.source_path),
                "deck_hash": deck.deck_hash,
                # copied from the gate's own plan, not observed in the engine
                "group": "plan",
            }
            for index, deck in enumerate(decks, start=1)
        ],
        "extra_deck_selection": {
            "mode": "explicit" if explicit else "seeded" if extras else "none",
            "selection_seed": None if explicit or not extras else EXTRA_DECK_SELECTION_SEED,
            "stems": [Path(d.source_path).stem for d in extras if d.source_path],
        },
        "replay_claim": (
            f"NOT_CLAIMED: the semantic tape model holds at most {tape_max_seats()} seats"
            if options.player_count > tape_max_seats()
            else None
        ),
        "pod": "reference_x2_plus_precons" if extras else "reference_x2",
        "table_a5": _is_table_a5(decks),
        "table_a5_basis": "true only when the seats are exactly the five A5 precons "
        "(seats_5_6_part_b_report.md); seats 1-4 of this gate are reference decks",
        "jar": jar,
        "checks": checks.render(),
        "check_groups": checks.group_summary(),
        "engine_checks_passed": checks.group_passed("engine"),
        "plan_checks_passed": checks.group_passed("plan"),
        "all_checks_passed": checks.all_passed,
    }


def _file_sha256(source_path: str | None) -> str | None:
    """SHA-256 of a deck file; None (unknown, never a digest of nothing) when unreadable."""
    if source_path is None:
        return None
    try:
        return hashlib.sha256(Path(source_path).read_bytes()).hexdigest()
    except OSError:
        return None


def _is_table_a5(decks: Sequence[RulesDeckInput]) -> bool:
    stems = [
        deck.deck_id.removeprefix(PRECON_FAMILY_PREFIX).split("/", 1)[0]
        for deck in decks
        if deck.deck_id.startswith(PRECON_FAMILY_PREFIX)
    ]
    return len(stems) == len(decks) and set(stems) == TABLE_A5_PRECONS


def _jar_after_run(options: GateOptions, jar: dict[str, Any], checks: _Checks) -> dict[str, Any]:
    """Hash the archive again after the run: a changed or vanished archive is a red check."""
    if options.jar is None:
        return jar
    try:
        after: str | None = jar_identity(options.jar)["sha256"]
    except GateConfigError:
        after = None
    unchanged = after is not None and after == jar["sha256"]
    checks.add("jar_unchanged", unchanged)
    return {**jar, "sha256_after_run": after, "unchanged": unchanged}


def _plan_checks(checks: _Checks, count: int = 1) -> None:
    # build_gate_setup raises on any seat gap, so a returned setup is a passed plan check.
    for _ in range(count):
        checks.add("seat_plan_contiguous", True)


def _config_error(exc: Exception) -> int:
    print(f"error: {exc}", file=sys.stderr)
    return 2


def _prepare(args: argparse.Namespace) -> tuple[GateOptions, dict[str, Any]] | int:
    try:
        options = resolve_options(args)
        jar = jar_identity(options.jar)
        if options.jar is not None:
            command = bridge_command_for_jar(options.jar)
            options = replace(options, command=command)
            # what the bridge JVM really gets: COMMANDER_LAB_XMAGE_JVM_FLAGS is spliced in
            jar["command"] = list(_with_jvm_flags(command))
            jar["jvm_flags_env"] = os.environ.get(XMAGE_JVM_FLAGS_ENV) or None
        return options, jar
    except GateConfigError as exc:
        return _config_error(exc)


def cmd_single(args: argparse.Namespace) -> int:
    prepared = _prepare(args)
    if isinstance(prepared, int):
        return prepared
    options, jar = prepared
    root = Path(args.root)
    try:
        scenario, decks, pilots = build_gate_setup(
            root, args.seed, options.player_count, options.extra_decks
        )
        runner = _make_runner(options)
    except GateConfigError as exc:
        return _config_error(exc)
    result = runner.run(scenario=scenario, decks=decks, pilots=pilots)
    summary = summarize_result(result, GATE_LABEL)
    passed = bool(result.terminal)
    if options.extended:
        checks = _Checks()
        _plan_checks(checks)
        checks.add_all(result_seat_checks(result, options.player_count))
        jar = _jar_after_run(options, jar, checks)
        summary["seat_gate"] = seat_gate_block(root, options, decks, checks, jar)
        passed = passed and checks.all_passed
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if passed else 1


def cmd_replay(args: argparse.Namespace) -> int:
    prepared = _prepare(args)
    if isinstance(prepared, int):
        return prepared
    options, jar = prepared
    root = Path(args.root)
    try:
        if options.player_count > tape_max_seats():
            raise GateConfigError(
                f"the semantic replay tape holds at most {tape_max_seats()} seats; "
                f"replay with {options.player_count} seats is not claimed (use single or batch)"
            )
        setup = build_gate_setup(root, args.seed, options.player_count, options.extra_decks)
        runner = _make_runner(options)
    except GateConfigError as exc:
        return _config_error(exc)
    checks = _Checks()
    runs = []
    for _ in range(2):
        scenario, decks, pilots = build_gate_setup(
            root, args.seed, options.player_count, options.extra_decks
        )
        result = runner.run(scenario=scenario, decks=decks, pilots=pilots)
        runs.append(summarize_result(result, GATE_LABEL))
        if options.extended:
            checks.add_all(result_seat_checks(result, options.player_count))
    # C1: the verdict comes from the semantic replay tape system (two
    # fresh-process recordings compared step by step, then a third fresh process
    # consuming the first tape); the twin transcript hash is a diagnostic.
    scenario, decks, pilots = setup
    with tempfile.TemporaryDirectory(prefix="real-deck-tapes-") as tape_dir:
        tape = run_semantic_tape_replay(
            runner, scenario=scenario, decks=decks, pilots=pilots, tape_dir=tape_dir
        )
        if options.extended:
            _plan_checks(checks)
            for name in ("first.tape.json", "second.tape.json"):
                checks.add_all(
                    tape_seat_checks(read_tape(Path(tape_dir) / name), options.player_count, decks)
                )
    semantic_match = tape.passed
    natural_terminal_runs_verified = all(run["terminal"] is True for run in runs)
    gate_passed = semantic_match and natural_terminal_runs_verified
    if options.extended:
        jar = _jar_after_run(options, jar, checks)
        gate_passed = gate_passed and checks.all_passed
    twin_match = runs[0]["semantic_transcript_sha256"] == runs[1]["semantic_transcript_sha256"]
    raw_match = runs[0]["raw_result_sha256"] == runs[1]["raw_result_sha256"]
    payload = {
        "gate": GATE_LABEL,
        "seed": args.seed,
        "semantic_replay_match": semantic_match,
        "usability_gate_passed": gate_passed,
        "natural_terminal_runs_verified": natural_terminal_runs_verified,
        "semantic_replay_scope": "bounded_decision_tape_with_native_concessions",
        "full_natural_terminal_replay_validated": False,
        "semantic_tape": tape.model_dump(mode="json"),
        "twin_transcript_hash_match": twin_match,
        "raw_result_match": raw_match,
        "bit_exact_replay_validated": False,
        "runs": runs,
    }
    if options.extended:
        payload["seat_gate"] = seat_gate_block(root, options, decks, checks, jar)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if gate_passed else 1


def cmd_batch(args: argparse.Namespace) -> int:
    if type(args.count) is not int or args.count < 1:
        print("batch count must be a positive integer", file=sys.stderr)
        return 2
    prepared = _prepare(args)
    if isinstance(prepared, int):
        return prepared
    options, jar = prepared
    root = Path(args.root)
    cases: list[FullGameBatchCase] = []
    try:
        for offset in range(args.count):
            seed = args.base_seed + offset
            scenario, decks, pilots = build_gate_setup(
                root, seed, options.player_count, options.extra_decks
            )
            cases.append(
                FullGameBatchCase(
                    case_id=_scenario_id(options.player_count, seed),
                    scenario=scenario,
                    decks=decks,
                    pilots=pilots,
                )
            )
        runner = _make_runner(options)
    except GateConfigError as exc:
        return _config_error(exc)
    batch = XmageFullGameBatchRunner(runner, Path(args.out_dir))
    report = batch.run(tuple(cases), resume=True, retry_failed=False)
    gate_passed = (
        report.total_cases == args.count
        and report.completed_cases == args.count
        and report.failed_cases == 0
        and [record.case_id for record in report.records] == [case.case_id for case in cases]
        and all(
            record.status == "completed"
            and record.result is not None
            and record.result.terminal is True
            and record.result.scenario == case.scenario
            and record.result.result_payload.get("terminal") is True
            and type(record.result.result_payload.get("seed")) is int
            and record.result.result_payload.get("seed") == case.scenario.seed
            for record, case in zip(report.records, cases, strict=True)
        )
    )
    summary: dict[str, Any] = {
        "gate": GATE_LABEL,
        "usability_gate_passed": gate_passed,
        "evidence_scope": "terminal_results_with_content_addressed_completed_reuse",
        "total_cases": report.total_cases,
        "completed_cases": report.completed_cases,
        "failed_cases": report.failed_cases,
        "resumed_cases": report.resumed_cases,
        "records": [
            {
                "case_id": record.case_id,
                "status": record.status,
                "elapsed_seconds": record.elapsed_seconds,
                "failure_class": (
                    str(record.failure_class) if record.failure_class is not None else None
                ),
                "failure_message": record.failure_message,
                "decision_count": (
                    record.result.decision_count if record.result is not None else None
                ),
                "terminal": record.result.terminal if record.result is not None else None,
                "winner_seats": (
                    list(record.result.winner_seats) if record.result is not None else None
                ),
            }
            for record in report.records
        ],
    }
    if options.extended:
        checks = _Checks()
        by_id = {record.case_id: record for record in report.records}
        for case in cases:
            _plan_checks(checks)
            record = by_id.get(case.case_id)
            # a failed record carries no result (FullGameBatchRecord enforces it), so a
            # missing result stays unknown; no status condition is needed here
            result = record.result if record is not None else None
            checks.add_all(result_seat_checks(result, options.player_count))
        jar = _jar_after_run(options, jar, checks)
        summary["seat_gate"] = seat_gate_block(root, options, cases[0].decks, checks, jar)
        summary["usability_gate_passed"] = gate_passed and checks.all_passed
        gate_passed = summary["usability_gate_passed"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if gate_passed else 1


def _positive_count(value: str) -> int:
    count = int(value)
    if count < 1:
        raise argparse.ArgumentTypeError("batch count must be positive")
    return count


def _add_seat_arguments(parser: argparse.ArgumentParser, *, sub: bool) -> None:
    # On the sub-parsers the default is SUPPRESS: an option given before the command must not
    # be overwritten by the sub-parser's own default.
    default: Any = argparse.SUPPRESS if sub else None
    parser.add_argument(
        "--player-count",
        type=_seat_count,
        default=default,
        help=f"seats at the table: {MIN_PLAYER_COUNT}, 5 or {MAX_PLAYER_COUNT} "
        f"(default {DEFAULT_PLAYER_COUNT})",
    )
    parser.add_argument(
        "--extra-decks",
        type=_stem_list,
        default=default,
        help="comma-separated precon file stems for seats 5 and 6 "
        "(default: seeded deterministic choice)",
    )
    parser.add_argument(
        "--jar",
        type=Path,
        default=default,
        help="bridge JAR; its SHA-256 goes into the report and it is the archive that runs",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Real-deck 4/5/6-seat technical usability gate")
    parser.add_argument("--root", default=str(ROOT))
    _add_seat_arguments(parser, sub=False)
    sub = parser.add_subparsers(dest="command", required=True)
    single = sub.add_parser("single")
    single.add_argument("--seed", type=int, default=BASE_SEED)
    single.add_argument("--out", required=True)
    _add_seat_arguments(single, sub=True)
    single.set_defaults(func=cmd_single)
    replay = sub.add_parser("replay")
    replay.add_argument("--seed", type=int, default=BASE_SEED)
    replay.add_argument("--out", required=True)
    _add_seat_arguments(replay, sub=True)
    replay.set_defaults(func=cmd_replay)
    batch = sub.add_parser("batch")
    batch.add_argument("--base-seed", type=int, default=BASE_SEED)
    batch.add_argument("--count", type=_positive_count, default=10)
    batch.add_argument("--out-dir", required=True)
    _add_seat_arguments(batch, sub=True)
    batch.set_defaults(func=cmd_batch)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
