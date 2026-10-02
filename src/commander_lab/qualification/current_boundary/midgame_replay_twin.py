"""AF09 Phase 2: clean-process replay twins of the REPLAY/RNG rows on the midgame lane.

The five replay/RNG obligations of the provider denominator
(``REPLAY_CLEAN_PROCESS``, ``REPLAY_DECISION_TAPE``, ``REPLAY_EVENT_TAPE``,
``REPLAY_STATE_HASHES``, ``RNG_RULES_TAPE``) are one scenario: P1 casts Burn Down
the House, chooses the Devil mode and three Devil tokens enter; the start-of-game
library shuffle (CR 103.2) is the Rules RNG operation. Each row then asks one
property of a clean replay of that scenario. This module produces the twin on
the production midgame lane and maps it to each row's own property.

The Rules RNG is taped with its *results*, not only call counts: the engine
reports each library shuffle's result as a digest of the permutation it left
the library in, relative to the deck's own first-seen order
(``get_rules_rng_tape``, an orchestration channel of digests only). The same
seed reproduces it in every process; a live control in a third process proves
that a different seed changes it.

Record and replay
-----------------

* **Record** (process A): the row's own decision script runs on the generic
  production executor (:func:`midgame_rows.execute_row`). Every distinct engine
  decision the process meets is taped with the engine's live Rules-RNG
  coordinate and results and a privileged state digest (``get_rules_rng_tape``),
  the qualified WS218 canonical digests of the decider's own observation, and
  the WS218 semantic fingerprints of what was selected. Every state-changing request the process sent (decision answers and
  arrival completions) is kept in order: that is the external input stream.
* **Replay** (process B, a fresh JVM): the record is constructed again with the
  same seed, and the external input stream is re-issued *from the tape alone*.
  The script is never read. Each recorded answer is resolved to the engine's
  offered option with the same semantic fingerprint; zero or several matches
  fail closed (``CHOSEN_OPTION_AMBIGUOUS``), never a first match.

The two runs are compared by :func:`replay_twins.compare_twin_runs` (the AF09
twin contract): fixture, build, Lab source, distinct observed processes, Rules
RNG binding and coordinates, the decision tape, the canonical event tape, the
checkpoint digest chain and each process's own terminal observation (the
replay's terminal is read from its own engine, never copied from the record).
Process-local identifiers (decision ids and native object ids) are recorded
separately and never compared; that they DIFFER between the processes while
every digest is equal is the evidence that the digests exclude process-local
identity. The game id is deliberately the same in both processes.

A replay whose engine offers a different frame for the same inputs and seed, or
whose tapes compare unequal, is a demonstrated replay violation (FAIL), never an
unexecuted row.

Nothing here computes legality, mutates engine state outside the two recorded
request kinds, or decides a Rules question.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from commander_lab.semantic_replay.fingerprint import (
    legal_set_digest,
    option_fingerprint,
    principal_observation_digest,
    public_state_digest,
)

from . import bridge_launcher
from . import midgame_lane as ml
from . import midgame_rows as midgame_rows_mod
from . import receipts as receipt_mod
from . import replay_twins as twins

ROWS: tuple[str, ...] = (
    "REPLAY_CLEAN_PROCESS",
    "REPLAY_DECISION_TAPE",
    "REPLAY_EVENT_TAPE",
    "REPLAY_STATE_HASHES",
    "RNG_RULES_TAPE",
)
EXECUTION_MODE = "AF09_MIDGAME_CLEAN_PROCESS_REPLAY_TWIN"
TEST_IDENTITY_PREFIX = "af09-midgame-replay-twin#"
DOCUMENT_SCHEMA = "commander-lab.af09-midgame-replay-twin/1.0.0"
LANE = "xmage-midgame-lane"

#: The request kinds that change engine state. Everything else is a read.
STATE_CHANGING = frozenset({"submit_midgame_decision", "submit_action", "complete_midgame_arrival"})
_NATIVE_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class ReplayTwinRowError(RuntimeError):
    """The row cannot be twinned; the message names the exact reason."""


class ReplayDivergence(ReplayTwinRowError):
    """The engine answered the same inputs and seed differently: a demonstrated violation."""


def rules_rng_tape(client: ml.MidgameLaneClient) -> dict[str, Any]:
    """The engine's Rules-RNG results and privileged state digest (digests only)."""
    response = client.request("get_rules_rng_tape", None)
    if not response.get("success"):
        raise ReplayTwinRowError(f"get_rules_rng_tape failed closed: {response.get('errors')}")
    payload = dict(response.get("payload") or {})
    if not isinstance(payload.get("rules_random_calls"), int) or not payload.get(
        "privileged_state_digest"
    ):
        raise ReplayTwinRowError("get_rules_rng_tape returned no RNG coordinate or digest")
    return payload


def row_spec(fixture_id: str) -> midgame_rows_mod.RowSpec:
    """The executor spec of the replay scenario, bound to the record's own tokens.

    The tokens are free text written before any engine existed; each binding
    states which engine event, frame or observed state it names. The tape is
    read from the engine's first event: the Rules RNG operation of these rows is
    the start-of-game library shuffle (CR 103.2), which precedes the arrival.
    """
    if fixture_id not in ROWS:
        raise ReplayTwinRowError(f"{fixture_id} is not a replay/RNG row")
    check = midgame_rows_mod.TerminalCheck
    devils = check("tokens_created", card_identity="Devil", value=3)
    return midgame_rows_mod.RowSpec(
        mana_sources=tuple(f"obj:replay-mountain-{index}" for index in range(1, 6)),
        mode_bindings=(("create_devils", "Devil creature tokens"),),
        terminal_checks=(devils,),
        observe_from_game_start=True,
        token_bindings=(
            (
                "rules_rng:library_shuffle:P1",
                check("events", event_type="LIBRARY_SHUFFLED", where=(("player_player", "P1"),)),
            ),
            (
                "decision:choose_mode:create_devils",
                # The engine's own class for a modal spell's mode frame is "mode".
                check("selected_frame", value="mode", label="Devil creature tokens"),
            ),
            ("create_Devil_token:3", devils),
        ),
    )


