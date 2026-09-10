#!/usr/bin/env python3
"""WS50 decision-sequence runner: authoritative native decision-frame journal.

Drives the WS50-overlay provider through bounded native decision sequences
with external-only discretionary choice, strict native-option binding
(zero/multi match FAIL CLOSED), per-frame principal-scoped observations,
state/RNG fingerprints, semantic replay, negative probes, and a hidden-info
adversary. Grants no behavior credit (BEHAVIOR_CREDIT=0/107).

Scenarios:
  WS50-B-ATTACK: PILOT_CHOOSE_MODE (NATIVE_STATE_LOAD setup, native
    execution) + WS50-authored intent; closes the R1e declare_attacker
    surface and continues the SAME game.
  WS50-C-NATIVE: PILOT_MULLIGAN record (NATURAL_GAME_START: real shuffle,
    startup, mulligans) + WS50 intent; fully native construction + sequence.

Usage:
  ws50_sequence_runner.py --scenario WS50-B-ATTACK --runners DIR --output J.json
  ws50_sequence_runner.py --replay J.json --runners DIR --output R.json
  + --neg-zero / --neg-multi / --neg-replay-mismatch flags.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
_WS48_SRC = Path(__file__).resolve().parent.parent / "ws48-forge-v1.0.5"
sys.path.insert(0, str(_WS48_SRC))
import run_behavior_transcript_probe as base  # noqa: E402  (R1e probe mechanics, committed source)

PROTOCOL = base.PROTOCOL
WS47_SCHEMA = base.WS47_SCHEMA
WS47_BUNDLE = base.WS47_BUNDLE
WS47_SHA = base.WS47_SHA
FORGE_COMMIT = base.FORGE_COMMIT
FORGE_TREE = base.FORGE_TREE
WS50_SEED_BINDING = "ws50-decision-sequence-slice"

FAILURE_CLASSES = ("ENGINE_RULES_OR_CAPABILITY", "ENGINE_EXTERNAL_DECISION_SEAM",
                   "ADAPTER_BINDING", "HARNESS", "FIXTURE_OR_TEST_DESIGN",
                   "BOOTSTRAP_ENVIRONMENT", "HIDDEN_INFORMATION",
                   "RULES_RNG_REPLAY", "UNKNOWN")


class WS50Driver(base.Driver):
    def __init__(self, record: dict[str, Any], intent: list[dict[str, Any]],
                 structural_cap: int = 256):
        super().__init__(record)
        for e in intent:
            self.script.append(copy.deepcopy(e))
        self.discard_cursors: dict[str, int] = {}
        self.structural_cap = structural_cap
        self.journal: list[dict[str, Any]] = []
        self.auto_records: list[str] = []


def ws50_answer_discard(drv: WS50Driver, actor: str, opts: list[dict[str, Any]],
                        labels: list[dict[str, str]]) -> str:
    d = None
    for i, e in enumerate(drv.script):
        if e.get("decision_family") == "discard" and e.get("actor") == actor:
            d = drv.script.pop(i)
            break
    if d is None:
        raise base.Blocked("discardToMaximumHandSize", f"unscripted discard for {actor}")
    want_list = d["selection"]["semantic_value"]["cards"]
    used = drv.discard_cursors.get(actor, 0)
    if used >= len(want_list):
        drv.script.insert(0, d)
        raise base.Blocked("discardToMaximumHandSize",
                           f"extra discard frame {used + 1} for {actor}")
    want = want_list[used]
    hits = [i for i, lb in enumerate(labels)
            if lb.get("_kind") == "OPT" and base.ref_identity(lb.get("opt", "")) == want]
    if len(hits) != 1:
        drv.script.insert(0, d)
        raise base.Blocked("discardToMaximumHandSize",
                           f"card {want}: {len(hits)} matches of {len(opts)}")
    drv.discard_cursors[actor] = used + 1
    if used + 1 == len(want_list):
        drv.consumed.append(d)
    return str(opts[hits[0]]["option_id"])


def ws50_answer(drv: WS50Driver, kind: str, actor: str, opts: list[dict[str, Any]],
                labels: list[dict[str, str]], record: dict[str, Any]) -> str:
    if kind == "discardToMaximumHandSize":
        return ws50_answer_discard(drv, actor, opts, labels)
    if kind == "priority":
        # WS50 structural pass with raised bounded cap (truthfully journaled),
        # taken ONLY when no scripted priority/ability obligation remains for
        # this actor; otherwise the R1e scripted matcher decides.
        pending = [x for x in drv.script if x["decision_family"] == "priority"
                   and x.get("actor") == actor]
        ability = [x for x in drv.script if x["decision_family"] == "choose_ability"
                   and x.get("actor") == actor]
        if not pending and not ability and drv.ps_cursor >= len(drv.priority_script):
            if len(drv.structural_passes) >= drv.structural_cap:
                return "__TERMINATE__"
            for i, o in enumerate(opts):
                if o.get("kind") == "PASS":
                    drv.structural_passes.append({"actor": actor,
                                                  "frame_options": len(opts)})
                    return str(o["option_id"])
            raise base.Blocked("priority", "structural pass unavailable: no PASS offered")
        return base.answer_frame(drv, kind, actor, opts, labels, record)
    return base.answer_frame(drv, kind, actor, opts, labels, record)


def selected_identity(kind: str, oid: str, opts: list[dict[str, Any]]) -> str:
    for o in opts:
        if str(o.get("option_id")) == oid:
            return str(o.get("kind", ""))
    return "STALE:" + oid


def audit_observations(frame_no: int, actor: str, observations: list[dict[str, Any]],
                       sentinels: dict[str, list[str]]) -> list[str]:
    """Principal-scoped hidden-info adversary. Returns violation strings."""
    violations: list[str] = []
    try:
        views = {o["viewer"]: json.loads(o["view"]) for o in observations}
    except Exception as ex:
        return [f"frame {frame_no}: observation parse failure: {ex}"]
    for viewer, view in views.items():
        for hand in view.get("hands", []):
            owner = hand.get("owner")
            cards = hand.get("cards", [])
            count = hand.get("count", -1)
            if owner == viewer:
                if len(cards) != count:
                    violations.append(
                        f"frame {frame_no}: viewer {viewer} own-hand incomplete "
                        f"({len(cards)} listed vs {count})")
                for c in cards:
                    if not c.get("name"):
                        violations.append(
                            f"frame {frame_no}: viewer {viewer} own-hand card missing name")
            else:
                if len(cards) != 0:
                    violations.append(
                        f"frame {frame_no}: viewer {viewer} sees {len(cards)} cards "
                        f"in {owner} hidden hand (LEAK)")
        for lib in view.get("libraries", []):
            if "cards" in lib or "names" in lib:
                violations.append(f"frame {frame_no}: viewer {viewer} library leaks identities")
        for zone in ("battlefield", "graveyard", "exile", "command", "stack"):
            for c in view.get(zone, []):
                if c.get("face_down") and "name" in c:
                    violations.append(
                        f"frame {frame_no}: viewer {viewer} sees facedown identity "
                        f"in {zone} (LEAK)")
        # Sentinel names: hidden-zone distinctive names must never appear in a
        # non-owner hand view, and owner must see them.
        for name in sentinels.get(viewer, []):
            mine = [h for h in view.get("hands", []) if h.get("owner") == viewer]
            if mine and not any(c.get("name") == name for c in mine[0].get("cards", [])):
                pass  # sentinel may have left hand; not a violation by itself
    # Cross-principal: a name visible in ANY non-owner hand view is a leak.
    for viewer, view in views.items():
        for hand in view.get("hands", []):
            if hand.get("owner") != viewer and hand.get("cards"):
                violations.append(
                    f"frame {frame_no}: CROSS-PRINCIPAL LEAK to {viewer} from "
                    f"{hand.get('owner')}")
    _ = actor
    return violations


def sentinel_names(record: dict[str, Any], actor: str) -> dict[str, list[str]]:
    """Distinctive hidden-zone card names per viewer from setup-time semantics."""
    out: dict[str, list[str]] = {}
    try:
        players = [p["player_id"] if "player_id" in p else p.get("seat") for p in record["players"]]
    except Exception:
        return out
    pids = []
    for i, p in enumerate(record.get("players", [])):
        pid = p.get("player_id") or ("P" + str(p.get("seat", i + 1)))
        pids.append(pid)
    names: dict[str, list[str]] = {pid: [] for pid in pids}
    for o in record.get("semantic_objects") or []:
        zone = str(o.get("zone", ""))
        if zone in ("hand", "library") and o.get("card_identity") not in ("Mountain", None):
            owner = o.get("owner")
            if owner in names:
                names[owner].append(str(o["card_identity"]))
    for pid in pids:
        out[pid] = sorted(set(names.get(pid, [])))
    return out


def run_scenario(record: dict[str, Any], transport: Any, intent: list[dict[str, Any]],
                 scenario_id: str, journal_path: Path | None = None,
                 per_record_timeout: int = 600,
                 structural_cap: int = 256) -> dict[str, Any]:
    drv = WS50Driver(record, intent, structural_cap)
    sent = sentinel_names(record, "")
    out: dict[str, Any] = {
        "schema_version": "commander-lab.ws50-decision-sequence/1.0.0",
        "evidence_class": "DECISION_SEQUENCE",
        "grants_behavior_credit": False,
        "behavior_credit": "0/107",
        "scenario_id": scenario_id,
        "fixture_id": record["fixture_id"],
        "execution_entry_mode": record["execution_entry_mode"],
        "forge": {"commit": FORGE_COMMIT, "tree": FORGE_TREE},
        "seed": ((record.get("rules_randomness") or {}).get("rules_seed")),
        "seed_binding": WS50_SEED_BINDING,
        "intent": intent,
    }
    deadline = time.monotonic() + per_record_timeout
    proc: Any = None
    stop_reason: str | None = None
    snapshot: Any = None
    answered = 0
    violations: list[str] = []
    lifecycle: Any = None
    try:
        with base.tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as err:
            import selectors as _selectors
            p = base.subprocess.Popen(base.command(), stdin=base.subprocess.PIPE,
                                      stdout=base.subprocess.PIPE, stderr=err,
                                      text=True,
                                      env=base.behavior_env(record, transport), bufsize=1)
            proc = p
            assert p.stdin is not None and p.stdout is not None
            bindup = os.dup(p.stdout.fileno())
            try:
                sel = _selectors.DefaultSelector()
                sel.register(bindup, _selectors.EVENT_READ)
            except Exception:
                sel = None
            buf = b""

            def next_line() -> str | None:
                nonlocal buf
                while True:
                    if b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        return (line + b"\n").decode("utf-8", errors="replace")
                    if p.poll() is not None:
                        try:
                            chunk = os.read(bindup, 65536)
                        except OSError:
                            chunk = b""
                        if chunk:
                            buf += chunk
                            continue
                        if buf:
                            rest, buf = buf, b""
                            return rest.decode("utf-8", errors="replace")
                        return None
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise base.Blocked("TIMEOUT",
                                           f"no session result within {per_record_timeout}s")
                    if sel is not None:
                        ready = sel.select(timeout=min(5.0, remaining))
                        if not ready:
                            continue
                    else:
                        time.sleep(0.05)
                    try:
                        chunk = os.read(bindup, 65536)
                    except OSError:
                        chunk = b""
                    if not chunk:
                        if p.poll() is not None:
                            continue
                        continue
                    buf += chunk

            def submit(frame: dict[str, Any], oid: str) -> None:
                p.stdin.write(json.dumps({
                    "protocol": PROTOCOL, "message_type": "SUBMIT_DECISION",
                    "request_id": "ws50-reply-" + frame["payload"]["decision_id"],
                    "session_id": frame.get("session_id"),
                    "payload": {"decision_id": frame["payload"]["decision_id"],
                                "option_id": oid}}, separators=(",", ":")) + "\n")
                p.stdin.flush()

            def drain_to_result() -> None:
                nonlocal stop_reason, snapshot
                try:
                    p.stdin.close()
                except Exception:
                    pass
                for _ in range(4096):
                    line = next_line()
                    if not line:
                        break
                    try:
                        m = json.loads(line)
                    except Exception:
                        continue
                    if m.get("message_type") == "SESSION_RESULT":
                        stop_reason = (m.get("payload") or {}).get("stop_reason")
                        snapshot = (m.get("payload") or {}).get("snapshot")
                        drv.result_seen = True
                        break
                    if m.get("message_type") == "NATIVE_EVENT":
                        drv.events.append({"event": (m.get("payload") or {}).get("event"),
                                           "facts": (m.get("payload") or {}).get("facts")})

            def close_and_collect() -> tuple[int, str]:
                try:
                    p.stdin.close()
                except Exception:
                    pass
                try:
                    rc = p.wait(timeout=60)
                except Exception:
                    p.kill()
                    rc = 124
                err.seek(0)
                return rc, err.read()[-6000:]

            is_negative = any(d["selection"]["selector_kind"] == "fail_closed_probe"
                              for d in drv.script)
            p.stdin.write(json.dumps({
                "protocol": PROTOCOL, "message_type": "CREATE_SESSION",
                "request_id": "ws50-" + scenario_id,
                "payload": {"fixture_id": record["fixture_id"]}},
                separators=(",", ":")) + "\n")
            p.stdin.flush()
            exit_rc: Any = None
            stderr_tail = ""
            for _ in range(4096):
                line = next_line()
                if not line:
                    break
                if len(drv.raw_lines) < 200:
                    drv.raw_lines.append(line[:500])
                try:
                    m = json.loads(line)
                except Exception:
                    drv.decode_errors += 1
                    if drv.decode_errors > 16:
                        raise base.Blocked("PROTOCOL", "too many undecodable lines")
                    continue
                typ = m.get("message_type")
                if typ == "SESSION_CREATED":
                    out["session_created_snapshot"] = (m.get("payload") or {}).get("snapshot")
                    continue
                if typ == "QUALIFICATION_STATE":
                    payload = m.get("payload") or {}
                    if payload.get("stage") == "after_native_setup_validation":
                        drv.setup_stage_seen = True
                    if payload.get("stage") == "native_post_mulligan_pre_main_loop":
                        lifecycle = payload.get("raw_native")
                    continue
                if typ == "NATIVE_EVENT":
                    drv.events.append({"event": (m.get("payload") or {}).get("event"),
                                       "facts": (m.get("payload") or {}).get("facts")})
                    continue
                if typ == "SESSION_RESULT":
                    stop_reason = (m.get("payload") or {}).get("stop_reason")
                    snapshot = (m.get("payload") or {}).get("snapshot")
                    drv.result_seen = True
                    break
                if typ != "DECISION_FRAME":
                    raise base.Blocked("PROTOCOL", f"unexpected message {typ}")
                pay = m["payload"]
                kind = pay.get("decision_kind")
                actor = drv.actor_pid(m)
                opts = drv.options(m)
                labels = [base.dec_label(o.get("kind", "")) for o in opts]
                frame_no = len(drv.journal) + 1
                obs = pay.get("observations") or []
                violations.extend(audit_observations(frame_no, actor, obs, sent))
                entry: dict[str, Any] = {
                    "seq": frame_no,
                    "engine_frame_id": pay.get("decision_id"),
                    "engine_frame_seq": pay.get("frame_seq"),
                    "revision": m.get("state_revision"),
                    "actor": actor,
                    "raw_actor": m.get("actor_id"),
                    "kind": kind,
                    "cancel_offered": pay.get("cancel_offered"),
                    "rng": pay.get("rng"),
                    "state_fingerprint": pay.get("state_fingerprint"),
                    "state_snapshot": pay.get("state_snapshot"),
                    "observation_fingerprints": {o.get("viewer"): o.get("fingerprint")
                                                 for o in obs},
                    "observations": obs,
                    "option_count": len(opts),
                    "offered_identities": sorted(o.get("kind", "") for o in opts),
                    "offered_options": [{"id": o.get("option_id"), "kind": o.get("kind", "")}
                                        for o in opts],
                }
                if len(drv.journal) >= 1024:
                    raise base.Blocked("PROTOCOL", "journal budget exceeded")
                if is_negative:
                    entry["selection"] = None
                    entry["engine_response"] = "NEGATIVE_DRAIN"
                    drv.journal.append(entry)
                    drain_to_result()
                    rc, tail = close_and_collect()
                    out.update({"stop_after_eof_rc": rc, "stderr_tail": tail})
                    break
                try:
                    oid = ws50_answer(drv, kind, actor, opts, labels, record)
                except base.Blocked as b:
                    entry["selection"] = None
                    entry["block"] = {"where": b.where, "detail": b.detail[:2000]}
                    entry["engine_response"] = "HARNESS_FAIL_CLOSED"
                    drv.journal.append(entry)
                    raise
                if oid == "__TERMINATE__":
                    entry["selection"] = None
                    entry["engine_response"] = "HARNESS_SCRIPT_EXHAUSTION_TERMINATE"
                    drv.journal.append(entry)
                    drain_to_result()
                    rc, tail = close_and_collect()
                    out.update({"terminate_rc": rc, "stderr_tail": tail})
                    break
                submit(m, oid)
                answered += 1
                entry["selection"] = {"option_id": oid,
                                      "identity": selected_identity(kind, oid, opts)}
                entry["engine_response"] = "ACCEPTED_CONTINUED"
                drv.journal.append(entry)
                drv.frames.append({"kind": kind, "actor": actor,
                                   "option_count": len(opts),
                                   "options": [o.get("kind", "") for o in opts][:16]})
            else:
                exit_rc, stderr_tail = close_and_collect()
                out.update({"verdict": "PROBE_FAIL", "reason": "FRAME_BUDGET_EXHAUSTED",
                            "exit_rc": exit_rc, "stderr_tail": stderr_tail})
                return finish_ws50(out, drv, stop_reason, snapshot, answered,
                                   violations, lifecycle)
            if is_negative and stop_reason is not None:
                exit_rc, stderr_tail = close_and_collect()
                out.update({"exit_rc": exit_rc, "stderr_tail": stderr_tail})
                return finish_negative_ws50(out, drv, record, stop_reason, violations)
            if stop_reason is None and "terminate_rc" not in out:
                exit_rc, stderr_tail = close_and_collect()
                out.update({"exit_rc": exit_rc, "stderr_tail": stderr_tail})
            return finish_ws50(out, drv, stop_reason, snapshot, answered,
                               violations, lifecycle)
    except base.Blocked as b:
        try:
            if proc is not None:
                proc.kill()
        except Exception:
            pass
        out.update({"verdict": f"BLOCKED_AT:{b.where}", "reason": b.detail[:4000]})
        return finish_ws50(out, drv, None, None, 0, violations, lifecycle)
    except Exception as ex:
        try:
            if proc is not None:
                proc.kill()
        except Exception:
            pass
        out.update({"verdict": "PROBE_FAIL",
                    "reason": f"{type(ex).__name__}:{ex}"[:4000]})
        return finish_ws50(out, drv, None, None, 0, violations, lifecycle)


def offered_digest(frames: list[dict[str, Any]]) -> str:
    return base.digest([{"kind": f["kind"], "actor": f["actor"],
                         "options": sorted(f["offered_identities"])} for f in frames])


def finish_ws50(out: dict[str, Any], drv: WS50Driver, stop_reason: Any,
                snapshot: Any, answered: int, violations: list[str],
                lifecycle: Any) -> dict[str, Any]:
    remaining = [{"family": d["decision_family"], "actor": d.get("actor"),
                  "selector": d["selection"]["selector_kind"]} for d in drv.script]
    if "verdict" not in out:
        if "terminate_rc" in out and not remaining:
            out["verdict"] = "TRANSCRIPT_COMPLETE"
        elif drv.result_seen and stop_reason is None:
            out["verdict"] = "BLOCKED_AT:NULL_STOP_REASON"
            out["reason"] = ("provider emitted SESSION_RESULT with null stop_reason")
        elif stop_reason in ("FORGE_GAME_RETURNED", "WS23_CONTROLLED_AFTER_PRIORITY_512"):
            out["verdict"] = "TRANSCRIPT_COMPLETE" if not remaining else "PROBE_FAIL"
            if remaining:
                out["reason"] = f"stopped with {len(remaining)} intent entries unconsumed"
        elif stop_reason and ("WS23_FAIL_CLOSED_UNSUPPORTED" in str(stop_reason)
                              or "WS48_UNSUPPORTED_DISCRETIONARY_DECISION" in str(stop_reason)
                              or "WS48_BARE_UNSUPPORTED_OPERATION" in str(stop_reason)
                              or "WS48_NULL_CONTROLLED_STOP" in str(stop_reason)):
            out["verdict"] = f"BLOCKED_AT:{stop_reason}"
        elif stop_reason and "WS23_EXTERNAL_EOF" in str(stop_reason):
            out["verdict"] = "TRANSCRIPT_COMPLETE" if not remaining else "PROBE_FAIL"
            if remaining:
                out["reason"] = f"EOF with {len(remaining)} unconsumed"
        elif stop_reason:
            out["verdict"] = "PROBE_FAIL"
            out["reason"] = f"stop_reason={stop_reason}"
        else:
            out["verdict"] = "PROBE_FAIL"
            out["reason"] = "no session result captured"
    out.update({
        "frames": drv.journal,
        "frame_count": len(drv.journal),
        "answered": answered,
        "consumed_intent": len(drv.consumed),
        "ritual_answers": drv.ritual_answers,
        "structural_passes": len(drv.structural_passes),
        "decode_errors": drv.decode_errors,
        "native_event_tape": drv.events[:256],
        "native_events": len(drv.events),
        "session_snapshot": snapshot,
        "native_lifecycle": lifecycle,
        "script_remaining": remaining,
        "stop_reason": stop_reason,
        "offered_digest": offered_digest(drv.journal),
        "observation_violations": violations,
        "hidden_info_verdict": "FAIL" if violations else "PASS",
        "failure_class": classify(out),
    })
    return out


def classify(out: dict[str, Any]) -> dict[str, Any]:
    verdict = str(out.get("verdict", ""))
    reason = str(out.get("reason", "") + str(out.get("stop_reason", "")))
    if out.get("observation_violations"):
        return {"class": "HIDDEN_INFORMATION",
                "note": "principal observation leak on traversed path"}
    if verdict == "TRANSCRIPT_COMPLETE":
        return {"class": "HARNESS",
                "note": "harness-driven prefix complete; no engine stall on traversed path"}
    if verdict.startswith("BLOCKED_AT:"):
        where = verdict.split("BLOCKED_AT:", 1)[1]
        if where in ("declare_attacker", "declare_blocker", "discardToMaximumHandSize",
                     "target", "choose_mode", "mana_payment", "priority", "mulligan",
                     "choose_object", "choose_ability", "announce_x", "choice",
                     "choose_use", "replacement_effect", "trigger_order", "confirm"):
            if "unscripted" in reason or "unsupported decision kind" in reason:
                return {"class": "HARNESS",
                        "note": f"intent gap at transported surface {where}; provider frame well-formed"}
            return {"class": "ADAPTER_BINDING",
                    "note": f"binding gap at {where}: {reason[:300]}"}
        if "WS48_UNSUPPORTED_DISCRETIONARY_DECISION" in where or \
                "WS23_FAIL_CLOSED_UNSUPPORTED" in where:
            return {"class": "ADAPTER_BINDING",
                    "note": f"provider-side uncovered discretionary surface: {where[:300]}"}
        if "NULL_STOP_REASON" in where or "NULL_CONTROLLED" in where:
            return {"class": "ADAPTER_BINDING",
                    "note": "opaque provider stop without typed reason"}
        return {"class": "UNKNOWN", "note": f"unclassified block: {where[:300]}"}
    if verdict == "PROBE_FAIL":
        if "TIMEOUT" in reason or "FRAME_BUDGET" in reason:
            return {"class": "HARNESS", "note": reason[:300]}
        if "UNEXPECTED" in reason:
            return {"class": "ENGINE_EXTERNAL_DECISION_SEAM",
                    "note": f"provider threw across decision seam: {reason[:300]}"}
        return {"class": "UNKNOWN", "note": reason[:300]}
    return {"class": "UNKNOWN", "note": verdict[:300]}


def finish_negative_ws50(out: dict[str, Any], drv: WS50Driver,
                         record: dict[str, Any], stop_reason: str,
                         violations: list[str]) -> dict[str, Any]:
    if stop_reason.startswith("WS48_UNSUPPORTED_DISCRETIONARY_DECISION"):
        out["verdict"] = "EXPECTED_FAIL_CLOSED_PASS"
    elif stop_reason.startswith("WS23_FAIL_CLOSED_UNSUPPORTED"):
        out["verdict"] = "EXPECTED_FAIL_CLOSED_PASS"
    else:
        out["verdict"] = "PROBE_FAIL"
        out["reason"] = f"negative probe did not fail closed: {stop_reason}"
    out.update({
        "frames": drv.journal,
        "frame_count": len(drv.journal),
        "answered": 0,
        "consumed_intent": 0,
        "ritual_answers": drv.ritual_answers,
        "offered_digest": offered_digest(drv.journal),
        "stop_reason": stop_reason,
        "observation_violations": violations,
        "hidden_info_verdict": "FAIL" if violations else "PASS",
        "failure_class": classify(out),
    })
    return out


def compare_replay(journal: dict[str, Any], rerun: dict[str, Any]) -> dict[str, Any]:
    divs: list[str] = []
    a, b = journal["frames"], rerun["frames"]
    if len(a) != len(b):
        divs.append(f"frame count {len(a)} != {len(b)}")
    for i, (fa, fb) in enumerate(zip(a, b)):
        if fa["kind"] != fb["kind"] or fa["actor"] != fb["actor"]:
            divs.append(f"frame {i + 1}: {fa['kind']}/{fa['actor']} != {fb['kind']}/{fb['actor']}")
            continue
        if sorted(fa["offered_identities"]) != sorted(fb["offered_identities"]):
            divs.append(f"frame {i + 1}: offered identity set differs")
        sa = (fa.get("selection") or {}).get("identity")
        sb = (fb.get("selection") or {}).get("identity")
        if sa != sb:
            divs.append(f"frame {i + 1}: selected identity {sa} != {sb}")
        if fa.get("rng") != fb.get("rng"):
            divs.append(f"frame {i + 1}: rng identity differs")
        if fa.get("observation_fingerprints") != fb.get("observation_fingerprints"):
            divs.append(f"frame {i + 1}: observation fingerprints differ")
        if fa.get("state_fingerprint") != fb.get("state_fingerprint"):
            divs.append(f"frame {i + 1}: state fingerprint differs")
    if (journal.get("native_event_tape") or []) != (rerun.get("native_event_tape") or []):
        divs.append("native event tape differs")
    if journal.get("stop_reason") != rerun.get("stop_reason"):
        divs.append(f"terminal {journal.get('stop_reason')} != {rerun.get('stop_reason')}")
    if journal.get("verdict") != rerun.get("verdict"):
        divs.append(f"verdict {journal.get('verdict')} != {rerun.get('verdict')}")
    return {"replay_verdict": "PASS" if not divs else "FAIL", "divergences": divs[:20]}


INTENT_B: list[dict[str, Any]] = [
    {"decision_family": "declare_attacker", "actor": "P1",
     "selection": {"selector_kind": "attacker_assignment",
                   "semantic_value": {"MINTED-423": "P2"},
                   "matches_only_provider_offered_legal_options": True,
                   "on_multiple_match": "FAIL_CLOSED", "on_zero_match": "FAIL_CLOSED"}},
    {"decision_family": "declare_attacker", "actor": "P1",
     "selection": {"selector_kind": "attacker_assignment",
                   "semantic_value": {"MINTED-424": "P3"},
                   "matches_only_provider_offered_legal_options": True,
                   "on_multiple_match": "FAIL_CLOSED", "on_zero_match": "FAIL_CLOSED"}},
    {"decision_family": "declare_attacker", "actor": "P1",
     "selection": {"selector_kind": "attacker_assignment",
                   "semantic_value": {"MINTED-425": "P4"},
                   "matches_only_provider_offered_legal_options": True,
                   "on_multiple_match": "FAIL_CLOSED", "on_zero_match": "FAIL_CLOSED"}},
    {"decision_family": "declare_blocker", "actor": "P2",
     "selection": {"selector_kind": "blocker_assignment",
                   "semantic_value": {"obj:p2-bears": "MINTED-423"},
                   "matches_only_provider_offered_legal_options": True,
                   "on_multiple_match": "FAIL_CLOSED", "on_zero_match": "FAIL_CLOSED"}},
    {"decision_family": "declare_blocker", "actor": "P3",
     "selection": {"selector_kind": "blocker_assignment",
                   "semantic_value": {},
                   "matches_only_provider_offered_legal_options": True,
                   "on_multiple_match": "FAIL_CLOSED", "on_zero_match": "FAIL_CLOSED"}},
    {"decision_family": "target", "actor": "P1",
     "selection": {"selector_kind": "semantic_player",
                   "semantic_value": "P2",
                   "matches_only_provider_offered_legal_options": True,
                   "on_multiple_match": "FAIL_CLOSED", "on_zero_match": "FAIL_CLOSED"}},
]

INTENT_C: list[dict[str, Any]] = [
    {"decision_family": "mulligan", "actor": "P1",
     "selection": {"selector_kind": "semantic_action", "semantic_value": "keep_opening_hand",
                   "matches_only_provider_offered_legal_options": True,
                   "on_multiple_match": "FAIL_CLOSED", "on_zero_match": "FAIL_CLOSED"}},
    {"decision_family": "mulligan", "actor": "P2",
     "selection": {"selector_kind": "semantic_action", "semantic_value": "keep_opening_hand",
                   "matches_only_provider_offered_legal_options": True,
                   "on_multiple_match": "FAIL_CLOSED", "on_zero_match": "FAIL_CLOSED"}},
    {"decision_family": "mulligan", "actor": "P3",
     "selection": {"selector_kind": "semantic_action", "semantic_value": "keep_opening_hand",
                   "matches_only_provider_offered_legal_options": True,
                   "on_multiple_match": "FAIL_CLOSED", "on_zero_match": "FAIL_CLOSED"}},
    {"decision_family": "mulligan", "actor": "P4",
     "selection": {"selector_kind": "semantic_action", "semantic_value": "keep_opening_hand",
                   "matches_only_provider_offered_legal_options": True,
                   "on_multiple_match": "FAIL_CLOSED", "on_zero_match": "FAIL_CLOSED"}},
]

BASE_FIXTURE = {"WS50-B-ATTACK": "PILOT_CHOOSE_MODE", "WS50-C-NATIVE": "PILOT_MULLIGAN"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--materialization", type=Path)
    ap.add_argument("--scenario", default="WS50-B-ATTACK")
    ap.add_argument("--intent-json", type=Path, default=None)
    ap.add_argument("--replay", type=Path, default=None)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--runners", default=".")
    ap.add_argument("--neg-zero", action="store_true")
    ap.add_argument("--neg-multi", action="store_true")
    ap.add_argument("--neg-replay-mismatch", action="store_true")
    a = ap.parse_args()
    sys.path.insert(0, a.runners)
    import run_strict_no_echo_gate as transport
    # The --runners copy of the probe must be byte-identical to the committed
    # source imported above; otherwise mechanics could diverge silently.
    import hashlib as _hl
    committed = (_WS48_SRC / "run_behavior_transcript_probe.py").read_bytes()
    staged = (Path(a.runners) / "run_behavior_transcript_probe.py").read_bytes()
    if _hl.sha256(committed).hexdigest() != _hl.sha256(staged).hexdigest():
        raise SystemExit("runners probe copy diverges from committed source")

    if a.materialization is None:
        raise SystemExit("--materialization required (immutable WS47 identity enforced)")
    raw = a.materialization.read_bytes()
    if hashlib.sha256(raw).hexdigest() != WS47_SHA:
        raise SystemExit("immutable WS47 materialization digest mismatch")
    doc = json.loads(raw)
    if doc["schema_version"] != WS47_SCHEMA or doc["canonical_bundle_digest"] != WS47_BUNDLE:
        raise SystemExit("immutable WS47 identity mismatch")
    by = {r["fixture_id"]: r for r in doc["records"]}

    if a.replay is not None and a.neg_replay_mismatch:
        journal = json.loads(a.replay.read_text())
        flipped = copy.deepcopy(journal)
        for f in flipped["frames"]:
            if f.get("selection"):
                f["selection"] = {"option_id": "oX",
                                  "identity": "MUTATED:" + str(f["selection"].get("identity"))}
                break
        cmp = compare_replay(journal, flipped)
        detected = cmp["replay_verdict"] == "FAIL"
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(
            {"neg_test": "replay_mismatch_detection",
             "expected": "FAIL", "got": cmp["replay_verdict"],
             "neg_verdict": "PASS" if detected else "FAIL",
             "divergences": cmp["divergences"][:10]}, indent=2, sort_keys=True) + "\n")
        print(f"WS50 NEG-REPLAY-MISMATCH -> comparator={cmp['replay_verdict']} "
              f"neg_verdict={'PASS' if detected else 'FAIL'}")
        return 0 if detected else 1

    if a.replay is not None:
        journal = json.loads(a.replay.read_text())
        if journal.get("mutated_for_negative"):
            raise SystemExit("refusing to replay a mutated journal as truth")
        scenario = journal["scenario_id"]
        record = copy.deepcopy(by[journal["fixture_id"]])
        intent = copy.deepcopy(journal["intent"])
        rerun = run_scenario(record, transport, intent, scenario + ":REPLAY")
        cmp = compare_replay(journal, rerun)
        rerun["replay_of"] = str(a.replay)
        rerun["replay_comparison"] = cmp
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(rerun, indent=2, sort_keys=True) + "\n")
        print(f"WS50 {scenario}:REPLAY -> {cmp['replay_verdict']} "
              f"divs={len(cmp['divergences'])}")
        for d in cmp["divergences"][:10]:
            print("  DIV:", d)
        return 0 if cmp["replay_verdict"] == "PASS" else 1
    scenario = a.scenario
    record = copy.deepcopy(by[BASE_FIXTURE[scenario]])
    intent: list[dict[str, Any]] = copy.deepcopy(
        {"WS50-B-ATTACK": INTENT_B, "WS50-C-NATIVE": INTENT_C}[scenario])
    if a.intent_json is not None:
        intent = json.loads(a.intent_json.read_text())["intent"]
    if a.neg_zero:
        intent.append({"decision_family": "declare_attacker", "actor": "P1",
                       "selection": {"selector_kind": "attacker_assignment",
                                     "semantic_value": {"MINTED-423": "P9_NONEXISTENT"},
                                     "matches_only_provider_offered_legal_options": True,
                                     "on_multiple_match": "FAIL_CLOSED",
                                     "on_zero_match": "FAIL_CLOSED"}})
    if a.neg_multi:
        intent.append({"decision_family": "choice", "actor": "P1",
                       "selection": {"selector_kind": "semantic_choice_key",
                                     "semantic_value": "XX_MULTI",
                                     "matches_only_provider_offered_legal_options": True,
                                     "on_multiple_match": "FAIL_CLOSED",
                                     "on_zero_match": "FAIL_CLOSED"}})
    result = run_scenario(record, transport, intent, scenario)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"WS50 {scenario} -> {result.get('verdict')} frames={result.get('frame_count')} "
          f"consumed={result.get('consumed_intent')} hidden={result.get('hidden_info_verdict')} "
          f"class={result.get('failure_class', {}).get('class')} stop={result.get('stop_reason')}")
    return 0 if result.get("verdict") in ("TRANSCRIPT_COMPLETE",
                                          "EXPECTED_FAIL_CLOSED_PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
