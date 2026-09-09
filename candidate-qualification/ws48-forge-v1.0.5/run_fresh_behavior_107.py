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


def behavior_env(record: dict[str, Any]) -> dict[str, str]:
    """Construction-equivalent env with the game allowed to continue."""
    e = dict(constr.env_for(record))
    e["COMMANDER_LAB_WS40_CONSTRUCTION_ONLY"] = "0"
    e["COMMANDER_LAB_FORGE_STOP_AFTER_PRIORITY"] = "100000"
    e["COMMANDER_LAB_WS48_BEHAVIOR"] = "1"
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


def derive_static_events(record: dict[str, Any], session: Session) -> None:
    """Record native bookkeeping markers from the construction snapshot.

    All values come from the provider-emitted native snapshot (typed
    observation), never from the requested record: Rules-RNG channels and
    predetermined draws from native rules_randomness, tested viewers from
    native knowledge_state.
    """
    from behavior_driver import BehaviorFailure as _BF

    first = session.snapshots[0]
    if first.get("natural_lifecycle") is True:
        # Natural-game lifecycle markers are derived when those fixtures run.
        return
    obs = first.get("ws45_observation") or {}
    if not obs:
        raise _BF("STATIC_DERIVATION_MISSING_OBSERVATION")
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
    session = Session(record, proc)
    evidence["session"] = session
    from behavior_driver import submit as _submit

    script = list(record.get("decision_script") or [])
    negatives = [d for d in script if d["selection"]["selector_kind"] == "fail_closed_probe"]
    if negatives:
        # Negative fixtures never submit: the provider must terminate with a
        # typed unsupported-decision failure by itself.
        stop = drive_until_result(session, _reject_all_frames)
        session.stop = stop
        code = str(stop.get("stop_reason") or "")
        if "UNSUPPORTED_DISCRETIONARY_DECISION" not in code:
            raise BehaviorFailure(f"NEGATIVE_NO_TYPED_FAIL_CLOSED:{code!r}")
        feed = list(session.feed)
        fams = {str(d.get("decision_family")) for d in negatives}
        for fam in fams:
            probe = next(d for d in negatives if d.get("decision_family") == fam)
            forbidden = [f"fallback_used:{probe['selection'].get('forbidden_probe', fam)}"]
            _ = forbidden
        return {
            "negative": True,
            "stop_reason": code,
            "feed": feed,
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
                raise BehaviorFailure(f"UNSCRIPTED_DECLARE:{kind}")
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
            sess.answer_forced_singleton(frame)
            return
        expected = sess.next_expected()
        if expected is not None:
            sess.answer_expected(frame, expected)
            return
        # Script exhausted: only scripted priority passes may continue the game
        # toward terminal resolution.
        if kind == "priority":
            sess.answer_pass(frame)
            return
        raise BehaviorFailure(f"POST_SCRIPT_UNEXPECTED_FRAME:{kind}")

    def on_snapshot(sess: Session) -> None:
        from behavior_driver import TerminalReached
        from behavior_driver import check_terminal_ready as _ready

        if len(sess.snapshots) == 1:
            derive_static_events(record, sess)
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
    result = verify_terminal(record, session)
    result["stop_reason"] = stop.get("stop_reason")
    result["matches"] = list(session.matches)
    result["feed"] = list(session.feed)
    if result["status"] != "PASS":
        raise BehaviorFailure(
            f"TERMINAL_VERIFICATION_FAIL:events={result['events']} posts={result['postconditions']}"
        )
    return result


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