# --------------------------------------------------------------------------- #
# Taping lane client
# --------------------------------------------------------------------------- #


class TapingLaneClient(ml.MidgameLaneClient):
    """A production lane client that also tapes each distinct pending decision.

    The only additional request is the orchestration channel
    ``get_rules_rng_tape``, issued once per distinct decision: the engine's
    live ``rules_random_calls``, its Rules-RNG results and a privileged state
    digest. It changes no engine state.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.checkpoints: list[dict[str, Any]] = []
        self._seen: set[str] = set()

    def pending_decision(
        self, *, attempts: int = 60, interval_s: float = 0.5
    ) -> dict[str, Any] | None:
        decision = super().pending_decision(attempts=attempts, interval_s=interval_s)
        if decision is None:
            return None
        decision_id = str(decision.get("decision_id") or "")
        if decision_id and decision_id not in self._seen:
            self._seen.add(decision_id)
            try:
                tape = rules_rng_tape(self)
            except ReplayTwinRowError as exc:
                raise ml.MidgameLaneError(str(exc)) from exc
            self.checkpoints.append(
                {
                    "decision": decision,
                    "rules_random_calls": tape["rules_random_calls"],
                    "privileged_state_digest": tape["privileged_state_digest"],
                }
            )
        return decision

    @property
    def pid(self) -> int | None:
        process: subprocess.Popen[str] | None = self._process
        return process.pid if process is not None else None


def open_taping_client(workspace: Path) -> TapingLaneClient:
    """The canonical midgame launch plan, as ``probe.open_client`` builds it."""
    plan = bridge_launcher.build_launch_plan("xmage", lane="midgame", xmage_workspace=workspace)
    return TapingLaneClient(plan.argv, plan.cwd, env_overrides=dict(plan.env_overrides))


# --------------------------------------------------------------------------- #
# Canonical tape entries
# --------------------------------------------------------------------------- #


def _options(decision: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(option) for option in decision.get("legal_options") or () if isinstance(option, dict)
    ]


def _native_ids(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [found for item in value.values() for found in _native_ids(item)]
    if isinstance(value, list):
        return [found for item in value for found in _native_ids(item)]
    return [value] if isinstance(value, str) and _NATIVE_ID.match(value) else []


def _fingerprints_by_option(
    decision: Mapping[str, Any], semantic_by_native: Mapping[str, str]
) -> dict[str, str]:
    """Each offered option's WS218 fingerprint plus its record occurrence identity.

    The WS218 fingerprint deliberately collides for indistinguishable objects
    (five Mountains). The record names each of them distinctly, and the engine
    binds every record object to a native id in each process
    (``placed_objects``); the semantic ids of the record objects an option names
    are therefore a process-independent occurrence identity. Objects the record
    does not name add nothing, so engine-created twins still collide and fail
    closed.
    """
    pilot_state = decision.get("pilot_state")
    state = pilot_state if isinstance(pilot_state, dict) else None
    prints = {}
    for option in _options(decision):
        occurrence = sorted(
            {
                semantic_by_native[native]
                for native in _native_ids(option)
                if native in semantic_by_native
            }
        )
        prints[str(option.get("option_id"))] = twins.sha256_json(
            {"ws218": option_fingerprint(option, state), "record_objects": occurrence}
        )
    return prints


def decision_identity(decision: Mapping[str, Any]) -> dict[str, Any]:
    """The process-independent identity of one engine decision frame.

    A frame without the decider's observation has no public or actor digest;
    it fails closed instead of hashing an empty state.
    """
    pilot_state = decision.get("pilot_state")
    if not isinstance(pilot_state, dict) or not pilot_state:
        raise ReplayTwinRowError(
            f"decision {str(decision.get('decision_id'))[:12]} carries no pilot_state"
        )
    state = pilot_state
    return {
        "decision_class": decision.get("decision_class"),
        "seat": decision.get("seat"),
        "minimum_selections": decision.get("minimum_selections"),
        "maximum_selections": decision.get("maximum_selections"),
        "legal_set_digest": legal_set_digest(_options(decision), state),
        "public_state_digest": public_state_digest(state),
        "observation_digest": principal_observation_digest(state),
    }


def _selected_option_ids(entry: Mapping[str, Any]) -> tuple[str, list[str], int | None]:
    """(decision id, selected option ids, numeric choice) of one answer request."""
    request = entry.get("request") or {}
    payload = request.get("payload") or {}
    if entry.get("message_type") == "submit_midgame_decision":
        response = payload.get("response") or {}
        numeric = response.get("numeric_choice")
        return (
            str(response.get("decision_id") or ""),
            [str(item) for item in response.get("selected_option_ids") or ()],
            numeric if isinstance(numeric, int) and not isinstance(numeric, bool) else None,
        )
    proposal = payload.get("proposal") or {}
    action_id = str(proposal.get("legal_action_id") or "")
    decision_id, _, option_id = action_id.partition(":")
    choices = proposal.get("choices") or {}
    selected = [str(item) for item in choices.get("selected_option_ids") or ()] or [option_id]
    numeric = choices.get("numeric_choice")
    return (
        decision_id,
        selected,
        numeric if isinstance(numeric, int) and not isinstance(numeric, bool) else None,
    )


def input_stream(
    tape: Sequence[Mapping[str, Any]],
    checkpoints: Sequence[Mapping[str, Any]],
    semantic_by_native: Mapping[str, str],
) -> list[dict[str, Any]]:
    """The ordered external inputs of one process, in process-independent form.

    A decision answer becomes the frame's identity plus the semantic
    fingerprints of what was selected; an arrival completion is kept as itself.
    A request the engine rejected changed nothing and is not an input.
    """
    by_decision = {
        str(checkpoint["decision"].get("decision_id")): checkpoint for checkpoint in checkpoints
    }
    stream: list[dict[str, Any]] = []
    for entry in tape:
        kind = str(entry.get("message_type"))
        if kind not in STATE_CHANGING or not (entry.get("response") or {}).get("success"):
            continue
        if kind == "complete_midgame_arrival":
            stream.append({"kind": "complete_midgame_arrival"})
            continue
        decision_id, selected, numeric = _selected_option_ids(entry)
        checkpoint = by_decision.get(decision_id)
        if checkpoint is None:
            raise ReplayTwinRowError(
                f"an answer names decision {decision_id[:12]} that was never taped"
            )
        decision = checkpoint["decision"]
        prints = _fingerprints_by_option(decision, semantic_by_native)
        missing = [option for option in selected if option not in prints]
        if missing:
            raise ReplayTwinRowError(
                f"an answer selected options the engine did not offer: {missing}"
            )
        stream.append(
            {
                "kind": "decision",
                "via": kind,
                "frame": decision_identity(decision),
                "selected_fingerprints": sorted(prints[option] for option in selected),
                "numeric_choice": numeric,
                "rules_random_calls": checkpoint.get("rules_random_calls"),
                "privileged_state_digest": checkpoint.get("privileged_state_digest"),
            }
        )
    return stream


def _canonical_value(value: Any, names: dict[str, str]) -> Any:
    if isinstance(value, str) and _NATIVE_ID.match(value):
        return names.setdefault(value, f"native#{len(names)}")
    return value


def canonical_events(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The engine's public event tape without process-local identity.

    Placed objects already carry their record semantic id. An object the engine
    created (a token) carries a native id, which is replaced by its order of
    first appearance: the same engine history yields the same labels in every
    process, a different history does not.
    """
    names: dict[str, str] = {}
    out = []
    for event in events:
        out.append(
            {
                str(key): _canonical_value(value, names)
                for key, value in sorted(event.items())
                if key != "sequence"
            }
        )
    return out


