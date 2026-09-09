#!/usr/bin/env python3
"""WS-48 behavior session driver core (provider-neutral state machine).

Drives one ``NATIVE_STATE_LOAD`` behavior session through the
``commander-lab.rules-service/1.1.0`` protocol:

- emits ``CREATE_SESSION``;
- consumes ``SESSION_CREATED`` / ``QUALIFICATION_STATE`` (snapshots) /
  ``DECISION_FRAME`` (dispatches to selector matchers) / ``EVENT`` (feed) /
  ``SESSION_RESULT``;
- matches scripted ``decision_script`` entries against provider-offered legal
  options only (zero or multiple matches FAIL closed);
- answers scripted priority passes with the offered ``PASS`` option;
- verifies ``expected_events`` via :mod:`behavior_events` and
  ``terminal_postconditions`` via :mod:`behavior_postconditions`.

Magic legality is never computed here. The driver only selects among options
the provider offered, by semantic descriptor match.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"ws48_{name}", _HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


behavior_events = _load("behavior_events")
behavior_postconditions = _load("behavior_postconditions")

PROTOCOL = "commander-lab.rules-service/1.1.0"


class BehaviorFailure(Exception):
    """Fail-closed behavior error carrying a machine-readable code."""


class TerminalReached(Exception):
    """Raised when script + required events + postconditions are all satisfied."""


# Provider DECISION_FRAME kind -> (contract decision family, contract frame event).
# Frame-event names are contract-exact (e.g. target_decision_frame, not
# target_frame). Kinds absent here are non-scripted native intermediates
# (diagnostic decision_frame events only).
FRAME_FAMILY: dict[str, tuple[str, str]] = {
    "priority": ("priority", "priority_decision_frame"),
    "chooseModeForAbility": ("choose_mode", "choose_mode_frame"),
    "chooseTargetsFor": ("target", "target_decision_frame"),
    "chooseTarget": ("target", "target_decision_frame"),
    "payMana": ("mana_payment", "mana_payment_frame"),
    "declareAttackers": ("declare_attacker", "declare_attacker_frame"),
    "declareBlockers": ("declare_blocker", "declare_blocker_frame"),
    "confirmAction": ("choose_use", "choose_use_frame"),
    "chooseBinary": ("choice", "choice_frame"),
    "announceRequirements": ("announce_x", "announce_x_frame"),
    "chooseSingleEntityForEffect": ("choose_object", "choose_object_frame"),
    "orderSimultaneousSa": ("trigger_order", "trigger_order_frame"),
    "chooseCardsPile": ("pile", "pile_frame"),
    "combatDamage": ("target_amount", "target_amount_frame"),
    "amountDistribution": ("multi_amount", "multi_amount_frame"),
    "chooseSingleReplacementEffect": ("replacement_effect", "replacement_effect_frame"),
}


def frame_family(kind: str) -> str | None:
    entry = FRAME_FAMILY.get(kind)
    return entry[0] if entry else None


def synthesize_frame_events(kind: str, actor: str | None) -> list[str]:
    """Contract-level feed events for one offered native decision frame."""
    entry = FRAME_FAMILY.get(kind)
    if entry is None or actor is None:
        return []
    family, frame_event = entry
    if family == "priority":
        return [f"priority:{actor}", f"{frame_event}:{actor}"]
    return [f"{frame_event}:{actor}", f"decision_frame:{family}"]


def provider_command() -> list[str]:
    raw = os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD")
    if not raw:
        raise BehaviorFailure("PROVIDER_CMD_MISSING")
    return shlex.split(raw)


def submit(proc: Any, frame: dict[str, Any], option_id: str, tag: str) -> None:
    proc.stdin.write(
        json.dumps(
            {
                "protocol": PROTOCOL,
                "message_type": "SUBMIT_DECISION",
                "request_id": f"ws48-behavior-{tag}-{frame['payload']['decision_id']}",
                "session_id": frame.get("session_id"),
                "payload": {
                    "decision_id": frame["payload"]["decision_id"],
                    "option_id": option_id,
                },
            },
            separators=(",", ":"),
        )
        + "\n"
    )
    proc.stdin.flush()


def offered_by_kind(frame: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for opt in frame["payload"].get("options") or []:
        by_kind.setdefault(str(opt.get("kind")), []).append(opt)
    return by_kind


def normalize_actor(actor: str | None) -> str | None:
    """Map native lobby names (seat-N) to contract player ids (PN)."""
    if actor is None:
        return None
    if actor.startswith("seat-") and actor[5:].isdigit():
        return f"P{int(actor[5:])}"
    return actor


def kind_segments(kind: str) -> list[str]:
    """Split an option-kind descriptor into :-separated segments."""
    return str(kind).split(":")


def kind_has_ref(kind: str, ref: str) -> bool:
    """True iff ``ref`` occurs as a full token (no prefix collisions).

    Semantic refs (``obj:...``) contain colons themselves, so plain segment
    splitting cannot work. A ref matches when preceded by start/':' and
    followed by a character outside [A-Za-z0-9_-] (so ``obj:micro-target``
    does not match ``obj:micro-target-2``, and ``P2`` does not match
    ``obj:P2-bears``).
    """
    import re

    return (
        re.search(r"(?:(?<=:)|(?<=^))" + re.escape(ref) + r"(?![A-Za-z0-9_-])", str(kind))
        is not None
    )


def match_single_option(frame: dict[str, Any], predicate, rule: str) -> dict[str, Any]:
    """Select the unique offered option satisfying ``predicate(kind, option)``.

    Zero or multiple matches raise :class:`BehaviorFailure` (fail closed).
    """
    hits = [o for o in frame["payload"].get("options") or [] if predicate(str(o.get("kind")), o)]
    if len(hits) != 1:
        raise BehaviorFailure(
            f"OPTION_MATCH_{'ZERO' if not hits else 'MULTIPLE'}:{rule}:"
            f"{frame['payload'].get('decision_kind')}:{frame['payload'].get('decision_id')}"
        )
    return hits[0]


def match_pass_option(frame: dict[str, Any]) -> dict[str, Any]:
    return match_single_option(frame, lambda kind, _o: kind == "PASS", "scripted_pass")


def match_semantic_action_object(frame: dict[str, Any], semantic_id: str) -> dict[str, Any]:
    """Match a cast/activate action whose descriptor references ``semantic_id``."""

    def pred(kind: str, opt: dict[str, Any]) -> bool:
        return "FORGE_LEGAL_ACTION" in kind and kind_has_ref(kind, semantic_id)

    return match_single_option(frame, pred, f"semantic_action:{semantic_id}")


def match_semantic_object(frame: dict[str, Any], semantic_id: str) -> dict[str, Any]:
    """Match a target/object option bound to ``semantic_id``."""

    def pred(kind: str, _o: dict[str, Any]) -> bool:
        return kind_has_ref(kind, semantic_id) and (
            "SEMANTIC" in kind or "TARGET" in kind or "NATIVE_OPTION" in kind
        )

    return match_single_option(frame, pred, f"semantic_object:{semantic_id}")


def match_semantic_player(frame: dict[str, Any], player_id: str) -> dict[str, Any]:
    def pred(kind: str, _o: dict[str, Any]) -> bool:
        return kind == f"PLAYER:{player_id}" or (kind_has_ref(kind, player_id) and "PLAYER" in kind)

    return match_single_option(frame, pred, f"semantic_player:{player_id}")


def match_semantic_object_any(frame: dict[str, Any], candidates: list[str]) -> dict[str, Any]:
    """Select the first contract-listed ref (in contract order) that is offered.

    Every submission is constrained to contract-listed values; completion
    requires all of them (the entry advances only when none remain).
    """

    def offered(ref: str) -> list[dict[str, Any]]:
        out = []
        for o in frame["payload"].get("options") or []:
            kind = str(o.get("kind"))
            if kind_has_ref(kind, ref) and ("SEMANTIC" in kind or "TARGET" in kind):
                out.append(o)
        return out

    for ref in candidates:
        hits = offered(ref)
        if len(hits) > 1:
            raise BehaviorFailure(
                f"MULTI_TARGET_NATIVE_NONUNIQUE:{ref}:{frame['payload'].get('decision_id')}"
            )
        if hits:
            return hits[0]
    raise BehaviorFailure(
        f"MULTI_TARGET_ZERO_MATCH:{candidates}:{frame['payload'].get('decision_id')}"
    )


def match_semantic_key(frame: dict[str, Any], key: str) -> dict[str, Any]:
    """Match a provider-labeled selection key (MODE_KEY:/LOYALTY_KEY:).

    Keys are contract-vocabulary tokens bound to native parameters
    provider-side; matching is exact-token-or-fail-closed.
    """

    def pred(kind: str, _o: dict[str, Any]) -> bool:
        return kind_has_ref(kind, key)

    return match_single_option(frame, pred, f"semantic_key:{key}")


def match_commander_cast(
    frame: dict[str, Any], expected: dict[str, Any], record: dict[str, Any]
) -> dict[str, Any]:
    """Match a cast_commander action to the provider-offered commander action.

    Links commander_id -> semantic object ref via the record's commander-bound
    semantic objects, then matches the offered legal action by that ref.
    A declared from_zone is verified against the offered action's zone segment.
    """
    value = expected["selection"]["semantic_value"]
    commander_id = value.get("commander_id")
    obj_ref = None
    for o in record.get("semantic_objects") or []:
        if o.get("commander_id") == commander_id:
            obj_ref = o.get("semantic_id")
            break
    if obj_ref is None:
        raise BehaviorFailure(f"COMMANDER_OBJ_UNRESOLVABLE:{commander_id}")
    from_zone = value.get("from_zone")

    def pred(kind: str, _o: dict[str, Any]) -> bool:
        if "FORGE_LEGAL_ACTION" not in kind or not kind_has_ref(kind, obj_ref):
            return False
        return from_zone is None or f":{from_zone}:" in kind

    return match_single_option(frame, pred, f"cast_commander:{commander_id}")


def match_stack_object(frame: dict[str, Any], stack_ref: str, session: Session) -> dict[str, Any]:
    """Resolve stack:N against the live native stack, then match by ref.

    stack:N is only resolvable when exactly N native stack objects exist
    (the denominator uses stack:1 with a single object); otherwise fail closed.
    """
    try:
        want = int(str(stack_ref).split(":")[1])
    except (IndexError, ValueError):
        raise BehaviorFailure(f"STACK_REF_MALFORMED:{stack_ref}") from None
    if not session.snapshots:
        raise BehaviorFailure(f"STACK_REF_NO_SNAPSHOT:{stack_ref}")
    entries = list(session.snapshots[-1].get("stack") or [])
    if len(entries) != want:
        raise BehaviorFailure(f"STACK_REF_AMBIGUOUS:{stack_ref}:native={len(entries)}")
    # Top-down: with exactly one object the order is unambiguous.
    target = entries[0].get("source_semantic_id")
    if not target:
        raise BehaviorFailure(f"STACK_REF_UNBOUND:{stack_ref}")
    return match_semantic_object(frame, str(target))


def match_mana_source(
    frame: dict[str, Any], remaining_refs: list[str]
) -> tuple[dict[str, Any], str, str]:
    """Select the first contract-listed source ref (in contract order) offered.

    Returns (option, ref, produced_symbol). Zero match fails closed; a ref
    offered twice natively fails closed as nonunique.
    """
    for ref in remaining_refs:
        hits = []
        for o in frame["payload"].get("options") or []:
            kind = str(o.get("kind"))
            if not kind.startswith("MANA_SOURCE:"):
                continue
            body = kind[len("MANA_SOURCE:") :]
            if ":" not in body:
                continue
            cand_ref, produced = body.rsplit(":", 1)
            if cand_ref == ref:
                hits.append((o, ref, produced))
        if len(hits) > 1:
            raise BehaviorFailure(
                f"MANA_SOURCE_NATIVE_NONUNIQUE:{ref}:{frame['payload'].get('decision_id')}"
            )
        if hits:
            return hits[0]
    raise BehaviorFailure(f"MANA_MATCH_ZERO:{remaining_refs}:{frame['payload'].get('decision_id')}")


def match_assignment(
    frame: dict[str, Any], expected: dict[str, str], prefix: str
) -> dict[str, Any]:
    """Match a whole-assignment label (ATTACK_ASSIGNMENT:/BLOCK_ASSIGNMENT:)."""

    def pred(kind: str, _o: dict[str, Any]) -> bool:
        if not kind.startswith(prefix):
            return False
        pairs = dict(p.split("=", 1) for p in kind[len(prefix) :].split(",") if "=" in p)
        return pairs == expected

    return match_single_option(frame, pred, f"assignment:{expected}")


class Session:
    """One driven behavior session; records evidence for the report."""

    def __init__(self, record: dict[str, Any], proc: Any) -> None:
        self.record = record
        self.proc = proc
        self.snapshots: list[dict[str, Any]] = []
        self.observation: dict[str, Any] | None = None
        self.feed: list[str] = []
        self.matches: list[dict[str, Any]] = []
        self.passes = 0
        self.decision_index = 0
        self.stop: dict[str, Any] | None = None
        # Progressive multi-pick state, keyed by script entry index:
        # target entries (remaining semantic values) and mana entries
        # (remaining source refs + produced symbols).
        self.multi_remaining: dict[int, list[str]] = {}
        self.mana_produced: dict[int, list[str]] = {}
        # Unified journal: (seq, kind, text) with kind in
        # {snapshot, event, frame, match} for anchored evaluation.
        self.journal: list[tuple[int, str, str]] = []
        self._seq = 0
        # Per-actor mulligan prompt counts for round lifecycle events.
        self.mulligan_rounds: dict[str, int] = {}
        # Whether static (construction-observation) events were derived.
        self.static_derived = False

    def _log(self, kind: str, text: str) -> None:
        self.journal.append((self._seq, kind, text))
        self._seq += 1

    def note_snapshot(self, index: int) -> None:
        self._log("snapshot", f"snapshot:{index}")

    def note_event(self, name: str) -> None:
        self.feed.append(name)
        self._log("event", name)

    def note_frame(self, kind: str, actor: str | None) -> None:
        norm = normalize_actor(actor)
        for synth in synthesize_frame_events(kind, norm):
            self.note_event(synth)
        self._log("frame", f"{kind}:{norm}")

    @property
    def script(self) -> list[dict[str, Any]]:
        return list(self.record.get("decision_script") or [])

    def next_expected(self) -> dict[str, Any] | None:
        if self.decision_index < len(self.script):
            return self.script[self.decision_index]
        return None

    def record_match(
        self,
        frame: dict[str, Any],
        option: dict[str, Any],
        rule: str,
        family: str | None = None,
        value: Any = None,
    ) -> None:
        options = frame["payload"].get("options") or []
        self.matches.append(
            {
                "decision_id": frame["payload"].get("decision_id"),
                "decision_kind": frame["payload"].get("decision_kind"),
                "actor": normalize_actor(frame.get("actor_id")),
                "match_rule": rule,
                "offered_count": len(options),
                "offered_digest": _digest_options(options),
                "selected_option_id": option.get("option_id"),
                "selected_kind": option.get("kind"),
                "submitted": True,
            }
        )
        self._log("match", rule)
        if family is not None:
            compact = value if isinstance(value, str) else _compact_value(value)
            self.note_event(f"decision:{family}:{compact}")

    def answer_pass(self, frame: dict[str, Any]) -> None:
        option = match_pass_option(frame)
        self.record_match(frame, option, "scripted_pass")
        submit(self.proc, frame, str(option["option_id"]), "pass")
        self.passes += 1

    def answer_forced_singleton(self, frame: dict[str, Any]) -> None:
        """Answer a frame with exactly one offered option and no script entry.

        Forced moves carry no discretion; logged distinctly from matches.
        """
        options = frame["payload"].get("options") or []
        if len(options) != 1:
            raise BehaviorFailure(
                f"UNSCRIPTED_MULTI_OPTION_FRAME:{frame['payload'].get('decision_kind')}:"
                f"{frame['payload'].get('decision_id')}"
            )
        option = options[0]
        self.matches.append(
            {
                "decision_id": frame["payload"].get("decision_id"),
                "decision_kind": frame["payload"].get("decision_kind"),
                "actor": normalize_actor(frame.get("actor_id")),
                "match_rule": "forced_singleton",
                "offered_count": 1,
                "offered_digest": _digest_options(options),
                "selected_option_id": option.get("option_id"),
                "selected_kind": option.get("kind"),
                "submitted": False,
            }
        )
        submit(self.proc, frame, str(option["option_id"]), "forced")
        self.passes += 1

    def answer_expected(self, frame: dict[str, Any], expected: dict[str, Any]) -> None:
        kind = frame["payload"].get("decision_kind")
        family = expected.get("decision_family")
        selector = expected["selection"]["selector_kind"]
        value = expected["selection"]["semantic_value"]
        actor = normalize_actor(frame.get("actor_id"))
        if actor and expected.get("actor") and actor != expected["actor"]:
            raise BehaviorFailure(
                f"ACTOR_MISMATCH:{frame['payload'].get('decision_id')}:{actor}:{expected['actor']}"
            )
        if selector == "semantic_action" and isinstance(value, dict):
            action = value.get("action")
            if action == "cast_commander":
                option = match_commander_cast(frame, expected, self.record)
                rule = f"semantic_action:{value}"
            else:
                option = match_semantic_action_object(frame, str(value.get("object", "")))
                rule = f"semantic_action:{value}"
        elif selector == "semantic_object":
            option = match_semantic_object(frame, str(value))
            rule = f"{selector}:{value}"
        elif selector in {
            "semantic_mode_key",
            "semantic_choice_key",
            "semantic_ability_key",
        }:
            option = match_semantic_key(frame, str(value))
            rule = f"{selector}:{value}"
        elif selector == "semantic_stack_object":
            option = match_stack_object(frame, str(value), self)
            rule = f"{selector}:{value}"
        elif selector == "semantic_objects":
            wanted = [str(v) for v in value]
            remaining = self.multi_remaining.setdefault(self.decision_index, list(wanted))
            option = match_semantic_object_any(frame, remaining)
            rule = f"{selector}:{value}"
            remaining.remove(_matched_ref(option, remaining))
            if remaining:
                self.record_match(
                    frame, option, rule + f":remaining={len(remaining)}", family, value
                )
                submit(self.proc, frame, str(option["option_id"]), "scripted")
                return
        elif selector == "semantic_player":
            option = match_semantic_player(frame, str(value))
            rule = f"semantic_player:{value}"
        elif selector in {
            "boolean",
            "integer",
            "mana_payment",
            "amount_assignment",
            "attacker_assignment",
            "blocker_assignment",
            "order",
            "partition",
        }:
            raise BehaviorFailure(f"SELECTOR_NEEDS_PROVIDER_SURFACE:{kind}:{family}:{selector}")
        elif selector == "fail_closed_probe":
            raise BehaviorFailure(
                f"FAIL_CLOSED_PROBE_REACHED_FRAME:{kind}:{family}:{frame['payload'].get('decision_id')}"
            )
        else:
            raise BehaviorFailure(f"UNKNOWN_SELECTOR:{kind}:{family}:{selector}")
        self.record_match(frame, option, rule, family, value)
        submit(self.proc, frame, str(option["option_id"]), "scripted")
        self.decision_index += 1


def _matched_ref(option: dict[str, Any], remaining: list[str]) -> str:
    """Identify which expected ref an offered option matched."""
    segments = kind_segments(str(option.get("kind")))
    for ref in remaining:
        if ref in segments:
            return ref
    raise BehaviorFailure(f"MATCHED_REF_UNRESOLVABLE:{segments}:{remaining}")


def _compact_value(value: Any) -> str:
    """Compact a semantic value for decision: feed events."""
    if isinstance(value, dict):
        parts = [f"{k}={_compact_value(v)}" for k, v in sorted(value.items())]
        return ",".join(parts)
    if isinstance(value, list):
        return "+".join(_compact_value(v) for v in value)
    return str(value)


def _digest_options(options: list[dict[str, Any]]) -> str:
    import hashlib

    canon = json.dumps(options, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def drive_until_result(
    session: Session,
    on_frame,
    max_messages: int = 4096,
    on_snapshot=None,
) -> dict[str, Any]:
    """Consume provider messages until SESSION_RESULT; delegate frames."""
    proc = session.proc
    for _ in range(max_messages):
        line = proc.stdout.readline()
        if not line:
            raise BehaviorFailure("PROVIDER_EOF")
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as ex:
            raise BehaviorFailure(f"PROVIDER_NON_JSON:{ex}") from ex
        typ = msg.get("message_type")
        if typ == "SESSION_CREATED":
            continue
        if typ == "QUALIFICATION_STATE":
            payload = msg.get("payload") or {}
            if "raw_native" in payload:
                session.snapshots.append(payload["raw_native"])
                session.note_snapshot(len(session.snapshots) - 1)
                if on_snapshot is not None:
                    on_snapshot(session)
            continue
        if typ == "EVENT":
            payload = msg.get("payload") or {}
            name = payload.get("name")
            if name:
                session.note_event(str(name))
            continue
        if typ == "DECISION_FRAME":
            session.note_frame(
                str(msg.get("payload", {}).get("decision_kind")), msg.get("actor_id")
            )
            on_frame(session, msg)
            continue
        if typ == "SESSION_RESULT":
            session.stop = dict(msg.get("payload") or {})
            return session.stop
        raise BehaviorFailure(f"UNEXPECTED_MESSAGE:{typ}")
    raise BehaviorFailure("MESSAGE_BUDGET_EXHAUSTED")


def open_session(record: dict[str, Any], env: dict[str, str]):
    proc = subprocess.Popen(
        provider_command(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        # Popen owns this handle for the session lifetime; closed with the process.
        stderr=tempfile.TemporaryFile(mode="w+t", encoding="utf-8"),  # noqa: SIM115
        text=True,
        env=env,
        bufsize=1,
    )
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(
        json.dumps(
            {
                "protocol": PROTOCOL,
                "message_type": "CREATE_SESSION",
                "request_id": "ws48-behavior-" + record["fixture_id"],
                "payload": {"fixture_id": record["fixture_id"]},
            },
            separators=(",", ":"),
        )
        + "\n"
    )
    proc.stdin.flush()
    return proc


def anchored_snapshot_index(record: dict[str, Any], session: Session) -> int | None:
    """Index of the first snapshot after the last required event.

    Postconditions describe terminal native outcomes; they must be evaluated
    at a checkpoint taken after the required native behavior completed, not
    at an arbitrary (e.g. game-end) snapshot.
    """
    required = set((record.get("expected_events") or {}).get("required_events") or [])
    if not required:
        return len(session.snapshots) - 1 if session.snapshots else None
    # Completion seq: the point at which the last-missing required event was
    # FIRST observed. (Recurring events such as priority:Pn must not drag the
    # anchor to game end; first-seen per event is what matters.)
    first_seen: dict[str, int] = {}
    for seq, kind, text in session.journal:
        if kind == "event" and text in required and text not in first_seen:
            first_seen[text] = seq
    if set(first_seen) != required:
        return None
    completion = max(first_seen.values())
    for seq, kind, text in session.journal:
        if kind == "snapshot" and seq > completion:
            return int(text.split(":", 1)[1])
    return None


def verify_terminal(
    record: dict[str, Any], session: Session, snapshot_idx: int | None = None
) -> dict[str, Any]:
    """Run event + postcondition verification over collected evidence.

    Postconditions evaluate at ``snapshot_idx`` (default: the completion
    anchor, i.e. the first checkpoint after the last required event).
    """
    if not session.snapshots:
        raise BehaviorFailure("NO_SNAPSHOTS")
    anchor = anchored_snapshot_index(record, session)
    if anchor is None:
        raise BehaviorFailure("NO_POST_RESOLUTION_SNAPSHOT")
    idx = anchor if snapshot_idx is None else snapshot_idx
    terminal = session.snapshots[idx]
    snapshot_texts = [json.dumps(s, ensure_ascii=False, sort_keys=True) for s in session.snapshots]
    events = behavior_events.verify(
        record.get("expected_events") or {}, session.feed, snapshot_texts
    )
    ctx = {
        "snapshot": terminal,
        "snapshot_index": idx,
        "feed": list(session.feed),
        "matches": list(session.matches),
        "stop": dict(session.stop or {}),
    }
    posts = behavior_postconditions.check_all(
        [str(x) for x in record.get("terminal_postconditions") or []], record, ctx
    )
    ok = events["status"] == "PASS" and posts["status"] == "PASS"
    return {
        "events": events,
        "postconditions": posts,
        "status": "PASS" if ok else "FAIL",
        "passes": session.passes,
        "decisions": session.decision_index,
        "snapshot_count": len(session.snapshots),
        "anchor_snapshot": anchor,
    }


def check_terminal_ready(record: dict[str, Any], session: Session) -> dict[str, Any] | None:
    """Return a PASS terminal result if the session may stop now, else None.

    Ready means: script fully consumed, every required event observed, and
    postconditions holding at the first satisfying checkpoint at or after
    the completion anchor. Later checkpoints may diverge (the game continues),
    so the earliest satisfying one is the terminal evidence.
    """
    if session.decision_index != len(session.script):
        return None
    required = set((record.get("expected_events") or {}).get("required_events") or [])
    if not required.issubset(set(session.feed)):
        return None
    try:
        anchor = anchored_snapshot_index(record, session)
    except BehaviorFailure:
        return None
    if anchor is None:
        return None
    for idx in range(anchor, len(session.snapshots)):
        try:
            result = verify_terminal(record, session, snapshot_idx=idx)
        except BehaviorFailure:
            return None
        if result["status"] == "PASS":
            return result
    return None
