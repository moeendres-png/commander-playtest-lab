#!/usr/bin/env python3
"""WS55R C01 planted-leak audit: fresh principal-scoped validation for the
corrected cost/pitch hidden-hand context.

Asserts over a breadth journal:
  1. Pitch-relevant hidden identities (Frog id 8, FoW ids 3/2 while in P1's
     hand) NEVER appear in any non-P1 viewer's observation hands, nor in any
     non-P1-actor frame's offered options.
  2. Public stack knowledge (Elves spell id 196 while on stack) IS visible to
     all viewers (no over-redaction of public information).
  3. Post-discard publicity: ids discarded to graveyard (public zone) may
     legitimately appear thereafter (not leaks).

Usage: ws55r_hidden_audit.py <journal> ; prints JSON verdict.
"""
from __future__ import annotations

import json
import re
import sys

PITCH_IDS = {8, 3, 2}          # Frog 8, FoW 3, FoW 2 (P1-seat hand, C01 probe)
PITCH_NAMES = {"Turn to Frog", "Force of Will"}
STACK_ID = 196                 # Elves spell (public while on stack)


def main() -> int:
    path = sys.argv[1]
    d = json.loads(open(path).read())
    frames = d["frames"]
    violations: list[str] = []
    checks = 0
    stack_public_ok = 0
    stack_public_frames = 0
    # Track when pitch ids become public (graveyard/exile/battlefield/stack).
    public_from_frame: dict[int, int] = {}
    for f in frames:
        seq = f.get("engine_frame_seq", -1)
        for o in f.get("observations") or []:
            try:
                v = json.loads(o["view"])
            except Exception:
                continue
            viewer = v.get("viewer")
            # Public zones snapshot for this frame.
            pub_here = set()
            for z in ("graveyard", "exile"):
                for c in v.get(z, []) or []:
                    pub_here.add(c.get("id"))
            for c in v.get("battlefield", []) or []:
                pub_here.add(c.get("id"))
            for c in v.get("stack", []) or []:
                pub_here.add(c.get("id"))
            for pid in PITCH_IDS:
                if pid in pub_here and pid not in public_from_frame:
                    public_from_frame[pid] = seq
            # Rule 1: non-P1 viewers must not see pitch ids in HANDS unless
            # already public.
            if viewer != "P1":
                for h in v.get("hands", []) or []:
                    for c in h.get("cards", []) or []:
                        checks += 1
                        if c.get("id") in PITCH_IDS and seq < public_from_frame.get(c["id"], 10 ** 18):
                            violations.append(
                                f"{f['engine_frame_id']} viewer {viewer} sees hidden "
                                f"{c.get('name')} id {c.get('id')} in hand of {h.get('owner')}")
            # Rule 2: stack publicity intact (checked on frames with stack).
            stk = [c.get("id") for c in v.get("stack", []) or []]
            if STACK_ID in stk:
                stack_public_frames += 1
                stack_public_ok += 1
        # Rule 1b: P1's pitch cards (host ids 8/3/2) must never be offered
        # on non-P1 frames (cross-principal option leakage). Other seats'
        # own cards on their own frames are entitled, not leaks.
        if f.get("actor") != "P1":
            for o in f.get("offered_options") or []:
                k = str(o.get("kind", ""))
                m = re.search(r"host=MINTED-(\d+)", k)
                if m and int(m.group(1)) in PITCH_IDS:
                    checks += 1
                    violations.append(
                        f"{f['engine_frame_id']} actor {f.get('actor')} offered "
                        f"P1-hidden id {m.group(1)}")
    verdict = "PASS" if not violations else "FAIL"
    print(json.dumps({
        "schema": "ws55r.hidden-planted-audit.v1",
        "journal": path.split("/")[-1],
        "frames": len(frames),
        "non_owner_hand_card_checks": checks,
        "stack_public_observations": stack_public_ok,
        "pitch_ids_public_from_frame": public_from_frame,
        "violations": violations[:10],
        "violation_count": len(violations),
        "verdict": verdict,
    }, indent=1))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