# --------------------------------------------------------------------------- #
# One process
# --------------------------------------------------------------------------- #


@dataclass
class ProcessRun:
    """What one fresh lane process observed (record or replay)."""

    role: str
    twin: twins.TwinRun
    execution: dict[str, Any] | None = None
    stream: list[dict[str, Any]] = field(default_factory=list)
    native_object_ids: dict[str, str] = field(default_factory=dict)
    divergence: bool = False


def _semantic_by_native(created: Mapping[str, Any]) -> dict[str, str]:
    placed = created.get("placed_objects") or {}
    return {str(native): str(semantic) for semantic, native in placed.items()}


def _process_identity(client: TapingLaneClient, role: str) -> twins.ProcessIdentity | None:
    pid = client.pid
    if pid is None:
        return None
    return twins.read_process_identity(pid, role=role, command=client._argv)


def _create(
    client: TapingLaneClient, record: Mapping[str, Any], seed: int, role: str
) -> dict[str, Any]:
    version = client.request("get_provider_version", None)
    if not version.get("success"):
        raise ReplayTwinRowError("get_provider_version failed closed")
    client.read_dimension_manifest()
    # One game id for both roles: it is process-local only by being reported
    # back, and the terminal digest must not differ by a name the Lab chose.
    game_id = f"af09-{record['fixture_id']}"
    created = client.request(
        "create_midgame_game",
        {
            "game_id": game_id,
            "plan_id": game_id,
            "seed": seed,
            "requested_starting_state": dict(record),
        },
    )
    if not created.get("success"):
        raise ReplayTwinRowError(f"creation refused: {created.get('errors')}")
    started = client.request("start_midgame_game", None)
    if not started.get("success"):
        raise ReplayTwinRowError(f"start refused: {started.get('errors')}")
    return dict(created.get("payload") or {})


