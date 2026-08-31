#!/usr/bin/env python3
"""WS-31 final discovery shim: add last-token search without relaxing authority matching."""
from __future__ import annotations
import ws31_acquire_gatherer_v2 as v2

_original = v2.query_variants

def query_variants(face: str) -> list[str]:
    vals = _original(face)
    tokens = v2.match_norm(face).split()
    if len(tokens) >= 2 and tokens[-1] not in vals:
        vals.append(tokens[-1])
    return vals

v2.query_variants = query_variants

if __name__ == "__main__":
    raise SystemExit(v2.base.main())
