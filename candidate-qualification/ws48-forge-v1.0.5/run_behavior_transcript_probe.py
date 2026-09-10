#!/usr/bin/env python3
"""WS48 behavior transcript probe v1 (TRANSCRIPT_PROBE, grants no credit).

Executes native Forge behavior continuation for selected WS47 v1.0.5 records:
CONSTRUCTION_ONLY is unset so the provider continues past setup into real
Rules execution. The harness answers ONLY scripted WS47 decisions by matching
scripted semantic selectors against provider-OFFERED option sets (exactly one
match required, else fail closed with typed evidence), submits the opaque
native option id, and records the complete decision transcript, offered-set
digests, native event tape, and stop classification.

Verdicts are TRANSCRIPT_COMPLETE / BLOCKED_AT:<kind> / EXPECTED_FAIL_CLOSED /
PROBE_FAIL. They are mechanism evidence only: no behavior credit, no gate
PASS. Terminal postcondition evaluation lives in the v2 credit runner.

Anti-echo: --mutate-target / --mutate-mode rewrite the HARNESS-side scripted
expectation and assert the provider-OFFERED transcript digest is unchanged,
proving observations originate from Forge rather than the request.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Any

PROTOCOL = "commander-lab.rules-service/1.1.0"
WS47_COMMIT = "192e2b77c0625ad26905bd0ee8dcc3f44a5796c8"
WS47_TREE = "f596c54d2cb229b9827c6c94a278175e8312c65c"
WS47_SCHEMA = "commander-lab.semantic-fixture-materialization/1.0.5"
WS47_BUNDLE = "631da205c4889929b87e1a3bbf342e8a5bd168e678c7551aaf6ca7a901901e01"
WS47_SHA = "0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3"
FORGE_COMMIT = "66caae16015bd403bc0a52fa6689afb5508f74d0"
FORGE_TREE = "40fc8f29ce4de31a964972461db2b48b4221e07f"

COLOR_SHORT = {"WHITE": "W", "BLUE": "U", "BLACK": "B", "RED": "R", "GREEN": "G",
               "COLORLESS": "C", "W": "W", "U": "U", "B": "B", "R": "R", "G": "G", "C": "C"}


def canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(v: Any) -> str:
    return hashlib.sha256(canon(v).encode()).hexdigest()


def dec_label(label: str) -> dict[str, str]:
    """Parse WS48:<kind>:<k>=<v>:... labels; returns {} for legacy labels."""
    out: dict[str, str] = {}
    if not label.startswith("WS48:"):
        out["_legacy"] = label
        return out
    parts = label.split(":")
    out["_kind"] = parts[1] if len(parts) > 1 else ""
    for seg in parts[2:]:
        if "=" in seg:
            k, v = seg.split("=", 1)
            out[k] = urllib.parse.unquote_plus(v)
        else:
            out[seg] = ""
    return out


class Blocked(Exception):
    def __init__(self, where: str, detail: str):
        super().__init__(f"{where}:{detail}")
        self.where = where
        self.detail = detail


def command() -> list[str]:
    raw = os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD")
    if not raw:
        raise RuntimeError("COMMANDER_LAB_FORGE_PROVIDER_CMD missing")
    return shlex.split(raw)


def behavior_env(record: dict[str, Any], transport: Any) -> dict[str, str]:
    if record["execution_entry_mode"] == "NATIVE_STATE_LOAD":
        e = transport.env_for(record)
    else:
        t = record["temporal_state"]
        e = os.environ.copy()
        e.update({
            "COMMANDER_LAB_FORGE_PLAYER_COUNT": str(len(record["players"])),
            "COMMANDER_LAB_FORGE_FIXTURE_ID": record["fixture_id"],
            "COMMANDER_LAB_WS40_ENTRY_MODE": "NATURAL_GAME_START",
            "COMMANDER_LAB_WS40_TURN": str(int(t["turn_number"])),
            "COMMANDER_LAB_WS40_ACTIVE_SEAT": "1",
            "COMMANDER_LAB_WS40_PRIORITY_SEAT": "1",
            "COMMANDER_LAB_WS40_PHASE": str(t["phase"]),
            "COMMANDER_LAB_WS40_STEP": str(t["step"]),
        })
        e.update(transport.knowledge_env(record))
        e.update(transport.randomness_env(record))
    e.pop("COMMANDER_LAB_WS40_CONSTRUCTION_ONLY", None)
    e["COMMANDER_LAB_WS40_CONSTRUCTION_ONLY"] = "0"
    e["COMMANDER_LAB_FORGE_STOP_AFTER_PRIORITY"] = "512"
    return e


class Driver:
    def __init__(self, record: dict[str, Any]):
        self.r = record
        self.script = [copy.deepcopy(d) for d in (record.get("decision_script") or [])]
        self.consumed: list[dict[str, Any]] = []
        self.priority_script = list(record.get("priority_script") or [])
        self.ps_cursor = 0
        self.cost_state = list(record.get("action_cost_state") or [])
        self.mana_cursors: dict[int, int] = {}
        self.target_cursors: dict[int, list[str]] = {}
        self.frames: list[dict[str, Any]] = []
        self.ritual_answers: list[dict[str, Any]] = []
        self.structural_passes: list[dict[str, Any]] = []
        self.decode_errors = 0
        self.offered_for_digest: list[Any] = []
        self.events: list[dict[str, Any]] = []
        self.setup_stage_seen = False

    def pop_script(self, family: str, actor_pid: str | None) -> dict[str, Any] | None:
        for i, d in enumerate(self.script):
            if d["decision_family"] != family:
                continue
            if actor_pid is not None and d.get("actor") != actor_pid:
                continue
            return self.script.pop(i)
        return None

    def ritual(self, frame_kind: str, option_id: str) -> None:
        """Record a construction-precedent startup answer (pre-setup ritual).

        NATIVE_STATE_LOAD sessions replay game startup (starting player +
        mulligan prompts for the pre-hook fresh game) before the state-load
        hook replaces the game state. These frames carry no scripted
        obligation; answering them KEEP/seat-1 reproduces the retained
        G48-07 construction precedent. Bounded to fail closed if abused.
        """
        self.ritual_answers.append({"kind": frame_kind, "option_id": option_id})
        if len(self.ritual_answers) > 8:
            raise Blocked("ritual", "startup ritual exceeded bound; refusing to mask decisions")

    def actor_pid(self, frame: dict[str, Any]) -> str:
        raw = frame.get("actor_id") or ""
        if raw.startswith("seat-"):
            try:
                return "P" + str(int(raw.split("-", 1)[1]))
            except ValueError:
                pass
        return raw

    def options(self, frame: dict[str, Any]) -> list[dict[str, Any]]:
        return list(frame["payload"].get("options") or [])

    def choose(self, frame: dict[str, Any], idx: int) -> str:
        return str(self.options(frame)[idx]["option_id"])


def ref_identity(ref: str) -> str | None:
    """Stable identity of a WS48 entity ref.

    Player refs: WS48:player:<pid>:<name> -> pid
    Card refs:   WS48:<ns>:<local>:<name> (ns is obj/cmd) -> ns:local
    Minted refs: WS48:MINTED-<n>:<name> -> MINTED-<n>
    Other refs:  None (no stable scripted identity)
    """
    if not isinstance(ref, str) or not ref.startswith("WS48:"):
        return None
    rest = ref[len("WS48:"):]
    if rest.startswith("player:"):
        segs = rest.split(":")
        return segs[1] if len(segs) >= 2 else None
    if rest.startswith(("entity:", "object:", "null")):
        return None
    segs = rest.split(":")
    if len(segs) >= 3 and segs[0] in ("obj", "cmd", "stack", "line"):
        return segs[0] + ":" + segs[1]
    if len(segs) >= 1 and segs[0].startswith("MINTED-"):
        return segs[0]
    return None


def sem_ref_match(label: dict[str, str], want_sid: str) -> bool:
    ref = label.get("tgt") or label.get("opt") or label.get("src") or ""
    return ref_identity(ref) == want_sid


def run_record(record: dict[str, Any], transport: Any,
               mutate: dict[str, str] | None = None,
               per_record_timeout: int = 600) -> dict[str, Any]:
    if mutate:
        record = copy.deepcopy(record)
        for d in record.get("decision_script") or []:
            if d["decision_family"] == "target" and d["selection"]["selector_kind"] == "semantic_player":
                d["selection"]["semantic_value"] = mutate.get("target", d["selection"]["semantic_value"])
            if d["decision_family"] == "choose_mode":
                d["selection"]["semantic_value"] = mutate.get("mode", d["selection"]["semantic_value"])
    drv = Driver(record)
    outcome: dict[str, Any] = {"fixture_id": record["fixture_id"], "mutated": bool(mutate)}
    deadline = time.monotonic() + per_record_timeout
    proc: Any = None
    try:
        with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as err:
            p = subprocess.Popen(command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=err, text=True, env=behavior_env(record, transport),
                                 bufsize=1)
            proc = p
            assert p.stdin is not None and p.stdout is not None
            # Binary reader on a duplicated fd: avoids clashing with the text
            # wrapper's internal buffer while keeping line semantics here.
            bindup = os.dup(p.stdout.fileno())
            sel = None
            buf = b""
            try:
                import selectors as _selectors
                sel = _selectors.DefaultSelector()
                sel.register(bindup, _selectors.EVENT_READ)
            except Exception:
                sel = None

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
                        raise Blocked("TIMEOUT", f"no session result within {per_record_timeout}s")
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
                    "request_id": "ws48-probe-reply-" + frame["payload"]["decision_id"],
                    "session_id": frame.get("session_id"),
                    "payload": {"decision_id": frame["payload"]["decision_id"],
                                "option_id": oid}}, separators=(",", ":")) + "\n")
                p.stdin.flush()

            def drain_to_result() -> None:
                """Close stdin (signal handler-unavailable) then keep reading
                until SESSION_RESULT or EOF; the provider must terminate
                itself with a typed stop reason."""
                nonlocal stop_reason, session_snapshot
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
                    typ = m.get("message_type")
                    if typ == "SESSION_RESULT":
                        stop_reason = (m.get("payload") or {}).get("stop_reason")
                        session_snapshot = (m.get("payload") or {}).get("snapshot")
                        break
                    if typ == "NATIVE_EVENT":
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

            # Negative probes: never answer; expect typed fail-closed termination.
            is_negative = any(d["selection"]["selector_kind"] == "fail_closed_probe"
                              for d in drv.script)
            p.stdin.write(json.dumps({
                "protocol": PROTOCOL, "message_type": "CREATE_SESSION",
                "request_id": "ws48-probe-" + record["fixture_id"],
                "payload": {"fixture_id": record["fixture_id"]}},
                separators=(",", ":")) + "\n")
            p.stdin.flush()

            stop_reason: str | None = None
            session_snapshot: Any = None
            answered = 0
            exit_rc: Any = None
            stderr_tail: str = ""
            decode_errors = 0
            for _ in range(4096):
                line = next_line()
                if not line:
                    break
                try:
                    m = json.loads(line)
                except Exception:
                    drv.decode_errors += 1
                    if drv.decode_errors > 16:
                        raise Blocked("PROTOCOL", "too many undecodable lines")
                    continue
                typ = m.get("message_type")
                if typ == "SESSION_CREATED":
                    continue
                if typ == "QUALIFICATION_STATE":
                    stage = (m.get("payload") or {}).get("stage")
                    if stage == "after_native_setup_validation":
                        drv.setup_stage_seen = True
                    continue
                if typ == "NATIVE_EVENT":
                    drv.events.append({"event": (m.get("payload") or {}).get("event"),
                                       "facts": (m.get("payload") or {}).get("facts")})
                    continue
                if typ == "SESSION_RESULT":
                    stop_reason = (m.get("payload") or {}).get("stop_reason")
                    session_snapshot = (m.get("payload") or {}).get("snapshot")
                    break
                if typ != "DECISION_FRAME":
                    raise Blocked("PROTOCOL", f"unexpected message {typ}")
                kind = m["payload"].get("decision_kind")
                actor = drv.actor_pid(m)
                opts = drv.options(m)
                labels = [dec_label(o.get("kind", "")) for o in opts]
                drv.offered_for_digest.append({"kind": kind, "actor": actor,
                                               "options": sorted(o.get("kind", "") for o in opts)})
                kinds = [o.get("kind", "") for o in opts]
                drv.frames.append({"kind": kind, "actor": actor,
                                   "option_count": len(kinds),
                                   "options": kinds[:16]})
                if len(drv.frames) > 256:
                    raise Blocked("PROTOCOL", "frame budget exceeded")
                if is_negative:
                    # Never answer: the external handler is intentionally
                    # unavailable. Drain until the provider terminates itself.
                    drain_to_result()
                    rc, tail = close_and_collect()
                    outcome.update({"stop_after_eof_rc": rc, "stderr_tail": tail})
                    break
                oid = answer_frame(drv, kind, actor, opts, labels, record)
                if oid == "__TERMINATE__":
                    drain_to_result()
                    rc, tail = close_and_collect()
                    outcome.update({"terminate_rc": rc, "stderr_tail": tail})
                    break
                submit(m, oid)
                answered += 1
            else:
                exit_rc, stderr_tail = close_and_collect()
                outcome.update({"verdict": "PROBE_FAIL", "reason": "FRAME_BUDGET_EXHAUSTED",
                                "exit_rc": exit_rc, "stderr_tail": stderr_tail})
                return finish(outcome, drv, stop_reason, session_snapshot, answered)
            if is_negative and stop_reason is not None:
                exit_rc, stderr_tail = close_and_collect()
                outcome.update({"exit_rc": exit_rc, "stderr_tail": stderr_tail})
                return finish_negative(outcome, drv, record, stop_reason)
            if stop_reason is None and "terminate_rc" not in outcome:
                # EOF without SESSION_RESULT: process crashed or exited
                # abnormally. Capture rc + stderr for causal classification.
                exit_rc, stderr_tail = close_and_collect()
                outcome.update({"exit_rc": exit_rc, "stderr_tail": stderr_tail})
            return finish(outcome, drv, stop_reason, session_snapshot, answered)
    except Blocked as b:
        try:
            if proc is not None:
                proc.kill()
        except Exception:
            pass
        outcome.update({"verdict": f"BLOCKED_AT:{b.where}", "reason": b.detail[:4000]})
        return finish(outcome, drv, None, None, 0)
    except Exception as ex:
        try:
            if proc is not None:
                proc.kill()
        except Exception:
            pass
        outcome.update({"verdict": "PROBE_FAIL", "reason": f"{type(ex).__name__}:{ex}"[:4000]})
        return finish(outcome, drv, None, None, 0)


def answer_frame(drv: Driver, kind: str, actor: str,
                 opts: list[dict[str, Any]], labels: list[dict[str, str]],
                 record: dict[str, Any]) -> str:
    def opt_id(i: int) -> str:
        return str(opts[i]["option_id"])

    if kind == "chooseStartingPlayer":
        if (record["execution_entry_mode"] == "NATIVE_STATE_LOAD"
                and not drv.setup_stage_seen):
            for i, o in enumerate(opts):
                if o.get("kind") == "PLAYER:seat-1":
                    drv.ritual(kind, str(o["option_id"]))
                    return str(o["option_id"])
            raise Blocked("chooseStartingPlayer", f"seat-1 not offered: {[o.get('kind') for o in opts]}")
        if record["execution_entry_mode"] == "NATURAL_GAME_START":
            # Startup ritual grounded in the requested start condition: every
            # natural denominator record requests active_player P1, and the
            # construction precedent (G48-07) starts seat-1. Recorded as
            # ritual, never as behavior credit. See checkpoint design note.
            want_active = (record.get("temporal_state") or {}).get("active_player", "P1")
            if want_active == "P1":
                for i, o in enumerate(opts):
                    if o.get("kind") == "PLAYER:seat-1":
                        drv.ritual(kind, str(o["option_id"]))
                        return str(o["option_id"])
            raise Blocked("chooseStartingPlayer",
                          f"non-P1 requested start needs explicit grounding: {want_active}")
        raise Blocked("chooseStartingPlayer", "post-setup starting-player choice is unscripted")
    if kind == "mulliganKeepHand":
        if (record["execution_entry_mode"] == "NATIVE_STATE_LOAD"
                and not drv.setup_stage_seen):
            for i, o in enumerate(opts):
                if o.get("kind") == "KEEP":
                    drv.ritual(kind, str(o["option_id"]))
                    return str(o["option_id"])
            raise Blocked("mulliganKeepHand", f"KEEP not offered in ritual: {[o.get('kind') for o in opts]}")
        d = drv.pop_script("mulligan", actor)
        if d is None:
            raise Blocked("mulligan", f"unscripted mulligan for {actor}")
        sv = d["selection"]["semantic_value"]
        if sv == "keep_opening_hand":
            want = "KEEP"
        elif sv in ("mulligan", "mulligan_once"):
            want = "MULLIGAN"
        else:
            drv.script.insert(0, d)
            raise Blocked("mulligan", f"unsupported mulligan semantic {sv}")
        for i, o in enumerate(opts):
            if o.get("kind") == want or (want == "KEEP" and o.get("kind") == "KEEP"):
                drv.consumed.append(d)
                return opt_id(i)
        # boolean-style fallback: KEEP=true mapping
        raise Blocked("mulligan", f"no offered match for {want}: {[o.get('kind') for o in opts]}")

    if kind == "priority":
        return answer_priority(drv, actor, opts, labels)
    if kind == "target":
        return answer_target(drv, actor, opts, labels)
    if kind == "choose_object":
        return answer_choose_object(drv, actor, opts, labels)
    if kind == "choose_mode":
        return answer_mode(drv, actor, opts, labels)
    if kind == "choose_ability":
        return answer_ability(drv, actor, opts, labels)
    if kind == "mana_payment":
        return answer_mana(drv, actor, opts, labels)
    if kind == "announce_x":
        return answer_number(drv, actor, opts, labels, "announce_x", "integer")
    if kind == "choice":
        return answer_choice(drv, actor, opts, labels)
    if kind == "choose_use":
        return answer_choose_use(drv, actor, opts, labels)
    if kind == "replacement_effect":
        return answer_replacement(drv, actor, opts, labels)
    if kind == "trigger_order":
        return answer_trigger_order(drv, actor, opts, labels)
    if kind == "declare_attacker":
        return answer_declare(drv, actor, opts, labels, "declare_attacker",
                              "attacker_assignment", "attacker", "defender")
    if kind == "declare_blocker":
        return answer_declare(drv, actor, opts, labels, "declare_blocker",
                              "blocker_assignment", "blocker", "attacker")
    if kind in ("confirm",):
        raise Blocked(kind, f"unscripted confirm frame: {[o.get('kind') for o in opts]}")
    raise Blocked(kind, f"unsupported decision kind: {[o.get('kind') for o in opts]}")


def answer_priority(drv: Driver, actor: str, opts: list[dict[str, Any]],
                    labels: list[dict[str, str]]) -> str:
    d = drv.pop_script("priority", actor)
    if d is not None:
        sv = d["selection"]["semantic_value"]
        if isinstance(sv, dict) and sv.get("action") in ("cast", "cast_commander"):
            want = sv.get("object") or sv.get("commander_id")
            hits = []
            for i, lb in enumerate(labels):
                if lb.get("_kind") != "ACT":
                    continue
                if lb.get("host") == want or (sv.get("action") == "cast_commander"
                                              and lb.get("cmd") == want):
                    hits.append(i)
            if len(hits) != 1:
                drv.script.insert(0, d)
                raise Blocked("priority",
                              f"scripted {want}: {len(hits)} offered matches of {len(opts)}")
            drv.consumed.append(d)
            return str(opts[hits[0]]["option_id"])
        drv.script.insert(0, d)
        raise Blocked("priority", f"unsupported priority semantic {sv}")
    ab = drv.pop_script("choose_ability", actor)
    if ab is not None:
        key = str(ab["selection"]["semantic_value"])
        tokens = [t for t in key.lower().replace("_", " ").split() if t]
        hits = []
        for i, lb in enumerate(labels):
            if lb.get("_kind") != "ACT":
                continue
            text = (lb.get("sa", "") + " " + lb.get("host", "")
                    + " " + lb.get("card", "")).lower()
            if all(t in text or (t.endswith("s") and t[:-1] in text)
                   or (t + "s" in text) for t in tokens):
                hits.append(i)
        if len(hits) != 1:
            drv.script.insert(0, ab)
            raise Blocked("priority",
                          f"ability {key}: {len(hits)} offered matches of {len(opts)}")
        drv.consumed.append(ab)
        return str(opts[hits[0]]["option_id"])
    if drv.ps_cursor < len(drv.priority_script):
        ps = drv.priority_script[drv.ps_cursor]
        if ps.get("holder") == actor:
            drv.ps_cursor += 1
            action = str(ps.get("action", ""))
            if action == "PASS":
                for i, o in enumerate(opts):
                    if o.get("kind") == "PASS":
                        return str(o["option_id"])
                raise Blocked("priority", "scripted PASS but no PASS offered")
            if action.startswith("CAST "):
                stuck = action
                raise Blocked("priority", f"scripted CAST action needs grounding: {stuck}")
    # STRUCTURAL_PASS: no unconsumed priority-family obligation remains for
    # this actor, so declining to act cannot skip script. PASS is offered by
    # the provider itself; passing advances the engine toward the next
    # declared decision (or natural game end). Every structural pass is
    # recorded with its frame. Bounded: after the cap, terminate to capture
    # the transcript instead of looping to the engine priority cap.
    pending_priority = [x for x in drv.script
                        if x["decision_family"] == "priority"
                        and x.get("actor") == actor]
    if not pending_priority:
        if len(drv.structural_passes) >= 64:
            return "__TERMINATE__"
        for i, o in enumerate(opts):
            if o.get("kind") == "PASS":
                drv.structural_passes.append({"actor": actor,
                                              "frame_options": len(opts)})
                return str(o["option_id"])
        raise Blocked("priority", "structural pass unavailable: no PASS offered")
    raise Blocked("priority", f"unscripted priority for {actor}; script remaining={len(drv.script)}")


def answer_target(drv: Driver, actor: str, opts: list[dict[str, Any]],
                  labels: list[dict[str, str]]) -> str:
    d = drv.pop_script("target", actor)
    if d is None:
        raise Blocked("target", f"unscripted target for {actor}")
    sel = d["selection"]["selector_kind"]
    sv = d["selection"]["semantic_value"]
    if sel == "semantic_player":
        hits = [i for i, lb in enumerate(labels)
                if lb.get("_kind") in ("TARGET", "TARGETPAIR")
                and ref_identity(lb.get("tgt", "")) == sv]
        if len(hits) != 1:
            drv.script.insert(0, d)
            raise Blocked("target", f"player {sv}: {len(hits)} matches")
        drv.consumed.append(d)
        return str(opts[hits[0]]["option_id"])
    if sel == "semantic_object":
        hits = [i for i, lb in enumerate(labels)
                if lb.get("_kind") in ("TARGET", "TARGETPAIR")
                and ref_identity(lb.get("tgt", "")) == sv]
        if len(hits) != 1:
            drv.script.insert(0, d)
            raise Blocked("target", f"object {sv}: {len(hits)} matches")
        drv.consumed.append(d)
        return str(opts[hits[0]]["option_id"])
    drv.script.insert(0, d)
    raise Blocked("target", f"selector {sel} needs v2 grounding")


def answer_choose_object(drv: Driver, actor: str, opts: list[dict[str, Any]],
                         labels: list[dict[str, str]]) -> str:
    d = drv.pop_script("choose_object", actor)
    if d is None:
        # also serve choose_ability via OPT:sa labels when scripted
        d = drv.pop_script("choose_ability", actor)
        if d is None:
            raise Blocked("choose_object", f"unscripted choose_object for {actor}")
    sv = d["selection"]["semantic_value"]
    if isinstance(sv, str):
        hits = [i for i, lb in enumerate(labels)
                if ref_identity(lb.get("opt", "")) == sv]
        if len(hits) != 1:
            drv.script.insert(0, d)
            raise Blocked("choose_object", f"object {sv}: {len(hits)} matches")
        drv.consumed.append(d)
        return str(opts[hits[0]]["option_id"])
    drv.script.insert(0, d)
    raise Blocked("choose_object", f"non-string semantic {sv} needs v2 grounding")


def answer_ability(drv: Driver, actor: str, opts: list[dict[str, Any]],
                   labels: list[dict[str, str]]) -> str:
    """Match scripted activated-ability keys against native ABILITY/OPT:sa labels."""
    d = drv.pop_script("choose_ability", actor)
    if d is None:
        raise Blocked("choose_ability", f"unscripted choose_ability for {actor}")
    key = str(d["selection"]["semantic_value"])
    tokens = [t for t in key.lower().replace("_", " ").split() if t]
    hits = []
    for i, lb in enumerate(labels):
        if lb.get("_kind") not in ("ABILITY", "OPT"):
            continue
        text = (lb.get("sa", "") + " " + lb.get("host", "")).lower()
        if all(t in text or (t.endswith("s") and t[:-1] in text)
               or (t + "s" in text) for t in tokens):
            hits.append(i)
    if len(hits) != 1:
        drv.script.insert(0, d)
        raise Blocked("choose_ability",
                      f"key {key}: {len(hits)} grounded matches")
    drv.consumed.append(d)
    return str(opts[hits[0]]["option_id"])


def answer_mode(drv: Driver, actor: str, opts: list[dict[str, Any]],
                labels: list[dict[str, str]]) -> str:
    d = drv.pop_script("choose_mode", actor)
    if d is None:
        raise Blocked("choose_mode", f"unscripted choose_mode for {actor}")
    key = str(d["selection"]["semantic_value"])
    tokens = [t for t in key.lower().replace("_", " ").split() if t]
    hits = []
    for i, lb in enumerate(labels):
        if lb.get("_kind") != "MODE":
            continue
        text = (lb.get("api", "") + " " + lb.get("desc", "")).lower()
        if all(t in text or (t.endswith("s") and t[:-1] in text)
               or (t + "s" in text) for t in tokens):
            hits.append(i)
    if len(hits) != 1:
        drv.script.insert(0, d)
        raise Blocked("choose_mode",
                      f"key {key}: {len(hits)} grounded matches; descs={[lb.get('desc', '')[:80] for lb in labels if lb.get('_kind') == 'MODE']}")
    drv.consumed.append(d)
    return str(opts[hits[0]]["option_id"])


def answer_mana(drv: Driver, actor: str, opts: list[dict[str, Any]],
                labels: list[dict[str, str]]) -> str:
    # consume explicit_payment_sources in scripted order across repeated frames
    sources: list[str] = []
    for cs in drv.cost_state:
        if cs.get("actor", actor) == actor or "actor" not in cs:
            sources.extend(cs.get("explicit_payment_sources") or [])
    key = actor
    used = drv.mana_cursors.get(key, 0)
    if used >= len(sources):
        raise Blocked("mana_payment", f"unscripted mana frame {used + 1} for {actor}")
    want = sources[used]
    hits = [i for i, lb in enumerate(labels)
            if lb.get("_kind") == "MANA" and ref_identity(lb.get("src", "")) == want]
    if len(hits) != 1:
        raise Blocked("mana_payment", f"source {want}: {len(hits)} matches")
    drv.mana_cursors[key] = used + 1
    return str(opts[hits[0]]["option_id"])


def answer_number(drv: Driver, actor: str, opts: list[dict[str, Any]],
                  labels: list[dict[str, str]], family: str, selector: str) -> str:
    d = drv.pop_script(family, actor)
    if d is None:
        raise Blocked(family, f"unscripted {family} for {actor}")
    want = str(int(d["selection"]["semantic_value"]))
    hits = [i for i, lb in enumerate(labels)
            if lb.get("_kind") == "NUM" and lb.get("n") == want]
    if len(hits) != 1:
        drv.script.insert(0, d)
        raise Blocked(family, f"n={want}: {len(hits)} matches")
    drv.consumed.append(d)
    return str(opts[hits[0]]["option_id"])


def answer_choice(drv: Driver, actor: str, opts: list[dict[str, Any]],
                  labels: list[dict[str, str]]) -> str:
    d = drv.pop_script("choice", actor)
    if d is None:
        raise Blocked("choice", f"unscripted choice for {actor}")
    sel = d["selection"]["selector_kind"]
    sv = d["selection"]["semantic_value"]
    if sel == "semantic_choice_key":
        want = COLOR_SHORT.get(str(sv).upper(), str(sv))
        hits = [i for i, lb in enumerate(labels)
                if lb.get("_kind") == "COLOR" and lb.get("color", "").upper() == want.upper()]
        if len(hits) != 1:
            drv.script.insert(0, d)
            raise Blocked("choice", f"color {sv}: {len(hits)} matches")
        drv.consumed.append(d)
        return str(opts[hits[0]]["option_id"])
    if sel == "boolean":
        want = "true" if sv is True else "false"
        hits = [i for i, lb in enumerate(labels)
                if lb.get("_kind") == "BOOL" and lb.get("val") == want]
        if len(hits) != 1:
            drv.script.insert(0, d)
            raise Blocked("choice", f"bool {sv}: {len(hits)} matches")
        drv.consumed.append(d)
        return str(opts[hits[0]]["option_id"])
    drv.script.insert(0, d)
    raise Blocked("choice", f"selector {sel} needs v2 grounding")


def answer_choose_use(drv: Driver, actor: str, opts: list[dict[str, Any]],
                      labels: list[dict[str, str]]) -> str:
    d = drv.pop_script("choose_use", actor)
    if d is None:
        # scry arrangement without explicit script entry is not permitted
        raise Blocked("choose_use", f"unscripted choose_use for {actor}")
    sv = d["selection"]["semantic_value"]
    if isinstance(sv, bool):
        want = "true" if sv else "false"
        hits = [i for i, lb in enumerate(labels)
                if lb.get("_kind") == "BOOL" and lb.get("val") == want]
        if len(hits) != 1:
            drv.script.insert(0, d)
            raise Blocked("choose_use", f"bool {sv}: {len(hits)} matches")
        drv.consumed.append(d)
        return str(opts[hits[0]]["option_id"])
    drv.script.insert(0, d)
    raise Blocked("choose_use", "non-boolean choose_use needs v2 grounding")


def answer_replacement(drv: Driver, actor: str, opts: list[dict[str, Any]],
                       labels: list[dict[str, str]]) -> str:
    d = drv.pop_script("replacement_effect", actor)
    if d is None:
        raise Blocked("replacement_effect", f"unscripted replacement for {actor}")
    sv = d["selection"]["semantic_value"]
    if isinstance(sv, bool):
        want = "true" if sv else "false"
        hits = [i for i, lb in enumerate(labels)
                if lb.get("_kind") == "REPL" and lb.get("apply") == want]
        if len(hits) != 1:
            drv.script.insert(0, d)
            raise Blocked("replacement_effect", f"apply={sv}: {len(hits)} matches")
        drv.consumed.append(d)
        return str(opts[hits[0]]["option_id"])
    drv.script.insert(0, d)
    raise Blocked("replacement_effect", "non-boolean replacement needs v2 grounding")


def answer_trigger_order(drv: Driver, actor: str, opts: list[dict[str, Any]],
                         labels: list[dict[str, str]]) -> str:
    d = drv.pop_script("trigger_order", actor)
    if d is None:
        raise Blocked("trigger_order", f"unscripted trigger_order for {actor}")
    want = [str(x).split(":", 1)[1].lower() if ":" in str(x) else str(x).lower()
            for x in d["selection"]["semantic_value"]]
    hits = []
    for i, lb in enumerate(labels):
        if lb.get("_kind") != "ORDER":
            continue
        first = lb.get("first", "").lower()
        second = lb.get("second", "").lower()
        if len(want) == 2 and want[0] in first and want[1] in second:
            if lb.get("order") == "0,1":
                hits.append(i)
        if len(want) == 2 and want[0] in second and want[1] in first:
            if lb.get("order") == "1,0":
                hits.append(i)
    if len(hits) != 1:
        drv.script.insert(0, d)
        raise Blocked("trigger_order", f"order {want}: {len(hits)} matches")
    drv.consumed.append(d)
    return str(opts[hits[0]]["option_id"])


def answer_declare(drv: Driver, actor: str, opts: list[dict[str, Any]],
                   labels: list[dict[str, str]], family: str, selector: str,
                   self_key: str, foe_key: str) -> str:
    d = drv.pop_script(family, actor)
    if d is None:
        raise Blocked(family, f"unscripted {family} for {actor}")
    assignment = d["selection"]["semantic_value"]
    # find this frame's subject: the single non-SKIP identity shared across options
    subjects = set()
    for lb in labels:
        sk = lb.get(self_key, "")
        if sk and sk != "SKIP":
            ident = ref_identity(sk)
            if ident is not None:
                subjects.add(ident)
    if len(subjects) != 1:
        drv.script.insert(0, d)
        raise Blocked(family, f"ambiguous frame subject: {sorted(subjects)}")
    subject = next(iter(subjects))
    want_foe = assignment.get(subject)
    if want_foe is None:
        # script-absence means SKIP; find SKIP option
        for i, lb in enumerate(labels):
            raw = opts[i].get("kind", "")
            if "SKIP" in raw:
                drv.consumed.append(d)
                return str(opts[i]["option_id"])
        drv.script.insert(0, d)
        raise Blocked(family, f"{subject} unscripted but no SKIP offered")
    hits = []
    for i, lb in enumerate(labels):
        if ref_identity(lb.get(foe_key, "")) == want_foe:
            hits.append(i)
    if len(hits) != 1:
        drv.script.insert(0, d)
        raise Blocked(family, f"{subject}->{want_foe}: {len(hits)} matches")
    drv.consumed.append(d)
    return str(opts[hits[0]]["option_id"])


def finish(outcome: dict[str, Any], drv: Driver, stop_reason: Any,
           snapshot: Any, answered: int) -> dict[str, Any]:
    remaining = [{"family": d["decision_family"], "actor": d.get("actor"),
                  "selector": d["selection"]["selector_kind"]} for d in drv.script]
    if "verdict" not in outcome:
        if "terminate_rc" in outcome and not remaining:
            # Harness-initiated EOF after the full script was consumed: the
            # provider's EOF-typed stop is the expected termination signal,
            # not a mid-script fail-closed.
            outcome["verdict"] = "TRANSCRIPT_COMPLETE"
        elif stop_reason in ("FORGE_GAME_RETURNED", "WS23_CONTROLLED_AFTER_PRIORITY_512"):
            if not remaining:
                outcome["verdict"] = "TRANSCRIPT_COMPLETE"
            else:
                outcome["verdict"] = "PROBE_FAIL"
                outcome["reason"] = f"stopped with {len(remaining)} scripted decisions unconsumed"
        elif stop_reason and ("WS23_FAIL_CLOSED_UNSUPPORTED" in str(stop_reason)
                               or "WS48_UNSUPPORTED_DISCRETIONARY_DECISION" in str(stop_reason)):
            outcome["verdict"] = f"BLOCKED_AT:{stop_reason}"
        elif stop_reason and "WS23_EXTERNAL_EOF" in str(stop_reason):
            outcome["verdict"] = "TRANSCRIPT_COMPLETE" if not remaining else "PROBE_FAIL"
            if remaining:
                outcome["reason"] = f"EOF with {len(remaining)} unconsumed"
        elif stop_reason:
            outcome["verdict"] = "PROBE_FAIL"
            outcome["reason"] = f"stop_reason={stop_reason}"
        else:
            outcome["verdict"] = "PROBE_FAIL"
            outcome["reason"] = "no session result captured"
    outcome.update({
        "setup_stage_seen": drv.setup_stage_seen,
        "frames": len(drv.frames),
        "answered": answered,
        "consumed": len(drv.consumed),
        "ritual_answers": drv.ritual_answers,
        "structural_passes": drv.structural_passes,
        "decode_errors": drv.decode_errors,
        "frames_detail": drv.frames[:64],
        "native_event_tape": drv.events[:128],
        "session_snapshot": snapshot,
        "script_remaining": remaining,
        "stop_reason": stop_reason,
        "offered_digest": digest(drv.offered_for_digest),
        "native_events": len(drv.events),
        "evidence_class": "TRANSCRIPT_PROBE",
    })
    return outcome


def finish_negative(outcome: dict[str, Any], drv: Driver,
                    record: dict[str, Any], stop_reason: str) -> dict[str, Any]:
    if stop_reason.startswith("WS48_UNSUPPORTED_DISCRETIONARY_DECISION"):
        outcome["verdict"] = "EXPECTED_FAIL_CLOSED_PASS"
    elif stop_reason.startswith("WS23_FAIL_CLOSED_UNSUPPORTED"):
        outcome["verdict"] = "EXPECTED_FAIL_CLOSED_PASS"
    else:
        outcome["verdict"] = "PROBE_FAIL"
        outcome["reason"] = f"negative probe did not fail closed: {stop_reason}"
    outcome.update({
        "setup_stage_seen": drv.setup_stage_seen,
        "frames": len(drv.frames),
        "answered": 0,
        "consumed": 0,
        "ritual_answers": drv.ritual_answers,
        "evidence_class": "TRANSCRIPT_PROBE",
        "offered_digest": digest(drv.offered_for_digest),
        "stop_reason": stop_reason,
    })
    return outcome


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--materialization", type=Path, required=True)
    ap.add_argument("--denominator", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--fixtures", default="",
                    help="comma-separated fixture ids; default: probe subset")
    ap.add_argument("--mutate-target", default="")
    ap.add_argument("--mutate-mode", default="")
    ap.add_argument("--runners", default=".",
                    help="directory containing run_strict_no_echo_gate.py transport")
    a = ap.parse_args()
    sys.path.insert(0, a.runners)
    import run_strict_no_echo_gate as transport

    raw = a.materialization.read_bytes()
    if hashlib.sha256(raw).hexdigest() != WS47_SHA:
        raise SystemExit("immutable WS47 materialization digest mismatch")
    doc = json.loads(raw)
    if doc["schema_version"] != WS47_SCHEMA or doc["canonical_bundle_digest"] != WS47_BUNDLE:
        raise SystemExit("immutable WS47 identity mismatch")
    denom_ids = list(json.loads(a.denominator.read_text())["fixture_ids"])
    if len(denom_ids) != 107 or len(set(denom_ids)) != 107:
        raise SystemExit("WS47 denominator is not exact 107")
    by = {r["fixture_id"]: r for r in doc["records"]}
    if a.fixtures.strip():
        wanted = [x.strip() for x in a.fixtures.split(",") if x.strip()]
    else:
        wanted = ["PILOT_PRIORITY", "PILOT_TARGET", "PILOT_CHOOSE_MODE",
                  "PILOT_MULLIGAN", "NEGATIVE_FIRST_OPTION", "HIDDEN_01",
                  "MICRO_PRIORITY", "WS05-MP-BLOCK-4", "CARD_02", "PLAYER_COUNT_2P"]
    for fid in wanted:
        if fid not in by:
            raise SystemExit(f"unknown fixture {fid}")
    mutate = None
    if a.mutate_target or a.mutate_mode:
        mutate = {"target": a.mutate_target or "P2", "mode": a.mutate_mode or "create_devils"}

    rows: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "schema_version": "commander-lab.ws48-behavior-transcript-probe/1.0.0",
        "evidence_class": "TRANSCRIPT_PROBE",
        "grants_behavior_credit": False,
        "ws47": {"commit": WS47_COMMIT, "tree": WS47_TREE, "schema": WS47_SCHEMA,
                 "bundle_digest": WS47_BUNDLE, "materialization_sha256": WS47_SHA},
        "forge": {"commit": FORGE_COMMIT, "tree": FORGE_TREE},
        "historical_successor_runtime_credit_imported": 0,
        "construction_credit": "107/107",
        "behavior_credit": "0/107",
        "mutated": bool(mutate),
        "rows": rows,
    }
    fail = False
    for i, fid in enumerate(wanted, 1):
        row = run_record(by[fid], transport, mutate=mutate)
        row["index"] = i
        rows.append(row)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(f"WS48 PROBE {i:02d}/{len(wanted)} {fid} -> {row.get('verdict')} "
              f"frames={row.get('frames')} consumed={row.get('consumed')}", flush=True)
        if row.get("verdict") == "PROBE_FAIL":
            fail = True
    summary = collections.Counter(r.get("verdict", "?").split(":")[0] for r in rows)
    result["summary"] = dict(sorted(summary.items()))
    a.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result.get("summary"), indent=2, sort_keys=True))
    return 1 if fail else 0


import collections  # noqa: E402  (kept at bottom to mirror repo runner style)


if __name__ == "__main__":
    raise SystemExit(main())