def _rules_rng(
    created: Mapping[str, Any],
    seed: int,
    stream: Sequence[Mapping[str, Any]],
    terminal_calls: Any,
    results: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """The Rules RNG binding, its operations with results, and its coordinates.

    First every Rules-RNG operation the engine reported, in engine order, each
    with its own ``before``/``after`` call coordinates and its result digest.
    Then one coordinate per answered decision: the engine's
    ``rules_random_calls`` when the decision was asked (``before``) and when
    the next one was asked or the run ended (``after``), so a coordinate is the
    Rules randomness the answer let the engine consume.
    """
    binding = dict(created.get("rules_seed_binding") or {})
    acknowledged = (
        binding.get("explicit_seed")
        if binding.get("rules_seed_explicit") is True and binding.get("rules_seed_matches") is True
        else None
    )
    calls = [entry.get("rules_random_calls") for entry in stream if entry.get("kind") == "decision"]
    operations = [
        {
            "operation": str(entry.get("operation")),
            "sequence": entry.get("sequence"),
            "seat": entry.get("seat"),
            "before": entry.get("before"),
            "after": entry.get("after"),
            "library_size": entry.get("library_size"),
            "result_digest": entry.get("result_digest"),
        }
        for entry in results
    ]
    coordinates = [
        *operations,
        *(
            {
                "sequence": index,
                "before": before,
                "after": calls[index + 1] if index + 1 < len(calls) else terminal_calls,
            }
            for index, before in enumerate(calls)
        ),
    ]
    return {
        "requested_seed": seed,
        "acknowledged_seed": acknowledged,
        "classification": "EXPLICIT_RULES_SEED" if acknowledged == seed else "UNACKNOWLEDGED",
        "controlled": acknowledged == seed,
        "rng_credit": "RULES_RNG_COORDINATES_PER_DECISION",
        "rng_call_coordinates": coordinates,
        "seed_scope": binding.get("seed_scope"),
    }


def _final_readback(
    client: TapingLaneClient,
) -> tuple[dict[str, Any], list[dict[str, Any]], int, list[dict[str, Any]], str]:
    """Pure reads of the parked engine after the last input (none is taped).

    Returns the observation, the public event tape, the final Rules-RNG call
    count, every Rules-RNG result and the final privileged state digest; an
    unreadable RNG tape fails closed.
    """
    client.pending_decision(attempts=5)
    observation = client.complete_arrival().get("observation") or {}
    events = client.events(0).get("events") or []
    tape = rules_rng_tape(client)
    results = [dict(entry) for entry in tape.get("rules_rng_results") or ()]
    return (
        dict(observation),
        [dict(event) for event in events],
        int(tape["rules_random_calls"]),
        results,
        str(tape["privileged_state_digest"]),
    )


def _terminal(observation: Mapping[str, Any], privileged_state_digest: str) -> dict[str, Any]:
    """This process's own terminal: its observation and its privileged state.

    Nothing is taken from the other process: the record's evaluated terminal
    facts stay in its execution document and are never part of the compared
    terminal.
    """
    return {
        "complete": True,
        "kind": "OBLIGATION_TERMINAL",
        "observation_digest": twins.sha256_json(_strip_ids(observation)),
        "privileged_state_digest": privileged_state_digest,
    }


def _strip_ids(value: Any, names: dict[str, str] | None = None) -> Any:
    names = {} if names is None else names
    if isinstance(value, dict):
        return {str(key): _strip_ids(item, names) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [_strip_ids(item, names) for item in value]
    return _canonical_value(value, names)


def _twin_run(
    *,
    role: str,
    record: Mapping[str, Any],
    seed: int,
    build: Mapping[str, Any],
    lab_source: Mapping[str, Any],
    client: TapingLaneClient,
    created: Mapping[str, Any],
    stream: list[dict[str, Any]],
    events: list[dict[str, Any]],
    observation: Mapping[str, Any],
    terminal_calls: Any,
    results: Sequence[Mapping[str, Any]],
    terminal_privileged_digest: str,
) -> twins.TwinRun:
    decisions = [
        {
            "index": index,
            "frame": entry["frame"],
            "selected_fingerprints": entry["selected_fingerprints"],
            "numeric_choice": entry["numeric_choice"],
        }
        for index, entry in enumerate(entry for entry in stream if entry["kind"] == "decision")
    ]
    checkpoints = [
        {
            "index": index,
            "position": position,
            "public_state_digest": entry["frame"]["public_state_digest"],
            "observation_digest": entry["frame"]["observation_digest"],
            "legal_set_digest": entry["frame"]["legal_set_digest"],
            "privileged_state_digest": entry["privileged_state_digest"],
            "rules_random_calls": entry["rules_random_calls"],
        }
        for index, (position, entry) in enumerate(
            (position, entry)
            for position, entry in enumerate(stream)
            if entry["kind"] == "decision"
        )
    ]
    return twins.TwinRun(
        role=role,
        candidate="xmage",
        fixture_identity={
            "fixture_id": record["fixture_id"],
            "requested_state_digest": record.get("requested_state_digest"),
            "obligation_digest": record.get("obligation_digest"),
            "seed": seed,
            "lane": LANE,
            "player_count": len(record.get("players") or ()),
        },
        candidate_build=dict(build),
        lab_source=dict(lab_source),
        process=_process_identity(client, role),
        rules_rng=_rules_rng(created, seed, stream, terminal_calls, results),
        decisions=decisions,
        semantic_events=canonical_events(events),
        checkpoint_state_hashes=checkpoints,
        terminal=_terminal(observation, terminal_privileged_digest),
        process_local_identifiers={
            "game_id": created.get("game_id"),
            "native_object_ids": dict(sorted((created.get("placed_objects") or {}).items())),
            "decision_ids": [
                str(checkpoint["decision"].get("decision_id")) for checkpoint in client.checkpoints
            ],
        },
    )


def _build(client: TapingLaneClient) -> dict[str, Any]:
    return {
        "engine_commit": client.engine_commit,
        "engine_artifact": dict(client.engine_artifact or {}),
    }


def record_process(
    workspace: Path,
    record: Mapping[str, Any],
    *,
    seed: int,
    lab_source: Mapping[str, Any],
    client_factory: Any = open_taping_client,
) -> ProcessRun:
    """Process A: the row's own script on the generic production executor."""
    with client_factory(workspace) as client:
        created = _create(client, record, seed, "RECORD")
        semantic_by_native = _semantic_by_native(created)
        execution = midgame_rows_mod.execute_row(
            client, dict(record), created, row_spec(str(record["fixture_id"]))
        )
        stream = input_stream(client.tape, client.checkpoints, semantic_by_native)
        observation, events, calls, results, privileged = _final_readback(client)
        document = execution.document()
        twin = _twin_run(
            role="RECORD",
            record=record,
            seed=seed,
            build=_build(client),
            lab_source=lab_source,
            client=client,
            created=created,
            stream=stream,
            events=events,
            observation=observation,
            terminal_calls=calls,
            results=results,
            terminal_privileged_digest=privileged,
        )
        return ProcessRun(
            "RECORD",
            twin,
            execution=document,
            stream=stream,
            native_object_ids=dict(created.get("placed_objects") or {}),
        )


def _resolve(
    decision: Mapping[str, Any], wanted: Sequence[str], semantic_by_native: Mapping[str, str]
) -> list[str]:
    """The offered option ids carrying exactly the recorded fingerprints.

    Each recorded fingerprint must name exactly one offered option. Several
    offers sharing a fingerprint are indistinguishable to the tape, so no
    choice among them is made: the replay fails closed.
    """
    prints = _fingerprints_by_option(decision, semantic_by_native)
    chosen: list[str] = []
    for fingerprint in wanted:
        matches = [option for option, value in prints.items() if value == fingerprint]
        if len(matches) != 1:
            raise ReplayTwinRowError(
                f"CHOSEN_OPTION_AMBIGUOUS: a recorded selection matched {len(matches)} offers"
            )
        chosen.append(matches[0])
    return chosen


def _submit(
    client: TapingLaneClient, decision: Mapping[str, Any], option_ids: list[str], via: str
) -> None:
    if via == "submit_midgame_decision":
        # Raises MidgameLaneError when the engine rejects the answer.
        client.submit_options(dict(decision), option_ids)
        return
    probe = midgame_rows_mod.probe_module()
    legal = probe.legal_actions(client)
    decision_id = str(decision.get("decision_id") or "")
    actions = [
        action
        for action in legal.get("actions") or ()
        if str(action.get("action_id") or "").partition(":")[0] == decision_id
        and str(action.get("action_id") or "").partition(":")[2] in option_ids
    ]
    if len(actions) != 1:
        raise ReplayTwinRowError(f"a replayed proposal matched {len(actions)} engine actions")
    # Exactly one engine action carries the recorded selection; never a first match.
    (matched,) = actions
    probe.submit_proposal(
        client,
        legal,
        matched,
        f"af09-replay-{len(client.checkpoints)}",
        selected_option_ids=option_ids if len(option_ids) > 1 else None,
    )


def replay_process(
    workspace: Path,
    record: Mapping[str, Any],
    recorded: ProcessRun,
    *,
    seed: int,
    lab_source: Mapping[str, Any],
    client_factory: Any = open_taping_client,
) -> ProcessRun:
    """Process B: the external inputs re-issued from the record's tape alone."""
    with client_factory(workspace) as client:
        created = _create(client, record, seed, "REPLAY")
        semantic_by_native = _semantic_by_native(created)
        failure: str | None = None
        divergence = False
        try:
            for position, entry in enumerate(recorded.stream):
                if entry["kind"] == "complete_midgame_arrival":
                    # As the record did: the engine parks on a decision first.
                    client.pending_decision(attempts=5)
                    client.complete_arrival()
                    continue
                decision = client.pending_decision()
                if decision is None:
                    raise ReplayDivergence(f"the engine went terminal before input {position}")
                if entry.get("numeric_choice") is not None:
                    raise ReplayTwinRowError(
                        "a recorded numeric answer is outside this replay consumer"
                    )
                if decision_identity(decision) != entry["frame"]:
                    # The replay never answers a frame it did not record.
                    raise ReplayDivergence(f"the engine frame at input {position} diverged")
                option_ids = _resolve(decision, entry["selected_fingerprints"], semantic_by_native)
                _submit(client, decision, option_ids, str(entry["via"]))
        except ReplayDivergence as exc:
            failure = str(exc)
            divergence = True
        except (ReplayTwinRowError, ml.MidgameLaneError) as exc:
            failure = str(exc)
        stream = input_stream(client.tape, client.checkpoints, semantic_by_native)
        observation, events, calls, results, privileged = _final_readback(client)
        twin = _twin_run(
            role="REPLAY",
            record=record,
            seed=seed,
            build=_build(client),
            lab_source=lab_source,
            client=client,
            created=created,
            stream=stream,
            events=events,
            observation=observation,
            terminal_calls=calls,
            results=results,
            terminal_privileged_digest=privileged,
        )
        twin.failure = failure
        if failure is not None:
            twin.terminal = {"complete": False, "kind": "REPLAY_FAILED_CLOSED", "detail": failure}
        return ProcessRun(
            "REPLAY",
            twin,
            stream=stream,
            native_object_ids=dict(created.get("placed_objects") or {}),
            divergence=divergence,
        )


# --------------------------------------------------------------------------- #
# Row properties
# --------------------------------------------------------------------------- #


def p1_seat(record: Mapping[str, Any]) -> int:
    """P1's seat index in the engine's seating order (the record's seat order)."""
    seated = sorted(record.get("players") or (), key=lambda player: player.get("seat", 0))
    for index, player in enumerate(seated):
        if player.get("player_id") == "P1":
            return index
    raise ReplayTwinRowError("the record seats no P1")


def _shuffle_results(run: ProcessRun) -> list[dict[str, Any]]:
    return [
        dict(entry)
        for entry in run.twin.rules_rng.get("rng_call_coordinates") or ()
        if entry.get("operation") == "LIBRARY_SHUFFLE"
    ]


def first_shuffle_digest(results: Sequence[Mapping[str, Any]], seat: int) -> str | None:
    """The result digest of the first library shuffle of ``seat``, if any."""
    for entry in results:
        if entry.get("operation") == "LIBRARY_SHUFFLE" and entry.get("seat") == seat:
            digest = entry.get("result_digest")
            return str(digest) if digest else None
    return None


def row_properties(
    fixture_id: str,
    record_run: ProcessRun,
    replay_run: ProcessRun,
    verified_twin: bool,
    *,
    seat: int = 0,
    seed_control: Mapping[str, Any] | None = None,
) -> dict[str, bool]:
    """The row's own property of the clean replay, each a check on the tapes.

    Every row also needs the scenario obligation (the record's script verified on
    the engine) and a verified twin. ``seat`` is P1's seat; ``seed_control`` is
    the live different-seed control (required by ``RNG_RULES_TAPE``).
    """
    execution = record_run.execution or {}
    decisions = record_run.twin.decisions
    events = record_run.twin.semantic_events
    common = {
        "scenario_obligation_observed": bool(execution.get("verified")),
        "clean_replay_equal_checkpoints": verified_twin,
    }
    if fixture_id == "REPLAY_CLEAN_PROCESS":
        own = {
            "replay_consumed_only_the_tape": replay_run.twin.failure is None
            and len(replay_run.stream) == len(record_run.stream),
        }
    elif fixture_id == "REPLAY_DECISION_TAPE":
        own = {
            "decision_tape_records_semantic_selections": bool(decisions)
            and all(decision["selected_fingerprints"] for decision in decisions),
            "mode_choice_taped": any(
                decision["frame"]["decision_class"] == "mode" for decision in decisions
            ),
        }
    elif fixture_id == "REPLAY_EVENT_TAPE":
        own = {
            "event_tape_records_the_tokens": sum(
                1 for event in events if event.get("type") == "CREATED_TOKEN"
            )
            == 3,
            "event_tape_free_of_native_ids": not any(
                isinstance(value, str) and _NATIVE_ID.match(value)
                for event in events
                for value in event.values()
            ),
        }
    elif fixture_id == "REPLAY_STATE_HASHES":
        record_ids = set(record_run.native_object_ids.values())
        replay_ids = set(replay_run.native_object_ids.values())
        own = {
            "process_local_identity_differs": bool(record_ids)
            and bool(replay_ids)
            and record_ids.isdisjoint(replay_ids),
            "public_and_actor_hashes_recorded": bool(record_run.twin.checkpoint_state_hashes)
            and all(
                entry["public_state_digest"] and entry["observation_digest"]
                for entry in record_run.twin.checkpoint_state_hashes
            ),
            "privileged_hashes_recorded": bool(record_run.twin.checkpoint_state_hashes)
            and all(
                entry.get("privileged_state_digest")
                for entry in record_run.twin.checkpoint_state_hashes
            )
            and bool(record_run.twin.terminal.get("privileged_state_digest")),
        }
    elif fixture_id == "RNG_RULES_TAPE":
        shuffles = _shuffle_results(record_run)
        p1 = [entry for entry in shuffles if entry.get("seat") == seat]
        control = seed_control or {}
        own = {
            # Every Rules-RNG operation is taped with the randomness it consumed
            # and its result.
            "rules_rng_results_recorded": bool(shuffles)
            and all(
                isinstance(entry.get("before"), int)
                and isinstance(entry.get("after"), int)
                and entry["after"] > entry["before"]
                and entry.get("result_digest")
                for entry in shuffles
            ),
            "p1_library_shuffle_result_taped": bool(p1)
            and any(
                event.get("type") == "LIBRARY_SHUFFLED" and event.get("player_player") == "P1"
                for event in events
            ),
            # The replay reproduced every result (the twin compares them); a
            # different seed in a third fresh process changed P1's result.
            "rng_result_depends_on_seed": control.get("detected") is True,
            "rng_tape_separate_from_decisions": all(
                "rules_random_calls" not in decision for decision in decisions
            ),
        }
    else:
        raise ReplayTwinRowError(f"{fixture_id} is not a replay/RNG row")
    return {**common, **own}


# --------------------------------------------------------------------------- #
# Producer
# --------------------------------------------------------------------------- #


def lab_source_identity(root: Path) -> dict[str, Any]:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()

    return {
        "commit": git("rev-parse", "HEAD"),
        "tree": git("rev-parse", "HEAD^{tree}"),
        "clean": git("status", "--porcelain") == "",
    }


def positive_receipt(
    fixture_id: str,
    record: Mapping[str, Any],
    document: Mapping[str, Any],
    *,
    candidate_commit: str,
    runner_digest: str,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema_version": receipt_mod.POSITIVE_FIXTURE_RECEIPT_SCHEMA,
        "candidate": "xmage",
        "candidate_commit": candidate_commit,
        "runner_digest": runner_digest,
        "fixture_id": fixture_id,
        "test_identity": TEST_IDENTITY_PREFIX + fixture_id,
        "execution_mode": EXECUTION_MODE,
        "obligation_exercised": {
            "required_events": list(
                (record.get("expected_events") or {}).get("required_events") or ()
            ),
            "terminal_postconditions": list(record.get("terminal_postconditions") or ()),
            "requested_state_digest": record.get("requested_state_digest"),
            "obligation_digest": record.get("obligation_digest"),
        },
        "observed_assertion": {
            "row_properties": dict(document["row_properties"]),
            "twin_digest": document["twin_digest"],
            "comparison_verdict": document["clean_process_twin"]["verdict"],
        },
        "assertion_kind": "POSITIVE_BEHAVIOUR",
        "assertion_class": "BEHAVIOUR_OBSERVED",
        "outcome": "PASS",
        "runtime_receipt_digest": document["twin_digest"],
    }
    receipt["receipt_digest"] = receipt_mod.document_digest(receipt)
    return receipt


def seed_control(
    workspace: Path,
    record: Mapping[str, Any],
    recorded: ProcessRun,
    *,
    seed: int,
    client_factory: Any = open_taping_client,
) -> dict[str, Any]:
    """Live negative control: a different seed must change P1's shuffle result.

    A third fresh process constructs the same record with ``seed + 1`` and
    reads the engine's Rules-RNG results once the game reached its first
    decision. If the result digest did not change, the taped result does not
    depend on the Rules RNG and is no replay evidence.
    """
    seat = p1_seat(record)
    recorded_digest = first_shuffle_digest(_shuffle_results(recorded), seat)
    control_seed = seed + 1
    with client_factory(workspace) as client:
        _create(client, record, control_seed, "SEED_CONTROL")
        if client.pending_decision() is None:
            raise ReplayTwinRowError("the seed control reached no decision")
        tape = rules_rng_tape(client)
    control_digest = first_shuffle_digest(tape.get("rules_rng_results") or (), seat)
    return {
        "control": "DIFFERENT_SEED_CHANGES_RULES_RNG_RESULT",
        "seat": seat,
        "seed": seed,
        "control_seed": control_seed,
        "recorded_result_digest": recorded_digest,
        "control_result_digest": control_digest,
        "detected": bool(recorded_digest)
        and bool(control_digest)
        and recorded_digest != control_digest,
    }


#: The comparison checks that bind identity and preconditions. A twin whose
#: failures are only outside this set compared the same build, source,
#: fixture and seed in distinct observed processes, and the engine still
#: answered differently: a demonstrated replay violation.
_PRECONDITION_CHECKS = frozenset(
    {
        "fixture_identity",
        "candidate_build",
        "lab_source",
        "process_identity_present",
        "process_identity_distinct",
        "rules_rng_acknowledged",
    }
)


def demonstrated_divergence(
    comparison: twins.TwinComparison, recorded: ProcessRun, replayed: ProcessRun
) -> dict[str, Any] | None:
    """The demonstrated replay violation of a twin, or None.

    Only when the record's own obligation was verified, every identity and
    precondition check passed, and either the engine offered a different
    frame for the same inputs (the replay failed closed on it) or a semantic
    tape compared unequal. A harness refusal (an ambiguous fingerprint, a
    missing observation) is never a demonstrated violation.
    """
    if not (recorded.execution or {}).get("verified"):
        return None
    failed = {check["check"] for check in comparison.checks if not check["passed"]}
    if failed & _PRECONDITION_CHECKS or any(
        name.startswith("required_section:") and name != "required_section:terminal_outcome"
        for name in failed
    ):
        return None
    semantic = sorted(
        failed
        & {
            "rules_rng",
            "decisions",
            "semantic_events",
            "checkpoint_state_hashes",
            "terminal_outcome",
        }
    )
    if replayed.divergence:
        return {
            "classification": "REPLAY_FRAME_DIVERGENCE",
            "detail": replayed.twin.failure,
            "differing_checks": semantic,
        }
    if replayed.twin.failure is not None:
        # The replay stopped on a harness refusal; its tapes are truncated, so
        # an unequal tape demonstrates nothing about the engine.
        return None
    if semantic:
        return {
            "classification": "REPLAY_TAPE_DIVERGENCE",
            "detail": [item for item in comparison.divergences if item.get("check") in semantic][
                :3
            ],
            "differing_checks": semantic,
        }
    return None


def twin_row(
    workspace: Path,
    record: Mapping[str, Any],
    *,
    seed: int,
    lab_source: Mapping[str, Any],
    client_factory: Any = open_taping_client,
) -> dict[str, Any]:
    """Record, replay, compare and evaluate one replay/RNG row."""
    fixture_id = str(record["fixture_id"])
    try:
        recorded = record_process(
            workspace, record, seed=seed, lab_source=lab_source, client_factory=client_factory
        )
        replayed = replay_process(
            workspace,
            record,
            recorded,
            seed=seed,
            lab_source=lab_source,
            client_factory=client_factory,
        )
    except (ReplayTwinRowError, ml.MidgameLaneError) as exc:
        return {"fixture_id": fixture_id, "verified": False, "detail": f"twin failed closed: {exc}"}
    control: dict[str, Any] | None = None
    if fixture_id == "RNG_RULES_TAPE":
        try:
            control = seed_control(
                workspace, record, recorded, seed=seed, client_factory=client_factory
            )
        except (ReplayTwinRowError, ml.MidgameLaneError) as exc:
            control = {
                "control": "DIFFERENT_SEED_CHANGES_RULES_RNG_RESULT",
                "detected": False,
                "detail": f"seed control failed closed: {exc}",
            }
    comparison = twins.compare_twin_runs(recorded.twin, replayed.twin)
    controls = twins.run_adversarial_controls(recorded.twin, replayed.twin)
    controls_ok = all(
        control.get("detected") for control in controls if control.get("applicable", True)
    )
    twin_document = twins.clean_process_twin_document(
        record=recorded.twin,
        replay=replayed.twin,
        comparison=comparison,
        adversarial_controls=controls,
    )
    verified_twin = bool(twin_document["verified"]) and controls_ok
    properties = row_properties(
        fixture_id,
        recorded,
        replayed,
        verified_twin,
        seat=p1_seat(record),
        seed_control=control,
    )
    divergence = demonstrated_divergence(comparison, recorded, replayed)
    document = {
        "schema_version": DOCUMENT_SCHEMA,
        "fixture_id": fixture_id,
        "execution_mode": EXECUTION_MODE,
        "clean_process_twin": twin_document,
        "adversarial_controls_all_detected": controls_ok,
        "row_properties": properties,
        "seed_control": control,
        "demonstrated_divergence": divergence,
        "record_execution": recorded.execution,
        "replay_failure": replayed.twin.failure,
        "process_local_identifiers": {
            "record": recorded.twin.process_local_identifiers,
            "replay": replayed.twin.process_local_identifiers,
        },
    }
    document["twin_digest"] = twins.sha256_json(twin_document)
    document["verified"] = all(properties.values())
    document["detail"] = (
        "clean-process twin verified with every row property"
        if document["verified"]
        else "not verified: " + ", ".join(name for name, held in properties.items() if not held)
    )
    if divergence is not None:
        document["verified"] = False
        document["detail"] = f"demonstrated replay violation: {divergence['classification']}"
    return document


def execute_and_persist(
    *,
    workspace: Path,
    records: Mapping[str, Mapping[str, Any]],
    candidate_commit: str,
    runner_digest: str,
    out_dir: Path,
    lab_root: Path,
    seed: int = 424242,
    fixtures: Sequence[str] | None = None,
    client_factory: Any = open_taping_client,
) -> dict[str, Any]:
    """Twin every replay/RNG row in fresh processes and persist its receipt.

    Earlier receipts of the selected rows are removed first. Only a verified row
    whose engine-reported build is the candidate commit earns a receipt.
    """
    selected = tuple(ROWS if fixtures is None else fixtures)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Every earlier replay-twin receipt goes, not only the selected rows': a
    # receipt credits only through the document of the run that wrote it.
    for fixture_id in ROWS:
        (out_dir / f"{TEST_IDENTITY_PREFIX.rstrip('#')}-{fixture_id}.json").unlink(missing_ok=True)
    lab_source = lab_source_identity(lab_root)
    rows: dict[str, Any] = {}
    for fixture_id in selected:
        record = records[fixture_id]
        document = twin_row(
            workspace, record, seed=seed, lab_source=lab_source, client_factory=client_factory
        )
        build = (document.get("clean_process_twin") or {}).get("candidate_build") or {}
        if build.get("engine_commit") != candidate_commit:
            # Nothing a foreign build did is credited or demonstrated here.
            if document.get("verified") or document.get("demonstrated_divergence"):
                document["detail"] = (
                    f"engine reported {build.get('engine_commit')}, "
                    f"not the candidate {candidate_commit}"
                )
            document["verified"] = False
            document["demonstrated_divergence"] = None
        if document.get("verified"):
            receipt = positive_receipt(
                fixture_id,
                record,
                document,
                candidate_commit=candidate_commit,
                runner_digest=runner_digest,
            )
            receipt_mod.persist(
                out_dir / f"{TEST_IDENTITY_PREFIX.rstrip('#')}-{fixture_id}.json", receipt
            )
            document["receipt_digest"] = receipt["receipt_digest"]
        rows[fixture_id] = document
    first_verified = next(
        (rows[fixture_id] for fixture_id in selected if rows[fixture_id].get("verified")), None
    )
    return {
        "schema_version": DOCUMENT_SCHEMA,
        "execution_mode": EXECUTION_MODE,
        "candidate": "xmage",
        "candidate_commit": candidate_commit,
        "runner_digest": runner_digest,
        "lab_source": lab_source,
        "rows_declared": len(rows),
        "rows_verified": sum(1 for document in rows.values() if document.get("verified")),
        "rows": rows,
        "clean_process_twin": (first_verified or {}).get("clean_process_twin"),
    }


def bound_receipt_digests(
    document: Mapping[str, Any] | None, *, candidate_commit: str, runner_digest: str
) -> dict[str, str]:
    """The receipt digest each row's credit must match, from a bound document.

    Empty unless the document is this lane's, names the candidate commit and
    the runner, and declares every replay/RNG row: a partial rerun, a foreign
    document or a stale receipt earns nothing.
    """
    if not document or document.get("execution_mode") != EXECUTION_MODE:
        return {}
    if (
        not candidate_commit
        or document.get("candidate_commit") != candidate_commit
        or document.get("runner_digest") != runner_digest
        or set((document.get("rows") or {}).keys()) != set(ROWS)
    ):
        return {}
    return {
        fixture_id: str(row["receipt_digest"])
        for fixture_id, row in (document.get("rows") or {}).items()
        if row.get("verified") and row.get("receipt_digest")
    }


def demonstrated_failures(
    document: Mapping[str, Any] | None, *, candidate_commit: str, runner_digest: str
) -> dict[str, dict[str, Any]]:
    """Rows whose twin demonstrated a replay violation, from a bound document.

    A frame or tape divergence under the same build, source, fixture, seed and
    inputs in distinct observed processes is a FAIL with its finding, never an
    unexecuted row. Only a document bound to the candidate commit and runner
    demonstrates anything.
    """
    if not document or document.get("execution_mode") != EXECUTION_MODE:
        return {}
    if (
        not candidate_commit
        or document.get("candidate_commit") != candidate_commit
        or document.get("runner_digest") != runner_digest
    ):
        return {}
    return {
        fixture_id: dict(row["demonstrated_divergence"])
        for fixture_id, row in (document.get("rows") or {}).items()
        if fixture_id in ROWS and row.get("demonstrated_divergence")
    }
