#!/usr/bin/env python3
"""WS-31 materialization hardening for authority-backed rules-path incidence.

The v1 materializer conservatively labeled six literal Oracle constructions as
HEURISTIC_DISCOVERY_ONLY and also guessed special-form subtypes from face count.
That made hundreds of otherwise authority-locked cards UNKNOWN.  This wrapper
keeps the v1 output contract but applies the stricter rule:

* literal Oracle constructs whose rules meaning is fixed by the current locked
  Comprehensive Rules are AUTHORITY_DERIVED;
* face count / `//` spelling alone never guesses split/transform subtype.

No runtime-functionality credit is created by this classification.
"""
from __future__ import annotations

import ws31_materialize as base

_original_derive_incidence = base.derive_incidence

_LITERAL_ORACLE_PATHS = {
    "zone-change semantics",
    "hidden library information",
    "counters",
    "attachments",
    "copies",
    "power/toughness layers",
}

_UNSUPPORTED_FACECOUNT_GUESSES = {
    "split cards",
    "double-faced / transforming cards",
}


def derive_incidence(rec):
    evidence = _original_derive_incidence(rec)
    out = []
    seen = set()
    for item in evidence:
        row = dict(item)
        if row.get("classification") == "HEURISTIC_DISCOVERY_ONLY":
            path = row.get("path")
            if path in _UNSUPPORTED_FACECOUNT_GUESSES:
                # Multiple faces or a project-level // spelling proves the
                # existence of faces, not the Magic special-form subtype.
                continue
            if path in _LITERAL_ORACLE_PATHS:
                row["classification"] = "AUTHORITY_DERIVED"
                row["evidence"] = (
                    "explicit official Oracle construct; canonical rules-path "
                    "meaning anchored by the current locked Comprehensive Rules"
                )
        key = (row.get("path"), row.get("classification"))
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


base.derive_incidence = derive_incidence


if __name__ == "__main__":
    raise SystemExit(base.main())
