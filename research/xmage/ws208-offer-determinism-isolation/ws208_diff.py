#!/usr/bin/env python3
"""WS208 pairwise layered-trace differ.

Compares N fresh-JVM traces of one construction and reports the FIRST
divergence at each layer:

  L_STATE   semantic state fingerprint (turn/phase/step/active/life/board/stack/...)
  L_HAND    diagnostic hand multisets (hidden-state causality probe)
  L_LIB     diagnostic library order hash / sizes
  L_NATIVE_SET   native pre-projection option SET (label multiset)
  L_NATIVE_ORDER native pre-projection option ORDER only
  L_PROJ_SET     projected post-projection SET
  L_PROJ_ORDER   projected ORDER only
  L_SELECT  selected label / class / actor

A layer is reported only with the exact first offset at which it differs.
SET vs ORDER: multiset(label) comparison is order-insensitive; order comparison
is position-sensitive. Sorting never "fixes" a SET divergence.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def native_multiset(dec):
    return Counter(o["label"] for o in dec["native_options"])


def native_order(dec):
    return [o["label"] for o in dec["native_options"]]


def proj_multiset(dec):
    return Counter(a["label"] for a in dec["projected_actions"])


def proj_order(dec):
    return [a["label"] for a in dec["projected_actions"]]


def state_key(dec):
    s = dec["state"]
    seats = []
    for seat in s.get("seats", []):
        seats.append((
            seat.get("life"),
            seat.get("hand_size"),
            seat.get("library_size"),
            tuple(seat.get("graveyard_names", [])),
            tuple(sorted(seat.get("mana_pool", {}).items())),
        ))
    return json.dumps({
        "turn": s.get("turn"), "phase": s.get("phase"), "step": s.get("step"),
        "active": s.get("active_seat"), "seats": seats,
        "board": s.get("battlefield"), "stack": s.get("stack"),
        "command": s.get("command_zone"), "exile": s.get("exile_names"),
    }, sort_keys=True)


def hand_key(dec):
    return json.dumps([
        list(seat.get("diagnostic_hand_names", []))
        for seat in dec["state"].get("seats", [])
    ])


def lib_key(dec):
    return json.dumps([
        (seat.get("library_size"),
         seat.get("diagnostic_library_order_hash"),
         seat.get("diagnostic_library_top3"))
        for seat in dec["state"].get("seats", [])
    ])


def select_key(dec):
    return (dec.get("class"), dec.get("actor_seat"), dec.get("selected_label"))


def load_trace(path):
    t = json.loads(Path(path).read_text())
    return {d["offset"]: d for d in t["decisions"]}, t


def main(argv):
    paths = [a for a in argv if not a.startswith("--")]
    if len(paths) < 2:
        print("usage: ws208_diff.py TRACE_A TRACE_B [TRACE_C ...]", file=sys.stderr)
        return 2
    traces = [load_trace(p) for p in paths]
    offsets = sorted(set.intersection(*[set(t[0].keys()) for t in traces]))
    print(f"common offsets: {len(offsets)} "
          f"(runs: {[t[1]['decisions_answered'] for t in traces]})")
    first = {}
    for off in offsets:
        decs = [t[0][off] for t in traces]
        if len({select_key(d) for d in decs}) > 1 and "L_SELECT" not in first:
            first["L_SELECT"] = off
        if len({state_key(d) for d in decs}) > 1 and "L_STATE" not in first:
            first["L_STATE"] = off
        if len({hand_key(d) for d in decs}) > 1 and "L_HAND" not in first:
            first["L_HAND"] = off
        if len({lib_key(d) for d in decs}) > 1 and "L_LIB" not in first:
            first["L_LIB"] = off
        if len({json.dumps(sorted(native_multiset(d).items())) for d in decs}) > 1 \
                and "L_NATIVE_SET" not in first:
            first["L_NATIVE_SET"] = off
        elif len({json.dumps(native_order(d)) for d in decs}) > 1 \
                and "L_NATIVE_ORDER" not in first:
            first["L_NATIVE_ORDER"] = off
        if len({json.dumps(sorted(proj_multiset(d).items())) for d in decs}) > 1 \
                and "L_PROJ_SET" not in first:
            first["L_PROJ_SET"] = off
        elif len({json.dumps(proj_order(d)) for d in decs}) > 1 \
                and "L_PROJ_ORDER" not in first:
            first["L_PROJ_ORDER"] = off
    print("FIRST DIVERGENCE PER LAYER:")
    for layer in ["L_STATE", "L_HAND", "L_LIB", "L_NATIVE_SET", "L_NATIVE_ORDER",
                  "L_PROJ_SET", "L_PROJ_ORDER", "L_SELECT"]:
        print(f"  {layer}: {first.get(layer, 'NO_DIVERGENCE_IN_COMMON_PREFIX')}")
    # Detail at the earliest layer divergence.
    earliest = min(first.values()) if first else None
    if earliest is not None:
        print(f"\nDETAIL AT EARLIEST DIVERGENT OFFSET {earliest}:")
        for i, (decmap, meta) in enumerate(traces):
            d = decmap[earliest]
            print(f"--- run{i} class={d['class']} actor={d['actor_seat']} "
                  f"sel={d['selected_label']!r}")
            print(f"    native({len(d['native_options'])}): "
                  f"{native_multiset(d)}")
            print(f"    native order: {native_order(d)}")
            print(f"    state: turn={d['state'].get('turn')} "
                  f"phase={d['state'].get('phase')} step={d['state'].get('step')} "
                  f"active={d['state'].get('active_seat')}")
            for s in d["state"]["seats"]:
                print(f"    seat{s['seat']}: life={s.get('life')} "
                      f"hand={s.get('diagnostic_hand_names')} "
                      f"lib={s.get('library_size')} "
                      f"top3={s.get('diagnostic_library_top3')} "
                      f"libhash={str(s.get('diagnostic_library_order_hash'))[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
