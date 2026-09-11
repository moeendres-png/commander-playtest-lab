#!/usr/bin/env python3
"""WS55R diag helper: summarize a breadth journal (hands, battlefield, block)."""
from __future__ import annotations

import json
import sys


def main() -> int:
    path = sys.argv[1]
    d = json.loads(open(path).read())
    print(f"verdict={d['verdict']} frames={d['frame_count']} consumed={d.get('consumed_intent')}")
    fr = d["frames"]
    last = fr[-1]
    print(f"blocked at: {last['engine_frame_id']} {last['kind']} {last['actor']}")
    print(f"block: {json.dumps(last.get('block'))[:300]}")
    snap = last.get("state_snapshot")
    try:
        s = json.loads(snap) if isinstance(snap, str) else (snap or {})
    except Exception:
        s = {}
    print(f"turn/phase: {s.get('turn')}/{s.get('phase')}")
    # Offered options at block.
    for o in (last.get("offered_options") or [])[:14]:
        print(f"  OPT {o.get('id')} {str(o.get('kind'))[:110]}")
    # Latest per-seat hands + battlefield (viewer P1 sees own; use each viewer).
    seen: dict[str, list] = {}
    bf = None
    stack = None
    for f in reversed(fr):
        for o in f.get("observations") or []:
            try:
                v = json.loads(o["view"])
            except Exception:
                continue
            vw = v.get("viewer")
            if vw not in seen:
                seen[vw] = [(c["id"], c["name"]) for h in v.get("hands", [])
                            for c in h.get("cards", []) if h.get("owner") == vw]
            if bf is None:
                bf = [(c.get("id"), c.get("name"), c.get("controller"))
                      for c in v.get("battlefield", [])]
                stk = v.get("stack", [])
                stack = [(c.get("id"), c.get("name")) for c in stk] if stk else []
        if len(seen) >= 4 and bf is not None:
            break
    for seat in ("P1", "P2", "P3", "P4"):
        print(f"  hand {seat}: {seen.get(seat)}")
    print(f"  battlefield: {bf}")
    print(f"  stack: {stack}")
    # Audit milestones anywhere.
    s_all = json.dumps(d)
    for kw in ("CANDIDATES", "chooseSingleReplacementEffect", "REPL:", "CALLED"):
        n = s_all.count(kw)
        if n:
            print(f"  milestone {kw!r} x{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
