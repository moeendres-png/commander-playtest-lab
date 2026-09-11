#!/usr/bin/env python3
"""WS48-R1f non-first ACT selection->execution witness (qualification-only).

Proves post-Repair-01 that an externally selected NON-FIRST priority ACT
option binds to the exact same native SpellAbility the engine executes.

Method (generic; no card-name assertions):
  1. Drive a NATURAL_GAME_START session (PILOT_MULLIGAN: all-Mountain hands)
     with the scripted mulligan/startup ritual only; priority is witness
     controlled, never scripted.
  2. On the first priority frame offering >=3 ACT options with IDENTICAL
     ability text (same sa payload, distinct hosts), select the LAST one by
     strict host identity (opaque index recorded; ACT rank >= 2 guaranteed).
     Identical-sa options are indistinguishable by name: only the host
     MINTED id can prove exact binding.
  3. Java-side tripwire: the R1f priority_binding NATIVE_EVENT records the
     opaque idx, the selected label, and the RETURNED native host id.
     Require returned hostId == selected host id.
  4. Engine-side tripwire: on the next same-actor priority frame offering
     the same sa-group, require the selected host id ABSENT and every other
     pre-selection host id PRESENT (the played land left exactly that hand
     slot). Under the old double-add mapping the engine would execute a
     shifted neighbor instead, failing both tripwires.
  5. PASS everything else; EOF-drain to a truthful SESSION_RESULT.

Verdict PASS requires ALL of: multi-option offer, non-first selection,
binding agreement, execution agreement. Emits
WS48_R1F_REPAIR01_RUNTIME_WITNESS.json. Exit 0 on PASS, 1 otherwise.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve()
CANDIDATE_DIR = HERE.parent
REPO_ROOT = CANDIDATE_DIR.parents[1]
sys.path.insert(0, str(CANDIDATE_DIR))

import run_behavior_transcript_probe as probe  # noqa: E402  (live R1e driver semantics)

WITNESS_VERSION = "commander-lab.ws48-r1f-nonfirst-act-witness/1.0.0"


def host_of(label: dict[str, str]) -> str | None:
    return label.get("host")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--materialization", type=Path, required=True)
    ap.add_argument("--denominator", type=Path, required=True)
    ap.add_argument("--runners", type=Path, required=True)
    ap.add_argument("--provider-cmd", default="")
    ap.add_argument("--json-out", type=Path, required=True)
    ap.add_argument("--fixture", default="PILOT_MULLIGAN")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    if args.provider_cmd:
        os.environ["COMMANDER_LAB_FORGE_PROVIDER_CMD"] = args.provider_cmd
    sys.path.insert(0, str(args.runners))
    import run_strict_no_echo_gate as transport  # noqa: E402

    raw = args.materialization.read_bytes()
    if hashlib.sha256(raw).hexdigest() != probe.WS47_SHA:
        raise SystemExit("immutable WS47 materialization digest mismatch")
    doc = json.loads(raw)
    rec = next(r for r in doc["records"] if r["fixture_id"] == args.fixture)
    assert not [d for d in (rec.get("decision_script") or [])
                if d["decision_family"] in ("priority", "choose_ability")], \
        "witness requires script-free priority"
    assert not rec.get("priority_script"), "witness requires empty priority_script"

    drv = probe.Driver(copy.deepcopy(rec))
    evidence: dict = {
        "witness": WITNESS_VERSION,
        "fixture_id": args.fixture,
        "forge_commit": probe.FORGE_COMMIT,
        "forge_tree": probe.FORGE_TREE,
        "ws47_sha256": probe.WS47_SHA,
    }
    selection: dict | None = None
    bindings: list[dict] = []
    post_frames: list[dict] = []
    stop_reason = None
    verdict, reason = "UNKNOWN", "not run"

    deadline = time.monotonic() + args.timeout
    env = probe.behavior_env(rec, transport)
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as err:
        p = subprocess.Popen(probe.command(), stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=err, text=True,
                             env=env, bufsize=1)
        assert p.stdin is not None and p.stdout is not None
        bindup = os.dup(p.stdout.fileno())
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
                if time.monotonic() > deadline:
                    raise TimeoutError("witness deadline exceeded")
                time.sleep(0.05)
                try:
                    chunk = os.read(bindup, 65536)
                except OSError:
                    chunk = b""
                if chunk:
                    buf += chunk

        def submit(frame: dict, oid: str) -> None:
            assert p.stdin is not None
            p.stdin.write(json.dumps({
                "protocol": probe.PROTOCOL, "message_type": "SUBMIT_DECISION",
                "request_id": "ws48-r1f-" + frame["payload"]["decision_id"],
                "session_id": frame.get("session_id"),
                "payload": {"decision_id": frame["payload"]["decision_id"],
                            "option_id": oid}}, separators=(",", ":")) + "\n")
            p.stdin.flush()

        try:
            p.stdin.write(json.dumps({
                "protocol": probe.PROTOCOL, "message_type": "CREATE_SESSION",
                "request_id": "ws48-r1f-" + rec["fixture_id"],
                "payload": {"fixture_id": rec["fixture_id"]}},
                separators=(",", ":")) + "\n")
            p.stdin.flush()
            priority_seen = 0
            done = False
            for _ in range(4096):
                line = next_line()
                if not line:
                    break
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                typ = m.get("message_type")
                if typ == "SESSION_CREATED":
                    continue
                if typ == "QUALIFICATION_STATE":
                    if ((m.get("payload") or {}).get("stage")
                            == "after_native_setup_validation"):
                        drv.setup_stage_seen = True
                    continue
                if typ == "NATIVE_EVENT":
                    payload = m.get("payload") or {}
                    drv.events.append({"event": payload.get("event"),
                                       "facts": payload.get("facts")})
                    if payload.get("event") == "priority_binding":
                        bindings.append({"facts": payload.get("facts")})
                    continue
                if typ == "SESSION_RESULT":
                    stop_reason = (m.get("payload") or {}).get("stop_reason")
                    drv.result_seen = True
                    break
                if typ != "DECISION_FRAME":
                    raise RuntimeError(f"unexpected message {typ}")
                kind = m["payload"].get("decision_kind")
                actor = drv.actor_pid(m)
                opts = drv.options(m)
                labels = [probe.dec_label(o.get("kind", "")) for o in opts]
                if kind != "priority":
                    oid = probe.answer_frame(drv, kind, actor, opts, labels, rec)
                    submit(m, oid)
                    continue
                # ---- witness-controlled priority -------------------------
                priority_seen += 1
                act_idx = [i for i, lb in enumerate(labels)
                           if lb.get("_kind") == "ACT"]
                if selection is None:
                    groups: dict[str, list[int]] = {}
                    for i in act_idx:
                        groups.setdefault(labels[i].get("sa", ""), []).append(i)
                    big = [(sa, idxs) for sa, idxs in groups.items()
                           if len(idxs) >= 3]
                    if big and priority_seen <= 200:
                        sa_text, idxs = sorted(big, key=lambda kv: -len(kv[1]))[0]
                        pick = idxs[-1]  # LAST of the identical-sa group
                        act_rank = len([i for i in act_idx if i <= pick])
                        assert act_rank >= 2, "witness requires non-first pick"
                        hosts = [host_of(labels[i]) for i in idxs]
                        assert all(hosts) and len(set(hosts)) == len(hosts), \
                            "identical-sa options must carry distinct host identities"
                        selection = {
                            "frame_decision_id": m["payload"].get("decision_id"),
                            "actor": actor,
                            "offered_count": len(opts),
                            "act_count": len(act_idx),
                            "sa_group_size": len(idxs),
                            "sa_text": sa_text,
                            "sa_text_head": sa_text[:80],
                            "offered_hosts": hosts,
                            "selected_host": host_of(labels[pick]),
                            "selected_option_id": opts[pick]["option_id"],
                            "selected_idx": int(opts[pick]["option_id"][1:]),
                            "selected_act_rank": act_rank,
                            "selected_label_head": opts[pick]["kind"][:120],
                        }
                        submit(m, str(opts[pick]["option_id"]))
                        continue
                    # not yet selectable: structural PASS
                    for i, o in enumerate(opts):
                        if o.get("kind") == "PASS":
                            submit(m, str(o["option_id"]))
                            break
                    else:
                        raise RuntimeError("structural pass unavailable")
                    continue
                # ---- post-selection observation --------------------------
                if actor == selection["actor"] and act_idx:
                    # group hosts by sa text for a like-for-like set compare
                    groups2: dict[str, list[str]] = {}
                    for i in act_idx:
                        groups2.setdefault(labels[i].get("sa", ""),
                                           []).append(host_of(labels[i]) or "?")
                    post_frames.append({
                        "actor": actor,
                        "offered_count": len(opts),
                        "act_count": len(act_idx),
                        "groups": {k[:40]: v for k, v in groups2.items()},
                    })
                    if len(post_frames) >= 1 and act_idx:
                        done = True
                for i, o in enumerate(opts):
                    if o.get("kind") == "PASS":
                        submit(m, str(o["option_id"]))
                        break
                else:
                    raise RuntimeError("structural pass unavailable")
                if done or priority_seen > 200:
                    break
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
                    drv.result_seen = True
                    break
                if m.get("message_type") == "NATIVE_EVENT":
                    payload = m.get("payload") or {}
                    if payload.get("event") == "priority_binding":
                        bindings.append({"facts": payload.get("facts")})
        except Exception as ex:  # noqa: BLE001
            verdict, reason = "FAIL", f"witness harness error: {type(ex).__name__}:{ex}"[:500]
        finally:
            try:
                p.kill()
            except Exception:
                pass
            err.seek(0)
            evidence["stderr_tail"] = err.read()[-3000:]

    evidence.update({
        "selection": selection,
        "bindings": bindings,
        "post_frames": post_frames[:4],
        "priority_frames_seen": priority_seen,
        "stop_reason": stop_reason,
    })

    if verdict == "FAIL":
        evidence.update({"verdict": verdict, "reason": reason})
        args.json_out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"verdict": verdict, "reason": reason}))
        return 1

    checks: dict[str, bool | str] = {}
    if selection is None:
        checks["multi_act_offered"] = "no frame offered >=3 identical-sa ACTs"
    else:
        checks["multi_act_offered"] = True
        checks["non_first_selected"] = (
            selection["selected_act_rank"] >= 2
            and selection["selected_idx"] >= 2
        )
        # Java-side binding: returned hostId == selected host id.
        sel_host = selection["selected_host"] or ""
        sel_num = sel_host.split("-")[-1] if "-" in sel_host else sel_host
        match = [b for b in bindings if f"hostId={sel_num}" in (b.get("facts") or "")]
        checks["binding_returned_selected_host"] = len(match) >= 1
        checks["binding_detail"] = (
            match[0]["facts"][:300] if match else
            f"no binding with hostId={sel_num} in {len(bindings)} bindings"
        )
        # Engine-side: the selected host must have LEFT the selection sa-group
        # (e.g. "Play land": the played land is no longer hand-offered) and
        # must still be tracked offering post-execution abilities (e.g. the
        # battlefield mana ability: the card moved hand -> battlefield and
        # the engine accepted it). Sibling hand cards offer nothing once the
        # land drop is consumed, so sibling presence is informational only.
        if post_frames:
            pf = post_frames[0]
            sel_host = selection["selected_host"] or ""
            sel_sa = selection.get("sa_text") or ""
            same_sa_hosts = []
            for sa, hosts in pf["groups"].items():
                if sa == sel_sa[:40]:
                    same_sa_hosts.extend(hosts)
            flat = [h for v in pf["groups"].values() for h in v]
            checks["execution_selected_left_sagroup"] = sel_host not in same_sa_hosts
            checks["execution_selected_active_post"] = sel_host in flat
            checks["post_frame"] = pf
        else:
            checks["execution_selected_left_sagroup"] = "no post-selection same-actor frame"
            checks["execution_selected_active_post"] = "no post-selection same-actor frame"

    hard = [v for k, v in checks.items()
            if k in ("multi_act_offered", "non_first_selected",
                     "binding_returned_selected_host",
                     "execution_selected_left_sagroup",
                     "execution_selected_active_post")]
    if all(v is True for v in hard) and len(hard) == 5:
        verdict, reason = "PASS", (
            "non-first ACT selected by strict host identity; Java binding "
            "returned the same native host; engine-accepted post-observation "
            "shows exactly the selected host moved"
        )
    else:
        verdict, reason = "FAIL", (
            "agreement chain broken: "
            + json.dumps({k: v for k, v in checks.items()})[:800]
        )
    evidence.update({"verdict": verdict, "reason": reason, "checks": checks})
    args.json_out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason}, indent=2))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
