#!/usr/bin/env python3
"""WS-48 fresh behavior 107 runner (Muse support lane).

Drives every v1.0.5 denominator record through native Forge behavior:
construct -> execute decision_script against provider-offered legal options
only -> verify expected_events -> verify terminal_postconditions.

Usage mirrors the construction runner; requires the provider classpath with
the WS-48 behavior surface compiled in:

  COMMANDER_LAB_FORGE_LANG_DIR=.../forge-gui/res/languages
  COMMANDER_LAB_FORGE_PROVIDER_CMD="java -cp $(cat provider.classpath) forge.game.player.Ws23ForgeBootstrap"
  python run_fresh_behavior_107.py --materialization ...v1_0_5.json \\
      --denominator ...WS47_PROVIDER_DENOMINATOR_107.json --output OUT.json

Unlike construction, this runner continues through failures to collect the
full denominator matrix; exit status is nonzero unless 107/107 PASS.
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import hashlib
import json
from pathlib import Path
from typing import Any

import run_fresh_construction_107 as constr
from behavior_driver import (
    BehaviorFailure,
    Session,
    drive_until_result,
    normalize_actor,
    open_session,
    verify_terminal,
)

WS47_COMMIT = "192e2b77c0625ad26905bd0ee8dcc3f44a5796c8"
WS47_TREE = "f596c54d2cb229b9827c6c94a278175e8312c65c"
WS47_SCHEMA = "commander-lab.semantic-fixture-materialization/1.0.5"
WS47_BUNDLE = "631da205c4889929b87e1a3bbf342e8a5bd168e678c7551aaf6ca7a901901e01"
WS47_SHA = "0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3"
FORGE_COMMIT = "66caae16015bd403bc0a52fa6689afb5508f74d0"
FORGE_TREE = "40fc8f29ce4de31a964972461db2b48b4221e07f"


def canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(v: Any) -> str:
    return hashlib.sha256(canon(v).encode()).hexdigest()


NEGATIVE_KINDS = {
    "NEGATIVE_FIRST_OPTION": "chooseModeForAbility",
    "NEGATIVE_GUI_DEFAULT": "chooseModeForAbility",
    "NEGATIVE_RANDOM_OPTION": "chooseTargetsFor",
    "NEGATIVE_SILENT_SKIP": "chooseTargetsFor",
    "NEGATIVE_DEFAULT_YES_NO": "confirmAction",
    "NEGATIVE_INTERNAL_AI": "declareAttackers",
    "NEGATIVE_PARENT_CLASS_FALLBACK": "chooseSingleEntityForEffect",
}


def behavior_env(record: dict[str, Any]) -> dict[str, str]:
    """Construction-equivalent env with the game allowed to continue."""
    e = dict(constr.env_for(record))
    e["COMMANDER_LAB_WS40_CONSTRUCTION_ONLY"] = "0"
    e["COMMANDER_LAB_FORGE_STOP_AFTER_PRIORITY"] = "100000"
    e["COMMANDER_LAB_WS48_BEHAVIOR"] = "1"
    for d in record.get("decision_script") or []:
        if d["selection"]["selector_kind"] == "fail_closed_probe":
            kind = NEGATIVE_KINDS.get(record["fixture_id"])
            if kind:
                e["COMMANDER_LAB_WS48_UNSUPPORTED_FAMILY"] = kind
            break
    return e


def mulligan_option_id(frame: dict[str, Any], keep: bool) -> str:
    want = "KEEP" if keep else "MULLIGAN"
    hits = [o for o in frame["payload"].get("options") or [] if o.get("kind") == want]
    if len(hits) != 1:
        raise BehaviorFailure(f"MULLIGAN_OPTION_{'ZERO' if not hits else 'MULTIPLE'}:{want}")
    return str(hits[0]["option_id"])


def starting_player_option_id(frame: dict[str, Any]) -> str:
    hits = [o for o in frame["payload"].get("options") or [] if o.get("kind") == "PLAYER:seat-1"]
    if len(hits) != 1:
        raise BehaviorFailure("STARTING_PLAYER_SEAT1_UNAVAILABLE")
    return str(hits[0]["option_id"])


def mana_expected_sources(
    record: dict[str, Any], entry_index: int
) -> tuple[list[str], list[str] | None]:
    """Resolve (expected source refs, required mana symbols) for a mana entry."""
    from behavior_driver import BehaviorFailure as _BF

    entry = record["decision_script"][entry_index]
    sv = entry["selection"]["semantic_value"]
    required = list(sv.get("mana", [])) if isinstance(sv, dict) else None
    if isinstance(sv, dict) and "sources" in sv:
        return list(sv["sources"]), required
    cast_idx = next(
        (
            i
            for i, d in enumerate(record["decision_script"])
            if d["causal_step_id"] == entry["causal_step_id"] and d["decision_family"] == "priority"
        ),
        None,
    )
    for cs in record.get("action_cost_state") or []:
        if cs.get("decision_index") == cast_idx:
            return list(cs["explicit_payment_sources"]), required
    raise _BF(f"MANA_SOURCES_UNRESOLVABLE:{entry['causal_step_id']}")


def derive_natural_events(record: dict[str, Any], session: Session, snap: dict[str, Any]) -> None:
    """Record native natural-game lifecycle markers (first observance each).

    All values come from provider-emitted native snapshots: deck/hand state,
    mulligan trace, Rules-RNG channels, turn/phase. Each marker is noted once
    (guarded by session flags) to keep the feed interpretable.
    """
    done = session.natural_done
    decks = list(snap.get("decks") or [])
    rr = snap.get("rules_randomness") or {}
    trace = list(snap.get("mulligan_trace") or [])
    turn = int(snap.get("native_turn") or 0)

    def once(key: str) -> bool:
        if key in done:
            return False
        done.add(key)
        return True

    if decks and once("game_created"):
        session.note_event("game_created")
    if (
        decks
        and all(int(d.get("commander_count", 0) or 0) >= 1 for d in decks)
        and once("commander_zones_initialized")
    ):
        session.note_event("commander_zones_initialized")
    channels = list(rr.get("channels") or [])
    if channels and once("libraries_shuffled"):
        session.note_event("libraries_shuffled")
        for ch in channels:
            session.note_event(f"rules_rng:{ch}")
    for d in rr.get("predetermined_semantic_draws") or []:
        key = f"rules_rng_draw:{d.get('channel')}:{d.get('operation')}:{d.get('result')}"
        if once(key):
            session.note_event(f"rules_rng:{d.get('operation')}:{d.get('result')}")
    if (
        decks
        and all(int(d.get("hand_count", -1) or -1) == 7 for d in decks)
        and once("opening_hands_drawn")
    ):
        session.note_event("opening_hands_drawn")
    if turn >= 1 and once("first_turn_started"):
        session.note_event("first_turn_started")
    for d in decks:
        pid = d.get("player_id")
        hand = int(d.get("hand_count", 7) or 7)
        key = f"bottom:{pid}:{max(0, 7 - hand)}"
        if once(key):
            session.note_event(f"bottom_count:{pid}:{max(0, 7 - hand)}")
    p1_trace = [t for t in trace if t.get("player") == "P1"]
    if p1_trace and once("free_mulligan"):
        first_mull = next((t for t in p1_trace if not t.get("keep")), None)
        if first_mull is not None:
            session.note_event(
                f"free_mulligan:{str(int(first_mull.get('cards_to_return', 1) or 0) == 0).lower()}"
            )
    if turn >= 1 and decks and once("first_turn_draw"):
        p1 = next((d for d in decks if d.get("player_id") == "P1"), None)
        if p1 is not None:
            session.note_event(
                f"first_turn_draw:{str(int(p1.get('hand_count', 7) or 7) > 7).lower()}"
            )


def derive_static_events(record: dict[str, Any], session: Session) -> None:
    """Record native bookkeeping markers from the construction snapshot.

    All values come from the provider-emitted native snapshot (typed
    observation), never from the requested record: Rules-RNG channels and
    predetermined draws from native rules_randomness, tested viewers from
    native knowledge_state.
    """
    from behavior_driver import BehaviorFailure as _BF

    setup = None
    for snap in session.snapshots:
        if isinstance(snap, dict) and snap.get("ws45_observation"):
            setup = snap
            break
    if setup is None:
        # Natural-game records carry Rules-RNG in lifecycle snapshots;
        # knowledge projection is covered by derive_natural_events flow.
        for snap in session.snapshots:
            if isinstance(snap, dict) and snap.get("natural_lifecycle") is True:
                rr = snap.get("rules_randomness") or {}
                for ch in rr.get("channels") or []:
                    session.note_event(f"rules_rng:{ch}")
                return
        raise _BF("STATIC_DERIVATION_MISSING_OBSERVATION")
    obs = setup.get("ws45_observation") or {}
    rr = obs.get("rules_randomness") or {}
    for ch in rr.get("channels") or []:
        session.note_event(f"rules_rng:{ch}")
    for d in rr.get("predetermined_semantic_draws") or []:
        session.note_event(f"rules_rng:{d.get('operation')}:{d.get('result')}")
    ks = obs.get("knowledge_state") or {}
    for v in ks.get("viewer_states") or []:
        session.note_event(f"knowledge_projection:{record['fixture_id']}:{v.get('viewer')}")


def drive_record(record: dict[str, Any], proc, evidence: dict[str, Any]) -> dict[str, Any]:
    """Drive one record to terminal verification. Raises BehaviorFailure."""
    from behavior_driver import Session

    session = Session(record, proc)
    evidence["session"] = session
    from behavior_driver import submit as _submit

    session.proc_env = dict(getattr(proc, "behavior_env", {}) or {})

    script = list(record.get("decision_script") or [])
    negatives = [d for d in script if d["selection"]["selector_kind"] == "fail_closed_probe"]
    if negatives:
        # Negative fixtures: setup frames are answered normally; the gated
        # probe frame is emitted by the provider and then fails closed with
        # a typed code without any submission.
        probe_actor = negatives[0].get("actor")
        hands = [
            o.get("semantic_id")
            for o in record.get("semantic_objects") or []
            if o.get("zone") == "hand"
            and o.get("controller") == probe_actor
            and "-mana-" not in str(o.get("semantic_id"))
        ]
        if len(hands) == 1:
            # Cause-cast fixtures (Burn/Bolt in hand): the harness initiates
            # the scripted cause through native legal options; only the probe
            # decision itself stays unanswered.
            session.neg_cause_ref = hands[0]
            session.neg_cause_actor = probe_actor
        stop = drive_until_result(session, on_frame_negative_setup)
        session.stop = stop
        code = str(stop.get("stop_reason") or "")
        if "UNSUPPORTED_DISCRETIONARY_DECISION" not in code:
            raise BehaviorFailure(f"NEGATIVE_NO_TYPED_FAIL_CLOSED:{code!r}")
        session.note_event("fail_closed:UNSUPPORTED_DISCRETIONARY_DECISION")
        fams = {str(d.get("decision_family")) for d in negatives}
        if not session.snapshots:
            raise BehaviorFailure("NEGATIVE_NO_SNAPSHOTS")
        import behavior_postconditions as _posts
        from behavior_driver import behavior_events as _events

        snapshot_texts = [
            json.dumps(s, ensure_ascii=False, sort_keys=True) for s in session.snapshots
        ]
        events = _events.verify(record.get("expected_events") or {}, session.feed, snapshot_texts)
        ctx = {
            "snapshot": session.snapshots[-1],
            "snapshot_index": len(session.snapshots) - 1,
            "feed": list(session.feed),
            "matches": list(session.matches),
            "stop": dict(session.stop or {}),
        }
        posts = _posts.check_all(
            [str(x) for x in record.get("terminal_postconditions") or []], record, ctx
        )
        if events["status"] != "PASS" or posts["status"] != "PASS":
            raise BehaviorFailure(f"NEGATIVE_VERIFICATION_FAIL:events={events} posts={posts}")
        return {
            "negative": True,
            "stop_reason": code,
            "families": sorted(fams),
            "events": events,
            "postconditions": posts,
            "status": "PASS",
            "feed": list(session.feed),
            "matches": list(session.matches),
        }

    def on_frame(sess: Session, frame: dict[str, Any]) -> None:
        from behavior_driver import (
            match_assignment as _match_assignment,
        )
        from behavior_driver import (
            match_mana_source as _match_mana,
        )

        kind = frame["payload"].get("decision_kind")
        if kind == "chooseStartingPlayer":
            _submit(proc, frame, starting_player_option_id(frame), "setup-starting")
            sess.note_event("starting_player:P1")
            sess.matches.append(
                {
                    "decision_id": frame["payload"].get("decision_id"),
                    "decision_kind": kind,
                    "match_rule": "setup_starting_player_seat1",
                    "offered_count": len(frame["payload"].get("options") or []),
                    "offered_digest": digest(frame["payload"].get("options") or []),
                    "submitted": True,
                }
            )
            return
        if kind == "mulliganKeepHand":
            expected = sess.next_expected()
            actor_pid = normalize_actor(frame.get("actor_id"))
            round_no = sess.mulligan_rounds.get(actor_pid, 0) + 1
            sess.mulligan_rounds[actor_pid] = round_no
            if expected is not None and expected["decision_family"] == "mulligan":
                action = expected["selection"]["semantic_value"]
                if action == "keep_opening_hand":
                    keep = True
                elif action in {"mulligan", "mulligan_once"}:
                    keep = False
                else:
                    raise BehaviorFailure(f"UNKNOWN_MULLIGAN_ACTION:{action!r}")
                rule = f"mulligan:{action}"
                sess.decision_index += 1
            else:
                # Pre-game setup prompt on records without a mulligan script
                # (e.g. NATIVE_STATE_LOAD): keep, exactly as construction does.
                keep = True
                rule = "setup_mulligan_keep"
                action = "keep_opening_hand"
            sess.note_event(
                f"{'keep' if action == 'keep_opening_hand' else 'mulligan'}:{actor_pid}:round{round_no}"
            )
            if action == "mulligan_once":
                sess.note_event(f"mulligan_once:{actor_pid}")
            _submit(proc, frame, mulligan_option_id(frame, keep), "mulligan")
            sess.matches.append(
                {
                    "decision_id": frame["payload"].get("decision_id"),
                    "decision_kind": kind,
                    "match_rule": rule,
                    "offered_count": len(frame["payload"].get("options") or []),
                    "offered_digest": digest(frame["payload"].get("options") or []),
                    "submitted": True,
                }
            )
            return
        if kind == "payMana":
            expected = sess.next_expected()
            if not (
                (sess.active_cost and sess.active_cost["remaining"])
                or (
                    expected is not None
                    and expected["selection"]["selector_kind"] == "mana_payment"
                )
            ):
                sess.answer_unscripted_discretion(frame)
                return
            entry_idx = sess.decision_index
            if sess.active_cost and sess.active_cost["remaining"]:
                remaining = sess.active_cost["remaining"]
                option, ref, produced = _match_mana(frame, remaining)
                remaining.remove(ref)
                sess.mana_produced.setdefault(entry_idx, []).append(produced)
                sess.record_match(frame, option, f"mana_payment:{ref}:{produced}")
                _submit(proc, frame, str(option["option_id"]), "mana")
                if not remaining:
                    sess.active_cost = None
                    if (
                        expected is not None
                        and expected["selection"]["selector_kind"] == "mana_payment"
                    ):
                        wanted, required = mana_expected_sources(record, entry_idx)
                        got = sess.mana_produced.get(entry_idx, [])
                        if required is not None and sorted(got) != sorted(required):
                            raise BehaviorFailure(f"MANA_SYMBOLS_MISMATCH:{got}:{required}")
                        sess.decision_index += 1
                return
            if expected is not None and expected["selection"]["selector_kind"] == "mana_payment":
                entry_idx = sess.decision_index
                wanted, required = mana_expected_sources(record, entry_idx)
                remaining = sess.multi_remaining.setdefault(entry_idx, list(wanted))
                option, ref, produced = _match_mana(frame, remaining)
                remaining.remove(ref)
                sess.mana_produced.setdefault(entry_idx, []).append(produced)
                sess.record_match(frame, option, f"mana_payment:{ref}:{produced}")
                _submit(proc, frame, str(option["option_id"]), "mana")
                if not remaining:
                    if required is not None and sorted(sess.mana_produced[entry_idx]) != sorted(
                        required
                    ):
                        raise BehaviorFailure(
                            f"MANA_SYMBOLS_MISMATCH:{sess.mana_produced[entry_idx]}:{required}"
                        )
                    sess.decision_index += 1
                return
            sess.answer_forced_singleton(frame)
            return
        if kind in {"declareAttackers", "declareBlockers"}:
            expected = sess.next_expected()
            if expected is None:
                sess.answer_unscripted_discretion(frame)
                return
            selector = expected["selection"]["selector_kind"]
            prefix = (
                "ATTACK_ASSIGNMENT:"
                if selector == "attacker_assignment"
                else "BLOCK_ASSIGNMENT:"
                if selector == "blocker_assignment"
                else None
            )
            if prefix is None:
                raise BehaviorFailure(f"DECLARE_KIND_SELECTOR_MISMATCH:{kind}:{selector}")
            option = _match_assignment(frame, dict(expected["selection"]["semantic_value"]), prefix)
            sess.record_match(
                frame, option, f"{selector}:{expected['selection']['semantic_value']}"
            )
            _submit(proc, frame, str(option["option_id"]), "declare")
            sess.decision_index += 1
            return
        if kind == "chooseTargetsFor":
            expected = sess.next_expected()
            if expected is not None and expected["selection"]["selector_kind"] in {
                "semantic_object",
                "semantic_objects",
                "semantic_player",
                "semantic_stack_object",
            }:
                sess.answer_expected(frame, expected)
                return
            sess.answer_unscripted_discretion(frame)
            return
        expected = sess.next_expected()
        if expected is not None:
            if kind == "priority":
                # Priority frames only consume priority-action entries for the
                # acting player; every other pending entry waits for its own
                # native frame kind while the game advances through passes.
                sel = expected["selection"]
                if (
                    sel["selector_kind"] == "semantic_action"
                    and isinstance(sel["semantic_value"], dict)
                    and normalize_actor(frame.get("actor_id")) == expected.get("actor")
                ):
                    sess.answer_expected(frame, expected)
                    return
                sess.answer_pass(frame)
                return
            sess.answer_expected(frame, expected)
            return
        # Script exhausted: priority passes continue the game toward terminal
        # resolution; anything else is unscripted pilot discretion.
        if kind == "priority":
            sess.answer_pass(frame)
            return
        sess.answer_unscripted_discretion(frame)

    def on_snapshot(sess: Session) -> None:
        from behavior_driver import TerminalReached
        from behavior_driver import check_terminal_ready as _ready
        from behavior_driver import diff_checkpoints as _diff

        if not sess.static_derived and any(
            isinstance(s, dict) and (s.get("ws45_observation") or s.get("natural_lifecycle"))
            for s in sess.snapshots
        ):
            derive_static_events(record, sess)
            sess.static_derived = True
        cur = sess.snapshots[-1]
        if isinstance(cur, dict) and cur.get("natural_lifecycle") is True:
            derive_natural_events(record, sess, cur)
        if (
            isinstance(cur, dict)
            and cur.get("behavior_checkpoint") is True
            and any(
                str(e).startswith("first_turn_draw:")
                for e in (record.get("expected_events") or {}).get("required_events") or []
            )
        ):
            for p in cur.get("players") or []:
                if p.get("player_id") == "P1":
                    sess.note_event(
                        f"first_turn_draw:{str(int(p.get('hand_count', 7) or 7) > 7).lower()}"
                    )
        if isinstance(cur, dict) and cur.get("behavior_checkpoint") is True:
            prev_idx = sess.prev_checkpoint_idx
            # Only diff checkpoints taken after native setup: pre-load
            # checkpoints (pre-state-load game) would fabricate transitions.
            setup_seen = any(
                isinstance(s, dict) and (s.get("ws45_observation") or s.get("natural_lifecycle"))
                for s in sess.snapshots
            )
            if setup_seen:
                if prev_idx is not None:
                    lineage = {
                        o.get("semantic_id"): o.get("card_lineage_id")
                        for o in record.get("semantic_objects") or []
                        if o.get("semantic_id") and o.get("card_lineage_id")
                    }
                    for ev in _diff(sess.snapshots[prev_idx], cur, lineage):
                        sess.note_event(ev)
                sess.prev_checkpoint_idx = len(sess.snapshots) - 1
        ready = _ready(record, sess)
        if ready is not None:
            raise TerminalReached(ready)

    from behavior_driver import TerminalReached as _Terminal

    try:
        stop = drive_until_result(session, on_frame, on_snapshot=on_snapshot)
    except _Terminal as term:
        ready = term.args[0]
        with contextlib.suppress(Exception):
            proc.stdin.close()
        try:
            raw_stop = None
            for _ in range(600):
                line = proc.stdout.readline()
                if not line:
                    break
                msg = json.loads(line)
                if msg.get("message_type") == "SESSION_RESULT":
                    raw_stop = msg.get("payload") or {}
                    break
            session.stop = raw_stop or {"stop_reason": "WS48_EARLY_TERMINAL_EOF"}
        finally:
            with contextlib.suppress(Exception):
                proc.kill()
        ready["stop_reason"] = (session.stop or {}).get("stop_reason")
        ready["matches"] = list(session.matches)
        ready["feed"] = list(session.feed)
        ready["early_terminal"] = True
        return ready
    if session.decision_index != len(script):
        raise BehaviorFailure(f"SCRIPT_INCOMPLETE:{session.decision_index}/{len(script)}")
    from behavior_driver import anchored_snapshot_index as _anchor

    anchor = _anchor(record, session)
    if anchor is None:
        raise BehaviorFailure("NO_POST_RESOLUTION_SNAPSHOT")
    result = None
    for idx in range(anchor, len(session.snapshots)):
        candidate = verify_terminal(record, session, snapshot_idx=idx)
        if result is None:
            result = candidate
        if candidate["status"] == "PASS":
            result = candidate
            break
    assert result is not None
    result["stop_reason"] = stop.get("stop_reason")
    result["matches"] = list(session.matches)
    result["feed"] = list(session.feed)
    if result["status"] != "PASS":
        raise BehaviorFailure(
            f"TERMINAL_VERIFICATION_FAIL:events={result['events']} posts={result['postconditions']}"
        )
    return result


def on_frame_negative_setup(sess: Session, frame: dict[str, Any]) -> None:
    """Setup/passes/cause for negative fixtures; the probe frame is never answered.

    Cause-casts (FIRST/GUI/RANDOM/SILENT) initiate the scripted cause from the
    record's hand object through native legal options; the gated probe frame
    itself is observed but never submitted (the provider fails closed on it).
    Everything is logged as negative_cause_*, never as a contract match.
    """
    from behavior_driver import normalize_actor as _norm
    from behavior_driver import submit as _submit

    kind = frame["payload"].get("decision_kind")
    if kind == "chooseStartingPlayer":
        _submit(sess.proc, frame, starting_player_option_id(frame), "setup-starting")
        sess.note_event("starting_player:P1")
        return
    if kind == "mulliganKeepHand":
        _submit(sess.proc, frame, mulligan_option_id(frame, True), "setup-mulligan")
        return
    gated = (sess.proc_env or {}).get("COMMANDER_LAB_WS48_UNSUPPORTED_FAMILY", "")
    if gated and kind == gated:
        sess.probe_seen = True
        return
    if kind == "priority":
        actor = _norm(frame.get("actor_id"))
        cause_ref = sess.neg_cause_ref
        if cause_ref is not None and not sess.neg_cause_done and actor == sess.neg_cause_actor:
            from behavior_driver import match_semantic_action_object as _match_cast

            option = _match_cast(frame, cause_ref)
            sess.record_match(frame, option, f"negative_cause_cast:{cause_ref}")
            _submit(sess.proc, frame, str(option["option_id"]), "negative-cause")
            sess.neg_cause_done = True
            return
        sess.answer_pass(frame)
        return
    if kind == "payMana":
        options = frame["payload"].get("options") or []
        if not options:
            raise BehaviorFailure("NEGATIVE_CAUSE_NO_MANA_OPTIONS")
        option = sorted(options, key=lambda o: str(o.get("option_id")))[0]
        sess.record_match(frame, option, "negative_cause_payment")
        _submit(sess.proc, frame, str(option["option_id"]), "negative-cause")
        return
    raise BehaviorFailure(f"NEGATIVE_FRAME_REACHED:{kind}:{frame['payload'].get('decision_id')}")


def _reject_all_frames(sess: Session, frame: dict[str, Any]) -> None:
    raise BehaviorFailure(f"NEGATIVE_FRAME_OFFERED:{frame['payload'].get('decision_kind')}")


def write_report(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--materialization", type=Path, required=True)
    ap.add_argument("--denominator", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args()
    raw = a.materialization.read_bytes()
    if hashlib.sha256(raw).hexdigest() != WS47_SHA:
        raise SystemExit("immutable WS47 materialization digest mismatch")
    doc = json.loads(raw)
    if doc["schema_version"] != WS47_SCHEMA or doc["canonical_bundle_digest"] != WS47_BUNDLE:
        raise SystemExit("immutable WS47 identity mismatch")
    ids = list(json.loads(a.denominator.read_text())["fixture_ids"])
    if len(ids) != 107 or len(set(ids)) != 107:
        raise SystemExit("WS47 denominator is not exact 107")
    if a.only:
        ids = [x for x in ids if x in set(a.only)]
    by_id = {r["fixture_id"]: r for r in doc["records"]}
    rows: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "schema_version": "commander-lab.ws48-forge-fresh-behavior-107/1.0.0",
        "status": "IN_PROGRESS",
        "denominator": 107,
        "pass_count": 0,
        "historical_successor_runtime_credit_imported": 0,
        "construction_credit": "107/107",
        "behavior_credit": "0/107",
        "ws47": {
            "commit": WS47_COMMIT,
            "tree": WS47_TREE,
            "schema": WS47_SCHEMA,
            "bundle_digest": WS47_BUNDLE,
            "materialization_sha256": WS47_SHA,
        },
        "forge": {"commit": FORGE_COMMIT, "tree": FORGE_TREE},
        "rows": rows,
    }
    for index, fid in enumerate(ids, 1):
        record = by_id[fid]
        proc = None
        evidence: dict[str, Any] = {}
        try:
            proc = open_session(record, behavior_env(record))
            detail = drive_record(record, proc, evidence)
            with contextlib.suppress(Exception):
                proc.stdin.close()
            proc.wait(timeout=120)
            rows.append(
                {
                    "index": index,
                    "fixture_id": fid,
                    "fixture_family": record["fixture_family"],
                    "behavior_status": "PASS",
                    "evidence_class": "RUNTIME_VERIFIED",
                    "detail": detail,
                    "forge_commit": FORGE_COMMIT,
                    "forge_tree": FORGE_TREE,
                }
            )
            print(f"WS48 BEHAVIOR {index:03d}/107 PASS {fid}", flush=True)
        except Exception as ex:
            if proc is not None:
                with contextlib.suppress(Exception):
                    proc.kill()
            sess = evidence.get("session")
            anchor = None
            anchor_cards: list[str] = []
            if sess is not None:
                from behavior_driver import anchored_snapshot_index as _anchor

                with contextlib.suppress(Exception):
                    anchor = _anchor(record, sess)
                if anchor is not None:
                    try:
                        anchor_cards = sorted(
                            str(c.get("semantic_id"))
                            for c in (sess.snapshots[anchor].get("cards") or [])
                            if c.get("semantic_id")
                        )
                    except Exception:
                        anchor_cards = []
            rows.append(
                {
                    "index": index,
                    "fixture_id": fid,
                    "fixture_family": record["fixture_family"],
                    "behavior_status": "FAIL",
                    "error": str(ex)[:4000],
                    "stop_reason": getattr(sess, "stop", {}).get("stop_reason")
                    if sess and sess.stop
                    else None,
                    "feed": list(sess.feed) if sess else [],
                    "matches": list(sess.matches) if sess else [],
                    "snapshot_count": len(sess.snapshots) if sess else 0,
                    "anchor_snapshot": anchor,
                    "anchor_cards": anchor_cards,
                    "forge_commit": FORGE_COMMIT,
                    "forge_tree": FORGE_TREE,
                }
            )
            print(f"WS48 BEHAVIOR {index:03d}/107 FAIL {fid}: {ex}", flush=True)
        result["pass_count"] = sum(1 for r in rows if r["behavior_status"] == "PASS")
        write_report(a.output, result)
    counts = collections.Counter(
        r["fixture_family"] for r in rows if r["behavior_status"] == "PASS"
    )
    result["family_counts"] = dict(sorted(counts.items()))
    if result["pass_count"] == 107:
        result.update({"status": "PASS", "behavior_credit": "107/107", "hard_gate": "PASS"})
    else:
        result.update({"status": "FAIL", "behavior_credit": f"{result['pass_count']}/107"})
    write_report(a.output, result)
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
