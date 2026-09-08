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

    @property
    def script(self) -> list[dict[str, Any]]:
        return list(self.record.get("decision_script") or [])

    def next_expected(self) -> dict[str, Any] | None:
        if self.decision_index < len(self.script):
            return self.script[self.decision_index]
        return None

    def record_match(self, frame: dict[str, Any], option: dict[str, Any], rule: str) -> None:
        options = frame["payload"].get("options") or []
        self.matches.append(
            {
                "decision_id": frame["payload"].get("decision_id"),
                "decision_kind": frame["payload"].get("decision_kind"),
                "actor": frame.get("actor_id"),
                "match_rule": rule,
                "offered_count": len(options),
                "offered_digest": _digest_options(options),
                "selected_option_id": option.get("option_id"),
                "selected_kind": option.get("kind"),
                "submitted": True,
            }
        )

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
            option = match_semantic_action_object(frame, str(value.get("object", "")))
            rule = f"semantic_action:{value}"
        elif selector in {
            "semantic_object",
            "semantic_stack_object",
            "semantic_mode_key",
            "semantic_choice_key",
            "semantic_ability_key",
        }:
            option = match_semantic_object(frame, str(value))
            rule = f"{selector}:{value}"
        elif selector == "semantic_objects":
            wanted = [str(v) for v in value]
            remaining = self.multi_remaining.setdefault(self.decision_index, list(wanted))
            option = match_semantic_object_any(frame, remaining)
            rule = f"{selector}:{value}"
            remaining.remove(_matched_ref(option, remaining))
            if remaining:
                self.record_match(frame, option, rule + f":remaining={len(remaining)}")
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
        self.record_match(frame, option, rule)
        submit(self.proc, frame, str(option["option_id"]), "scripted")
        self.decision_index += 1


def _matched_ref(option: dict[str, Any], remaining: list[str]) -> str:
    """Identify which expected ref an offered option matched."""
    segments = kind_segments(str(option.get("kind")))
    for ref in remaining:
        if ref in segments:
            return ref
    raise BehaviorFailure(f"MATCHED_REF_UNRESOLVABLE:{segments}:{remaining}")


def _digest_options(options: list[dict[str, Any]]) -> str:
    import hashlib

    canon = json.dumps(options, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def drive_until_result(
    session: Session,
    on_frame,
    max_messages: int = 4096,
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
            continue
        if typ == "EVENT":
            payload = msg.get("payload") or {}
            name = payload.get("name")
            if name:
                session.feed.append(str(name))
            continue
        if typ == "DECISION_FRAME":
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


def verify_terminal(record: dict[str, Any], session: Session) -> dict[str, Any]:
    """Run event + postcondition verification over collected evidence."""
    if not session.snapshots:
        raise BehaviorFailure("NO_SNAPSHOTS")
    terminal = session.snapshots[-1]
    snapshot_texts = [json.dumps(s, ensure_ascii=False, sort_keys=True) for s in session.snapshots]
    events = behavior_events.verify(
        record.get("expected_events") or {}, session.feed, snapshot_texts
    )
    ctx = {
        "snapshot": terminal,
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
    }
